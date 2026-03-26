from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from agent_framework.core.state import AgentState
from agent_framework.edges.routers import react_router
from agent_framework.nodes.llm_node import llm_node
from agent_framework.nodes.tool_node import build_tool_node


def build_research_subgraph(search_tools: list[Any] | None = None) -> StateGraph:
    """构建专注于网络调研任务的子图。"""
    graph = StateGraph(AgentState)
    tool_node = build_tool_node(search_tools or [])

    graph.add_node("research_llm", llm_node)
    graph.add_node("research_tools", tool_node)

    graph.add_edge(START, "research_llm")
    graph.add_conditional_edges(
        "research_llm", react_router, {"tools": "research_tools", "end": END}
    )
    graph.add_edge("research_tools", "research_llm")

    return graph
