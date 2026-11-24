"""审计日志 MCP Tools"""

from __future__ import annotations

from fastmcp import FastMCP

from core.audit import AuditLogger


def register_audit_tools(mcp: FastMCP, app_state) -> None:
    """注册审计日志 MCP Tools"""

    @mcp.tool
    def list_audit_logs(source: str | None = None, actor: str | None = None, limit: int = 100) -> list[dict]:
        """查询审计日志（仅 admin 角色可调用）。

        Args:
            source: 来源过滤（"web"、"mcp" 或 None 表示全部）
            actor: 操作人过滤（API Key name 或留空查全部）
            limit: 返回记录数上限

        Returns:
            审计日志列表，每项包含 timestamp/source/actor/action/target/success 字段
        """
        audit = app_state.audit_logger
        if not audit:
            return []
        logs = audit.query(source=source, actor=actor, limit=limit)
        from dataclasses import asdict
        return [asdict(e) for e in logs]