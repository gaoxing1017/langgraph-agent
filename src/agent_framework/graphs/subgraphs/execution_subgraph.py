from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from agent_framework.core.state import AgentState
from agent_framework.edges.routers import react_router
from agent_framework.nodes.llm_node import llm_node
from agent_framework.nodes.tool_node import build_tool_node


def build_execution_subgraph(execution_tools: list[Any] | None = None) -> StateGraph:
    """构建专注于代码执行与任务执行的子图。"""
    graph = StateGraph(AgentState)
    tool_node = build_tool_node(execution_tools or [])

    graph.add_node("execution_llm", llm_node)
    graph.add_node("execution_tools", tool_node)

    graph.add_edge(START, "execution_llm")
    graph.add_conditional_edges(
        "execution_llm", react_router, {"tools": "execution_tools", "end": END}
    )
    graph.add_edge("execution_tools", "execution_llm")

    return graph
