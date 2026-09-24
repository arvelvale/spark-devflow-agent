"""门控语义：阈值方向写反是这个项目最怕的一类 bug，这里逐格覆盖 gate.py 顶部的表。"""
import pytest

from agent.config import Thresholds
from agent.gate import ToolGate
from agent.tools import build_registry

from conftest import FakeDecision, noul_ans

REG = build_registry()


def gate_with(scope: float | None, collateral: float = 0.0, confirm_answer: bool = True, fail: bool = False):
    asked = []

    def confirm(req):
        asked.append(req)
        return confirm_answer

    values = {"in_scope": scope, "collateral": collateral}
    dec = FakeDecision(lambda n, q, s: noul_ans(values[n]) if scope is not None else None, fail=fail)
    return ToolGate(Thresholds(), dec, confirm), asked


def check(g, tool, allowed=True):
    return g.check(REG.get(tool), {"path": "a.py"}, allowed=allowed, goal="修 bug", request="修 bug", plan=["改代码"])


def test_read_is_always_allowed_without_jev():
    g, asked = gate_with(0.0)
    r = check(g, "read_file", allowed=False)
    assert r.decision == "allow" and r.execute and not asked
    assert not g.decision.calls  # 只读不花 JEV 调用


def test_not_whitelisted_write_is_denied():
    g, asked = gate_with(0.99)
    r = check(g, "edit_file", allowed=False)
    assert r.decision == "deny" and not r.execute and not asked


@pytest.mark.parametrize("scope,collateral,decision", [
    (0.90, 0.10, "allow"),    # 合理步骤、无越界 → 免确认
    (0.50, 0.49, "allow"),    # 两个阈值的边界：in_scope ≥ 0.50 且 collateral < 0.50
    (0.49, 0.10, "confirm"),  # 不像合理步骤 → 问用户
    (0.95, 0.50, "confirm"),  # 再合理，只要可能删改无关内容 → 问用户（越界优先）
    (0.95, 0.96, "confirm"),
])
def test_write_local_two_signals(scope, collateral, decision):
    g, asked = gate_with(scope, collateral)
    r = check(g, "edit_file")
    assert r.decision == decision and bool(asked) == (decision == "confirm") and r.execute


def test_write_local_user_refuses():
    g, _ = gate_with(0.3, confirm_answer=False)
    r = check(g, "edit_file")
    assert r.decision == "confirm" and r.confirmed is False and not r.execute


@pytest.mark.parametrize("scope,decision", [(0.99, "confirm"), (0.50, "confirm"), (0.49, "deny"), (0.0, "deny")])
def test_external_always_confirms_or_denies(scope, decision):
    # 外部写一律人工确认；in_scope < 0.50 → 直接拒绝，不打扰用户
    g, asked = gate_with(scope)
    r = check(g, "linear_create_issue")
    assert r.decision == decision
    assert bool(asked) == (decision == "confirm")


def test_jev_down_falls_back_to_confirm():
    g, asked = gate_with(None, fail=True)
    r = check(g, "edit_file")
    assert r.decision == "confirm" and r.fallback and asked


def test_no_confirm_callback_means_no():
    g = ToolGate(Thresholds(), FakeDecision(lambda n, q, s: noul_ans(0.1)), None)
    assert not check(g, "edit_file").execute


def test_gate_state_carries_plan_and_clips_long_args():
    g, _ = gate_with(0.9)
    g.check(REG.get("write_file"), {"path": "a.py", "content": "x" * 5000}, allowed=True,
            goal="g", request="r", plan=["写测试"])
    state = g.decision.calls[0][0]
    assert state["plan"] == ["写测试"] and len(state["arguments"]["content"]) < 1600
