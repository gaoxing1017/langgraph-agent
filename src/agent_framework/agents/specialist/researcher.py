from __future__ import annotations

from typing import Any

from agent_framework.agents.base_agent import BaseAgent
from agent_framework.config.settings import Settings
from agent_framework.graphs.subgraphs.research_subgraph import build_research_subgraph
from agent_framework.tools.registry import ToolRegistry


class ResearcherAgent(BaseAgent):
    """专注于网络调研与信息收集的专家智能体。"""

    def __init__(self, settings: Settings, tool_registry: ToolRegistry | None = None) -> None:
        super().__init__(settings)
        self._tool_registry = tool_registry or ToolRegistry()

    def build_graph(self, checkpointer: Any = None, store: Any = None, **kwargs: Any) -> None:
        search_tools = self._tool_registry.get_by_category("search")
        graph = build_research_subgraph(search_tools=search_tools)
        self._graph = graph.compile(checkpointer=checkpointer, store=store)
