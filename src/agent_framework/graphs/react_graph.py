"""ReAct（推理 + 行动）图 — 默认的单智能体图。

拓扑结构：
    START → llm → ──────────────────────── END
                ↘ (存在 tool_calls)
                  tools → llm → ...

react_router 条件边在 LLM 响应包含 tool_calls 时路由到 tools；
否则图终止。
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from agent_framework.core.state import AgentState, InputState, OutputState
from agent_framework.edges.routers import react_router
from agent_framework.graphs.base_graph import BaseGraphBuilder
from agent_framework.nodes.llm_node import llm_node
from agent_framework.nodes.tool_node import build_tool_node


class ReActGraphBuilder(BaseGraphBuilder):
    def __init__(self, tools: list[Any] | None = None) -> None:
        self._tools = tools or []

    def build(self) -> StateGraph:
        """组装 ReAct 图：llm 节点、ToolNode 以及条件路由。"""
        graph = StateGraph(AgentState, input=InputState, output=OutputState)

        tool_node = build_tool_node(self._tools)

        graph.add_node("llm", llm_node)
        graph.add_node("tools", tool_node)

        graph.add_edge(START, "llm")
        graph.add_conditional_edges("llm", react_router, {"tools": "tools", "end": END})
        graph.add_edge("tools", "llm")

        return graph


def build_react_graph() -> StateGraph:
    """LangGraph Studio / langgraph dev 使用的无参数工厂函数。

    工具列表通过 AgentContext（configurable）在运行时注入，
    工厂函数本身不接受额外参数，以符合 LangGraph Server 的 factory 签名规范。
    如需编程方式构建，请直接使用 ReActGraphBuilder。
    """
    return ReActGraphBuilder().build()
