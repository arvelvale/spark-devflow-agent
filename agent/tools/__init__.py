"""工具注册表。新增工具：在对应模块的 TOOLS 里加一项即可。"""
from __future__ import annotations

from . import fs, git, internal, linear, obsidian, shell
from .base import Permission, Tool, ToolContext, ToolError, ToolRegistry, truncate


def build_registry() -> ToolRegistry:
    reg = ToolRegistry()
    for module in (fs, git, shell, obsidian, linear, internal):
        for tool in module.TOOLS:
            reg.register(tool)
    return reg


__all__ = ["Permission", "Tool", "ToolContext", "ToolError", "ToolRegistry", "build_registry", "truncate"]
