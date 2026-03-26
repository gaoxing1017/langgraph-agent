from __future__ import annotations

from typing import Any

from agent_framework.agents.base_agent import BaseAgent
from agent_framework.config.settings import Settings
from agent_framework.graphs.supervisor_graph import build_supervisor_graph


class CoordinatorAgent(BaseAgent):
    """多智能体协调器：supervisor 将任务委派给专家子图。"""

    def __init__(
        self,
        settings: Settings,
        specialist_graphs: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(settings)
        self._specialist_graphs = specialist_graphs or {}

    def build_graph(self, checkpointer: Any = None, store: Any = None, **kwargs: Any) -> None:
        graph = build_supervisor_graph(specialist_graphs=self._specialist_graphs)
        self._graph = graph.compile(checkpointer=checkpointer, store=store)
