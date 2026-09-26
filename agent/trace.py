"""决策轨迹：每个结构化决策一行 JSON。格式契约见 docs/接口/03-决策轨迹格式.md。"""
from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable

TRACE_VERSION = 1

EVENT_TYPES = {
    "turn.start", "skill.select", "route.model", "route.escalate", "memory.recall",
    "llm.call", "tool.gate", "tool.call", "context.compress", "memory.write",
    "turn.end", "error",
    "subagent.start", "subagent.end",  # 2026-09-26 新增（只增不改）
    "guard.drift",                     # 2026-09-26 新增：连续跑偏提醒
}

REQUIRED = ("v", "ts", "session", "turn", "seq", "type", "data")
LONG_FIELD = 500


def shorten(value, limit: int = LONG_FIELD):
    """轨迹里的长字段截断成"前 200 字…[共 N 字]"（接口约定第 2 条）。"""
    if isinstance(value, str) and len(value) > limit:
        return value[:200] + f"…[共 {len(value)} 字]"
    if isinstance(value, dict):
        return {k: shorten(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [shorten(v, limit) for v in value]
    return value


def validate_event(event: dict) -> list[str]:
    """返回问题列表，空列表表示合法。"""
    problems = [f"缺少字段 {k}" for k in REQUIRED if k not in event]
    if event.get("type") not in EVENT_TYPES:
        problems.append(f"未知事件类型 {event.get('type')}")
    if not isinstance(event.get("data"), dict):
        problems.append("data 必须是对象")
    return problems


class Trace:
    def __init__(self, session: str, path: Path | None = None):
        self.session = session
        self.path = path
        self.turn = 0
        self._seq = 0
        self._lock = threading.Lock()
        self._listeners: list[Callable[[dict], None]] = []
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)

    def subscribe(self, fn: Callable[[dict], None]) -> None:
        self._listeners.append(fn)

    def emit(
        self,
        type_: str,
        data: dict,
        *,
        latency_ms: float | None = None,
        provider: str | None = None,
        model: str | None = None,
        usage: dict | None = None,
        fallback: bool | None = None,
    ) -> dict:
        assert type_ in EVENT_TYPES, type_
        with self._lock:
            self._seq += 1
            event = {
                "v": TRACE_VERSION,
                "ts": datetime.now().astimezone().isoformat(timespec="milliseconds"),
                "session": self.session,
                "turn": self.turn,
                "seq": self._seq,
                "type": type_,
            }
            if latency_ms is not None:
                event["latency_ms"] = round(latency_ms)
            if provider:
                event["provider"] = provider
            if model:
                event["model"] = model
            if usage:
                event["usage"] = {"input_tokens": int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0),
                                  "output_tokens": int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)}
            if fallback is not None:
                event["fallback"] = fallback
            event["data"] = shorten(data)
            if self.path:
                with self.path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        for fn in self._listeners:
            try:
                fn(event)
            except Exception:  # 监听方（面板、CLI 打印）出错不能影响 agent
                pass
        return event
