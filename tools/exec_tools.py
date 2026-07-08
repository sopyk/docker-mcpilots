"""容器内执行命令 MCP Tools（高风险，需 exec:run 权限）"""
from __future__ import annotations

from fastmcp import FastMCP

from core.docker_client import DockerClient
from core.app_state import AppState
from core.auth import PermissionDeniedError


def register_exec_tools(mcp: FastMCP, docker_client: DockerClient, app_state: AppState):
    """注册 exec 相关的 MCP Tools"""

    @mcp.tool
    async def exec_container(
        container_id: str,
        command: str,
        workdir: str | None = None,
    ) -> dict:
        """在容器内执行命令。需要 exec:run 权限，且受容器 scope 限制。

        高风险操作：仅对可信的、用于排障的专用容器开放。
        建议通过 scope 将 exec 权限限制在特定工具容器内。

        Args:
            container_id: 容器 ID 或名称。
            command: 要执行的命令（如 "ls -la /app" 或 "cat /etc/os-release"）。
            workdir: 工作目录，不传则使用容器默认工作目录。
        """
        from fastmcp.server.dependencies import get_fastmcp_context

        ctx = get_fastmcp_context()
        key_config = await ctx.get_state("auth_key_config") if ctx and ctx.request_context else None

        if key_config is None:
            return {"success": False, "error": "Authentication required"}

        try:
            app_state.permission_checker.check(
                key_config,
                "exec:run",
                container_name=container_id,
            )
        except PermissionDeniedError as e:
            return {"success": False, "error": str(e)}

        return docker_client.exec_container(
            container_id,
            command,
            workdir=workdir,
        )
