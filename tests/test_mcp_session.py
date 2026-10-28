"""MCP HTTP 会话空闲超时配置测试（core.mcp_session）。

背景：fastmcp 4.1.0 起默认空闲 1800s 销毁会话（4.0.x 永不过期），
导致长连接客户端出现 ``transport session expired`` / tools 为空。
"""
from __future__ import annotations

import fastmcp
import pytest

from core.mcp_session import (
    ENV_VAR,
    configure_session_idle_timeout,
    resolve_session_idle_timeout,
)


@pytest.fixture(autouse=True)
def _restore_fastmcp_setting():
    """每个用例结束后还原全局设置，避免污染其他测试。"""
    original = fastmcp.settings.http_session_idle_timeout
    yield
    fastmcp.settings.http_session_idle_timeout = original


@pytest.mark.parametrize("raw", ["none", "NONE", "never", "off", "false", "0", "-1", "", "  none  "])
def test_disabled_values_resolve_to_none(raw: str):
    """显式关闭 → None（会话永不过期）"""
    assert resolve_session_idle_timeout(raw) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1800", 1800.0), ("86400", 86400.0), ("12.5", 12.5), ("1", 1.0)],
)
def test_positive_values_resolve_to_seconds(raw: str, expected: float):
    assert resolve_session_idle_timeout(raw) == expected


@pytest.mark.parametrize("raw", ["abc", "12s", "--", "none2"])
def test_invalid_values_fall_back_to_none(raw: str, caplog):
    """非法值不能把服务搞崩，回落"永不过期"并留 warning"""
    assert resolve_session_idle_timeout(raw) is None
    assert "不是合法秒数" in caplog.text


def test_default_is_none_when_env_missing(monkeypatch):
    """不设置环境变量时默认关闭超时（与 v2.1.2 / fastmcp 4.0.x 行为一致）"""
    monkeypatch.delenv(ENV_VAR, raising=False)
    assert resolve_session_idle_timeout() is None


def test_env_var_is_used(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "600")
    assert resolve_session_idle_timeout() == 600.0

    monkeypatch.setenv(ENV_VAR, "none")
    assert resolve_session_idle_timeout() is None


def test_configure_writes_fastmcp_settings(monkeypatch):
    """configure 必须真正写进 fastmcp.settings（run_async 只认这里）"""
    monkeypatch.setattr(fastmcp.settings, "http_session_idle_timeout", 1800.0)

    assert configure_session_idle_timeout("none") is None
    assert fastmcp.settings.http_session_idle_timeout is None

    assert configure_session_idle_timeout("900") == 900.0
    assert fastmcp.settings.http_session_idle_timeout == 900.0


def test_configure_default_closes_timeout(monkeypatch):
    """默认调用（无参数、无环境变量）应关闭超时"""
    monkeypatch.delenv(ENV_VAR, raising=False)
    monkeypatch.setattr(fastmcp.settings, "http_session_idle_timeout", 1800.0)

    configure_session_idle_timeout()

    assert fastmcp.settings.http_session_idle_timeout is None
