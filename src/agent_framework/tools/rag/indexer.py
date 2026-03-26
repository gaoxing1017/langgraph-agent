from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


async def index_document(
    content: str,
    store: Any,
    namespace: tuple[str, ...],
    doc_id: str,
    metadata: dict | None = None,
) -> None:
    """将文档片段索引到向量存储中。"""
    try:
        await store.aput(
            namespace=namespace,
            key=doc_id,
            value={"content": content, "metadata": metadata or {}},
        )
        logger.debug("文档已索引", doc_id=doc_id, namespace=namespace)
    except Exception as exc:
        logger.error("文档索引失败", error=str(exc), doc_id=doc_id)
        raise
