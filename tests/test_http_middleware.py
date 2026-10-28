"""请求级超时中间件测试（core.http_middleware.RequestTimeoutMiddleware）"""
from __future__ import annotations

import asyncio

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from core.http_middleware import RequestTimeoutMiddleware, get_request_timeout_seconds


async def _slow(request) -> JSONResponse:
    await asyncio.sleep(2)
    return JSONResponse({"ok": True})


async def _fast(request) -> JSONResponse:
    return JSONResponse({"ok": True})


def _make_app(timeout_seconds: float) -> Starlette:
    app = Starlette(
        routes=[
            Route("/slow", _slow, methods=["GET"]),
            Route("/fast", _fast, methods=["GET"]),
        ]
    )
    app.add_middleware(RequestTimeoutMiddleware, timeout_seconds=timeout_seconds)
    return app


def test_middleware_allows_fast_requests():
    """快速请求不应被误伤"""
    client = TestClient(_make_app(timeout_seconds=5))
    r = client.get("/fast")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_middleware_times_out_slow_request():
    """慢请求（> timeout）应返回 503 并快速失败，而不是挂起"""
    client = TestClient(_make_app(timeout_seconds=0.2))
    r = client.get("/slow")
    assert r.status_code == 503
    assert r.json()["error"] == "timeout"


def test_get_request_timeout_seconds_default_and_env(monkeypatch):
    """默认 60s；环境变量可覆盖"""
    monkeypatch.delenv("MCP_HTTP_REQUEST_TIMEOUT", raising=False)
    assert get_request_timeout_seconds() == 60.0
    monkeypatch.setenv("MCP_HTTP_REQUEST_TIMEOUT", "12.5")
    assert get_request_timeout_seconds() == 12.5
    monkeypatch.setenv("MCP_HTTP_REQUEST_TIMEOUT", "abc")
    assert get_request_timeout_seconds() == 60.0
