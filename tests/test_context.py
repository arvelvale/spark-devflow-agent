from agent.config import Thresholds
from agent.context import ArchiveStore, Compressor, Conversation, WorkingState, estimate_tokens
from agent.tools import build_registry
from agent.tools.base import ToolContext

from conftest import FakeDecision, noul_ans, score_ans


def build_conv(tmp_path, turns: int, tool_chars: int = 3000) -> Conversation:
    conv = Conversation(archive=ArchiveStore(tmp_path / "archive.jsonl"))
    for t in range(1, turns + 1):
        conv.add({"role": "user", "content": f"第{t}轮的请求：处理文件 f{t}.py"}, t)
        conv.add({"role": "assistant", "content": "", "tool_calls": [
            {"id": f"c{t}", "type": "function", "function": {"name": "read_file", "arguments": '{"path": "x"}'}}]}, t)
        conv.add({"role": "tool", "tool_call_id": f"c{t}", "content": f"结果{t} " + "数据" * (tool_chars // 2)}, t)
        conv.add({"role": "assistant", "content": f"第{t}轮完成"}, t)
    return conv


def assert_tool_pairs_intact(messages):
    """每条 tool 消息前面必须有带同一 id 的 assistant tool_calls（否则下一次 API 调用会报错）。"""
    pending = set()
    for m in messages:
        if m["role"] == "assistant":
            assert not pending, f"tool_calls 没有全部得到结果：{pending}"
            pending = {c["id"] for c in m.get("tool_calls") or []}
        elif m["role"] == "tool":
            assert m["tool_call_id"] in pending
            pending.discard(m["tool_call_id"])
        else:
            assert not pending


def small_budget(**kw) -> Thresholds:
    th = Thresholds(context_budget=4000, keep_recent_turns=2, keep_recent_tool_results=1)
    for k, v in kw.items():
        setattr(th, k, v)
    return th


def test_estimate_tokens_mixed():
    assert estimate_tokens("") == 0
    assert 8 <= estimate_tokens("上下文压缩测试一下下") <= 11
    assert estimate_tokens("a" * 360) in range(95, 105)


def test_no_compression_under_watermark(tmp_path):
    conv = build_conv(tmp_path, 1, tool_chars=100)
    assert Compressor(small_budget(), None, None).maybe_compress(conv, 100, WorkingState(), 1) is None


def test_phase_a_elides_old_tool_results_only(tmp_path):
    conv = build_conv(tmp_path, 3, tool_chars=3000)
    n_before = len(conv.messages)
    th = small_budget(compress_target=0.99, keep_recent_turns=5)  # 不允许整轮压缩，只测阶段 A
    ev = Compressor(th, None, None).maybe_compress(conv, 200, WorkingState(), 3)
    assert ev and ev["phases"][0]["phase"] == "tool_results"
    assert len(conv.messages) == n_before  # 不删消息
    tools = [m for m in conv.messages if m["role"] == "tool"]
    assert tools[0]["content"].startswith("[已压缩]") and not tools[-1]["content"].startswith("[已压缩]")
    rid = tools[0]["content"].split("read_archive('")[1].split("'")[0]
    assert conv.archive.get(rid)["content"].startswith("结果1")  # 原文可取回
    assert_tool_pairs_intact(conv.messages)


def test_phase_b_follows_jev_verdicts(tmp_path):
    conv = build_conv(tmp_path, 5, tool_chars=3000)
    verdict = {1: 0, 2: 1, 3: 2}  # 第1轮可丢弃、第2轮留摘要、第3轮必须保留

    def responder(name, q, state):
        t = int(name.split("_")[1])
        if name.startswith("value_"):
            return score_ans(verdict[t])
        return noul_ans(0.1)

    comp = Compressor(small_budget(compress_target=0.05), FakeDecision(responder), lambda p: "摘要：读了文件")
    working = WorkingState(goal="修 bug", todo=[{"item": "跑测试", "done": False}])
    ev = comp.maybe_compress(conv, 200, working, 5)
    verdicts = {c["id"]: c["verdict"] for c in ev["chunks"]}
    assert verdicts["turn-1"] == "drop" and verdicts["turn-2"] == "summarize"
    assert verdicts.get("turn-3") == "summarize_forced"  # 预算不够时才动"必须保留"的块，并标注
    assert set(conv.turns) == {4, 5}  # 最近两轮原样保留
    assert conv.archive.get("turn-2")[0]["content"].startswith("第2轮")
    assert "摘要：读了文件" in conv.render_summaries()
    assert working.goal == "修 bug" and working.open_items() == ["跑测试"]  # 保护清单不受影响
    assert_tool_pairs_intact(conv.messages)


def test_open_items_upgrade_drop_to_summary(tmp_path):
    conv = build_conv(tmp_path, 4)

    def responder(name, q, state):
        return score_ans(0) if name.startswith("value_") else noul_ans(0.9)

    ev = Compressor(small_budget(compress_target=0.05), FakeDecision(responder), lambda p: "摘要").maybe_compress(
        conv, 200, WorkingState(), 4)
    assert all(c["verdict"] != "drop" for c in ev["chunks"])  # 含未完成事项的块不丢


def test_fallback_without_jev_summarizes(tmp_path):
    conv = build_conv(tmp_path, 4)
    ev = Compressor(small_budget(compress_target=0.05), FakeDecision(fail=True), None).maybe_compress(
        conv, 200, WorkingState(), 4)
    assert all(c["verdict"] == "summarize" for c in ev["chunks"])
    assert "用户：" in conv.render_summaries()  # 摘要模型不可用时走抽取式兜底


def test_read_archive_tool(tmp_path):
    conv = build_conv(tmp_path, 4)
    Compressor(small_budget(compress_target=0.05), None, lambda p: "摘要").maybe_compress(conv, 200, WorkingState(), 4)
    ctx = ToolContext(workspace=tmp_path, vault=tmp_path, working=WorkingState(), archive=conv.archive)
    out = build_registry().get("read_archive").handler({"id": "turn-1"}, ctx)
    assert "第1轮的请求" in out


def test_working_state_render_and_evidence_cap():
    w = WorkingState()
    assert "update_plan" in w.render()
    w.update(goal="目标", constraints=["不改 main"], todo=["a", {"item": "b", "done": True}])
    w.update(evidence=[f"e{i}" for i in range(30)])
    assert len(w.evidence) == WorkingState.MAX_EVIDENCE and w.evidence[-1] == "e29"
    text = w.render()
    assert "[x] b" in text and "[ ] a" in text and "不改 main" in text


def test_noop_compression_logged_once_per_turn(tmp_path):
    from agent.trace import Trace
    conv = build_conv(tmp_path, 2, tool_chars=100)
    tr = Trace("s", tmp_path / "t.jsonl")
    comp = Compressor(small_budget(keep_recent_turns=5), None, None, tr)
    for _ in range(3):  # 系统提示本身就超预算，但没有可压的轮次
        assert comp.maybe_compress(conv, 5000, WorkingState(), 2) is None
    lines = (tmp_path / "t.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and '"noop": true' in lines[0]
