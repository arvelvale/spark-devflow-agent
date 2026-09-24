"""接口契约：任务集格式、轨迹格式、JEV 客户端缓存与降级。"""
import json

import pytest

from agent.decision import DecisionClient, DecisionUnavailable, noul
from agent.trace import Trace, shorten, validate_event
from eval.taskset import aggregate, load_taskset, score_task, validate_taskset

from conftest import ROOT


def test_repo_taskset_valid():
    from agent.skills import load_skills
    skills, _ = load_skills(ROOT / "skills")
    data = load_taskset(ROOT / "eval" / "tasks" / "skill-selection-v1.json", {s.name for s in skills})
    cats = [t["category"] for t in data["tasks"]]
    assert cats.count("none") >= 5 and cats.count("multi") >= 2


def test_taskset_validation_catches_mistakes():
    bad = {"version": 1, "name": "x", "tasks": [
        {"id": "a", "category": "none", "input": "hi", "expect": {"skills": ["plan-writer"]}},
        {"id": "a", "category": "single", "input": "x", "expect": {"skills": []}},
        {"id": "b", "category": "multi", "input": "y", "expect": {"skills": ["x"], "tier": "gpu"}},
    ]}
    problems = "\n".join(validate_taskset(bad, {"plan-writer"}))
    for needle in ("none 类", "id 重复", "恰好 1 个", "至少 2 个", "tier", "未知技能"):
        assert needle in problems


def test_scoring():
    assert score_task(["a"], ["a"])["exact"]
    s = score_task(["a"], ["b"], ["b"])
    assert s["miss"] and s["wrong"] and s["confused"] == ["b"]
    assert score_task([], ["a"])["forced"]
    m = aggregate([
        {"category": "single", "score": score_task(["a"], ["a"]), "tier_ok": True},
        {"category": "none", "score": score_task([], ["a"]), "tier_ok": None},
    ])
    assert m["exact"] == 0.5 and m["forced_rate"] == 1.0 and m["tier_agree"] == 1.0


def test_trace_file_and_shortening(tmp_path):
    tr = Trace("s1", tmp_path / "t.jsonl")
    got = []
    tr.subscribe(got.append)
    tr.subscribe(lambda e: 1 / 0)  # 监听方出错不影响
    tr.turn = 1
    ev = tr.emit("tool.call", {"tool": "write_file", "args": {"content": "x" * 2000}}, usage={"prompt_tokens": 5})
    assert not validate_event(ev) and got == [ev]
    assert ev["usage"] == {"input_tokens": 5, "output_tokens": 0}
    assert "共 2000 字" in ev["data"]["args"]["content"]
    line = json.loads((tmp_path / "t.jsonl").read_text(encoding="utf-8"))
    assert line["type"] == "tool.call" and line["session"] == "s1"
    assert validate_event({"type": "nope", "data": 1})
    assert shorten(["a" * 600])[0].endswith("共 600 字]")


def test_decision_cache_and_replay(tmp_path, monkeypatch):
    calls = []

    def fake_post(url, body, headers, **kw):
        calls.append(body)
        return {"model": "jev-1.13.0", "answers": {"q": {"type": "noul", "noul": 0.7}},
                "usage": {"input_tokens": 50, "output_tokens": 5}}, 0.2

    monkeypatch.setattr("agent.decision.post_json", fake_post)
    cache = tmp_path / "c.sqlite"
    live = DecisionClient("u", "jev-latest", "key", cache_path=cache)
    q = {"q": noul("是吗")}
    assert live.ask("s", q).noul("q") == 0.7
    d2 = live.ask("s", q)
    assert d2.cached and len(calls) == 1 and live.totals["input_tokens"] == 50
    replay = DecisionClient("u", "jev-latest", "", cache_path=cache, mode="replay")
    assert replay.available and replay.ask("s", q).noul("q") == 0.7
    with pytest.raises(DecisionUnavailable):
        replay.ask("另一个 state", q)


def test_decision_without_key_is_unavailable():
    with pytest.raises(DecisionUnavailable):
        DecisionClient("u", "m", "").ask("s", {"q": noul("x")})


def test_extract_json_prefers_outermost():
    from agent.llm import extract_json
    assert extract_json('[{"a": 1}, {"b": 2}]') == [{"a": 1}, {"b": 2}]
    assert extract_json('好的：```json\n{"skills": ["x"]}\n```') == {"skills": ["x"]}
    assert extract_json('先说一句 {不是json} 然后 {"ok": true}') == {"ok": True}
    assert extract_json("没有 JSON") is None
