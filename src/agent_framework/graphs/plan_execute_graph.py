"""Plan-and-Execute 图。

拓扑结构：
    START → planner → execute_step → llm → tools → execute_step → ...
                                          ↘ END  （无更多步骤/发生错误）

planner 通过结构化输出生成类型化的 Plan（list[str]）。
execute_step 逐次将一个步骤注入为 HumanMessage。
llm+tools 处理完该步骤后，plan_execute_router 检查是否还有更多步骤。
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from agent_framework.core.state import AgentState, InputState, OutputState
from agent_framework.edges.routers import plan_execute_router, react_router
from agent_framework.graphs.base_graph import BaseGraphBuilder
from agent_framework.nodes.executor_node import executor_node
from agent_framework.nodes.llm_node import llm_node
from agent_framework.nodes.planner_node import planner_node
from agent_framework.nodes.tool_node import build_tool_node


class PlanExecuteGraphBuilder(BaseGraphBuilder):
    def __init__(self, tools: list[Any] | None = None) -> None:
        self._tools = tools or []

    def build(self) -> StateGraph:
        """组装 Plan-Execute 图，包含 planner、executor、llm 和工具节点。"""
        graph = StateGraph(AgentState, input=InputState, output=OutputState)

        tool_node = build_tool_node(self._tools)

        graph.add_node("planner", planner_node)
        graph.add_node("execute_step", executor_node)
        graph.add_node("llm", llm_node)
        graph.add_node("tools", tool_node)

        graph.add_edge(START, "planner")
        graph.add_edge("planner", "execute_step")
        graph.add_conditional_edges(
            "execute_step",
            plan_execute_router,
            {"execute": "llm", "end": END},
        )
        graph.add_conditional_edges("llm", react_router, {"tools": "tools", "end": "execute_step"})
        graph.add_edge("tools", "execute_step")

        return graph


def build_plan_execute_graph() -> StateGraph:
    """LangGraph Studio / langgraph dev 使用的无参数工厂函数。

    工具列表通过 AgentContext（configurable）在运行时注入，
    工厂函数本身不接受额外参数，以符合 LangGraph Server 的 factory 签名规范。
    如需编程方式构建，请直接使用 PlanExecuteGraphBuilder。
    """
    return PlanExecuteGraphBuilder().build()
