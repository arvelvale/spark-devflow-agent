"""agent 自身状态相关的工具：维护工作记忆、取回压缩原文、查长期记忆、读技能参考文档。"""
from __future__ import annotations

import json

from .base import Permission, Tool, ToolContext, ToolError, arg, params, safe_path


def update_plan(args: dict, ctx: ToolContext) -> str:
    ctx.working.update(
        goal=arg(args, "goal"),
        constraints=args.get("constraints"),
        todo=args.get("todo"),
        evidence=args.get("evidence"),
    )
    return "工作记忆已更新：\n" + ctx.working.render()


def read_archive(args: dict, ctx: ToolContext) -> str:
    if ctx.archive is None:
        raise ToolError("本会话没有归档")
    rid = arg(args, "id", required=True)
    payload = ctx.archive.get(rid)
    if payload is None:
        raise ToolError(f"找不到归档 {rid}")
    if isinstance(payload, list) and payload and isinstance(payload[0], dict) and "cid" in payload[0]:
        # 阶段 A 逐调用裁剪的归档：[{cid, tool, arguments, result}]
        want = str(arg(args, "call", "") or "")
        rows = [r for r in payload if not want or r["cid"] == want]
        return "\n\n".join(f"[{r['cid']}] {r['tool']}({r['arguments']})\n{r['result']}" for r in rows)[:12000]
    if isinstance(payload, list):  # 一整轮消息
        from ..context import render_messages
        return render_messages(payload, 12000)
    if isinstance(payload, dict) and "content" in payload:
        return payload["content"]
    return json.dumps(payload, ensure_ascii=False)[:12000]


def recall_memory(args: dict, ctx: ToolContext) -> str:
    if ctx.memory is None:
        raise ToolError("记忆库未启用")
    hits = ctx.memory.recall(arg(args, "query", required=True), min(int(arg(args, "k", 5)), 10))
    # 这里只返回可共享的记忆：工具结果可能进入云端模型的上下文
    lines = [m.line() for m, _ in hits if m.privacy != "local"]
    return "\n".join(lines) or "没有相关记忆"


def read_skill_file(args: dict, ctx: ToolContext) -> str:
    skill = arg(args, "skill", required=True)
    base = ctx.skill_dirs.get(skill)
    if base is None:
        raise ToolError(f"技能 {skill} 本轮未加载，不能读它的文件")
    path = safe_path(base, arg(args, "path", required=True))
    if not path.is_file():
        raise ToolError(f"{skill} 下没有 {args['path']}")
    return path.read_text(encoding="utf-8")


TOOLS = [
    Tool("update_plan",
         "维护工作记忆（目标、约束、待办、关键证据）。它不会被上下文压缩丢掉。多步任务开始时写下目标和待办，"
         "每完成一步把对应待办标记 done。todo 和 constraints 传入即整体替换；evidence 追加。",
         params({
             "goal": {"type": "string"},
             "constraints": {"type": "array", "items": {"type": "string"}},
             "todo": {"type": "array", "items": {"type": "object", "properties": {
                 "item": {"type": "string"}, "done": {"type": "boolean"}}, "required": ["item"]}},
             "evidence": {"type": "array", "items": {"type": "string"},
                          "description": "关键证据：文件路径、命令、测试结果摘要"},
         }),
         Permission.READ, update_plan),
    Tool("read_archive", "取回被压缩掉的对话原文或工具结果（编号见系统提示里的摘要或 [已压缩] 标记）。"
         "逐调用裁剪的归档可以用 call 只取其中一个调用（如 t3）。",
         params({"id": {"type": "string"}, "call": {"type": "string", "description": "可选：只取某个调用，如 t3"}}, ["id"]),
         Permission.READ, read_archive),
    Tool("recall_memory", "按关键词检索长期记忆（之前会话里记下的事实、约定、决定）。",
         params({"query": {"type": "string"}, "k": {"type": "integer"}}, ["query"]), Permission.READ, recall_memory),
    Tool("read_skill_file", "读取本轮已加载技能目录下的参考文件（如 references/output-format.md）。",
         params({"skill": {"type": "string"}, "path": {"type": "string"}}, ["skill", "path"]),
         Permission.READ, read_skill_file),
]
