"""HTTP 中间件：请求 ID 注入与访问日志记录。

中间件按注册顺序的逆序应用（最外层最后注册）。
请求 ID 绑定到 structlog 上下文变量，使请求期间
发出的每条日志行自动包含 request_id 字段。
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """向每个请求和响应注入唯一的 X-Request-ID 请求头。

    ID 同时绑定到 structlog 的 contextvars，使该请求的
    所有日志行自动包含 request_id，无需显式传递。
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request_id)
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        structlog.contextvars.unbind_contextvars("request_id")
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """在 INFO 级别记录传入请求和传出响应的状态码。"""

    async def dispatch(self, request: Request, call_next) -> Response:
        logger.info("请求", method=request.method, path=request.url.path)
        response = await call_next(request)
        logger.info("响应", status_code=response.status_code, path=request.url.path)
        return response
