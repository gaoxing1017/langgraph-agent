from __future__ import annotations

import structlog
from langchain_core.tools import tool

logger = structlog.get_logger(__name__)


@tool
async def http_get(url: str, headers: dict | None = None) -> str:
    """向外部 API 发起 HTTP GET 请求。

    Args:
        url: 请求的 URL。
        headers: 可选的 HTTP 请求头字典。
    """
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers or {})
            response.raise_for_status()
            return response.text[:5000]  # 限制响应体大小
    except httpx.HTTPStatusError as exc:
        return f"HTTP error {exc.response.status_code}: {exc.response.text[:500]}"
    except Exception as exc:
        logger.error("HTTP 请求失败", url=url, error=str(exc))
        return f"Request error: {exc}"
