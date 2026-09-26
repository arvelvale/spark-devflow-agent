"""受限命令执行：只允许白名单前缀（测试、编译检查、运行演示项目），不经过 shell。"""
from __future__ import annotations

import shlex
import subprocess
import sys

from .base import Permission, Tool, ToolContext, ToolError, arg, params, subprocess_env

FORBIDDEN_CHARS = set(";|&><`$\n")


def run_command(args: dict, ctx: ToolContext) -> str:
    command = str(arg(args, "command", required=True)).strip()
    if any(ch in FORBIDDEN_CHARS for ch in command):
        raise ToolError("命令里不能有 ; | & > < ` $ 或换行（不经过 shell，无法管道或重定向）。"
                        "需要特定数据或环境变量的验证，写成测试（测试里可以建临时文件、设环境变量）")
    allowed = next((p for p in ctx.shell_allow if command == p or command.startswith(p + " ")), None)
    if not allowed:
        raise ToolError("命令不在白名单内。允许的前缀：" + " / ".join(ctx.shell_allow)
                        + "。要验证某个行为，把它写成测试再跑测试，不要在命令行手工造数据")
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        raise ToolError(f"命令解析失败：{exc}")
    if argv[0] in {"python", "python3"}:
        argv[0] = sys.executable  # 节点上可能只有 python3
    timeout = min(int(arg(args, "timeout", 120)), 300)
    try:
        proc = subprocess.run(argv, cwd=ctx.workspace, capture_output=True, text=True, env=subprocess_env(),
                              encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ToolError(f"命令超时（{timeout}s）")
    output = (proc.stdout + ("\n" + proc.stderr if proc.stderr.strip() else "")).strip()
    return f"退出码 {proc.returncode}\n{output or '（无输出）'}"


TOOLS = [
    Tool("run_command",
         "在工作区根目录运行白名单内的命令（如 python -m pytest -q）。返回退出码和输出。不支持管道、重定向。",
         params({"command": {"type": "string"}, "timeout": {"type": "integer", "description": "秒，默认 120"}},
                ["command"]),
         Permission.WRITE_LOCAL, run_command),
]
