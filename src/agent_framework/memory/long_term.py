"""长期记忆：跨会话的用户事实，存储于 AsyncPostgresStore。

事实以 (user_id, "facts") 为命名空间，确保每个用户拥有隔离的
键值存储。当 AsyncPostgresStore 配置了 IndexConfig 时，
store.asearch() 会对查询执行 pgvector 余弦相似度搜索。
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


async def store_fact(
    store: Any,
    user_id: str,
    key: str,
    content: str,
    metadata: dict | None = None,
) -> None:
    """将一个事实存储到用户的长期记忆命名空间中。"""
    await store.aput(
        namespace=(user_id, "facts"),
        key=key,
        value={"content": content, "metadata": metadata or {}},
    )
    logger.debug("事实已存储", user_id=user_id, key=key)


async def retrieve_facts(
    store: Any,
    user_id: str,
    query: str,
    limit: int = 5,
) -> list[str]:
    """从用户的长期记忆中检索相关事实。"""
    results = await store.asearch(
        namespace=(user_id, "facts"),
        query=query,
        limit=limit,
    )
    return [r.value.get("content", "") for r in results if r.value]
