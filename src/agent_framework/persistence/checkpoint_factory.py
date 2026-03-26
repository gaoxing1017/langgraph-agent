"""Checkpointer 工厂函数。

根据 CHECKPOINTER_TYPE 返回适当的 LangGraph checkpoint saver：
  "memory"   → MemorySaver（进程内，非持久化——仅用于开发/测试）
  "postgres" → AsyncPostgresSaver（PostgreSQL 后端，生产级）

首次运行时会自动调用 AsyncPostgresSaver.setup()，
创建所需的表（checkpoints、checkpoint_blobs、
checkpoint_writes、checkpoint_migrations）。
"""

from __future__ import annotations

from typing import Any

import structlog

from agent_framework.config.settings import Settings

logger = structlog.get_logger(__name__)


async def get_checkpointer(settings: Settings) -> Any:
    """返回 MemorySaver（开发）或 AsyncPostgresSaver（生产）。"""
    if settings.CHECKPOINTER_TYPE == "postgres":
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            checkpointer = AsyncPostgresSaver.from_conn_string(settings.DATABASE_URL)
            await checkpointer.setup()
            logger.info("PostgresSaver 初始化完成")
            return checkpointer
        except ImportError:
            logger.warning("langgraph-checkpoint-postgres 未安装，回退到 MemorySaver")

    from langgraph.checkpoint.memory import MemorySaver
    logger.info("MemorySaver 初始化完成")
    return MemorySaver()
