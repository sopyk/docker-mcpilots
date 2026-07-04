"""容器管理 MCP Tools"""
from __future__ import annotations

from fastmcp import FastMCP

from core.docker_client import DockerClient


def register_container_tools(mcp: FastMCP, docker_client: DockerClient):
    """注册容器管理相关的 MCP Tools"""

    @mcp.tool
    def list_containers(
        status: str | None = None,
        all: bool = False,
    ) -> list[dict]:
        """列出 Docker 容器。

        Args:
            status: 过滤状态，可选 "running"、"exited"，不传则返回运行中的容器。
            all: 是否返回所有容器（包括已停止的），设为 true 时忽略 status。
        """
        return docker_client.list_containers(status=status, all=all)

    @mcp.tool
    def inspect_container(container_id: str) -> dict:
        """获取指定容器的详细信息。

        Args:
            container_id: 容器 ID 或名称。
        """
        return docker_client.get_container(container_id)

    @mcp.tool
    def start_container(container_id: str) -> dict:
        """启动指定容器。需要 container:start 权限。

        Args:
            container_id: 容器 ID 或名称。
        """
        return docker_client.start_container(container_id)

    @mcp.tool
    def stop_container(container_id: str) -> dict:
        """停止指定容器。需要 container:stop 权限。

        Args:
            container_id: 容器 ID 或名称。
        """
        return docker_client.stop_container(container_id)

    @mcp.tool
    def restart_container(container_id: str) -> dict:
        """重启指定容器。需要 container:restart 权限。

        Args:
            container_id: 容器 ID 或名称。
        """
        return docker_client.restart_container(container_id)

    @mcp.tool
    def get_container_logs(container_id: str, tail: int | None = None) -> dict:
        """获取容器日志。需要 container:logs 权限。

        Args:
            container_id: 容器 ID 或名称。
            tail: 返回最后 N 行日志，不传则返回全部。
        """
        return docker_client.get_container_logs(container_id, tail=tail)

    @mcp.tool
    def get_container_stats(container_id: str) -> dict:
        """获取容器实时资源占用（CPU、内存、网络）。需要 container:stats 权限。

        Args:
            container_id: 容器 ID 或名称。
        """
        return docker_client.get_container_stats(container_id)

    @mcp.tool
    def remove_container(container_id: str, force: bool = False) -> dict:
        """删除指定容器。需要 container:remove 权限（仅 admin 角色）。

        Args:
            container_id: 容器 ID 或名称。
            force: 是否强制删除运行中的容器。
        """
        return docker_client.remove_container(container_id, force=force)
