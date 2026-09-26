"""子助手：只读、不递归、上下文隔离、并行汇总、轨迹事件、选模型。"""
import pytest

from agent import subagents
from agent.kernel import Agent
from agent.tools import ToolError
from agent.trace import validate_event

from conftest import FakeDecision, FakeLLM, reply


def make(cfg, monkeypatch, local_script, default=None, healthy=True):
    clients = {"local": FakeLLM("local", local_script, default), "backup": FakeLLM("backup"),
               "cloud": FakeLLM("cloud", [], reply("云端结论"))}
    agent = Agent(cfg, decision=FakeDecision(), clients=clients, use_jev=False)
    monkeypatch.setattr(agent.router, "healthy", lambda ep, ttl=60: healthy)
    events = []
    agent.trace.subscribe(events.append)
    return agent, clients, events


def task(desc="查金额路径", prompt="找出 add 函数在哪里定义、金额是怎么存的，给出文件和行号"):
    return {"description": desc, "prompt": prompt}


def test_subagent_explores_and_returns_only_conclusion(cfg, monkeypatch):
    agent, clients, events = make(cfg, monkeypatch, [
        reply(calls=[("code_outline", {"path": "."})]),
        reply("结论：金额按字符串存，app.py 里直接 sum。"),
    ])
    out = subagents.delegate(agent, cfg.local, [task()])
    assert "结论：金额按字符串存" in out and "完成" in out
    sub_msgs = clients["local"].received[1]
    assert sub_msgs[0]["content"] == subagents.EXPLORE_SYSTEM  # 独立上下文：系统提示是子助手自己的
    assert any(m["role"] == "tool" for m in sub_msgs)           # 工具结果留在子助手里
    assert not agent.conv.messages                               # 主对话一条都没多
    kinds = [e["type"] for e in events]
    assert kinds == ["subagent.start", "subagent.end"] and all(not validate_event(e) for e in events)
    end = events[-1]["data"]
    assert end["ok"] and end["tools"] == ["code_outline"] and end["steps"] == 2


def test_subagent_is_read_only_and_cannot_recurse(cfg, monkeypatch):
    agent, clients, _ = make(cfg, monkeypatch, [
        reply(calls=[("write_file", {"path": "pwned.txt", "content": "x"}), ("delegate", {"tasks": [task()]})]),
        reply("写不了，只能汇报。"),
    ])
    subagents.delegate(agent, cfg.local, [task()])
    assert not (cfg.workspace / "pwned.txt").exists()
    offered = clients["local"].tools_seen[0]
    assert "delegate" not in offered and "write_file" not in offered and "update_plan" not in offered
    tool_msgs = [m["content"] for m in clients["local"].received[1] if m["role"] == "tool"]
    assert len(tool_msgs) == 2 and all("只能用只读工具" in m for m in tool_msgs)


def test_parallel_tasks_all_reported(cfg, monkeypatch):
    agent, _, events = make(cfg, monkeypatch, [], default=reply("查到了"))
    out = subagents.delegate(agent, cfg.local, [task("甲"), task("乙"), task("丙")])
    assert out.count("查到了") == 3 and "甲" in out and "丙" in out
    assert sum(e["type"] == "subagent.end" for e in events) == 3


def test_step_limit_forces_answer(cfg, monkeypatch):
    agent, clients, events = make(cfg, monkeypatch, [], default=reply(calls=[("list_dir", {})]))
    out = subagents.delegate(agent, cfg.local, [task()])
    assert "步数用完" in out and events[-1]["data"]["stopped"] == "max_steps"
    assert clients["local"].tools_seen[-1] == []  # 最后一步不再给工具，逼它收尾


def test_prefers_private_local_model_else_follows_main(cfg, monkeypatch):
    agent, clients, _ = make(cfg, monkeypatch, [], default=reply("本机结论"))
    assert subagents.pick_endpoint(agent, cfg.cloud) is cfg.local
    agent2, clients2, _ = make(cfg, monkeypatch, [], healthy=False)
    assert subagents.pick_endpoint(agent2, cfg.cloud) is cfg.cloud
    assert "云端结论" in subagents.delegate(agent2, cfg.cloud, [task()])


def test_delegate_tool_validates_input(cfg, monkeypatch):
    agent, _, _ = make(cfg, monkeypatch, [])
    tool = agent.registry.get("delegate")
    with pytest.raises(ToolError, match="1–4"):
        tool.handler({"tasks": [task()] * 5}, agent.ctx)
    with pytest.raises(ToolError, match="背景要写全"):
        tool.handler({"tasks": [{"description": "x", "prompt": "短"}]}, agent.ctx)


def test_main_loop_can_delegate(cfg, monkeypatch):
    """主循环里调用 delegate：子助手的结论作为一条工具结果回到主对话。"""
    agent, clients, events = make(cfg, monkeypatch, [
        reply('{"skills": []}'),                                   # 基线选技能
        reply(calls=[("delegate", {"tasks": [task()]})]),          # 主 agent 派发
        reply("子助手结论：在 app.py:3"),                           # 子助手直接回答
        reply("汇总完毕"),                                          # 主 agent 收尾
    ])
    res = agent.run_turn("金额是怎么算的")
    assert res.reply == "汇总完毕"
    tool_msg = next(m for m in agent.conv.messages if m["role"] == "tool")
    assert "子助手结论：在 app.py:3" in tool_msg["content"]
    assert {"subagent.start", "subagent.end"} <= {e["type"] for e in events}
