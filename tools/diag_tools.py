"""系统诊断 MCP Tools"""
from __future__ import annotations

from fastmcp import FastMCP
from core.system_diag import SystemDiag


def register_diag_tools(mcp: FastMCP, system_diag: SystemDiag):
    """注册系统诊断相关的 MCP Tools"""

    @mcp.tool
    def get_system_info() -> dict:
        """获取系统概览信息（主机名、操作系统、内核版本、运行时间）。"""
        return system_diag.get_system_info()

    @mcp.tool
    def get_cpu_info(per_core: bool = False) -> dict:
        """获取 CPU 使用率和信息。

        Args:
            per_core: 是否返回每个逻辑核心的使用率。
        """
        return system_diag.get_cpu_info(per_core=per_core)

    @mcp.tool
    def get_memory_info() -> dict:
        """获取内存使用情况（物理内存和 Swap）。"""
        return system_diag.get_memory_info()

    @mcp.tool
    def get_disk_info() -> dict:
        """获取所有磁盘分区的使用情况。"""
        return system_diag.get_disk_info()

    @mcp.tool
    def get_network_info() -> dict:
        """获取网络接口流量统计。"""
        return system_diag.get_network_info()
