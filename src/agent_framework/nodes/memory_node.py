from __future__ import annotations

"""记忆节点：连接图与长期存储的桥梁。

memory_read_node  — 在 LLM 节点之前调用；从历史会话中检索相关事实
                    并将其注入为 memory_context。
memory_write_node — 在图产生 final_answer 后调用；
                    将答案持久化，以便后续会话检索。

当 memory_enabled=False 或存储不可用时，两个节点均为空操作。
"""

from langchain_core.runnables import RunnableConfig

from typing import Any

import structlog

from agent_framework.core.context import AgentContext
from agent_framework.core.state import AgentState

logger = structlog.get_logger(__name__)


async def memory_read_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """读取相关的长期记忆并以 memory_context 形式注入状态。"""
    configurable = config.get("configurable", {})
    context: AgentContext = configurable.get("context", {})
    store = configurable.get("store")

    if not store or not context.get("memory_enabled", False):
        return {}

    user_id = context.get("user_id", "anonymous")
    messages = state.get("messages", [])
    if not messages:
        return {}

    # 使用最后一条用户消息作为查询词
    last_message = messages[-1]
    query = getattr(last_message, "content", "")

    try:
        results = await store.asearch(
            namespace=(user_id, "facts"),
            query=query,
            limit=5,
        )
        if results:
            context_parts = [r.value.get("content", "") for r in results if r.value]
            memory_context = "\n".join(context_parts)
            logger.debug("记忆已加载", item_count=len(results), user_id=user_id)
            return {"memory_context": memory_context}
    except Exception as exc:
        logger.warning("读取记忆失败", error=str(exc))

    return {}


async def memory_write_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """将对话中的重要事实持久化到长期记忆。"""
    configurable = config.get("configurable", {})
    context: AgentContext = configurable.get("context", {})
    store = configurable.get("store")

    if not store or not context.get("memory_enabled", False):
        return {}

    final_answer = state.get("final_answer")
    if not final_answer:
        return {}

    user_id = context.get("user_id", "anonymous")
    thread_id = state.get("thread_id", "unknown")

    try:
        await store.aput(
            namespace=(user_id, "facts"),
            key=f"{thread_id}_answer",
            value={"content": final_answer, "thread_id": thread_id},
        )
        logger.debug("记忆已写入", user_id=user_id)
    except Exception as exc:
        logger.warning("写入记忆失败", error=str(exc))

    return {}
