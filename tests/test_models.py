"""模型设置：Key 不回传、换地址作废 Key、分工位生效、隐私记忆不进非私有模型。"""
import json

import pytest

from agent.kernel import Agent
from agent.llm import LLMError
from agent.models import ModelConfigError, ModelStore, looks_private

from conftest import FakeDecision, FakeLLM, reply
from test_server import call, login, running  # noqa: F401  (running 是 fixture)

KEY = "sk-test-abcdef123456"


def store(cfg):
    return ModelStore(cfg.models_path)


def add_remote(cfg, pid="acme", key=KEY, private=None, models=("acme-large", "acme-mini")):
    data = {"name": "Acme", "base_url": "https://api.acme.example/v1", "api_key": key,
            "models": [{"name": m} for m in models], "use_proxy": True}
    if private is not None:
        data["private"] = private
    store(cfg).upsert_provider(cfg, pid, data)


def test_no_file_means_defaults_untouched(cfg):
    before = (cfg.local.model, cfg.backup.model, cfg.cloud.model)
    assert store(cfg).apply(cfg) == [] and not cfg.models_path.exists()
    assert (cfg.local.model, cfg.backup.model, cfg.cloud.model) == before
    view = store(cfg).public(cfg)
    assert [p["id"] for p in view["providers"]] == ["vllm", "ollama", "stepfun"] and not view["saved"]


def test_key_saved_but_never_exposed(cfg):
    add_remote(cfg)
    assert KEY in cfg.models_path.read_text(encoding="utf-8")
    view = store(cfg).public(cfg)
    assert KEY not in json.dumps(view)
    acme = next(p for p in view["providers"] if p["id"] == "acme")
    assert acme["has_key"] and acme["key_source"] == "panel" and not acme["private"]


def test_omitting_key_keeps_it_and_changing_url_drops_it(cfg):
    add_remote(cfg)
    s = store(cfg)
    s.upsert_provider(cfg, "acme", {"name": "Acme 2", "base_url": "https://api.acme.example/v1",
                                    "models": ["acme-large"], "use_proxy": True})
    assert s.provider(cfg, "acme").api_key == KEY  # 没传 api_key = 保持不变
    s.upsert_provider(cfg, "acme", {"name": "Acme", "base_url": "https://evil.example/v1", "models": ["acme-large"]})
    p = s.provider(cfg, "acme")
    assert p.api_key == "" and p.api_key_env == ""  # 地址变了，旧 Key 不能跟过去


def test_url_rules():
    assert looks_private("http://127.0.0.1:8000/v1") and looks_private("http://192.168.1.5:11434/v1")
    assert not looks_private("https://api.openai.com/v1")


@pytest.mark.parametrize("data,msg", [
    ({"base_url": "http://api.acme.example/v1", "models": ["m"]}, "https"),
    ({"base_url": "ftp://x/v1", "models": ["m"]}, "http"),
    ({"base_url": "https://api.acme.example/v1", "models": []}, "模型"),
])
def test_bad_provider_rejected(cfg, data, msg):
    with pytest.raises(ModelConfigError, match=msg):
        store(cfg).upsert_provider(cfg, "acme", data)


def test_slots_apply_and_in_use_protection(cfg):
    add_remote(cfg)
    s = store(cfg)
    s.set_slots(cfg, {"cloud": {"provider": "acme", "model": "acme-large"}})
    s.apply(cfg)
    assert cfg.cloud.model == "acme-large" and cfg.cloud.api_key == KEY and cfg.cloud.use_proxy
    assert cfg.cloud.name == "cloud"  # 分工位名不变，轨迹契约里的 endpoint 字段照旧
    with pytest.raises(ModelConfigError, match="难题"):
        s.delete_provider(cfg, "acme")
    with pytest.raises(ModelConfigError, match="难题"):
        s.upsert_provider(cfg, "acme", {"base_url": "https://api.acme.example/v1", "models": ["acme-mini"]})
    with pytest.raises(ModelConfigError, match="不存在"):
        s.set_slots(cfg, {"local": {"provider": "acme", "model": "nope"}})


def test_asr_follows_stepfun_provider_not_cloud_slot(cfg):
    add_remote(cfg)
    s = store(cfg)
    s.set_slots(cfg, {"cloud": {"provider": "acme", "model": "acme-large"}})  # 先把难题位让出来，才能改阶跃的模型
    s.upsert_provider(cfg, "stepfun", {"name": "阶跃", "base_url": "https://api.stepfun.com/step_plan/v1",
                                       "api_key": "sk-step-xyz789", "models": ["step-5-preview"]})
    s.apply(cfg)
    assert cfg.asr.base_url.startswith("https://api.stepfun.com") and cfg.asr.api_key == "sk-step-xyz789"


# ---------------- 隐私：非私有模型看不到隐私记忆，也不跑辅助任务 ----------------
def run_with_secret(cfg, monkeypatch, private: bool) -> str:
    cfg.local.private = private
    clients = {"local": FakeLLM("local", [reply('{"skills": []}'), reply("好的")]), "backup": FakeLLM("backup", []),
               "cloud": FakeLLM("cloud", [])}
    agent = Agent(cfg, decision=FakeDecision(), clients=clients, use_jev=False)
    monkeypatch.setattr(agent.router, "healthy", lambda ep, ttl=60: True)
    agent.memory_store.add("semantic", "preference", "晨熠的体检报告放在 D 盘私密目录", privacy="local")
    agent.run_turn("体检报告放哪了")
    # 基线模式第一次调用是选技能；取主循环那次（system 提示词）
    return next(m[0]["content"] for m in clients["local"].received if m[0]["role"] == "system")


def test_private_memory_reaches_private_model(cfg, monkeypatch):
    assert "体检报告放在" in run_with_secret(cfg, monkeypatch, True)


def test_private_memory_never_reaches_remote_primary(cfg, monkeypatch):
    assert "体检报告放在" not in run_with_secret(cfg, monkeypatch, False)


def test_auxiliary_tasks_refuse_non_private_models(cfg, monkeypatch):
    cfg.local.private = False
    cfg.backup.private = False
    agent = Agent(cfg, decision=FakeDecision(), clients={n: FakeLLM(n, [reply("x")]) for n in ("local", "backup", "cloud")},
                  use_jev=False)
    monkeypatch.setattr(agent.router, "healthy", lambda ep, ttl=60: True)
    with pytest.raises(LLMError, match="私有"):
        agent.local.complete("总结一下")


# ---------------- HTTP 接口 ----------------
def test_models_api_roundtrip(running):
    app, port = running
    assert call(port, "GET", "/api/models")[0] == 401
    cookie = login(port)
    status, body, _ = call(port, "PUT", "/api/models/providers/acme", {
        "name": "Acme", "base_url": "https://api.acme.example/v1", "api_key": KEY, "models": ["acme-large"]},
        cookie=cookie)
    assert status == 200 and KEY not in json.dumps(body)
    status, body, _ = call(port, "PUT", "/api/models/slots", {"cloud": {"provider": "acme", "model": "acme-large"}},
                           cookie=cookie)
    assert status == 200 and body["slots"]["cloud"]["provider"] == "acme"
    assert app.cfg.cloud.model == "acme-large"  # 立即套到运行配置，新会话就用它
    assert call(port, "DELETE", "/api/models/providers/acme", cookie=cookie)[0] == 400
    status, body, _ = call(port, "PUT", "/api/models/providers/Bad_ID", {"base_url": "https://x.example/v1",
                                                                         "models": ["m"]}, cookie=cookie)
    assert status == 400 and "编号" in body["error"]


def test_models_test_endpoint_redacts_key(running, monkeypatch):
    app, port = running
    cookie = login(port)
    call(port, "PUT", "/api/models/providers/acme", {"base_url": "https://api.acme.example/v1", "api_key": KEY,
                                                     "models": ["acme-large"]}, cookie=cookie)

    def boom(self, *a, **k):
        raise LLMError(f"HTTP 401: invalid key {KEY}")
    monkeypatch.setattr("agent.server.LLMClient.chat", boom)
    status, body, _ = call(port, "POST", "/api/models/providers/acme/test", {"model": "acme-large"}, cookie=cookie)
    assert status == 200 and body["ok"] is False and KEY not in body["error"] and "***" in body["error"]
