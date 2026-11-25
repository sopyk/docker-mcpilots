"""审计日志 MCP Tools"""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.dependencies import CurrentContext
from fastmcp.server.context import Context

from core.audit import AuditLogger
from core.auth import PermissionDeniedError


def register_audit_tools(mcp: FastMCP, app_state) -> None:
    """注册审计日志 MCP Tools"""

    @mcp.tool
    async def list_audit_logs(
        source: str | None = None,
        actor: str | None = None,
        limit: int = 100,
        ctx: Context = CurrentContext(),
    ) -> list[dict]:
        """查询审计日志（仅 admin 角色可调用）。

        Args:
            source: 来源过滤（"web"、"mcp" 或 None 表示全部）
            actor: 操作人过滤（API Key name 或留空查全部）
            limit: 返回记录数上限

        Returns:
            审计日志列表，每项包含 timestamp/source/actor/action/target/success 字段
        """
        key_config = await ctx.get_state("auth_key_config")
        if key_config is None:
            return [{"success": False, "error": "Authentication required"}]
        try:
            app_state.permission_checker.check(key_config, "audit:read")
        except PermissionDeniedError as e:
            return [{"success": False, "error": str(e)}]

        audit = app_state.audit_logger
        if not audit:
            return []
        logs = audit.query(source=source, actor=actor, limit=limit)
        from dataclasses import asdict
        return [asdict(e) for e in logs]