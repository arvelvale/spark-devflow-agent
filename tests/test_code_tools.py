"""代码结构工具：Python 语法树大纲、其他语言兜底、符号定义与引用、路径沙箱。"""
import pytest

from agent.context import WorkingState
from agent.tools import build_registry
from agent.tools.base import ToolContext, ToolError

REG = build_registry()

PY = '''"""模块说明"""
import json
from . import util

RATE = 100


class Ledger(Base):
    """账本"""

    def add(self, amount: int, note: str = "") -> dict:
        """记一笔"""
        return {}


def total(entries):
    return sum(e["amount"] for e in entries)
'''

TS = '''export function formatCents(v: number): string {
  return (v / 100).toFixed(2);
}
export class Wallet {}
const helper = (x) => x;
'''


@pytest.fixture
def ctx(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "ledger.py").write_text(PY, encoding="utf-8")
    (tmp_path / "pkg" / "use.py").write_text("from .ledger import total\nprint(total([]))\n", encoding="utf-8")
    (tmp_path / "web.ts").write_text(TS, encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.js").write_text("function hidden() {}\n", encoding="utf-8")
    return ToolContext(workspace=tmp_path, vault=tmp_path, working=WorkingState())


def run(name, args, ctx):
    return REG.get(name).handler(args, ctx)


def test_python_outline_has_signatures_and_line_spans(ctx):
    out = run("code_outline", {"path": "pkg/ledger.py"}, ctx)
    assert "class Ledger(Base)  # 账本" in out
    assert "def add(self, amount: int, note: str='') -> dict  # 记一笔" in out
    assert "L16-17  def total(entries)" in out and "RATE = …" in out and "import json, ." in out


def test_directory_outline_covers_other_languages_and_skips_vendor(ctx):
    out = run("code_outline", {}, ctx)
    assert "## web.ts" in out and "formatCents" in out and "class Wallet" in out
    assert "node_modules" not in out and "hidden" not in out


def test_find_symbol_separates_definition_from_references(ctx):
    out = run("find_symbol", {"name": "total"}, ctx)
    defs, refs = out.split("引用")
    assert "pkg/ledger.py:L16-17" in defs
    assert "pkg/use.py:1:" in refs and "pkg/use.py:2:" in refs and "ledger.py:16" not in refs


def test_syntax_error_is_reported_not_raised(ctx):
    (ctx.workspace / "bad.py").write_text("def broken(:\n", encoding="utf-8")
    assert "语法错误" in run("code_outline", {"path": "bad.py"}, ctx)


def test_sandbox_and_input_checks(ctx):
    with pytest.raises(ToolError):
        run("code_outline", {"path": "../"}, ctx)
    with pytest.raises(ToolError):
        run("find_symbol", {"name": "a.b; rm"}, ctx)
