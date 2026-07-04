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
    def get_container_logs(
        container_id: str,
        tail: int | None = None,
        since: str | None = None,
        until: str | None = None,
        timestamps: bool = False,
    ) -> dict:
        """获取容器日志。需要 container:logs 权限。

        Args:
            container_id: 容器 ID 或名称。
            tail: 返回最后 N 行日志，不传则返回全部。
            since: 起始时间（RFC3339 格式如 "2026-07-04T00:00:00" 或相对时间如 "1h"、"30m"）。
            until: 结束时间（同上）。
            timestamps: 是否在每行日志前加时间戳，排查时序问题时建议开启。
        """
        return docker_client.get_container_logs(
            container_id,
            tail=tail,
            since=since,
            until=until,
            timestamps=timestamps,
        )

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

    # ── 容器诊断工具 ──

    @mcp.tool
    def get_container_processes(container_id: str) -> dict:
        """获取容器内运行的进程列表（排查"容器为什么卡住"）。

        Args:
            container_id: 容器 ID 或名称。
        """
        return docker_client.get_container_processes(container_id)

    @mcp.tool
    def get_container_health(container_id: str) -> dict:
        """获取容器健康检查状态（排查"容器为什么不健康"）。

        返回最近几次健康检查的结果和失败次数。

        Args:
            container_id: 容器 ID 或名称。
        """
        return docker_client.get_container_health(container_id)

    @mcp.tool
    def get_container_networks(container_id: str) -> dict:
        """获取容器网络详情（排查"容器连不上网"）。

        返回容器的 IP、网关、端口映射、DNS、所属网络。

        Args:
            container_id: 容器 ID 或名称。
        """
        return docker_client.get_container_networks(container_id)

    @mcp.tool
    def get_container_mounts(container_id: str) -> dict:
        """获取容器挂载卷详情（排查"数据丢失/权限不对"）。

        返回容器所有挂载点、类型、读写权限、源路径。

        Args:
            container_id: 容器 ID 或名称。
        """
        return docker_client.get_container_mounts(container_id)

    @mcp.tool
    def get_container_changes(container_id: str) -> dict:
        """获取容器文件系统变更（排查"容器里改了什么"）。

        返回容器相比镜像有变更的文件列表及变更类型（added/modified/deleted）。

        Args:
            container_id: 容器 ID 或名称。
        """
        return docker_client.get_container_changes(container_id)
