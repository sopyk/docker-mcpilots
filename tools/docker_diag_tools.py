"""Docker 资源诊断 MCP Tools（网络、卷等）"""
from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.server.dependencies import CurrentContext
from fastmcp.server.context import Context

from core.docker_client import DockerClient
from core.app_state import AppState
from core.auth import PermissionDeniedError


def register_docker_diag_tools(mcp: FastMCP, docker_client: DockerClient, app_state: AppState):
    """注册 Docker 资源诊断相关的 MCP Tools"""

    @mcp.tool
    async def list_networks(
        ctx: Context = CurrentContext(),
    ) -> list[dict]:
        """列出所有 Docker 网络（排查"容器之间通不通"）。

        返回每个网络的名称、驱动、子网和连接的容器。
        """
        key_config = await ctx.get_state("auth_key_config")
        if key_config is None:
            return [{"success": False, "error": "Authentication required"}]
        try:
            app_state.permission_checker.check(key_config, "network:list")
        except PermissionDeniedError as e:
            return [{"success": False, "error": str(e)}]
        return docker_client.list_networks()

    @mcp.tool
    async def list_volumes(
        ctx: Context = CurrentContext(),
    ) -> list[dict]:
        """列出所有 Docker 卷（排查"数据存储在哪里"）。

        返回每个卷的名称、驱动、挂载点路径、创建时间、是否在使用中。
        """
        key_config = await ctx.get_state("auth_key_config")
        if key_config is None:
            return [{"success": False, "error": "Authentication required"}]
        try:
            app_state.permission_checker.check(key_config, "volume:list")
        except PermissionDeniedError as e:
            return [{"success": False, "error": str(e)}]
        return docker_client.list_volumes()
