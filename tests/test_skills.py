import pytest

from agent.config import Thresholds
from agent.skills import SkillFormatError, SkillSelector, load_skills, parse_skill
from agent.tools import build_registry

from conftest import ROOT, FakeDecision, FakeLLM, choice_ans, noul_ans, reply

REG = build_registry()


@pytest.fixture(scope="module")
def skills():
    loaded, errors = load_skills(ROOT / "skills", set(REG.names()))
    assert not errors, errors
    return loaded


def test_repo_skills_all_valid(skills):
    names = {s.name for s in skills}
    assert {"issue-breakdown", "plan-writer", "implement-change", "progress-logger", "status-sync",
            "standup-brief", "review-gate", "meeting-to-tasks"} <= names


def test_write_tools_only_in_whitelists(skills):
    # standup-brief 纯只读：白名单里不应出现写工具
    s = next(s for s in skills if s.name == "standup-brief")
    assert all(REG.get(t).permission.value == "read" for t in s.allowed_tools)


def write_skill(tmp_path, dirname, frontmatter, body="正文"):
    d = tmp_path / dirname
    d.mkdir()
    (d / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n{body}\n", encoding="utf-8")
    return d / "SKILL.md"


GOOD = """name: demo-skill
description: 演示
version: 0.1.0
allowed-tools: []
triggers: [a, b]
not-for: [c]"""


def test_parse_good(tmp_path):
    s = parse_skill(write_skill(tmp_path, "demo-skill", GOOD))
    assert s.key == "demo_skill" and s.model == "auto"


@pytest.mark.parametrize("mutate,msg", [
    (lambda t: t.replace("name: demo-skill", "name: Demo_Skill"), "kebab"),
    (lambda t: t.replace("triggers: [a, b]", "triggers: [a]"), "triggers"),
    (lambda t: t.replace("not-for: [c]", ""), "not-for"),
    (lambda t: t.replace("version: 0.1.0", "version: 1"), "version"),
    (lambda t: t + "\nmodel: gpu", "model"),
])
def test_parse_rejects(tmp_path, mutate, msg):
    with pytest.raises(SkillFormatError, match=msg):
        parse_skill(write_skill(tmp_path, "demo-skill", mutate(GOOD)))


def test_unknown_tool_reported(tmp_path):
    write_skill(tmp_path, "demo-skill", GOOD.replace("allowed-tools: []", "allowed-tools: [rm_rf]"))
    ok, errors = load_skills(tmp_path, set(REG.names()))
    assert not ok and "rm_rf" in errors[0]


def jev(stage1: dict, gate: tuple, fits: dict):
    acts, proc, prose = gate

    def responder(name, q, state):
        if name == "skill":
            return choice_ans(stage1)
        if name in ("acts", "procedure", "prose"):
            return noul_ans({"acts": acts, "procedure": proc, "prose": prose}[name])
        if name.startswith("fits_"):
            return noul_ans(fits[name[5:]])
        return None
    return FakeDecision(responder)


def test_two_stage_selects_best(skills):
    dec = jev({"progress_logger": 0.6, "standup_brief": 0.3, "none": 0.1}, (0.9, 0.8, 0.1),
              {"progress_logger": 0.9, "standup_brief": 0.2})
    sel = SkillSelector(skills, Thresholds(), dec, None).select("把今天的提交写进日志")
    assert sel.names == ["progress-logger"] and sel.mode == "jev" and not sel.fallback
    assert sel.detail["gate"]["value"] == pytest.approx((0.9 + 0.8 + 0.9) / 3, abs=1e-3)


def test_gate_below_threshold_selects_nothing(skills):
    dec = jev({"progress_logger": 0.9, "none": 0.1}, (0.1, 0.1, 0.9), {"progress_logger": 0.9})
    sel = SkillSelector(skills, Thresholds(), dec, None).select("rebase 和 merge 有啥区别")
    assert sel.names == [] and len(dec.calls) == 1  # 门控挡住就不进第二级


def test_low_fits_rejects_all(skills):
    dec = jev({"plan_writer": 0.5, "none": 0.5}, (0.8, 0.8, 0.2), {"plan_writer": 0.2})
    assert SkillSelector(skills, Thresholds(), dec, None).select("x").names == []


def test_multi_skill(skills):
    dec = jev({"implement_change": 0.5, "status_sync": 0.4, "none": 0.1}, (0.9, 0.9, 0.1),
              {"implement_change": 0.9, "status_sync": 0.8})
    sel = SkillSelector(skills, Thresholds(), dec, None).select("修完 bug 把 issue 关掉")
    assert sel.names == ["implement-change", "status-sync"]


def test_fallback_to_baseline_when_jev_down(skills):
    llm = FakeLLM("local", [reply('好的：{"skills": ["standup-brief"]}')])
    sel = SkillSelector(skills, Thresholds(), FakeDecision(fail=True), llm).select("站会简报")
    assert sel.fallback and sel.mode == "baseline" and sel.names == ["standup-brief"]


def test_baseline_ignores_unknown_names(skills):
    llm = FakeLLM("local", [reply('{"skills": ["rm-everything", "plan-writer"]}')])
    assert SkillSelector(skills, Thresholds(), None, llm).select("x", mode="baseline").names == ["plan-writer"]
