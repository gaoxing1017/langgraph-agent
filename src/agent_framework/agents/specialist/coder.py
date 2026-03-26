from __future__ import annotations

from typing import Any

from agent_framework.agents.base_agent import BaseAgent
from agent_framework.config.settings import Settings
from agent_framework.graphs.subgraphs.execution_subgraph import build_execution_subgraph
from agent_framework.tools.registry import ToolRegistry


class CoderAgent(BaseAgent):
    """专注于代码生成与执行的专家智能体。"""

    def __init__(self, settings: Settings, tool_registry: ToolRegistry | None = None) -> None:
        super().__init__(settings)
        self._tool_registry = tool_registry or ToolRegistry()

    def build_graph(self, checkpointer: Any = None, store: Any = None, **kwargs: Any) -> None:
        code_tools = self._tool_registry.get_by_category("code")
        graph = build_execution_subgraph(execution_tools=code_tools)
        self._graph = graph.compile(checkpointer=checkpointer, store=store)
