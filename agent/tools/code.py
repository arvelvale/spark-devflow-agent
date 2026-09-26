"""代码结构工具：用语法树看项目骨架，按行号精读，少整文件读取。

为什么省 token：一次 DAY-298 修复里输入 token 占 93%——每一步都把整段上下文重发一遍，
所以"每步上下文有多大"比"输出多长"更要紧。整文件 read_file 进了上下文就会被后面每一步重复计费；
先看大纲（几十行）再按行号读一个函数，同样的信息量只占几分之一。

- Python 用标准库 ast（节点上零安装），给出类 / 函数 / 方法的签名、行号范围、文档首行、import
- 其他语言用正则兜底（JS/TS/Go/Rust/Java 的常见定义形式），只给名字和行号，不保证完整
- find_symbol：定义位置（ast）+ 引用位置（按单词边界搜索）
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from .base import Permission, Tool, ToolContext, ToolError, arg, params, safe_path
from .fs import SKIP_DIRS, _read_text

MAX_FILES = 80
OTHER_DEF = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?"
    r"(?:function\*?\s+(\w+)|class\s+(\w+)|interface\s+(\w+)|type\s+(\w+)\s*=|"
    r"(?:const|let)\s+(\w+)\s*=\s*(?:async\s*)?\(|func\s+(?:\([^)]*\)\s*)?(\w+)|fn\s+(\w+)|"
    r"(?:pub\s+)?(?:struct|enum|trait)\s+(\w+))")
CODE_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".go", ".rs", ".java", ".kt"}


def _sig(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    try:
        args = ast.unparse(node.args)
    except Exception:  # 极少数新语法 unparse 不了
        args = "…"
    ret = f" -> {ast.unparse(node.returns)}" if node.returns is not None else ""
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return f"{prefix} {node.name}({args}){ret}"


def _doc(node) -> str:
    doc = ast.get_docstring(node) or ""
    return doc.strip().splitlines()[0][:80] if doc.strip() else ""


def _span(node) -> str:
    end = getattr(node, "end_lineno", None) or node.lineno
    return f"L{node.lineno}-{end}" if end != node.lineno else f"L{node.lineno}"


def outline_python(text: str) -> list[str]:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [f"（语法错误，第 {exc.lineno} 行：{exc.msg}）"]
    out: list[str] = []
    imports = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            imports.append(f"{'.' * node.level}{node.module or ''}")
    if imports:
        out.append("import " + ", ".join(dict.fromkeys(imports))[:200])
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = _doc(node)
            out.append(f"{_span(node)}  {_sig(node)}" + (f"  # {doc}" if doc else ""))
        elif isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(b) for b in node.bases)
            doc = _doc(node)
            out.append(f"{_span(node)}  class {node.name}" + (f"({bases})" if bases else "") + (f"  # {doc}" if doc else ""))
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    d = _doc(sub)
                    out.append(f"  {_span(sub)}  {_sig(sub)}" + (f"  # {d}" if d else ""))
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = [t.id for t in targets if isinstance(t, ast.Name) and t.id.isupper()]
            if names:  # 只列模块级常量，普通变量是噪音
                out.append(f"L{node.lineno}  {', '.join(names)} = …")
    return out


def outline_other(text: str) -> list[str]:
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        m = OTHER_DEF.match(line)
        if m:
            out.append(f"L{n}  {line.strip()[:120]}")
    return out[:120]


def outline_file(path: Path) -> list[str]:
    text = _read_text(path)
    lines = outline_python(text) if path.suffix == ".py" else outline_other(text)
    return lines or ["（没有顶层定义）"]


def _code_files(base: Path, root: Path) -> list[Path]:
    files = []
    for f in sorted(base.rglob("*")):
        if f.is_file() and f.suffix in CODE_EXT and not any(p in SKIP_DIRS for p in f.relative_to(root).parts):
            files.append(f)
    return files


def code_outline(args: dict, ctx: ToolContext) -> str:
    root = ctx.workspace.resolve()
    target = safe_path(ctx.workspace, arg(args, "path", "."))
    if target.is_file():
        n = len(_read_text(target).splitlines())
        return f"{target.relative_to(root).as_posix()}（{n} 行）\n" + "\n".join(outline_file(target))
    if not target.is_dir():
        raise ToolError(f"路径不存在：{args.get('path', '.')}")
    files = _code_files(target, root)
    if not files:
        return "这个目录下没有代码文件"
    blocks = []
    for f in files[:MAX_FILES]:
        try:
            body = outline_file(f)
        except ToolError:
            continue
        n = len(f.read_text(encoding="utf-8", errors="replace").splitlines())
        blocks.append(f"## {f.relative_to(root).as_posix()}（{n} 行）\n" + "\n".join(body))
    more = f"\n…（另有 {len(files) - MAX_FILES} 个文件未列出，缩小 path 再看）" if len(files) > MAX_FILES else ""
    return "\n\n".join(blocks) + more + "\n\n提示：用 read_file 的 start_line / max_lines 按上面的行号精读。"


def find_symbol(args: dict, ctx: ToolContext) -> str:
    name = arg(args, "name", required=True).strip()
    if not re.fullmatch(r"[A-Za-z_]\w*", name):
        raise ToolError("name 只能是一个标识符，比如 add_amount 或 Ledger")
    root = ctx.workspace.resolve()
    defs, refs = [], []
    word = re.compile(rf"\b{re.escape(name)}\b")
    for f in _code_files(root, root):
        rel = f.relative_to(root).as_posix()
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        def_lines: set[int] = set()
        if f.suffix == ".py":
            try:
                for node in ast.walk(ast.parse(text)):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
                        what = _sig(node) if not isinstance(node, ast.ClassDef) else f"class {node.name}"
                        defs.append(f"{rel}:{_span(node)}  {what}")
                        def_lines.add(node.lineno)
            except SyntaxError:
                pass
        for n, line in enumerate(text.splitlines(), 1):
            if n in def_lines or not word.search(line):
                continue
            if f.suffix != ".py" and OTHER_DEF.match(line):
                defs.append(f"{rel}:L{n}  {line.strip()[:120]}")
            else:
                refs.append(f"{rel}:{n}: {line.strip()[:160]}")
    if not defs and not refs:
        return f"没找到 {name}"
    out = ["定义：", *(defs or ["（没找到定义，可能来自第三方库）"]), f"\n引用（{len(refs)} 处）："]
    out += refs[:40] + ([f"…（还有 {len(refs) - 40} 处）"] if len(refs) > 40 else [])
    return "\n".join(out)


TOOLS = [
    Tool("code_outline",
         "看代码骨架：文件或目录下每个文件的类、函数签名、行号范围、文档首行（Python 用语法树，其他语言按定义行）。"
         "了解项目结构、定位要改的函数时先用它，再用 read_file 按行号精读，比整文件读取省得多。",
         params({"path": {"type": "string", "description": "文件或目录，默认工作区根目录"}}),
         Permission.READ, code_outline),
    Tool("find_symbol",
         "找一个函数 / 类在哪里定义、被哪些地方引用（文件:行号）。改函数签名或排查调用链前用它。",
         params({"name": {"type": "string", "description": "标识符，比如 add_amount"}}, ["name"]),
         Permission.READ, find_symbol),
]
