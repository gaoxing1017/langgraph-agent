"""Wikipedia 搜索工具。

获取最接近匹配标题的 Wikipedia 文章。结果截断为 2000 字符，
以避免向 LLM 上下文窗口中注入过多内容。
需要 wikipedia 包（pip install wikipedia）。
"""

from __future__ import annotations

import structlog
from langchain_core.tools import tool

logger = structlog.get_logger(__name__)


@tool
async def wikipedia_search(query: str) -> str:
    """在 Wikipedia 上搜索某个主题的相关信息。

    Args:
        query: 要搜索的主题或问题。
    """
    try:
        import wikipedia  # type: ignore[import]
        import asyncio
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, wikipedia.search, query)
        if not results:
            return "No Wikipedia results found."
        page = await loop.run_in_executor(None, wikipedia.page, results[0])
        # 截断为 2000 字符——完整文章可能超过 50000 字符
        return page.content[:2000]
    except ImportError:
        return "Wikipedia not available. Install wikipedia package."
    except Exception as exc:
        logger.error("Wikipedia 搜索失败", error=str(exc))
        return f"Wikipedia error: {exc}"
