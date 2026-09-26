from agent.config import Thresholds
from agent.context import ArchiveStore, Compressor, Conversation, WorkingState, collect_calls, estimate_tokens
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
        if name.startswith("keep_"):  # 阶段 A 逐调用裁剪：全部保留，只测阶段 B
            return noul_ans(0.9)
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



# ---------------- 阶段 A：逐个工具调用裁剪 ----------------
def one_long_turn(tmp_path, n: int = 5, chars: int = 3000) -> Conversation:
    """单轮长任务：一轮里连着 n 次工具调用（旧阶段 B 对这种情况无能为力）。"""
    conv = Conversation(archive=ArchiveStore(tmp_path / "archive.jsonl"))
    conv.add({"role": "user", "content": "把金额精度的 bug 修了"}, 1)
    for k in range(1, n + 1):
        conv.add({"role": "assistant", "content": f"第{k}步说明", "tool_calls": [
            {"id": f"c{k}", "type": "function", "function": {"name": "read_file", "arguments": f'{{"path": "f{k}.py"}}'}}]}, 1)
        conv.add({"role": "tool", "tool_call_id": f"c{k}", "content": f"文件{k}原文 " + "代码" * (chars // 2)}, 1)
    return conv


def verdicts_by_cid(table):
    def responder(name, q, state):
        if name.startswith("keep_call_"):
            return noul_ans(table[name.removeprefix("keep_call_")][0])
        if name.startswith("keep_result_"):
            return noul_ans(table[name.removeprefix("keep_result_")][1])
        return None
    return responder


def test_prunes_inside_a_single_long_turn(tmp_path):
    conv = one_long_turn(tmp_path)
    table = {"t1": (0.1, 0.1), "t2": (0.8, 0.2), "t3": (0.9, 0.9), "t4": (0.1, 0.1)}  # t5 最近一条，受保护
    dec = FakeDecision(verdicts_by_cid(table))
    th = small_budget(compress_target=0.05)
    ev = Compressor(th, dec, None).maybe_compress(conv, 200, WorkingState(goal="修精度 bug"), 1)
    phase = ev["phases"][0]
    assert phase["phase"] == "tool_calls" and (phase["kept"], phase["truncated"], phase["removed"]) == (1, 1, 2)
    ids = [c["id"] for m in conv.messages if m["role"] == "assistant" for c in m.get("tool_calls") or []]
    assert ids == ["c2", "c3", "c5"]                                    # t1、t4 连调用带结果一起删
    results = {m["tool_call_id"]: m["content"] for m in conv.messages if m["role"] == "tool"}
    assert results["c2"].startswith("[已压缩] 文件2原文") and "read_archive('calls-1-1')" in results["c2"]
    assert results["c3"].startswith("文件3原文") and results["c5"].startswith("文件5原文")
    texts = [m["content"] for m in conv.messages if m["role"] == "assistant"]
    assert "第1步说明" in texts and "第4步说明" in texts                   # 文字一律不删，只摘掉调用
    archived = {x["cid"]: x for x in conv.archive.get("calls-1-1")}
    assert set(archived) == {"t1", "t2", "t4"} and archived["t1"]["result"].startswith("文件1原文")
    assert "移除了 2 次" in conv.render_summaries() and "calls-1-1" in conv.render_summaries()
    assert_tool_pairs_intact(conv.messages)


def test_jev_sees_whole_conversation_without_raw_results(tmp_path):
    conv = one_long_turn(tmp_path, n=3)
    dec = FakeDecision(lambda n, q, s: noul_ans(0.9))
    Compressor(small_budget(compress_target=0.05), dec, None).maybe_compress(conv, 200, WorkingState(goal="g"), 1)
    state = dec.calls[0][0]
    view = state["conversation"]
    assert "用户：把金额精度的 bug 修了" in view and "[t1] read_file" in view and "成功，" in view
    assert "[保留] read_file" in view          # 最近一条结果受保护，只作为上下文给出，不出题
    assert "代码代码" not in view              # 结果原文不进 state
    assert set(dec.calls[0][1]) == {"keep_call_t1", "keep_result_t1", "keep_call_t2", "keep_result_t2"}


def test_message_with_two_calls_keeps_the_survivor(tmp_path):
    conv = Conversation(archive=ArchiveStore(tmp_path / "a.jsonl"))
    conv.add({"role": "user", "content": "看两个文件"}, 1)
    conv.add({"role": "assistant", "content": "", "tool_calls": [
        {"id": "a", "type": "function", "function": {"name": "read_file", "arguments": "{}"}},
        {"id": "b", "type": "function", "function": {"name": "git_log", "arguments": "{}"}}]}, 1)
    conv.add({"role": "tool", "tool_call_id": "a", "content": "甲" * 3000}, 1)
    conv.add({"role": "tool", "tool_call_id": "b", "content": "乙" * 3000}, 1)
    conv.add({"role": "assistant", "content": "", "tool_calls": [
        {"id": "c", "type": "function", "function": {"name": "list_dir", "arguments": "{}"}}]}, 1)
    conv.add({"role": "tool", "tool_call_id": "c", "content": "丙" * 3000}, 1)
    dec = FakeDecision(verdicts_by_cid({"t1": (0.1, 0.1), "t2": (0.9, 0.9)}))
    Compressor(small_budget(compress_target=0.05), dec, None).maybe_compress(conv, 200, WorkingState(), 1)
    calls = [[c["id"] for c in m["tool_calls"]] for m in conv.messages if m.get("tool_calls")]
    assert calls == [["b"], ["c"]]
    assert_tool_pairs_intact(conv.messages)


def test_falls_back_to_rules_when_jev_down_or_state_too_big(tmp_path):
    conv = one_long_turn(tmp_path)
    ev = Compressor(small_budget(compress_target=0.05), FakeDecision(fail=True), None).maybe_compress(
        conv, 200, WorkingState(), 1)
    assert ev["phases"][0]["phase"] == "tool_results"
    conv2 = one_long_turn(tmp_path / "b")
    ev2 = Compressor(small_budget(compress_target=0.05, compress_state_tokens=10), FakeDecision(), None).maybe_compress(
        conv2, 200, WorkingState(), 1)
    assert ev2["phases"][0]["phase"] == "tool_results" and "token" in ev2["fallback_reason"]


def test_short_and_pinned_calls_are_not_asked(tmp_path):
    conv = one_long_turn(tmp_path, n=3, chars=100)  # 结果都很短
    calls = collect_calls(conv, keep_recent=1)
    assert [c.pinned for c in calls] == [False, False, True]
    dec = FakeDecision(lambda n, q, s: noul_ans(0.1))
    Compressor(small_budget(context_budget=200, compress_target=0.05), dec, None).maybe_compress(
        conv, 200, WorkingState(), 1)
    assert not dec.calls  # 没有值得问的调用，不花 JEV 请求



def test_kept_calls_are_not_reasked_until_context_moves(tmp_path):
    conv = one_long_turn(tmp_path, n=4)
    dec = FakeDecision(lambda n, q, s: noul_ans(0.9))  # 全部保留
    comp = Compressor(small_budget(compress_target=0.05, keep_recent_turns=5, compress_rejudge_after=3), dec, None)
    comp.maybe_compress(conv, 200, WorkingState(), 1)
    assert len(dec.calls) == 1
    comp.maybe_compress(conv, 200, WorkingState(), 1)    # 什么都没变：不再花请求
    assert len(dec.calls) == 1
    for k in range(5, 8):                                 # 又新增 3 次调用：旧的可以重问了
        conv.add({"role": "assistant", "content": "", "tool_calls": [
            {"id": f"c{k}", "type": "function", "function": {"name": "read_file", "arguments": "{}"}}]}, 1)
        conv.add({"role": "tool", "tool_call_id": f"c{k}", "content": "新" * 2000}, 1)
    comp.maybe_compress(conv, 200, WorkingState(), 1)
    assert len(dec.calls) == 2 and "keep_result_t1" in dec.calls[1][1]


def test_read_archive_returns_pruned_calls(tmp_path):
    """实测里 read_archive 取逐调用裁剪的归档会报错（按消息列表去渲染），这里走真实工具验证能取回。"""
    conv = one_long_turn(tmp_path)
    dec = FakeDecision(verdicts_by_cid({"t1": (0.1, 0.1), "t2": (0.8, 0.2), "t3": (0.9, 0.9), "t4": (0.9, 0.9)}))
    Compressor(small_budget(compress_target=0.05), dec, None).maybe_compress(conv, 200, WorkingState(), 1)
    ctx = ToolContext(workspace=tmp_path, vault=tmp_path, working=WorkingState(), archive=conv.archive)
    tool = build_registry().get("read_archive")
    out = tool.handler({"id": "calls-1-1"}, ctx)
    assert out.startswith("[t1] read_file") and "文件1原文" in out and "文件2原文" in out
    only = tool.handler({"id": "calls-1-1", "call": "t2"}, ctx)
    assert "文件2原文" in only and "文件1原文" not in only


def test_refetched_result_is_protected_and_cooldown_holds(tmp_path):
    conv = one_long_turn(tmp_path, n=4)
    dec = FakeDecision(lambda n, q, s: noul_ans(0.9 if n.startswith("keep_call") else 0.1))  # 全部截短
    comp = Compressor(small_budget(compress_target=0.05, keep_recent_tool_results=1), dec, None)
    comp.maybe_compress(conv, 200, WorkingState(), 1)
    n_asks = len(dec.calls)
    assert comp.maybe_compress(conv, 200, WorkingState(), 1) is None and len(dec.calls) == n_asks  # 冷却中
    # 模型把 f1.py 重新读了一遍（同样的工具和参数），然后又读了几个别的，把上下文撑大
    conv.add({"role": "assistant", "content": "", "tool_calls": [
        {"id": "again", "type": "function", "function": {"name": "read_file", "arguments": '{"path": "f1.py"}'}}]}, 1)
    conv.add({"role": "tool", "tool_call_id": "again", "content": "文件1原文 " + "代码" * 1500}, 1)
    for k in range(10, 13):
        conv.add({"role": "assistant", "content": "", "tool_calls": [
            {"id": f"x{k}", "type": "function", "function": {"name": "list_dir", "arguments": f'{{"n": {k}}}'}}]}, 1)
        conv.add({"role": "tool", "tool_call_id": f"x{k}", "content": "目录" * 1500}, 1)
    comp.maybe_compress(conv, 200, WorkingState(), 1)
    again = next(m for m in conv.messages if m.get("tool_call_id") == "again")
    assert again["content"].startswith("文件1原文")  # 重读回来的不再被截
