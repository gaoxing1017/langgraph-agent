"""语义记忆：对存储的用户知识进行向量相似度搜索。

委托给 AsyncPostgresStore.asearch()，当 store 上配置了 IndexConfig 时
该方法使用 pgvector 余弦相似度进行搜索。
若 store 不可用，将优雅回退并返回空结果，而不是抛出异常。
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


async def semantic_search(
    store: Any,
    user_id: str,
    query: str,
    namespace_suffix: str = "facts",
    limit: int = 5,
) -> list[dict[str, Any]]:
    """对用户记忆执行向量相似度搜索。"""
    try:
        results = await store.asearch(
            namespace=(user_id, namespace_suffix),
            query=query,
            limit=limit,
        )
        return [
            {"key": r.key, "content": r.value.get("content", ""), "score": getattr(r, "score", None)}
            for r in results
            if r.value
        ]
    except Exception as exc:
        logger.error("语义搜索失败", error=str(exc))
        return []
