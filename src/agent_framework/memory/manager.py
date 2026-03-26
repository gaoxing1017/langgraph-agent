"""MemoryManager：所有记忆层的统一门面。

在每个应用实例化一次，并从 memory_read_node 中调用
MemoryManager.retrieve_context()，或在会话结束时调用 create_episode()。
"""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.messages import AnyMessage

from agent_framework.memory.episodic import summarize_and_store_episode
from agent_framework.memory.long_term import retrieve_facts, store_fact
from agent_framework.memory.semantic import semantic_search

logger = structlog.get_logger(__name__)


class MemoryManager:
    """协调所有记忆层的统一门面。"""

    def __init__(self, store: Any, llm: Any | None = None) -> None:
        self._store = store
        self._llm = llm

    async def retrieve_context(self, user_id: str, query: str) -> str:
        """结合长期事实和情节摘要检索相关上下文。

        Args:
            user_id: 命名空间键；每个用户拥有隔离的记忆存储。
            query:   用于语义检索的自然语言查询。
        Returns:
            格式化字符串，可直接注入 LLM 系统提示。
        """
        facts = await retrieve_facts(self._store, user_id, query)
        semantic = await semantic_search(self._store, user_id, query, namespace_suffix="episodes")

        parts: list[str] = []
        if facts:
            parts.append("**Relevant facts:**\n" + "\n".join(facts))
        if semantic:
            parts.append("**Related episodes:**\n" + "\n".join(s["content"] for s in semantic))

        return "\n\n".join(parts)

    async def store_fact(self, user_id: str, key: str, content: str) -> None:
        await store_fact(self._store, user_id, key, content)

    async def create_episode(
        self,
        messages: list[AnyMessage],
        user_id: str,
        session_id: str,
    ) -> None:
        if self._llm is None:
            logger.warning("MemoryManager：LLM 未设置，跳过情节创建")
            return
        await summarize_and_store_episode(messages, self._store, user_id, session_id, self._llm)
