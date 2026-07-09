"""镜像管理 MCP Tools"""
from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.server.dependencies import CurrentContext
from fastmcp.server.context import Context

from core.docker_client import DockerClient
from core.app_state import AppState
from core.auth import PermissionDeniedError


def register_image_tools(mcp: FastMCP, docker_client: DockerClient, app_state: AppState):
    """注册镜像管理相关的 MCP Tools"""

    @mcp.tool
    async def list_images(
        name_filter: str | None = None,
        ctx: Context = CurrentContext(),
    ) -> list[dict]:
        """列出本地 Docker 镜像。

        Args:
            name_filter: 按镜像名称过滤，如 "nginx"。
        """
        key_config = await ctx.get_state("auth_key_config")
        if key_config is None:
            return [{"success": False, "error": "Authentication required"}]
        try:
            app_state.permission_checker.check(key_config, "image:list")
        except PermissionDeniedError as e:
            return [{"success": False, "error": str(e)}]
        return docker_client.list_images(name_filter=name_filter)

    @mcp.tool
    async def inspect_image(
        image_name: str,
        ctx: Context = CurrentContext(),
    ) -> dict:
        """获取镜像详细信息（排查"镜像有没有问题"）。

        返回镜像的入口命令、环境变量、暴露端口、历史构建层等信息。

        Args:
            image_name: 镜像 ID 或名称（如 "nginx:latest"）。
        """
        key_config = await ctx.get_state("auth_key_config")
        if key_config is None:
            return {"success": False, "error": "Authentication required"}
        try:
            app_state.permission_checker.check(key_config, "image:inspect")
        except PermissionDeniedError as e:
            return {"success": False, "error": str(e)}
        return docker_client.inspect_image(image_name)

    @mcp.tool
    async def pull_image(
        image_name: str,
        tag: str | None = None,
        ctx: Context = CurrentContext(),
    ) -> dict:
        """从 Docker Hub 拉取镜像。需要 image:pull 权限。

        Args:
            image_name: 镜像名称，如 "nginx"。
            tag: 镜像标签，如 "alpine"，不传则默认为 "latest"。
        """
        key_config = await ctx.get_state("auth_key_config")
        if key_config is None:
            return {"success": False, "error": "Authentication required"}
        try:
            app_state.permission_checker.check(key_config, "image:pull")
        except PermissionDeniedError as e:
            return {"success": False, "error": str(e)}
        return docker_client.pull_image(image_name, tag=tag)

    @mcp.tool
    async def remove_image(
        image_name: str,
        force: bool = False,
        ctx: Context = CurrentContext(),
    ) -> dict:
        """删除本地镜像。需要 image:remove 权限（仅 admin 角色）。

        Args:
            image_name: 镜像 ID 或名称（如 "nginx:latest"）。
            force: 是否强制删除。
        """
        key_config = await ctx.get_state("auth_key_config")
        if key_config is None:
            return {"success": False, "error": "Authentication required"}
        try:
            app_state.permission_checker.check(key_config, "image:remove")
        except PermissionDeniedError as e:
            return {"success": False, "error": str(e)}
        return docker_client.remove_image(image_name, force=force)
