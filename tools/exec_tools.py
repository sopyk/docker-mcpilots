"""容器内执行命令 MCP Tools（高风险，需 exec:run 权限）"""
from __future__ import annotations

import asyncio

from fastmcp import FastMCP
from fastmcp.dependencies import CurrentContext
from fastmcp.server.context import Context

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
        timeout: int | None = 30,
        ctx: Context = CurrentContext(),
    ) -> dict:
        """在容器内执行命令。需要 exec:run 权限，且受容器 scope 限制。

        高风险操作：仅对可信的、用于排障的专用容器开放。
        建议通过 scope 将 exec 权限限制在特定工具容器内。

        Args:
            container_id: 容器 ID 或名称。
            command: 要执行的命令（如 "ls -la /app" 或 "cat /etc/os-release"）。
            workdir: 工作目录，不传则使用容器默认工作目录。
            timeout: 执行超时秒数，默认 30 秒，超过后强制返回错误。设为 0 或 None 表示不限时。

        Returns:
            包含 success、exit_code、stdout、stderr 的结果字典。
        """
        key_config = await ctx.get_state("auth_key_config")

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

        try:
            if timeout and timeout > 0:
                return await asyncio.wait_for(
                    asyncio.to_thread(
                        docker_client.exec_container,
                        container_id,
                        command,
                        workdir=workdir,
                        timeout=timeout,
                    ),
                    timeout=timeout,
                )
            return await asyncio.to_thread(
                docker_client.exec_container, container_id, command, workdir=workdir
            )
        except asyncio.TimeoutError:
            return {"success": False, "error": f"Command timed out after {timeout}s"}
