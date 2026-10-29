"""MCP HTTP 服务请求级超时中间件。

背景（issue #1 / v2.1.3 实测）：曾出现 TCP 层正常（端口 open）但 HTTP 事件循环
卡死（POST /mcp initialize 挂起、GET /health 空响应）的半死状态，客户端
（Hermes 等）会对着同一个连接无限挂起，而不是快速失败。

本中间件为 MCP HTTP 应用添加请求级超时，超时后返回 503，
避免「事件循环卡死 → 客户端长时间挂起」的问题。
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

DEFAULT_REQUEST_TIMEOUT_SECONDS = 60.0


def get_request_timeout_seconds() -> float:
    """从环境变量 MCP_HTTP_REQUEST_TIMEOUT 读取，默认 60s"""
    raw = os.environ.get("MCP_HTTP_REQUEST_TIMEOUT", "")
    try:
        value = float(raw)
        if value > 0:
            return value
    except (ValueError, TypeError):
        pass
    return DEFAULT_REQUEST_TIMEOUT_SECONDS


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """为 MCP HTTP 应用添加请求级超时"""

    def __init__(self, app, timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS) -> None:
        super().__init__(app)
        self.timeout_seconds = timeout_seconds

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        try:
            return await asyncio.wait_for(call_next(request), timeout=self.timeout_seconds)
        except asyncio.TimeoutError:
            logger.warning(
                "MCP HTTP 请求超时: path=%s timeout=%ss",
                request.url.path,
                self.timeout_seconds,
            )
            return JSONResponse(
                {"error": "timeout", "message": f"Request timed out after {self.timeout_seconds}s"},
                status_code=503,
            )
