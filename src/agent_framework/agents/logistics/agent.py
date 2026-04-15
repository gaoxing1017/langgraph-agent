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
from langgraph.types import Command

from agent_framework.agents.base_agent import BaseAgent
from agent_framework.config.settings import Settings
from agent_framework.agents.logistics.dify_registry import build_dify_registry
from agent_framework.agents.logistics.graph import LogisticsOrchestratorGraphBuilder
from agent_framework.agents.logistics.skill_registry import SkillRegistry

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

    def __init__(self, settings: Settings, skill_registry: SkillRegistry | None = None) -> None:
        super().__init__(settings)
        self._dify_registry = build_dify_registry(settings)
        self._skill_registry = skill_registry

    def build_graph(self, checkpointer: Any = None, store: Any = None, **kwargs: Any) -> None:
        """编译协调器图，存入 self._graph。"""
        graph = LogisticsOrchestratorGraphBuilder().build()
        self._graph = graph.compile(checkpointer=checkpointer, store=store)
        logger.info(
            "logistics_orchestrator_graph_compiled",
            mock_mode=self._settings.DIFY_MOCK_MODE,
        )

    def _build_config(
        self,
        thread_id: str,
        user_id: str,
        tenant_id: str,
        memory_enabled: bool = True,
    ) -> RunnableConfig:
        """构建图调用所需的 RunnableConfig，避免 run/stream 重复代码。"""
        cfg: dict = {
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
        if self._skill_registry:
            cfg["configurable"]["skill_registry"] = self._skill_registry
        return cfg

    async def run(
        self,
        user_message: str,
        thread_id: str = "default",
        user_id: str = "anonymous",
        tenant_id: str = "default",
        memory_enabled: bool = True,
        resume: str | None = None,
    ) -> dict[str, Any]:
        """执行协调流程，返回 final_answer 与完整 messages。

        当 resume 不为 None 时，以 Command(resume=...) 恢复被 interrupt() 挂起的图。
        若结果中包含待处理的中断，在返回字典中附加 __interrupt__ 键。
        """
        config = self._build_config(thread_id, user_id, tenant_id, memory_enabled)

        if resume is not None:
            input_state: Any = Command(resume=resume)
            logger.info(
                "orchestrator_run_resume",
                thread_id=thread_id,
                user_id=user_id,
                resume_preview=str(resume)[:80],
            )
        else:
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

        # 检查是否存在待处理的中断（validate_tasks 触发的 interrupt()）
        graph_state = await self._graph.aget_state(config)
        if graph_state.next and any(t.interrupts for t in graph_state.tasks):
            interrupts = [i for t in graph_state.tasks for i in t.interrupts]
            result["__interrupt__"] = interrupts[0].value

        logger.info(
            "orchestrator_run_done",
            thread_id=thread_id,
            has_answer=bool(result.get("final_answer")),
            interrupted=("__interrupt__" in result),
            error_count=len(result.get("errors", [])),
        )
        return result

    async def stream(
        self,
        user_message: str,
        thread_id: str = "default",
        user_id: str = "anonymous",
        tenant_id: str = "default",
        resume: str | None = None,
    ):
        """流式执行，yield LangGraph event 供 SSE 使用。

        当 resume 不为 None 时，以 Command(resume=...) 恢复被 interrupt() 挂起的图。
        若流结束后仍存在中断，额外 yield 一个 {"event": "__interrupt__", ...} 事件。
        """
        config = self._build_config(thread_id, user_id, tenant_id)

        if resume is not None:
            input_state: Any = Command(resume=resume)
        else:
            input_state = {
                "messages": [HumanMessage(content=user_message)],
                "thread_id": thread_id,
            }

        async for event in self._graph.astream_events(input_state, config=config, version="v2"):
            yield event

        # 流结束后检查是否存在待处理的中断
        graph_state = await self._graph.aget_state(config)
        if graph_state.next and any(t.interrupts for t in graph_state.tasks):
            interrupts = [i for t in graph_state.tasks for i in t.interrupts]
            yield {"event": "__interrupt__", "data": {"value": interrupts[0].value}}
