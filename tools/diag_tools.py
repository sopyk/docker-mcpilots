"""系统诊断 MCP Tools"""
from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.server.dependencies import CurrentContext
from fastmcp.server.context import Context

from core.system_diag import SystemDiag
from core.app_state import AppState
from core.auth import PermissionDeniedError


def register_diag_tools(mcp: FastMCP, system_diag: SystemDiag, app_state: AppState):
    """注册系统诊断相关的 MCP Tools"""

    @mcp.tool
    async def get_system_info(
        ctx: Context = CurrentContext(),
    ) -> dict:
        """获取系统概览信息（主机名、操作系统、内核版本、运行时间）。"""
        key_config = await ctx.get_state("auth_key_config")
        if key_config is None:
            return {"success": False, "error": "Authentication required"}
        try:
            app_state.permission_checker.check(key_config, "system:info")
        except PermissionDeniedError as e:
            return {"success": False, "error": str(e)}
        return system_diag.get_system_info()

    @mcp.tool
    async def get_cpu_info(
        per_core: bool = False,
        ctx: Context = CurrentContext(),
    ) -> dict:
        """获取 CPU 使用率和信息。

        Args:
            per_core: 是否返回每个逻辑核心的使用率。
        """
        key_config = await ctx.get_state("auth_key_config")
        if key_config is None:
            return {"success": False, "error": "Authentication required"}
        try:
            app_state.permission_checker.check(key_config, "system:info")
        except PermissionDeniedError as e:
            return {"success": False, "error": str(e)}
        return system_diag.get_cpu_info(per_core=per_core)

    @mcp.tool
    async def get_memory_info(
        ctx: Context = CurrentContext(),
    ) -> dict:
        """获取内存使用情况（物理内存和 Swap）。"""
        key_config = await ctx.get_state("auth_key_config")
        if key_config is None:
            return {"success": False, "error": "Authentication required"}
        try:
            app_state.permission_checker.check(key_config, "system:info")
        except PermissionDeniedError as e:
            return {"success": False, "error": str(e)}
        return system_diag.get_memory_info()

    @mcp.tool
    async def get_disk_info(
        ctx: Context = CurrentContext(),
    ) -> dict:
        """获取所有磁盘分区的使用情况。"""
        key_config = await ctx.get_state("auth_key_config")
        if key_config is None:
            return {"success": False, "error": "Authentication required"}
        try:
            app_state.permission_checker.check(key_config, "system:info")
        except PermissionDeniedError as e:
            return {"success": False, "error": str(e)}
        return system_diag.get_disk_info()

    @mcp.tool
    async def get_network_info(
        ctx: Context = CurrentContext(),
    ) -> dict:
        """获取网络接口流量统计。"""
        key_config = await ctx.get_state("auth_key_config")
        if key_config is None:
            return {"success": False, "error": "Authentication required"}
        try:
            app_state.permission_checker.check(key_config, "system:info")
        except PermissionDeniedError as e:
            return {"success": False, "error": str(e)}
        return system_diag.get_network_info()
