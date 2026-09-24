"""Git 工具。只读操作默认可用；commit / 建分支属于本地写。不提供 push（外部可见，演示范围外）。"""
from __future__ import annotations

import re
import subprocess

from .base import Permission, Tool, ToolContext, ToolError, arg, params

AGENT_IDENTITY = ["-c", "user.name=dgx-agent", "-c", "user.email=dgx-agent@localhost"]
SAFE_REF = re.compile(r"^[\w./~^@{}:-]+$")


def _git(ctx: ToolContext, *argv: str, timeout: int = 30) -> str:
    try:
        proc = subprocess.run(
            ["git", *argv], cwd=ctx.workspace, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except FileNotFoundError:
        raise ToolError("节点上没有 git")
    except subprocess.TimeoutExpired:
        raise ToolError(f"git {argv[0]} 超时")
    if proc.returncode != 0:
        raise ToolError(f"git {argv[0]} 失败：{(proc.stderr or proc.stdout).strip()[:500]}")
    return proc.stdout


def _ref(value: str | None) -> str | None:
    if value is None:
        return None
    if not SAFE_REF.match(value) or value.startswith("-"):
        raise ToolError(f"非法的引用：{value}")
    return value


def git_status(args: dict, ctx: ToolContext) -> str:
    branch = _git(ctx, "branch", "--show-current").strip() or "（游离 HEAD）"
    status = _git(ctx, "status", "--short").strip()
    return f"当前分支：{branch}\n{status or '工作区干净'}"


def git_log(args: dict, ctx: ToolContext) -> str:
    n = min(max(int(arg(args, "n", 10)), 1), 50)
    argv = ["log", f"-{n}", "--date=format:%Y-%m-%d %H:%M", "--pretty=format:%h %ad %an  %s"]
    since = arg(args, "since")
    if since:
        argv.append(f"--since={since}")
    if arg(args, "stat", False):
        argv.append("--stat")
    return _git(ctx, *argv).strip() or "没有提交"


def git_diff(args: dict, ctx: ToolContext) -> str:
    target = _ref(arg(args, "target"))
    argv = ["diff"]
    if arg(args, "staged", False):
        argv.append("--cached")
    if target:
        argv.append(target)
    path = arg(args, "path")
    if path:
        argv += ["--", path]
    out = _git(ctx, *argv)
    return out.strip() or "没有差异"


def git_show(args: dict, ctx: ToolContext) -> str:
    ref = _ref(arg(args, "ref", "HEAD"))
    return _git(ctx, "show", "--stat", "--patch", ref).strip()


def git_commit(args: dict, ctx: ToolContext) -> str:
    message = arg(args, "message", required=True)
    paths = arg(args, "paths") or []
    if isinstance(paths, str):
        paths = [paths]
    if paths:
        _git(ctx, "add", "--", *paths)
    else:
        _git(ctx, "add", "-A")
    if not _git(ctx, "diff", "--cached", "--name-only").strip():
        raise ToolError("没有可提交的改动")
    _git(ctx, *AGENT_IDENTITY, "commit", "-m", message)
    return _git(ctx, "log", "-1", "--stat", "--pretty=format:已提交 %h %s").strip()


def git_branch(args: dict, ctx: ToolContext) -> str:
    name = _ref(arg(args, "name", required=True))
    _git(ctx, "switch", "-c", name)
    return f"已创建并切换到分支 {name}"


TOOLS = [
    Tool("git_status", "查看当前分支和未提交的改动。", params({}), Permission.READ, git_status),
    Tool("git_log", "查看最近的提交记录。",
         params({"n": {"type": "integer", "description": "条数，默认 10"},
                 "since": {"type": "string", "description": "起始时间，如 '2026-09-23' 或 'yesterday'"},
                 "stat": {"type": "boolean", "description": "是否附带每个提交改了哪些文件"}}),
         Permission.READ, git_log),
    Tool("git_diff", "查看改动。默认是未暂存的工作区改动；target 可填提交或区间（如 HEAD~3..HEAD）。",
         params({"target": {"type": "string"}, "staged": {"type": "boolean"}, "path": {"type": "string"}}),
         Permission.READ, git_diff),
    Tool("git_show", "查看某个提交的说明和改动。", params({"ref": {"type": "string", "description": "默认 HEAD"}}),
         Permission.READ, git_show),
    Tool("git_commit", "暂存并提交改动。paths 为空时提交全部改动。提交说明用中文，一句话说清做了什么。",
         params({"message": {"type": "string"}, "paths": {"type": "array", "items": {"type": "string"}}}, ["message"]),
         Permission.WRITE_LOCAL, git_commit),
    Tool("git_branch", "从当前位置新建分支并切换过去。", params({"name": {"type": "string"}}, ["name"]),
         Permission.WRITE_LOCAL, git_branch),
]
