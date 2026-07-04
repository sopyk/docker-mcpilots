"""镜像管理 MCP Tools"""
from __future__ import annotations

from fastmcp import FastMCP
from core.docker_client import DockerClient


def register_image_tools(mcp: FastMCP, docker_client: DockerClient):
    """注册镜像管理相关的 MCP Tools"""

    @mcp.tool
    def list_images(name_filter: str | None = None) -> list[dict]:
        """列出本地 Docker 镜像。

        Args:
            name_filter: 按镜像名称过滤，如 "nginx"。
        """
        return docker_client.list_images(name_filter=name_filter)

    @mcp.tool
    def pull_image(image_name: str, tag: str | None = None) -> dict:
        """从 Docker Hub 拉取镜像。需要 image:pull 权限。

        Args:
            image_name: 镜像名称，如 "nginx"。
            tag: 镜像标签，如 "alpine"，不传默认为 "latest"。
        """
        return docker_client.pull_image(image_name, tag=tag)

    @mcp.tool
    def remove_image(image_name: str, force: bool = False) -> dict:
        """删除本地镜像。需要 image:remove 权限（仅 admin 角色）。

        Args:
            image_name: 镜像 ID 或名称（如 "nginx:latest"）。
            force: 是否强制删除。
        """
        return docker_client.remove_image(image_name, force=force)
