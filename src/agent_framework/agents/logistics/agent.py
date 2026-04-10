from __future__ import annotations

"""物流供应链企业一级协调器 Agent。

职责：
- 构建并编译 LogisticsOrchestratorGraph
- 将 Dify 注册表注入 configurable，供 dispatch_node 使用
- 提供统一的 run() 入口，支持同步结果与流式事件两种模式
"""

from typing import Any

import structlog
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from agent_framework.agents.base_agent import BaseAgent
from agent_framework.config.settings import Settings
from agent_framework.agents.logistics.dify_registry import build_dify_registry
from agent_framework.agents.logistics.graph import LogisticsOrchestratorGraphBuilder

logger = structlog.get_logger(__name__)


class LogisticsOrchestratorAgent(BaseAgent):
    """企业级物流供应链协调器。

    Usage:
        agent = LogisticsOrchestratorAgent(settings)
        agent.build_graph(checkpointer=checkpointer, store=store)
        result = await agent.run(
            user_message="查一下订单 SO-001 的物流状态",
            thread_id="thread-123",
            user_id="user-456",
        )
    """

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._dify_registry = build_dify_registry(settings)

    def build_graph(self, checkpointer: Any = None, store: Any = None, **kwargs: Any) -> None:
        """编译协调器图，存入 self._graph。"""
        graph = LogisticsOrchestratorGraphBuilder().build()
        self._graph = graph.compile(checkpointer=checkpointer, store=store)
        logger.info(
            "logistics_orchestrator_graph_compiled",
            mock_mode=self._settings.DIFY_MOCK_MODE,
        )

    async def run(
        self,
        user_message: str,
        thread_id: str = "default",
        user_id: str = "anonymous",
        tenant_id: str = "default",
        memory_enabled: bool = True,
    ) -> dict[str, Any]:
        """执行协调流程，返回 final_answer 与完整 messages。"""
        config: RunnableConfig = {
            "configurable": {
                "thread_id": thread_id,
                "settings": self._settings,
                "dify_registry": self._dify_registry,
                "context": {
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "memory_enabled": memory_enabled,
                },
            }
        }
        input_state = {
            "messages": [HumanMessage(content=user_message)],
            "thread_id": thread_id,
        }

        logger.info(
            "orchestrator_run_start",
            thread_id=thread_id,
            user_id=user_id,
            message_preview=user_message[:80],
        )

        result = await self._graph.ainvoke(input_state, config=config)

        logger.info(
            "orchestrator_run_done",
            thread_id=thread_id,
            has_answer=bool(result.get("final_answer")),
            error_count=len(result.get("errors", [])),
        )
        return result

    async def stream(
        self,
        user_message: str,
        thread_id: str = "default",
        user_id: str = "anonymous",
        tenant_id: str = "default",
    ):
        """流式执行，yield LangGraph event 供 SSE 使用。"""
        config: RunnableConfig = {
            "configurable": {
                "thread_id": thread_id,
                "settings": self._settings,
                "dify_registry": self._dify_registry,
                "context": {
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "memory_enabled": True,
                },
            }
        }
        input_state = {
            "messages": [HumanMessage(content=user_message)],
            "thread_id": thread_id,
        }
        async for event in self._graph.astream_events(input_state, config=config, version="v2"):
            yield event
