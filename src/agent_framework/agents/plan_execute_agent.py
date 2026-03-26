from __future__ import annotations

from typing import Any

from agent_framework.agents.base_agent import BaseAgent
from agent_framework.config.settings import Settings
from agent_framework.graphs.plan_execute_graph import build_plan_execute_graph
from agent_framework.tools.registry import ToolRegistry


class PlanExecuteAgent(BaseAgent):
    """Plan-and-Execute 智能体：先生成结构化计划，再逐步执行。"""

    def __init__(self, settings: Settings, tool_registry: ToolRegistry | None = None) -> None:
        super().__init__(settings)
        self._tool_registry = tool_registry or ToolRegistry()

    def build_graph(self, checkpointer: Any = None, store: Any = None, **kwargs: Any) -> None:
        tools = self._tool_registry.as_langchain_tools()
        graph = build_plan_execute_graph(tools=tools)
        self._graph = graph.compile(checkpointer=checkpointer, store=store)
