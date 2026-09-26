"""模型设置：像 OpenCode 那样登记供应商（接口地址 + API Key + 模型），再给三个分工位各选一个模型。

分工位（名字沿用代码里的 local / backup / cloud，决策轨迹契约不变）：
  local   主力：日常任务走它；它若是私有模型，摘要、记忆抽取这类辅助任务也由它跑
  backup  备用：主力连不上时顶上
  cloud   难题：JEV 判为难题、或主力连续给出非法工具参数时升级到它

私有（private）：模型部署在自己控制的机器上（本机 vLLM / Ollama 等）。
  只有私有模型能看到隐私记忆、跑辅助任务；落在非私有模型上的轮次，隐私记忆一律过滤。
  这就是改造前"云端轮次过滤隐私"那条规则，判断依据从分工位名换成了这个标记——
  所以用户把主力换成境外 API 时，隐私记忆不会跟着出去。

存储：<data_dir>/models.json（var/ 已 gitignore），写入后权限 600。API Key 明文存在节点上这个文件里：
  面板本身有口令保护，文件只有本账号能读；任何接口都不回传 Key 原文，只回"是否已设置 / 来源"。
  Key 解析顺序：文件里的 api_key 非空优先，否则读 api_key_env 指向的环境变量（.env）。
安全：改了供应商的接口地址却没重填 Key 时，旧 Key 连同环境变量回退一起作废——
  防止把已存的 Key 发到一个新地址上。
没有 models.json 时一切照旧（默认值来自 config.py 和环境变量），第一次在面板里保存才生成。
"""
from __future__ import annotations

import copy
import ipaddress
import json
import os
import re
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from .config import Endpoint

if TYPE_CHECKING:
    from .config import Config

SLOTS = ("local", "backup", "cloud")
PROVIDER_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
VERSION = 1

# 预设只填接口地址；模型名各家更新太快，用"从接口拉取"或手填。
# use_proxy：节点直连不了境外，境外服务要经操作机代理（SSH 反向隧道）出去
PRESETS: list[dict] = [
    {"id": "openai", "name": "OpenAI", "base_url": "https://api.openai.com/v1", "use_proxy": True},
    {"id": "anthropic", "name": "Anthropic", "base_url": "https://api.anthropic.com/v1", "use_proxy": True},
    {"id": "openrouter", "name": "OpenRouter", "base_url": "https://openrouter.ai/api/v1", "use_proxy": True},
    {"id": "deepseek", "name": "DeepSeek", "base_url": "https://api.deepseek.com/v1"},
    {"id": "moonshot", "name": "月之暗面 Kimi", "base_url": "https://api.moonshot.cn/v1"},
    {"id": "zhipu", "name": "智谱 GLM", "base_url": "https://open.bigmodel.cn/api/paas/v4"},
    {"id": "dashscope", "name": "阿里云百炼", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    {"id": "siliconflow", "name": "硅基流动", "base_url": "https://api.siliconflow.cn/v1"},
    {"id": "stepfun", "name": "阶跃星辰", "base_url": "https://api.stepfun.com/step_plan/v1"},
    {"id": "ollama", "name": "Ollama（本机）", "base_url": "http://127.0.0.1:11434/v1", "private": True},
    {"id": "vllm", "name": "vLLM（本机）", "base_url": "http://127.0.0.1:8000/v1", "private": True},
]


class ModelConfigError(ValueError):
    """给前端看的中文说明。"""


def looks_private(base_url: str) -> bool:
    """接口地址是回环或内网地址 → 默认当私有模型。只是新建时的默认勾选，用户可以改。"""
    host = urlparse(base_url).hostname or ""
    if host in ("localhost",) or host.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


@dataclass
class ModelSpec:
    name: str
    max_tokens: int = 8192
    max_concurrency: int = 4
    extra: dict = field(default_factory=dict)     # 附加到请求体的字段（如关推理）
    no_think: dict = field(default_factory=dict)  # 辅助任务关思考时额外合并的字段

    def to_dict(self) -> dict:
        return {"name": self.name, "max_tokens": self.max_tokens, "max_concurrency": self.max_concurrency,
                "extra": self.extra, "no_think": self.no_think}

    @classmethod
    def from_dict(cls, d: dict) -> "ModelSpec":
        return cls(name=str(d["name"]), max_tokens=int(d.get("max_tokens") or 8192),
                   max_concurrency=int(d.get("max_concurrency") or 4),
                   extra=dict(d.get("extra") or {}), no_think=dict(d.get("no_think") or {}))


@dataclass
class Provider:
    id: str
    name: str
    base_url: str
    api_key: str = ""
    api_key_env: str = ""
    private: bool = False
    use_proxy: bool = False
    timeout: float = 180.0
    models: list[ModelSpec] = field(default_factory=list)

    def model(self, name: str) -> ModelSpec | None:
        return next((m for m in self.models if m.name == name), None)

    @property
    def key_source(self) -> str | None:
        if self.api_key:
            return "panel"
        if self.api_key_env and os.environ.get(self.api_key_env):
            return "env"
        return None

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "base_url": self.base_url, "api_key": self.api_key,
                "api_key_env": self.api_key_env, "private": self.private, "use_proxy": self.use_proxy,
                "timeout": self.timeout, "models": [m.to_dict() for m in self.models]}

    @classmethod
    def from_dict(cls, d: dict) -> "Provider":
        return cls(id=str(d["id"]), name=str(d.get("name") or d["id"]), base_url=str(d["base_url"]),
                   api_key=str(d.get("api_key") or ""), api_key_env=str(d.get("api_key_env") or ""),
                   private=bool(d.get("private")), use_proxy=bool(d.get("use_proxy")),
                   timeout=float(d.get("timeout") or 180.0),
                   models=[ModelSpec.from_dict(m) for m in d.get("models") or []])

    def endpoint(self, slot: str, spec: ModelSpec) -> Endpoint:
        return Endpoint(name=slot, base_url=self.base_url, model=spec.name, api_key_env=self.api_key_env,
                        use_proxy=self.use_proxy, max_concurrency=spec.max_concurrency, timeout=self.timeout,
                        extra=dict(spec.extra), no_think=dict(spec.no_think), max_tokens=spec.max_tokens,
                        api_key_value=self.api_key, private=self.private, provider=self.id)


def _seed_provider(pid: str, name: str, ep: Endpoint, private: bool) -> Provider:
    return Provider(id=pid, name=name, base_url=ep.base_url, api_key_env=ep.api_key_env, private=private,
                    use_proxy=ep.use_proxy, timeout=ep.timeout,
                    models=[ModelSpec(ep.model, ep.max_tokens, ep.max_concurrency, dict(ep.extra), dict(ep.no_think))])


def seed_from(cfg: "Config") -> tuple[list[Provider], dict]:
    """没有 models.json 时的初始内容：把 config.py 的三个默认端点翻译成三个供应商。"""
    providers = [
        _seed_provider("vllm", "vLLM（本机）", cfg.local, True),
        _seed_provider("ollama", "Ollama（本机）", cfg.backup, True),
        _seed_provider("stepfun", "阶跃星辰", cfg.cloud, False),
    ]
    slots = {"local": {"provider": "vllm", "model": cfg.local.model},
             "backup": {"provider": "ollama", "model": cfg.backup.model},
             "cloud": {"provider": "stepfun", "model": cfg.cloud.model}}
    return providers, slots


class ModelStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    # ---------- 读写 ----------
    def exists(self) -> bool:
        return self.path.exists()

    def load(self, cfg: "Config") -> tuple[list[Provider], dict]:
        if not self.path.exists():
            return seed_from(cfg)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return [Provider.from_dict(p) for p in data.get("providers", [])], dict(data.get("slots") or {})

    def save(self, providers: list[Provider], slots: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        body = json.dumps({"version": VERSION, "providers": [p.to_dict() for p in providers], "slots": slots},
                          ensure_ascii=False, indent=2)
        # 先建空文件并收紧权限再写 Key（Windows 上 chmod 只影响只读位，开发机无所谓）
        tmp.write_text("", encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        tmp.write_text(body, encoding="utf-8")
        os.replace(tmp, self.path)

    # ---------- 应用到运行配置 ----------
    def apply(self, cfg: "Config") -> list[str]:
        """把 models.json 的分工位写进 cfg.local / backup / cloud。返回问题列表（分工位指向不存在的模型等）。"""
        if not self.path.exists():
            return []
        providers, slots = self.load(cfg)
        by_id = {p.id: p for p in providers}
        problems = []
        for slot in SLOTS:
            ref = slots.get(slot) or {}
            p = by_id.get(ref.get("provider", ""))
            spec = p.model(ref.get("model", "")) if p else None
            if p is None or spec is None:
                problems.append(f"{slot} 指向的模型不存在，沿用默认值")
                continue
            setattr(cfg, slot, p.endpoint(slot, spec))
        stepfun = by_id.get("stepfun")
        if stepfun is not None:  # 语音识别跟着阶跃供应商走（Key 可能是在面板里填的）
            cfg.asr = Endpoint("asr", stepfun.base_url, "", api_key_env=stepfun.api_key_env,
                               use_proxy=stepfun.use_proxy, api_key_value=stepfun.api_key, provider="stepfun")
        return problems

    # ---------- 给前端的视图（绝不含 Key 原文） ----------
    def public(self, cfg: "Config") -> dict:
        providers, slots = self.load(cfg)
        return {
            "saved": self.path.exists(),
            "providers": [{
                "id": p.id, "name": p.name, "base_url": p.base_url, "private": p.private, "use_proxy": p.use_proxy,
                "has_key": p.key_source is not None, "key_source": p.key_source, "key_env": p.api_key_env,
                "models": [{"name": m.name, "max_tokens": m.max_tokens} for m in p.models],
            } for p in providers],
            "slots": slots,
            "presets": PRESETS,
        }

    # ---------- 修改 ----------
    def upsert_provider(self, cfg: "Config", pid: str, data: dict) -> None:
        if not PROVIDER_ID.match(pid):
            raise ModelConfigError("供应商编号只能用小写字母、数字和连字符，最长 32 位")
        base_url = str(data.get("base_url", "")).strip().rstrip("/")
        u = urlparse(base_url)
        if u.scheme not in ("http", "https") or not u.hostname:
            raise ModelConfigError("接口地址要以 http:// 或 https:// 开头")
        if u.scheme == "http" and not looks_private(base_url):
            raise ModelConfigError("公网地址必须用 https，否则 API Key 会明文在网上传")
        names = [str(m.get("name", "") if isinstance(m, dict) else m).strip() for m in data.get("models") or []]
        names = [n for n in dict.fromkeys(names) if n]
        if not names:
            raise ModelConfigError("至少填一个模型名")
        if len(names) > 50 or any(len(n) > 120 for n in names):
            raise ModelConfigError("模型太多或名字太长")
        with self._lock:
            providers, slots = self.load(cfg)
            old = next((p for p in providers if p.id == pid), None)
            prev = copy.deepcopy(old) if old else Provider(pid, pid, base_url)
            specs = []
            for n in names:  # 已有模型保留它的并发、附加字段等高级设置
                spec = prev.model(n) or ModelSpec(n)
                mt = next((m.get("max_tokens") for m in data.get("models") or []
                           if isinstance(m, dict) and m.get("name") == n and m.get("max_tokens")), None)
                if mt:
                    spec.max_tokens = max(256, min(int(mt), 200_000))
                specs.append(spec)
            p = Provider(
                id=pid, name=str(data.get("name") or pid).strip()[:40], base_url=base_url,
                api_key=prev.api_key, api_key_env=prev.api_key_env,
                private=bool(data.get("private", looks_private(base_url))),
                use_proxy=bool(data.get("use_proxy", False)), timeout=prev.timeout, models=specs)
            if old and old.base_url != base_url:
                p.api_key, p.api_key_env = "", ""  # 换了地址：旧 Key 不能跟过去
            if "api_key" in data and data["api_key"] is not None:
                p.api_key = str(data["api_key"]).strip()  # 空串 = 清掉面板里的 Key，回退到环境变量
            for slot, ref in slots.items():
                if ref.get("provider") == pid and not p.model(ref.get("model", "")):
                    raise ModelConfigError(f"模型 {ref.get('model')} 正在给「{SLOT_LABEL[slot]}」用，先换掉再删")
            providers = [x for x in providers if x.id != pid] + [p] if old is None else \
                [p if x.id == pid else x for x in providers]
            self.save(providers, slots)

    def delete_provider(self, cfg: "Config", pid: str) -> None:
        with self._lock:
            providers, slots = self.load(cfg)
            for slot, ref in slots.items():
                if ref.get("provider") == pid:
                    raise ModelConfigError(f"这个供应商正在给「{SLOT_LABEL[slot]}」用，先换掉再删")
            left = [p for p in providers if p.id != pid]
            if len(left) == len(providers):
                raise ModelConfigError("没有这个供应商")
            self.save(left, slots)

    def set_slots(self, cfg: "Config", data: dict) -> None:
        with self._lock:
            providers, slots = self.load(cfg)
            by_id = {p.id: p for p in providers}
            new = dict(slots)
            for slot in SLOTS:
                ref = data.get(slot)
                if ref is None:
                    continue
                p = by_id.get(str(ref.get("provider", "")))
                if p is None or p.model(str(ref.get("model", ""))) is None:
                    raise ModelConfigError(f"「{SLOT_LABEL[slot]}」选的模型不存在")
                new[slot] = {"provider": p.id, "model": str(ref["model"])}
            self.save(providers, new)

    def provider(self, cfg: "Config", pid: str) -> Provider:
        p = next((x for x in self.load(cfg)[0] if x.id == pid), None)
        if p is None:
            raise ModelConfigError("没有这个供应商")
        return p


SLOT_LABEL = {"local": "主力", "backup": "备用", "cloud": "难题"}


def discover_models(p: Provider, timeout: float = 10.0) -> list[str]:
    """GET {base_url}/models 拉模型列表（OpenAI 兼容接口都有）。"""
    headers = {"Authorization": f"Bearer {p.api_key or os.environ.get(p.api_key_env, '')}"} \
        if (p.api_key or p.api_key_env) else {}
    opener = urllib.request.build_opener(*([] if p.use_proxy else [urllib.request.ProxyHandler({})]))
    req = urllib.request.Request(p.base_url.rstrip("/") + "/models", headers=headers)
    try:
        with opener.open(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ModelConfigError(f"拉取失败（HTTP {exc.code}）" + ("，检查 API Key" if exc.code in (401, 403) else ""))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        hint = "；境外服务要勾选「经操作机代理出境」" if not p.use_proxy and not p.private else ""
        raise ModelConfigError(f"连不上 {urlparse(p.base_url).hostname}：{getattr(exc, 'reason', exc)}{hint}")
    except json.JSONDecodeError:
        raise ModelConfigError("接口返回的不是 JSON，地址可能填错了（一般以 /v1 结尾）")
    items = data.get("data") if isinstance(data, dict) else data
    ids = [str(m.get("id")) for m in items or [] if isinstance(m, dict) and m.get("id")]
    return sorted(set(ids))[:500]
