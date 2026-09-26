"""技能脚本：技能目录 scripts/ 下、在 frontmatter 里声明过的 Python 脚本。

为什么要脚本：确定性的活（收集提交和纪要、跑测试并只摘出失败项）交给模型一步步调工具，
每一步都要重发整段上下文；写成脚本就是一次调用、一段精简输出。
边界：
- 只能跑本轮已命中技能里声明过的脚本；参数是字符串列表，不经过 shell
- 权限按声明走：read 直接运行，write_local 和 run_command 一样过 JEV 门控（kernel 里解析）
- 子进程拿不到任何 API Key（subprocess_env），工作目录是工作区根目录，120 秒超时
"""
from __future__ import annotations

import subprocess

from .base import PYTHON, Permission, Tool, ToolContext, ToolError, arg, params, subprocess_env

TIMEOUT = 120


def run_skill_script(args: dict, ctx: ToolContext) -> str:
    skill = str(arg(args, "skill", required=True))
    script = str(arg(args, "script", required=True))
    spec = ctx.skill_scripts.get(skill, {}).get(script)
    if spec is None:
        have = [f"{k}/{n}" for k, v in ctx.skill_scripts.items() for n in v]
        raise ToolError(f"{skill} 没有声明脚本 {script}。本轮可用：{', '.join(have) or '无'}")
    argv = arg(args, "args", []) or []
    if not isinstance(argv, list) or len(argv) > 20 or any(not isinstance(a, (str, int, float)) for a in argv):
        raise ToolError("args 必须是字符串列表（最多 20 个）")
    argv = [str(a) for a in argv]
    if any(len(a) > 500 for a in argv):
        raise ToolError("单个参数太长")
    base = ctx.skill_dirs[skill]
    env = subprocess_env(SKILL_DIR=str(base), WORKSPACE=str(ctx.workspace), VAULT=str(ctx.vault))
    try:
        proc = subprocess.run([PYTHON, str(base / "scripts" / script), *argv], cwd=ctx.workspace, env=env,
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        raise ToolError(f"脚本超时（{TIMEOUT}s）")
    out = proc.stdout.strip()
    err = proc.stderr.strip()
    if proc.returncode != 0:
        return f"退出码 {proc.returncode}\n{out}\n{err[-2000:]}".strip()
    return out or "（脚本没有输出）"


TOOLS = [
    Tool("run_skill_script",
         "运行本轮已加载技能自带的脚本（技能说明里列出的 scripts）。确定性的收集、统计、跑测试优先用它，一次拿到精简结果。",
         params({"skill": {"type": "string", "description": "技能名，如 standup-brief"},
                 "script": {"type": "string", "description": "脚本名，如 collect.py"},
                 "args": {"type": "array", "items": {"type": "string"}, "description": "命令行参数，可省略"}},
                ["skill", "script"]),
         Permission.WRITE_LOCAL, run_skill_script),  # 实际权限按脚本声明解析，见 Agent._resolve_tool
]
