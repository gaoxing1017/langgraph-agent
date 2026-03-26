"""ToolRegistry：所有可用工具的中央目录。

工具注册时携带类别标签，专家智能体用它来
请求仅与自身领域相关的工具（如 researcher 使用 "search"，
coder 使用 "code"）。

get_enabled() 方法实现每次调用的白名单机制：
空列表表示启用所有工具；非空列表作为允许列表使用。
"""

from __future__ import annotations

import structlog
from langchain_core.tools import BaseTool

logger = structlog.get_logger(__name__)


class ToolRegistry:
    """所有工具的中央 registry，支持动态发现和类别过滤。"""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._categories: dict[str, list[str]] = {}

    def register(self, tool: BaseTool, category: str = "general") -> None:
        self._tools[tool.name] = tool
        self._categories.setdefault(category, []).append(tool.name)
        logger.debug("工具已注册", name=tool.name, category=category)

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise KeyError(f"工具未找到：{name}")
        return self._tools[name]

    def get_enabled(self, names: list[str]) -> list[BaseTool]:
        """返回白名单中的工具。空列表表示返回所有工具。"""
        if not names:
            return list(self._tools.values())
        return [self._tools[n] for n in names if n in self._tools]

    def get_by_category(self, category: str) -> list[BaseTool]:
        names = self._categories.get(category, [])
        return [self._tools[n] for n in names if n in self._tools]

    def as_langchain_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())
