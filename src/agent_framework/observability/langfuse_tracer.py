from __future__ import annotations

from typing import Any

import structlog

from agent_framework.config.settings import Settings

logger = structlog.get_logger(__name__)


def get_langfuse_handler(
    settings: Settings,
    thread_id: str = "",
    user_id: str = "",
    trace_name: str = "agent-run",
) -> Any | None:
    """构建并返回 Langfuse CallbackHandler，若已禁用则返回 None。"""
    if not settings.LANGFUSE_ENABLED:
        return None

    try:
        from langfuse.callback import CallbackHandler
        handler = CallbackHandler(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY.get_secret_value(),
            host=settings.LANGFUSE_HOST,
            session_id=thread_id or None,
            user_id=user_id or None,
            trace_name=trace_name,
        )
        logger.debug("Langfuse handler 已创建", thread_id=thread_id)
        return handler
    except ImportError:
        logger.warning("langfuse 包未安装，链路追踪已禁用")
        return None
    except Exception as exc:
        logger.error("Langfuse handler 创建失败", error=str(exc))
        return None
