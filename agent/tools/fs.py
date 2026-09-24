"""工作区文件工具。所有路径都限制在工作区根目录内。"""
from __future__ import annotations

import re

from .base import Permission, Tool, ToolContext, ToolError, arg, params, safe_path

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules", ".venv", "venv"}
MAX_WRITE_CHARS = 200_000


def _read_text(path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ToolError(f"{path.name} 不是 UTF-8 文本文件")


def read_file(args: dict, ctx: ToolContext) -> str:
    path = safe_path(ctx.workspace, arg(args, "path", required=True))
    if not path.is_file():
        raise ToolError(f"文件不存在：{args['path']}")
    lines = _read_text(path).splitlines()
    start = max(int(arg(args, "start_line", 1)), 1)
    count = min(max(int(arg(args, "max_lines", 400)), 1), 2000)
    chunk = lines[start - 1:start - 1 + count]
    width = len(str(start + len(chunk)))
    body = "\n".join(f"{i:>{width}}| {line}" for i, line in enumerate(chunk, start))
    more = len(lines) - (start - 1 + len(chunk))
    tail = f"\n…（还有 {more} 行，用 start_line={start + len(chunk)} 继续读）" if more > 0 else ""
    return f"{args['path']}（共 {len(lines)} 行）\n{body}{tail}"


def list_dir(args: dict, ctx: ToolContext) -> str:
    path = safe_path(ctx.workspace, arg(args, "path", "."))
    if not path.is_dir():
        raise ToolError(f"目录不存在：{args.get('path', '.')}")
    depth = min(int(arg(args, "depth", 2)), 4)
    root = ctx.workspace.resolve()
    out: list[str] = []

    def walk(p, level):
        for child in sorted(p.iterdir(), key=lambda c: (c.is_file(), c.name)):
            if child.name in SKIP_DIRS:
                continue
            rel = child.relative_to(root).as_posix()
            out.append(("  " * level) + (rel + "/" if child.is_dir() else rel))
            if child.is_dir() and level + 1 < depth:
                walk(child, level + 1)
            if len(out) >= 300:
                return

    walk(path, 0)
    return "\n".join(out) or "（空目录）"


def search_text(args: dict, ctx: ToolContext) -> str:
    pattern = arg(args, "pattern", required=True)
    base = safe_path(ctx.workspace, arg(args, "path", "."))
    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error:
        rx = re.compile(re.escape(pattern), re.IGNORECASE)
    hits: list[str] = []
    root = ctx.workspace.resolve()
    files = [base] if base.is_file() else sorted(base.rglob("*"))
    for f in files:
        if not f.is_file() or any(part in SKIP_DIRS for part in f.relative_to(root).parts):
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                hits.append(f"{f.relative_to(root).as_posix()}:{n}: {line.strip()[:200]}")
                if len(hits) >= 60:
                    return "\n".join(hits) + "\n…（结果过多，只显示前 60 条）"
    return "\n".join(hits) or "没有匹配"


def write_file(args: dict, ctx: ToolContext) -> str:
    path = safe_path(ctx.workspace, arg(args, "path", required=True))
    content = arg(args, "content", "")
    if not isinstance(content, str):
        raise ToolError("content 必须是字符串")
    if len(content) > MAX_WRITE_CHARS:
        raise ToolError(f"内容过长（{len(content)} 字），请拆分")
    if any(part in {".git"} for part in path.parts):
        raise ToolError("不允许直接写 .git 目录")
    existed = path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return f"{'覆盖' if existed else '新建'} {args['path']}（{len(content.splitlines())} 行）"


def edit_file(args: dict, ctx: ToolContext) -> str:
    path = safe_path(ctx.workspace, arg(args, "path", required=True))
    old = arg(args, "old", required=True)
    new = arg(args, "new", "")
    if not path.is_file():
        raise ToolError(f"文件不存在：{args['path']}")
    text = _read_text(path)
    count = text.count(old)
    if count == 0:
        raise ToolError("没找到 old 文本（要求与文件内容逐字一致，含缩进）。先用 read_file 确认原文")
    if count > 1:
        raise ToolError(f"old 文本出现了 {count} 次，请带上更多上下文使其唯一")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
    return f"已修改 {args['path']}：替换 {len(old.splitlines()) or 1} 行为 {len(new.splitlines()) or 0} 行"


TOOLS = [
    Tool("read_file", "读取工作区内的文本文件（带行号）。大文件用 start_line / max_lines 分段读。",
         params({"path": {"type": "string", "description": "相对工作区根目录的路径"},
                 "start_line": {"type": "integer", "description": "从第几行开始，默认 1"},
                 "max_lines": {"type": "integer", "description": "最多读几行，默认 400"}}, ["path"]),
         Permission.READ, read_file),
    Tool("list_dir", "列出工作区目录结构（跳过 .git 等）。",
         params({"path": {"type": "string", "description": "相对路径，默认根目录"},
                 "depth": {"type": "integer", "description": "展开层数，默认 2，最多 4"}}),
         Permission.READ, list_dir),
    Tool("search_text", "在工作区文件里搜索文本或正则，返回 文件:行号: 内容。",
         params({"pattern": {"type": "string"}, "path": {"type": "string", "description": "限定目录或文件，默认全部"}},
                ["pattern"]),
         Permission.READ, search_text),
    Tool("write_file", "新建或整体覆盖一个文件。只改局部时优先用 edit_file。",
         params({"path": {"type": "string"}, "content": {"type": "string", "description": "完整文件内容"}},
                ["path", "content"]),
         Permission.WRITE_LOCAL, write_file),
    Tool("edit_file", "把文件中唯一出现的一段文本 old 替换成 new（逐字匹配，含缩进）。",
         params({"path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}},
                ["path", "old", "new"]),
         Permission.WRITE_LOCAL, edit_file),
]
