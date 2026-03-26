from __future__ import annotations

from typing import Any

import structlog

from agent_framework.config.settings import Settings

logger = structlog.get_logger(__name__)


async def get_postgres_store(settings: Settings) -> Any | None:
    """返回用于长期记忆的 AsyncPostgresStore，若不可用则返回 None。"""
    try:
        from langgraph.store.postgres import AsyncPostgresStore
        store = AsyncPostgresStore.from_conn_string(settings.DATABASE_URL)
        await store.setup()
        logger.info("AsyncPostgresStore 初始化完成")
        return store
    except ImportError:
        logger.warning("langgraph-checkpoint-postgres 未安装，store 不可用")
        return None
    except Exception as exc:
        logger.error("AsyncPostgresStore 初始化失败", error=str(exc))
        return None
