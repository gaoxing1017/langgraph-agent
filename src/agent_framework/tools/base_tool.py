"""带自动重试的基础工具，用于处理瞬时网络错误。

继承 RetryableTool 并实现 _arun()。tenacity 的 @retry 装饰器
能透明地处理 RateLimitError 和超时；LLM 不会感知到这些瞬时失败，
除非所有重试均耗尽。

注意：_run() 有意未实现——框架中的所有工具均以异步优先。
同步调用方应使用 asyncio.run(_arun(...))。
"""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.tools import BaseTool
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = structlog.get_logger(__name__)


class RetryableTool(BaseTool):
    """在瞬时错误时自动重试的 BaseTool 子类。"""

    max_retries: int = 3
    name: str = "retryable_tool"
    description: str = "A retryable tool"

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """同步执行——不支持；请使用 _arun()。"""
        raise NotImplementedError("RetryableTool 仅支持异步。请使用 _arun()。")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
        reraise=True,
    )
    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("子类必须实现 _arun")
