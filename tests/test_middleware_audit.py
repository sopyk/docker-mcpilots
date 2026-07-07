"""AuthMiddleware 审计钩子测试（on_call_tool）"""
import sys
import asyncio
from unittest.mock import MagicMock, AsyncMock

# Mock 未安装的第三方模块（必须在 import main 之前）
if 'psutil' not in sys.modules:
    sys.modules['psutil'] = MagicMock()
if 'fastmcp' not in sys.modules:
    _m = MagicMock()
    _m.server.middleware.Middleware = object
    _m.server.middleware.MiddlewareContext = MagicMock
    sys.modules['fastmcp'] = _m
    sys.modules['fastmcp.server'] = _m.server
    sys.modules['fastmcp.server.middleware'] = _m.server.middleware
    sys.modules['fastmcp.server.dependencies'] = _m.server.dependencies
if 'mcp' not in sys.modules:
    sys.modules['mcp'] = MagicMock()
    sys.modules['mcp.types'] = MagicMock()
if 'starlette' not in sys.modules:
    sys.modules['starlette'] = MagicMock()
    sys.modules['starlette.responses'] = MagicMock()

import pytest
from main import AuthMiddleware


def _make_context(tool_name: str, key_name: str | None = None):
    """构造 on_call_tool 用的 mock context"""
    message = MagicMock()
    message.name = tool_name
    ctx = MagicMock()
    ctx.request_context = True
    if key_name:
        kc = MagicMock()
        kc.name = key_name
        ctx.get_state = AsyncMock(return_value=kc)
    else:
        ctx.get_state = AsyncMock(return_value=None)
    context = MagicMock()
    context.message = message
    context.fastmcp_context = ctx
    return context


def test_on_call_tool_logs_success():
    """Tool 调用成功时记录审计日志，target 为 tool 名"""
    audit_logger = MagicMock()
    app_state = MagicMock()
    app_state.audit_logger = audit_logger
    mw = AuthMiddleware(app_state)

    context = _make_context("list_containers", "test-key")
    call_next = AsyncMock(return_value={"success": True})

    asyncio.run(mw.on_call_tool(context, call_next))

    audit_logger.log.assert_called_once()
    entry = audit_logger.log.call_args[0][0]
    assert entry.action == "tools.call"
    assert entry.target == "list_containers"
    assert entry.actor == "test-key"
    assert entry.success is True
    assert entry.source == "mcp"


def test_on_call_tool_logs_failure():
    """Tool 调用失败时记录审计日志，success=False"""
    audit_logger = MagicMock()
    app_state = MagicMock()
    app_state.audit_logger = audit_logger
    mw = AuthMiddleware(app_state)

    context = _make_context("start_container", None)
    call_next = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(RuntimeError):
        asyncio.run(mw.on_call_tool(context, call_next))

    audit_logger.log.assert_called_once()
    entry = audit_logger.log.call_args[0][0]
    assert entry.success is False
    assert entry.target == "start_container"
    assert entry.actor == "unknown"


def test_on_call_tool_no_audit_logger():
    """未配置 audit_logger 时不报错"""
    app_state = MagicMock()
    app_state.audit_logger = None
    mw = AuthMiddleware(app_state)

    context = _make_context("list_images", "key")
    call_next = AsyncMock(return_value=[])

    result = asyncio.run(mw.on_call_tool(context, call_next))
    assert result == []
