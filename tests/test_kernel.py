"""端到端（假模型 + 假 JEV）：一轮 turn 的完整时序、门控、降级、轨迹格式。"""
import json

import pytest

from agent.kernel import Agent
from agent.llm import LLMError
from agent.trace import validate_event

from conftest import FakeDecision, FakeLLM, choice_ans, noul_ans, reply


def make_agent(cfg, monkeypatch, local_script, *, decision=None, cloud_script=None, confirm=None, use_jev=True):
    clients = {"local": FakeLLM("local", local_script), "backup": FakeLLM("backup", []),
               "cloud": FakeLLM("cloud", cloud_script or [])}
    agent = Agent(cfg, decision=decision or FakeDecision(), clients=clients, confirm=confirm, use_jev=use_jev)
    monkeypatch.setattr(agent.router, "healthy", lambda ep, ttl=60: True)
    return agent, clients


def pick(skill_key: str | None, appropriate: float = 0.9, hard: float = 0.0):
    """技能选择命中 skill_key（None = 门控挡住），工具 appropriate，难度 P(hard)。"""
    def responder(name, q, state):
        if name == "skill":
            probs = {k: 0.0 for k in q["criteria"]}
            probs[skill_key or "none"] = 1.0
            return choice_ans(probs)
        if name in ("acts", "procedure"):
            return noul_ans(0.9 if skill_key else 0.05)
        if name == "prose":
            return noul_ans(0.1 if skill_key else 0.95)
        if name.startswith("fits_"):
            return noul_ans(0.9)
        if name == "in_scope":
            return noul_ans(appropriate)
        if name == "collateral":
            return noul_ans(0.05)
        if name == "difficulty":
            return choice_ans({"simple": 1 - hard, "moderate": 0.0, "hard": hard})
        if name == "writes_code":
            return noul_ans(0.0)
        return None
    return FakeDecision(responder)


def events(agent):
    lines = (agent.cfg.data_dir / "runs" / agent.session / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def test_read_only_turn(cfg, monkeypatch):
    agent, clients = make_agent(cfg, monkeypatch, [
        reply(calls=[("read_file", {"path": "README.md"})]),
        reply("README 里写了 demo add 用法。"),
    ], decision=pick(None))
    res = agent.run_turn("README 里写了什么")
    assert res.stopped == "final" and "demo add" in res.reply and res.skills == [] and res.tier == "local"
    # 没命中技能：只暴露只读工具
    assert "edit_file" not in clients["local"].tools_seen[0] and "read_file" in clients["local"].tools_seen[0]
    # 工具结果回填给了模型
    assert any(m["role"] == "tool" and "demo add" in m["content"] for m in clients["local"].received[1])
    evs = events(agent)
    assert all(not validate_event(e) for e in evs)
    types = [e["type"] for e in evs]
    assert types[0] == "turn.start" and types[-1] == "turn.end"
    assert {"skill.select", "route.model", "memory.recall", "llm.call", "tool.gate", "tool.call"} <= set(types)
    assert [e["seq"] for e in evs] == sorted(e["seq"] for e in evs)


def test_skill_loads_body_and_write_tools(cfg, monkeypatch):
    agent, clients = make_agent(cfg, monkeypatch, [
        reply(calls=[("edit_file", {"path": "app.py", "old": "sum(xs)", "new": "sum(xs) or 0"})]),
        reply("改好了"),
    ], decision=pick("implement_change", appropriate=0.95))
    res = agent.run_turn("把 total 改一下")
    assert res.skills == ["implement-change"]
    system = clients["local"].received[0][0]["content"]
    assert '<skill name="implement-change">' in system
    assert "edit_file" in clients["local"].tools_seen[0]
    assert "or 0" in (cfg.workspace / "app.py").read_text(encoding="utf-8")
    assert any("edit_file" in e for e in agent.working.evidence)  # 写操作自动进关键证据


def test_user_refusal_blocks_write(cfg, monkeypatch):
    asked = []
    agent, clients = make_agent(cfg, monkeypatch, [
        reply(calls=[("edit_file", {"path": "app.py", "old": "sum(xs)", "new": "0"})]),
        reply("好的，不改了"),
    ], decision=pick("implement_change", appropriate=0.4), confirm=lambda r: asked.append(r) or False)
    agent.run_turn("把 total 改成 0")
    assert asked and asked[0].tool == "edit_file"
    assert "sum(xs)" in (cfg.workspace / "app.py").read_text(encoding="utf-8")
    tool_msg = next(m for m in clients["local"].received[1] if m["role"] == "tool")
    assert "用户拒绝" in tool_msg["content"]
    gate_ev = next(e for e in events(agent) if e["type"] == "tool.gate")
    assert gate_ev["data"]["decision"] == "confirm" and gate_ev["data"]["confirmed"] is False


def test_hallucinated_write_without_skill_denied(cfg, monkeypatch):
    agent, _ = make_agent(cfg, monkeypatch, [
        reply(calls=[("write_file", {"path": "x.txt", "content": "x"})]),
        reply("没法写"),
    ], decision=pick(None))
    agent.run_turn("随便写个文件")
    assert not (cfg.workspace / "x.txt").exists()


def test_hard_task_routes_to_cloud(cfg, monkeypatch):
    agent, clients = make_agent(cfg, monkeypatch, [], cloud_script=[reply("云端完成")],
                                decision=pick("implement_change", hard=0.8))
    res = agent.run_turn("重构存储层并修掉精度问题")
    assert res.tier == "cloud" and res.reply == "云端完成" and not clients["local"].received


def test_local_failure_escalates(cfg, monkeypatch):
    agent, clients = make_agent(cfg, monkeypatch, [LLMError("本地挂了")], decision=pick(None))
    clients["backup"].script = [LLMError("备用也挂了")]
    clients["cloud"].script = [reply("云端接手了")]
    res = agent.run_turn("你好")
    assert res.reply == "云端接手了" and res.tier == "cloud"
    esc = [e["data"] for e in events(agent) if e["type"] == "route.escalate"]
    assert [(e["from"], e["to"]) for e in esc] == [("local", "backup"), ("backup", "cloud")]


def test_malformed_args_escalate_to_cloud(cfg, monkeypatch):
    bad = reply(calls=[("read_file", {})], raw_args={"read_file": "{path: README"})
    agent, clients = make_agent(cfg, monkeypatch, [bad, bad], cloud_script=[reply("我来")], decision=pick(None))
    res = agent.run_turn("读一下 README")
    assert res.tier == "cloud" and res.reply == "我来"
    # 非法参数的错误信息回填给了模型，让它有机会自己改
    assert any("合法的 JSON" in m.get("content", "") for m in clients["local"].received[1] if m["role"] == "tool")


def test_all_models_down(cfg, monkeypatch):
    agent, clients = make_agent(cfg, monkeypatch, [LLMError("x")], decision=pick(None))
    clients["backup"].script = [LLMError("y")]
    clients["cloud"].script = [LLMError("z")]
    res = agent.run_turn("你好")
    assert res.stopped == "error" and "不可用" in res.reply


def test_jev_down_whole_turn_still_works(cfg, monkeypatch):
    agent, clients = make_agent(cfg, monkeypatch, [reply("基线也能答")], decision=FakeDecision(fail=True))
    clients["local"].script.insert(0, reply('{"skills": []}'))  # 基线选技能用掉一次本地调用
    res = agent.run_turn("你好")
    assert res.reply == "基线也能答"
    sel = next(e for e in events(agent) if e["type"] == "skill.select")
    assert sel["fallback"] is True and sel["data"]["mode"] == "baseline"


def test_max_steps_reports_open_items(cfg, monkeypatch):
    cfg.max_steps = 3
    loop = reply(calls=[("update_plan", {"goal": "g", "todo": [{"item": "还没做的事"}]})])
    agent, _ = make_agent(cfg, monkeypatch, [loop, loop, loop], decision=pick(None))
    res = agent.run_turn("做个多步任务")
    assert res.stopped == "max_steps" and "还没做的事" in res.reply


def test_compression_triggers_in_long_session(cfg, monkeypatch):
    cfg.thresholds.context_budget = 3000
    big = "很长的输出" * 400
    script = []
    for _ in range(4):
        script += [reply(calls=[("search_text", {"pattern": "def"})]), reply("完成")]
    agent, clients = make_agent(cfg, monkeypatch, script, decision=pick(None))
    monkeypatch.setattr(agent.registry.get("search_text"), "handler", lambda a, c: big)
    for i in range(4):
        agent.run_turn(f"第 {i} 次查找")
    assert any(e["type"] == "context.compress" for e in events(agent))
    for msgs in clients["local"].received:  # 每次发给模型的消息里 tool_calls 配对都完整
        ids = set()
        for m in msgs:
            if m["role"] == "assistant":
                ids = {c["id"] for c in m.get("tool_calls") or []}
            if m["role"] == "tool":
                assert m["tool_call_id"] in ids


def test_skill_name_called_as_tool_is_explained(cfg, monkeypatch):
    # 实测问题（2026-09-24）：本地模型把技能名 standup-brief 当工具调用
    agent, clients = make_agent(cfg, monkeypatch, [reply(calls=[("standup-brief", {})]), reply("好")],
                                decision=pick("standup_brief"))
    agent.run_turn("站会简报")
    tool_msg = next(m for m in clients["local"].received[1] if m["role"] == "tool")
    assert "是技能不是工具" in tool_msg["content"]
    assert any(e["type"] == "tool.call" and e["data"]["tool"] == "standup-brief" for e in events(agent))


def test_truncated_output_gets_one_nudge(cfg, monkeypatch):
    # 实测问题（2026-09-24）：step-5 修 bug 时一步用满输出上限被截断，整轮空手而归
    cut = reply("def total(...): 很长的代码……")
    cut.finish_reason = "length"
    agent, clients = make_agent(cfg, monkeypatch, [cut, reply("改用工具后完成")], decision=pick(None))
    res = agent.run_turn("修一下")
    assert res.reply == "改用工具后完成" and res.stopped == "final"
    assert any("不要在回复里贴大段代码" in (m.get("content") or "") for m in clients["local"].received[1])
