"""ReAct（推理 + 行动）图 — 默认的单智能体图。

拓扑结构：
    START → llm → ──────────────────────── END
                ↘ (存在 tool_calls)
                  tools → llm → ...

react_router 条件边在 LLM 响应包含 tool_calls 时路由到 tools；
否则图终止。
"""

from __future__ import annotations

from functools import partial
from typing import Any

from langchain_core.runnables import RunnableConfig
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

        # 将编译时工具列表注入 llm_node，作为 configurable["tools"] 的 fallback
        node_fn = partial(_llm_node_with_tools, default_tools=self._tools)

        graph.add_node("llm", node_fn)
        graph.add_node("tools", tool_node)

        graph.add_edge(START, "llm")
        graph.add_conditional_edges("llm", react_router, {"tools": "tools", "end": END})
        graph.add_edge("tools", "llm")

        return graph


async def _llm_node_with_tools(
    state: AgentState,
    config: RunnableConfig,
    default_tools: list[Any],
) -> dict[str, Any]:
    """llm_node 的包装：当 configurable 未提供工具时，回退到编译时的默认工具列表。"""
    configurable = config.get("configurable", {})
    if not configurable.get("tools"):
        config = {**config, "configurable": {**configurable, "tools": default_tools}}
    return await llm_node(state, config)


def build_react_graph() -> StateGraph:
    """LangGraph Studio / langgraph dev 使用的无参数工厂函数。

    默认注册 tavily_search 工具，Studio 中可直接使用搜索能力。
    编程方式构建时请直接使用 ReActGraphBuilder(tools=[...])。
    """
    from agent_framework.tools.search.tavily_search import tavily_search
    return ReActGraphBuilder(tools=[tavily_search]).build()
