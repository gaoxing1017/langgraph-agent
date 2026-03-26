from __future__ import annotations

from typing import Any

from langgraph.prebuilt import ToolNode as _ToolNode


def build_tool_node(tools: list[Any]) -> _ToolNode:
    """根据工具列表构建 ToolNode。

    ToolNode 通过 asyncio.gather 并行执行工具，
    并返回 ToolMessage 结果（包括错误消息），不会抛出异常。
    """
    return _ToolNode(tools)
