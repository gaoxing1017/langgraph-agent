"""Tavily 网络搜索工具。

返回排名靠前的搜索结果的格式化摘要。需要 TAVILY_API_KEY 环境变量。
当 tavily-python 包未安装时会优雅降级。
"""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.tools import tool

logger = structlog.get_logger(__name__)


@tool
async def tavily_search(query: str) -> str:
    """使用 Tavily 搜索网络，返回相关结果的摘要。

    Args:
        query: 搜索查询字符串。
    """
    try:
        from tavily import AsyncTavilyClient  # type: ignore[import]
        import os
        client = AsyncTavilyClient(api_key=os.getenv("TAVILY_API_KEY", ""))
        result = await client.search(query, max_results=5)
        results = result.get("results", [])
        if not results:
            return "No results found."
        # 限制为 3 条结果，以合理控制上下文窗口的使用量
        summaries = [
            f"**{r.get('title', 'No title')}**\n{r.get('content', '')}"
            for r in results[:3]
        ]
        return "\n\n".join(summaries)
    except ImportError:
        return "Tavily search not available. Install tavily-python."
    except Exception as exc:
        logger.error("Tavily 搜索失败", error=str(exc))
        return f"Search error: {exc}"
