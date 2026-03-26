"""所有智能体类型的抽象基类。

子类实现 build_graph() 以编译并存储 self._graph。
BaseAgent 随后提供 ainvoke() 和 astream() 方法，
负责配置构建、递归限制执行和结构化日志记录。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

import structlog

from agent_framework.config.settings import Settings
from agent_framework.core.context import AgentContext
from agent_framework.core.errors import AgentError
from agent_framework.core.state import AgentState

logger = structlog.get_logger(__name__)


class BaseAgent(ABC):
    """所有智能体的抽象基类。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._graph: Any | None = None  # 由 build_graph() 设置；使用 Any 避免循环导入

    @abstractmethod
    def build_graph(self, **kwargs: Any) -> None:
        """编译 LangGraph 图。在启动时调用一次。"""
        ...

    def _make_config(self, context: AgentContext, thread_id: str, **extra: Any) -> dict[str, Any]:
        """为单次图调用构建 RunnableConfig 字典。

        Args:
            context:   每次请求的运行时配置（LLM provider、工具白名单、用户 id）。
            thread_id: 将 checkpointer 状态限定到此对话线程。
            **extra:   额外的 configurable 键（如 store=、tools=）。
        Returns:
            包含 "configurable" 和 "recursion_limit" 的字典，可直接传入 ainvoke()。
        """
        return {
            "configurable": {
                "thread_id": thread_id,
                "settings": self._settings,
                "context": context,
                **extra,
            },
            # recursion_limit 限制 LangGraph 内部步骤计数器（每次节点调用计 1 步）
            "recursion_limit": context.get("max_iterations", 20) * 2,
        }

    async def ainvoke(
        self,
        input_state: AgentState,
        context: AgentContext,
        thread_id: str = "default",
        **kwargs: Any,
    ) -> AgentState:
        if self._graph is None:
            raise AgentError("图未构建。请在调用前先执行 build_graph()。")
        config = self._make_config(context, thread_id, **kwargs)
        logger.info("智能体调用", thread_id=thread_id)
        result: AgentState = await self._graph.ainvoke(input_state, config=config)
        return result

    async def astream(
        self,
        input_state: AgentState,
        context: AgentContext,
        thread_id: str = "default",
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        if self._graph is None:
            raise AgentError("图未构建。请在调用前先执行 build_graph()。")
        config = self._make_config(context, thread_id, **kwargs)
        # version="v2" 是获取 on_chat_model_stream token 级别事件所必需的
        async for event in self._graph.astream_events(input_state, config=config, version="v2"):
            yield event
