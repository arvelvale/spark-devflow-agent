"""工具注册表、权限级别、结果截断与路径沙箱。"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:  # 只做类型标注，避免循环导入
    from ..context import ArchiveStore, WorkingState
    from ..memory import MemoryStore
    from .linear import LinearClient


class Permission(str, Enum):
    READ = "read"                # 只读：默认可用
    WRITE_LOCAL = "write_local"  # 本地写：需技能白名单 + JEV 门控
    EXTERNAL = "external"        # 外部可见写：需技能白名单 + 一律人工确认


class ToolError(Exception):
    """工具执行失败（给模型看的错误信息，不含内部堆栈）。"""


@dataclass
class ToolContext:
    workspace: Path
    vault: Path
    working: "WorkingState"
    archive: "ArchiveStore | None" = None
    memory: "MemoryStore | None" = None
    linear: "LinearClient | None" = None
    skill_dirs: dict[str, Path] = field(default_factory=dict)  # 本轮已命中技能 → 目录
    skill_scripts: dict[str, dict] = field(default_factory=dict)  # 本轮已命中技能 → {脚本名: SkillScript}
    shell_allow: tuple[str, ...] = ()


Handler = Callable[[dict, ToolContext], str]


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    permission: Permission
    handler: Handler
    max_chars: int | None = None   # None = 用全局上限

    def schema(self) -> dict:
        return {"type": "function", "function": {
            "name": self.name, "description": self.description, "parameters": self.parameters}}


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"工具重名：{tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools)

    def by_permission(self, perm: Permission) -> list[str]:
        return [t.name for t in self._tools.values() if t.permission == perm]

    def schemas(self, names: list[str]) -> list[dict]:
        return [self._tools[n].schema() for n in names if n in self._tools]


def params(properties: dict[str, dict], required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": properties, "required": required or []}


def truncate(text: str, limit: int) -> tuple[str, bool]:
    """超长结果保留头尾（报错信息常在末尾），中间标注截掉了多少。"""
    if len(text) <= limit:
        return text, False
    head = int(limit * 0.7)
    tail = limit - head
    cut = len(text) - head - tail
    return f"{text[:head]}\n…[中间省略 {cut} 字]…\n{text[-tail:]}", True


def safe_path(root: Path, rel: str) -> Path:
    """把相对路径解析到 root 内；越界（../、绝对路径、符号链接逃逸）一律拒绝。"""
    if not isinstance(rel, str) or not rel.strip():
        rel = "."
    root_resolved = root.resolve()
    candidate = (root_resolved / rel.strip().lstrip("/\\")).resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise ToolError(f"路径越界：{rel}（只能访问 {root.name}/ 内的文件）")
    return candidate


def arg(args: dict, name: str, default: Any = None, *, required: bool = False) -> Any:
    if name not in args or args[name] in (None, ""):
        if required:
            raise ToolError(f"缺少参数 {name}")
        return default
    return args[name]


# 子进程只拿到这些环境变量：工作区代码（测试、技能脚本）不该看到任何 API Key 和代理设置
_ENV_KEEP = ("PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL",
             "COMSPEC", "PATHEXT")


def subprocess_env(**extra: str) -> dict[str, str]:
    env = {k: os.environ[k] for k in _ENV_KEEP if k in os.environ}
    env.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    env.update(extra)
    return env


PYTHON = sys.executable
