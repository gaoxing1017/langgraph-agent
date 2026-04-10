from __future__ import annotations

"""记忆加载节点。

memory_load_node：
  - 从 PostgreSQL Store 加载用户偏好（user_preferences）
  - 加载当前 thread 的历史摘要（short_term_summary）
  - 若 store 不可用或 memory_enabled=False，静默跳过

注：保存逻辑已迁移至 turn_finalize_node（每轮必执行）。
"""

from typing import Any

import structlog
from langchain_core.runnables import RunnableConfig

from agent_framework.core.context import AgentContext
from agent_framework.agents.logistics.state import OrchestratorState

logger = structlog.get_logger(__name__)


async def memory_load_node(
    state: OrchestratorState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """从长期记忆加载用户偏好与历史摘要，注入 state 供后续节点使用。"""
    configurable = config.get("configurable", {})
    context: AgentContext = configurable.get("context", {})
    store = configurable.get("store")

    if not context.get("memory_enabled", True) or store is None:
        logger.debug("memory_load_skipped", reason="disabled_or_no_store")
        return {}

    user_id = context.get("user_id", "anonymous")
    tenant_id = context.get("tenant_id", "default")
    thread_id = state.get("thread_id", "")
    updates: dict[str, Any] = {}

    try:
        pref_key = f"preferences/{tenant_id}/{user_id}"
        pref_item = await store.aget(namespace=("logistics", "user_prefs"), key=pref_key)
        if pref_item:
            updates["user_preferences"] = pref_item.value
            logger.debug("memory_preferences_loaded", user_id=user_id)

        summary_key = f"summary/{thread_id}"
        summary_item = await store.aget(namespace=("logistics", "summaries"), key=summary_key)
        if summary_item:
            updates["short_term_summary"] = summary_item.value.get("summary", "")
            logger.debug("memory_summary_loaded", thread_id=thread_id)
    except Exception as exc:
        logger.warning("memory_load_error", error=str(exc))

    return updates
