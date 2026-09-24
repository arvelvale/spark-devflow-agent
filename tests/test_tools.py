import pytest

from agent.context import WorkingState
from agent.tools import ToolContext, ToolError, build_registry
from agent.tools.base import Permission, safe_path, truncate

from conftest import git


@pytest.fixture
def ctx(cfg):
    return ToolContext(workspace=cfg.workspace, vault=cfg.vault_dir, working=WorkingState(),
                       shell_allow=cfg.shell_allow)


@pytest.fixture
def reg():
    return build_registry()


def call(reg, name, args, ctx):
    return reg.get(name).handler(args, ctx)


def test_registry_permissions(reg):
    assert reg.get("read_file").permission == Permission.READ
    assert reg.get("edit_file").permission == Permission.WRITE_LOCAL
    assert reg.get("linear_create_issue").permission == Permission.EXTERNAL
    # 不提供 push：外部可见的 git 操作不在演示范围
    assert not [n for n in reg.names() if "push" in n]


@pytest.mark.parametrize("bad", ["../secret.txt", "..\\secret.txt", "a/../../x", "/etc/passwd/../../../x"])
def test_safe_path_rejects_escape(tmp_path, bad):
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(ToolError):
        safe_path(root, bad)


def test_read_write_edit(reg, ctx):
    assert "1| # demo" in call(reg, "read_file", {"path": "README.md"}, ctx)
    call(reg, "write_file", {"path": "docs/new.md", "content": "a\nb\n"}, ctx)
    assert (ctx.workspace / "docs" / "new.md").read_text(encoding="utf-8") == "a\nb\n"
    call(reg, "edit_file", {"path": "app.py", "old": "return sum(xs)", "new": "return sum(xs) or 0"}, ctx)
    assert "or 0" in (ctx.workspace / "app.py").read_text(encoding="utf-8")
    with pytest.raises(ToolError, match="没找到"):
        call(reg, "edit_file", {"path": "app.py", "old": "不存在的文本", "new": "x"}, ctx)


def test_edit_requires_unique_match(reg, ctx):
    (ctx.workspace / "dup.txt").write_text("x\nx\n", encoding="utf-8")
    with pytest.raises(ToolError, match="2 次"):
        call(reg, "edit_file", {"path": "dup.txt", "old": "x", "new": "y"}, ctx)


def test_write_refuses_git_dir(reg, ctx):
    with pytest.raises(ToolError):
        call(reg, "write_file", {"path": ".git/config", "content": "x"}, ctx)


def test_search_and_list(reg, ctx):
    assert "app.py:1:" in call(reg, "search_text", {"pattern": "def total"}, ctx)
    listing = call(reg, "list_dir", {}, ctx)
    assert "README.md" in listing and ".git" not in listing


@pytest.mark.parametrize("cmd", ["rm -rf /", "python -m unittest; rm x", "python -m unittest | cat",
                                 "python -c 'print(1)'", "pythonx -m pytest"])
def test_shell_rejects(reg, ctx, cmd):
    with pytest.raises(ToolError):
        call(reg, "run_command", {"command": cmd}, ctx)


def test_shell_runs_allowed(reg, ctx):
    (ctx.workspace / "test_ok.py").write_text(
        "import unittest\nclass T(unittest.TestCase):\n    def test_a(self):\n        self.assertTrue(True)\n",
        encoding="utf-8")
    out = call(reg, "run_command", {"command": "python -m unittest"}, ctx)
    assert out.startswith("退出码 0") and "OK" in out


def test_git_tools(reg, ctx):
    assert "初始化" in call(reg, "git_log", {"n": 5}, ctx)
    assert "工作区干净" in call(reg, "git_status", {}, ctx)
    call(reg, "git_branch", {"name": "agent/fix"}, ctx)
    (ctx.workspace / "app.py").write_text("def total(xs):\n    return 0\n", encoding="utf-8")
    assert "return 0" in call(reg, "git_diff", {}, ctx)
    out = call(reg, "git_commit", {"message": "改 total"}, ctx)
    assert "已提交" in out
    assert git(ctx.workspace, "branch", "--show-current").strip() == "agent/fix"
    with pytest.raises(ToolError, match="没有可提交"):
        call(reg, "git_commit", {"message": "空"}, ctx)


def test_git_ref_injection_rejected(reg, ctx):
    with pytest.raises(ToolError):
        call(reg, "git_show", {"ref": "--output=/tmp/x"}, ctx)


def test_notes(reg, ctx):
    assert "周会.md" in call(reg, "list_notes", {}, ctx)
    assert "修复精度" in call(reg, "read_note", {"path": "会议纪要/周会.md"}, ctx)
    with pytest.raises(ToolError):
        call(reg, "read_note", {"path": "../ws/README.md"}, ctx)


def test_update_plan_and_truncate(reg, ctx):
    call(reg, "update_plan", {"goal": "修 bug", "todo": [{"item": "写测试"}, "改代码"], "evidence": ["app.py"]}, ctx)
    assert ctx.working.goal == "修 bug" and ctx.working.open_items() == ["写测试", "改代码"]
    text, cut = truncate("a" * 1000 + "END", 100)
    assert cut and text.endswith("END") and "省略" in text


def test_linear_without_key(reg, ctx):
    with pytest.raises(ToolError, match="未配置"):
        call(reg, "linear_list_issues", {}, ctx)
