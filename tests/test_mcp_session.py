"""MCP HTTP 会话空闲超时配置测试（core.mcp_session）。

背景：fastmcp 4.1.0 起默认空闲 1800s 销毁会话（4.0.x 永不过期），
导致长连接客户端出现 ``transport session expired`` / tools 为空。
"""
from __future__ import annotations

import ast
import asyncio
import logging
from pathlib import Path

import fastmcp
import pytest

from core.mcp_session import (
    ENV_VAR,
    configure_session_idle_timeout,
    resolve_session_idle_timeout,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _restore_fastmcp_setting():
    """每个用例结束后还原全局设置，避免污染其他测试。"""
    original = fastmcp.settings.http_session_idle_timeout
    yield
    fastmcp.settings.http_session_idle_timeout = original


@pytest.mark.parametrize(
    "raw", ["none", "NONE", "never", "off", "false", "disabled", "", "  none  "]
)
def test_disabled_values_resolve_to_none(raw: str):
    """显式关闭 → None（会话永不过期）"""
    assert resolve_session_idle_timeout(raw) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1800", 1800.0), ("86400", 86400.0), ("12.5", 12.5), ("1", 1.0), (" 600 ", 600.0)],
)
def test_positive_values_resolve_to_seconds(raw: str, expected: float):
    assert resolve_session_idle_timeout(raw) == expected


@pytest.mark.parametrize(
    "raw", ["abc", "12s", "24h", "--", "none2", "0", "-5", "inf", "nan", "1e400"]
)
def test_invalid_values_fall_back_to_none(raw: str, caplog):
    """非法值不能把服务搞崩（含 inf/nan/<=0），回落"永不过期"并留 warning"""
    with caplog.at_level(logging.WARNING):
        assert resolve_session_idle_timeout(raw) is None
    assert "回落到「会话永不过期」" in caplog.text


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


# ──────────────────────────────────────────────────────────
# 语义验证：None 是否真的等于"不过期"（不只是属性被写进去）
# ──────────────────────────────────────────────────────────


def _session_manager_idle_timeout(setting: float | None):
    """真实构建 FastMCP HTTP app，返回会话管理器实际持有的 idle timeout。

    这是 H1 的守卫：``None`` 必须原样传到 SDK 的会话管理器
    （SDK 侧 ``None`` 表示不做空闲回收），否则"关闭超时"就是假修复。
    """
    from fastmcp import FastMCP

    async def _probe():
        app = FastMCP("probe").http_app()
        async with app.lifespan(app):
            for route in app.routes:
                manager = getattr(getattr(route, "app", None), "session_manager", None)
                if manager is not None:
                    if not hasattr(manager, "session_idle_timeout"):
                        pytest.skip("当前 fastmcp 版本的会话管理器不暴露 session_idle_timeout")
                    return manager.session_idle_timeout
        return "manager-not-found"

    original = fastmcp.settings.http_session_idle_timeout
    fastmcp.settings.http_session_idle_timeout = setting
    try:
        return asyncio.run(_probe())
    finally:
        fastmcp.settings.http_session_idle_timeout = original


def test_none_really_disables_idle_expiry():
    """None 必须原样到达会话管理器（而不是被归一化成 1800）"""
    assert _session_manager_idle_timeout(None) is None


def test_numeric_setting_reaches_session_manager():
    """数字必须原样到达会话管理器（证明链路没被写死）"""
    assert _session_manager_idle_timeout(123.0) == 123.0


# ──────────────────────────────────────────────────────────
# 接线守卫：main.py 必须在 mcp.run() 之前调用配置
# ──────────────────────────────────────────────────────────


def _call_line_numbers(tree: ast.AST, func_name: str) -> list[int]:
    lines = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = node.func
            name = getattr(target, "id", None) or getattr(target, "attr", None)
            if name == func_name:
                lines.append(node.lineno)
    return lines


def _mcp_run_line_numbers(tree: ast.AST) -> list[int]:
    """只匹配 ``mcp.run(...)``，避免误命中其它 ``xxx.run()``。"""
    lines = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "run"
            and getattr(node.func.value, "id", None) == "mcp"
        ):
            lines.append(node.lineno)
    return lines


def test_main_calls_session_config_before_run():
    """重构时不能把修复弄丢：配置调用必须存在且早于 mcp.run()"""
    main_src = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(main_src)

    configure_lines = _call_line_numbers(tree, "configure_session_idle_timeout")
    run_lines = _mcp_run_line_numbers(tree)

    assert configure_lines, "main.py 必须调用 configure_session_idle_timeout()"
    assert run_lines, "main.py 必须调用 mcp.run()"
    assert min(configure_lines) < min(run_lines), (
        "configure_session_idle_timeout() 必须在 mcp.run() 之前调用，"
        "否则 fastmcp 4.1.x 会回落到 30 分钟空闲过期"
    )
