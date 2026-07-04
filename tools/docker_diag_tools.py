"""Docker 资源诊断 MCP Tools（网络、卷等）"""
from __future__ import annotations

from fastmcp import FastMCP
from core.docker_client import DockerClient


def register_docker_diag_tools(mcp: FastMCP, docker_client: DockerClient):
    """注册 Docker 资源诊断相关的 MCP Tools"""

    @mcp.tool
    def list_networks() -> list[dict]:
        """列出所有 Docker 网络（排查"容器之间通不通"）。

        返回每个网络的名称、驱动、子网和连接的容器。
        """
        return docker_client.list_networks()

    @mcp.tool
    def list_volumes() -> list[dict]:
        """列出所有 Docker 卷（排查"数据存储在哪里"）。

        返回每个卷的名称、驱动、挂载点路径、创建时间、是否在使用中。
        """
        return docker_client.list_volumes()
