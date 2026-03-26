from __future__ import annotations

from typing import Any

import structlog
from langchain_core.tools import tool

logger = structlog.get_logger(__name__)


def build_retriever_tool(store: Any, namespace_prefix: str = "docs") -> Any:
    """构建以 AsyncPostgresStore 为后端的向量检索工具。"""

    @tool
    async def vector_retriever(query: str, user_id: str = "default") -> str:
        """从知识库中检索相关文档。

        Args:
            query: 用于语义检索的搜索查询。
            user_id: 用于限定搜索命名空间的用户 ID。
        """
        try:
            results = await store.asearch(
                namespace=(namespace_prefix, user_id),
                query=query,
                limit=5,
            )
            if not results:
                return "No relevant documents found."
            chunks = [r.value.get("content", "") for r in results if r.value]
            return "\n\n".join(chunks)
        except Exception as exc:
            logger.error("向量检索失败", error=str(exc))
            return f"Retrieval error: {exc}"

    return vector_retriever
