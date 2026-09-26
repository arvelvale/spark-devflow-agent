"""delegate：把独立的调查任务派给只读子 agent 并行跑，只收回结论（实现见 agent/subagents.py）。"""
from __future__ import annotations

from .base import Permission, Tool, ToolContext, ToolError, arg, params

MAX_TASKS = 4


def delegate(args: dict, ctx: ToolContext) -> str:
    if ctx.delegate is None:
        raise ToolError("当前环境不支持派发子助手")
    tasks = arg(args, "tasks", required=True)
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= MAX_TASKS:
        raise ToolError(f"tasks 必须是 1–{MAX_TASKS} 个任务的列表")
    clean = []
    for t in tasks:
        if not isinstance(t, dict):
            raise ToolError("每个任务是 {description, prompt}")
        desc = " ".join(str(t.get("description", "")).split())[:40]
        prompt = str(t.get("prompt", "")).strip()
        if not desc or len(prompt) < 10:
            raise ToolError("每个任务都要有简短的 description 和完整的 prompt（子助手看不到对话，背景要写全）")
        clean.append({"description": desc, "prompt": prompt[:4000]})
    return ctx.delegate(clean)


TOOLS = [
    Tool("delegate",
         "派只读的探索子助手去调查，可一次派 1–4 个并行。子助手有独立上下文，只把结论（≤400 字，带文件行号等证据）交回来，"
         "中间读过的文件不会进你的上下文。适合：要读很多文件才能回答的问题、几个互不相关的问题同时查。"
         "不适合：一两个工具调用就能查到的事（自己查更省），以及任何需要改文件的事（子助手不能写）。",
         params({"tasks": {"type": "array", "items": {"type": "object", "properties": {
             "description": {"type": "string", "description": "3–10 个字的任务名，如「查金额计算路径」"},
             "prompt": {"type": "string", "description": "完整任务：要回答什么、从哪里查、结论要包含什么。子助手看不到对话，背景写全"},
         }, "required": ["description", "prompt"]}}}, ["tasks"]),
         Permission.READ, delegate),
]
