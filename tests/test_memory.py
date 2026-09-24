import json

import pytest

from agent.config import Thresholds
from agent.memory import MemoryManager, MemoryStore, entities, tokens

from conftest import FakeDecision, noul_ans


def test_tokens_cover_chinese_and_entities():
    t = tokens("金额按分存整数 DAY-7")
    assert {"金额", "额按", "整数", "day-7"} <= t
    assert "DAY-7" in entities("修复 DAY-7，改 tinyledger/store.py")
    assert "tinyledger/store.py" in entities("修复 DAY-7，改 tinyledger/store.py")


def test_recall_ranks_relevant_first(tmp_path):
    s = MemoryStore(tmp_path / "m.sqlite")
    s.add("semantic", "convention", "开发日志写在 docs/progress/日期.md，三个小节")
    s.add("semantic", "fact", "金额统一按分存整数，读取老数据时自动换算")
    s.add("semantic", "preference", "回复要先给结论")
    hits = s.recall("金额精度的问题怎么修", 3)
    assert hits[0][0].content.startswith("金额统一")
    assert s.recall("完全无关的询问 xyz", 3) == []


def test_select_thresholds_and_privacy(tmp_path):
    s = MemoryStore(tmp_path / "m.sqlite")
    a = s.add("semantic", "fact", "金额统一按分存整数")
    b = s.add("semantic", "fact", "金额导出 CSV 用 UTF-8 BOM")
    c = s.add("semantic", "fact", "金额相关的会议在周三")
    p = s.add("profile", "preference", "金额相关的事情我最近很焦虑", privacy="local")
    values = {a.id: 0.9, b.id: 0.5, c.id: 0.1}

    def responder(name, q, state):
        return noul_ans(values[name.split("_", 1)[1]])

    dec = FakeDecision(responder)
    mm = MemoryManager(s, Thresholds(), dec)
    sel = mm.select("金额精度怎么修", "修金额", "local")
    assert [m.id for m in sel.full] == [a.id]            # ≥ 0.70 原文
    assert b.id in [m.id for m in sel.brief]             # 0.40–0.70 摘要位
    assert c.id not in [m.id for m in sel.full + sel.brief]  # < 0.40 丢弃
    assert p.id in [m.id for m in sel.brief]             # 本地轮次：隐私记忆按关键词放摘要位
    sent = json.dumps([st for st, _ in dec.calls], ensure_ascii=False)
    assert "焦虑" not in sent                             # 隐私记忆永远不进 JEV

    sel_cloud = mm.select("金额精度怎么修", "修金额", "cloud")
    assert p.id not in [m.id for m in sel_cloud.full + sel_cloud.brief]
    assert p.id in sel_cloud.detail["excluded_private"]


def test_select_fallback_uses_keyword_top3(tmp_path):
    s = MemoryStore(tmp_path / "m.sqlite")
    for i in range(5):
        s.add("semantic", "fact", f"金额规则 {i}")
    sel = MemoryManager(s, Thresholds(), FakeDecision(fail=True)).select("金额规则", "", "local")
    assert sel.fallback and len(sel.brief) == 3 and not sel.full


def test_write_back_gates(tmp_path):
    s = MemoryStore(tmp_path / "m.sqlite")
    worth = {"金额按分存整数": 0.9, "日志放 docs/progress": 0.5, "今天调用了三次工具": 0.1}

    def responder(name, q, state):
        return noul_ans(worth[state["candidate"]])

    extracted = json.dumps([
        {"content": "金额按分存整数", "kind": "decision", "privacy": "shareable"},
        {"content": "日志放 docs/progress", "kind": "convention", "privacy": "shareable"},
        {"content": "今天调用了三次工具", "kind": "fact", "privacy": "shareable"},
    ], ensure_ascii=False)
    mm = MemoryManager(s, Thresholds(), FakeDecision(responder), extract=lambda p: extracted)
    items = mm.write_back("修精度", ["implement-change"], [{"tool": "edit_file", "ok": True}], "修好了", "对话")
    status = {i.get("content") or s.get(i["id"]).content: i["status"] for i in items if i.get("layer") != "episodic"}
    assert status == {"金额按分存整数": "active", "日志放 docs/progress": "pending", "今天调用了三次工具": "discard"}
    assert len(s.list("active", "episodic")) == 1  # 每轮一条情景记忆

    # 同样的内容再来一次：识别为重复，不新增
    items2 = mm.write_back("再修", [], [], "好", "对话")
    assert any(i["status"] == "duplicate" for i in items2)


def test_private_candidates_go_pending(tmp_path):
    s = MemoryStore(tmp_path / "m.sqlite")
    extracted = '[{"content": "用户说最近压力很大", "kind": "preference", "privacy": "local"}]'
    dec = FakeDecision(lambda n, q, st: noul_ans(0.99))
    items = MemoryManager(s, Thresholds(), dec, extract=lambda p: extracted).write_back("x", [], [], "y", "z")
    assert [i["status"] for i in items if i.get("layer") == "profile"] == ["pending"]
    assert not dec.calls  # 隐私候选不送 JEV


@pytest.mark.parametrize("existing,new,dup", [
    # 2026-09-24 面板里看到的真实重复：同一事实换了说法
    ('金额统一按"分"存整数，读取老数据时自动换算。优先级高于月度汇总', '金额统一改成按"分"存整数，读取老数据时自动转换', True),
    ('金额计算不得用 float 累加，统一按"分"存整数，读取老数据时自动换算', '金额计算不得用 float 累加，统一按"分"存整数', True),
    ("金额按分存整数", "CSV 导出：编码用 UTF-8 带 BOM，不然 Excel 打开中文乱码", False),
    ("开发日志写在 docs/progress/日期.md", "计划文档写在 docs/plans/日期-短名.md", False),
])
def test_near_duplicate_catches_paraphrase(tmp_path, existing, new, dup):
    s = MemoryStore(tmp_path / "m.sqlite")
    s.add("semantic", "fact", existing)
    assert (s.near_duplicate(new) is not None) == dup
