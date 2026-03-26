from __future__ import annotations

from typing import Any

from agent_framework.agents.base_agent import BaseAgent
from agent_framework.config.settings import Settings
from agent_framework.graphs.react_graph import build_react_graph
from agent_framework.tools.registry import ToolRegistry


class AnalystAgent(BaseAgent):
    """专注于数据分析与推理的专家智能体。"""

    SYSTEM_PROMPT = (
        "You are a data analyst. Analyze the provided data carefully, "
        "identify patterns, and provide clear, evidence-based conclusions."
    )

    def __init__(self, settings: Settings, tool_registry: ToolRegistry | None = None) -> None:
        super().__init__(settings)
        self._tool_registry = tool_registry or ToolRegistry()

    def build_graph(self, checkpointer: Any = None, store: Any = None, **kwargs: Any) -> None:
        analysis_tools = self._tool_registry.get_by_category("analysis")
        graph = build_react_graph(tools=analysis_tools)
        self._graph = graph.compile(checkpointer=checkpointer, store=store)
