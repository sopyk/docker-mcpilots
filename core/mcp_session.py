"""MCP HTTP 会话生命周期配置。

背景（v2.1.3-rc.4 实景问题）：
fastmcp 4.1.0 起，Streamable HTTP 的会话默认空闲 1800 秒（30 分钟）后就销毁
（4.0.x 是"永不过期"）。长时间挂着会话的客户端（Hermes 等）在空闲后会拿到
``404 Session not found``，表现为 ``transport session expired`` / tools 列表为空。
由于 ``requirements.txt`` 之前只做了范围锁定，v2.1.2 镜像装到 fastmcp 4.0.3，
rc.4 镜像装到 4.1.4，导致"代码没改、行为变了"。

这里把默认恢复为与 4.0.x 一致的"永不过期"，同时保留环境变量覆盖能力：

- ``MCP_SESSION_IDLE_TIMEOUT=none``（默认）→ 会话永不过期（仅客户端 DELETE 时销毁）
- ``MCP_SESSION_IDLE_TIMEOUT=86400`` → 空闲 24 小时后销毁（内存有界）
- 非法值（含 ``inf`` / ``nan`` / ``<=0`` / 无法解析的字符串）→ WARNING 并回落"永不过期"

注意：``fastmcp.settings`` 是 pydantic 模型，默认不校验赋值
（``validate_assignment=False``），写错类型不会报错，只会静默生效，
所以本模块只写 ``float | None`` 两种类型，并在这里做输入校验。
环境变量优先级：本模块（``MCP_SESSION_IDLE_TIMEOUT``）优先于 fastmcp 自带的
``FASTMCP_HTTP_SESSION_IDLE_TIMEOUT``（后者不会生效，因为这里会显式覆盖）。
"""
from __future__ import annotations

import logging
import math
import os

import fastmcp

logger = logging.getLogger(__name__)

# 与 fastmcp 4.0.x 的默认行为保持一致：会话永不过期
DEFAULT_SESSION_IDLE_TIMEOUT: float | None = None

# 显式表示"关闭超时"的取值（大小写不敏感）
_DISABLED_VALUES = {"", "none", "never", "off", "false", "disabled"}

ENV_VAR = "MCP_SESSION_IDLE_TIMEOUT"


def resolve_session_idle_timeout(raw: str | None = None) -> float | None:
    """把环境变量解析成 ``http_session_idle_timeout`` 的取值。

    Args:
        raw: 原始字符串；不传时读取 ``MCP_SESSION_IDLE_TIMEOUT``。

    Returns:
        ``None`` 表示永不过期；正浮点数表示空闲多少秒后过期。
    """
    value = str(raw if raw is not None else os.environ.get(ENV_VAR, "none")).strip().lower()
    if value in _DISABLED_VALUES:
        return DEFAULT_SESSION_IDLE_TIMEOUT
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        logger.warning(
            "%s=%r 不是合法秒数，回落到「会话永不过期」", ENV_VAR, value
        )
        return DEFAULT_SESSION_IDLE_TIMEOUT
    if not math.isfinite(seconds) or seconds <= 0:
        logger.warning(
            "%s=%r 必须是正的有限秒数，回落到「会话永不过期」", ENV_VAR, value
        )
        return DEFAULT_SESSION_IDLE_TIMEOUT
    return seconds


def configure_session_idle_timeout(raw: str | None = None) -> float | None:
    """把解析结果写入 fastmcp 全局设置，必须在 ``mcp.run()`` 之前调用。"""
    timeout = resolve_session_idle_timeout(raw)
    fastmcp.settings.http_session_idle_timeout = timeout
    if timeout is None:
        logger.info("MCP HTTP 会话空闲超时：已关闭（会话永不过期）")
    else:
        logger.info("MCP HTTP 会话空闲超时：%g 秒", timeout)
    return timeout
