"""门控语义：阈值方向写反是这个项目最怕的一类 bug，这里逐格覆盖架构 3.3d 的表。"""
import pytest

from agent.config import Thresholds
from agent.gate import ToolGate
from agent.tools import build_registry

from conftest import FakeDecision, noul_ans

REG = build_registry()


def gate_with(appropriate: float | None, confirm_answer: bool = True, fail: bool = False):
    asked = []

    def confirm(req):
        asked.append(req)
        return confirm_answer

    dec = FakeDecision(lambda n, q, s: noul_ans(appropriate) if appropriate is not None else None, fail=fail)
    return ToolGate(Thresholds(), dec, confirm), asked


def check(g, tool, allowed=True):
    return g.check(REG.get(tool), {"path": "a.py"}, allowed=allowed, goal="修 bug", request="修 bug")


def test_read_is_always_allowed_without_jev():
    g, asked = gate_with(0.0)
    r = check(g, "read_file", allowed=False)
    assert r.decision == "allow" and r.execute and not asked
    assert not g.decision.calls  # 只读不花 JEV 调用


def test_not_whitelisted_write_is_denied():
    g, asked = gate_with(0.99)
    r = check(g, "edit_file", allowed=False)
    assert r.decision == "deny" and not r.execute and not asked


@pytest.mark.parametrize("v,decision,asked_user", [(0.95, "allow", False), (0.80, "allow", False),
                                                   (0.79, "confirm", True), (0.10, "confirm", True)])
def test_write_local_threshold_direction(v, decision, asked_user):
    # 设计值：appropriate ≥ 0.80 → 免确认执行（越大越放心）；低于 0.80 → 问用户
    g, asked = gate_with(v)
    r = check(g, "edit_file")
    assert r.decision == decision and bool(asked) == asked_user and r.execute


def test_write_local_user_refuses():
    g, _ = gate_with(0.3, confirm_answer=False)
    r = check(g, "edit_file")
    assert r.decision == "confirm" and r.confirmed is False and not r.execute


@pytest.mark.parametrize("v,decision", [(0.99, "confirm"), (0.50, "confirm"), (0.49, "deny"), (0.0, "deny")])
def test_external_always_confirms_or_denies(v, decision):
    # 设计值：外部写一律人工确认；appropriate < 0.50 → 直接拒绝，不打扰用户
    g, asked = gate_with(v)
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
