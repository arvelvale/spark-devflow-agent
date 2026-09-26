"""技能脚本：声明校验、只跑已声明的、权限按声明解析、子进程拿不到 API Key。"""
import pytest

from agent.context import WorkingState
from agent.kernel import Agent
from agent.skills import SkillFormatError, parse_skill
from agent.tools import Permission, build_registry
from agent.tools.base import ToolContext, ToolError

from conftest import FakeDecision, FakeLLM

HEAD = """---
name: demo-skill
description: 演示技能
version: 0.1.0
allowed-tools: []
triggers: [a, b]
not-for: [c]
{scripts}---
正文
"""


def make_skill(tmp_path, scripts_yaml: str, files: dict[str, str]):
    d = tmp_path / "skills" / "demo-skill"
    (d / "scripts").mkdir(parents=True)
    for name, code in files.items():
        (d / "scripts" / name).write_text(code, encoding="utf-8")
    (d / "SKILL.md").write_text(HEAD.format(scripts=scripts_yaml), encoding="utf-8")
    return d / "SKILL.md"


READ_DECL = "scripts:\n  - name: env_dump.py\n    description: 打印环境\n    permission: read\n"


def test_declared_script_parses(tmp_path):
    s = parse_skill(make_skill(tmp_path, READ_DECL, {"env_dump.py": "print(1)"}))
    assert [(x.name, x.permission) for x in s.scripts] == [("env_dump.py", "read")]


@pytest.mark.parametrize("decl,msg", [
    ("scripts:\n  - name: missing.py\n    description: x\n    permission: read\n", "不存在"),
    ("scripts:\n  - name: env_dump.py\n    description: x\n    permission: root\n", "permission"),
    ("scripts:\n  - name: ../evil.py\n    description: x\n    permission: read\n", "不合法"),
])
def test_bad_declarations_rejected(tmp_path, decl, msg):
    with pytest.raises(SkillFormatError, match=msg):
        parse_skill(make_skill(tmp_path, decl, {"env_dump.py": "print(1)"}))


def ctx_for(tmp_path, skill):
    return ToolContext(workspace=tmp_path, vault=tmp_path, working=WorkingState(),
                       skill_dirs={skill.name: skill.path.parent},
                       skill_scripts={skill.name: {x.name: x for x in skill.scripts}})


def test_script_runs_without_api_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("STEPFUN_API_KEY", "sk-should-not-leak")
    monkeypatch.setenv("TYPESAFE_API_KEY", "tk-should-not-leak")
    code = "import os\nprint(sorted(k for k in os.environ if 'KEY' in k or 'PROXY' in k.upper()))\nprint(os.environ['WORKSPACE'])"
    skill = parse_skill(make_skill(tmp_path, READ_DECL, {"env_dump.py": code}))
    out = build_registry().get("run_skill_script").handler({"skill": "demo-skill", "script": "env_dump.py"},
                                                            ctx_for(tmp_path, skill))
    assert "should-not-leak" not in out and "API_KEY" not in out and str(tmp_path) in out


def test_run_command_env_has_no_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("LINEAR_API_KEY", "lin-should-not-leak")
    (tmp_path / "t.py").write_text("import os\nprint('LINEAR_API_KEY' in os.environ)\n", encoding="utf-8")
    ctx = ToolContext(workspace=tmp_path, vault=tmp_path, working=WorkingState(), shell_allow=("python t.py",))
    assert "False" in build_registry().get("run_command").handler({"command": "python t.py"}, ctx)


def test_undeclared_script_refused(tmp_path):
    skill = parse_skill(make_skill(tmp_path, READ_DECL, {"env_dump.py": "print(1)", "sneaky.py": "print(2)"}))
    with pytest.raises(ToolError, match="没有声明"):
        build_registry().get("run_skill_script").handler({"skill": "demo-skill", "script": "sneaky.py"},
                                                         ctx_for(tmp_path, skill))


def test_permission_follows_declaration(cfg, tmp_path):
    decl = READ_DECL + "  - name: tests.py\n    description: 跑测试\n    permission: write_local\n"
    skill = parse_skill(make_skill(tmp_path, decl, {"env_dump.py": "print(1)", "tests.py": "print(2)"}))
    agent = Agent(cfg, decision=FakeDecision(), clients={n: FakeLLM(n) for n in ("local", "backup", "cloud")},
                  use_jev=False)
    agent.ctx.skill_scripts = {skill.name: {x.name: x for x in skill.scripts}}
    tool = agent.registry.get("run_skill_script")
    read_tool, ok1 = agent._resolve_tool(tool, {"skill": "demo-skill", "script": "env_dump.py"})
    write_tool, ok2 = agent._resolve_tool(tool, {"skill": "demo-skill", "script": "tests.py"})
    other, ok3 = agent._resolve_tool(tool, {"skill": "demo-skill", "script": "nope.py"})
    assert (read_tool.permission, ok1) == (Permission.READ, True)
    assert (write_tool.permission, ok2) == (Permission.WRITE_LOCAL, True)
    assert (other.permission, ok3) == (Permission.WRITE_LOCAL, False)  # 未声明：保持最严，再由工具拒绝
    assert tool.permission == Permission.WRITE_LOCAL  # 注册表里的原件没被改


def test_repo_skill_scripts_are_valid():
    from pathlib import Path
    from agent.skills import load_skills
    skills, errors = load_skills(Path(__file__).resolve().parents[1] / "skills", set(build_registry().names()))
    assert not errors
    by = {s.name: s for s in skills}
    assert by["standup-brief"].script("collect.py").permission == "read"
    assert by["implement-change"].script("test_report.py").permission == "write_local"
