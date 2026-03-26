"""Supervisor（多智能体协调器）图。

拓扑结构：
    START → supervisor → researcher → supervisor
                       → coder      → supervisor
                       → analyst    → supervisor
                       → END

supervisor 是一个标准 LLM 节点，其 tool_calls 指定目标专家。
每个专家是一个以节点形式注册的已编译子图。
专家完成任务后始终回到 supervisor。
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import create_react_agent

from agent_framework.core.state import AgentState, InputState, OutputState
from agent_framework.graphs.base_graph import BaseGraphBuilder
from agent_framework.nodes.llm_node import llm_node


class SupervisorGraphBuilder(BaseGraphBuilder):
    def __init__(
        self,
        specialist_graphs: dict[str, Any] | None = None,
        supervisor_tools: list[Any] | None = None,
    ) -> None:
        self._specialists = specialist_graphs or {}
        self._supervisor_tools = supervisor_tools or []

    def build(self) -> StateGraph:
        """组装带有动态专家路由的 supervisor 图。"""
        graph = StateGraph(AgentState, input=InputState, output=OutputState)

        # Supervisor 节点
        graph.add_node("supervisor", llm_node)

        # 将专家子图注册为节点
        for name, subgraph in self._specialists.items():
            graph.add_node(name, subgraph)

        def supervisor_router(state: AgentState) -> str:
            messages = state.get("messages", [])
            if not messages:
                return END
            last = messages[-1]
            tool_calls = getattr(last, "tool_calls", [])
            if tool_calls:
                # tool_calls[0]["name"] 必须匹配 self._specialists 中的某个键；
                # 未识别的名称直接路由到 END。
                target = tool_calls[0].get("name", END)
                if target in self._specialists:
                    return target
            return END

        graph.add_edge(START, "supervisor")
        # "__end__" 是 LangGraph 内部哨兵值；END 常量解析为此值。
        targets = {name: name for name in self._specialists}
        targets["__end__"] = END
        graph.add_conditional_edges("supervisor", supervisor_router, targets)

        for name in self._specialists:
            graph.add_edge(name, "supervisor")

        return graph


def build_supervisor_graph() -> StateGraph:
    """LangGraph Studio / langgraph dev 使用的无参数工厂函数。

    专家子图和工具列表在运行时通过 AgentContext（configurable）传入，
    工厂函数本身不接受额外参数，以符合 LangGraph Server 的 factory 签名规范。
    如需在代码中以编程方式构建，请直接使用 SupervisorGraphBuilder。
    """
    return SupervisorGraphBuilder().build()
