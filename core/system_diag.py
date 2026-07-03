"""系统诊断模块 - 通过 psutil 采集 CPU、内存、磁盘、网络信息"""
from __future__ import annotations

import datetime
import platform
import socket

import psutil


class SystemDiag:
    """系统诊断信息采集器"""

    def get_system_info(self) -> dict:
        """获取系统概览信息"""
        boot_ts = psutil.boot_time()
        now_ts = datetime.datetime.now().timestamp()
        return {
            "hostname": socket.gethostname(),
            "os": platform.system(),
            "kernel": platform.release(),
            "architecture": platform.machine(),
            "boot_time": datetime.datetime.fromtimestamp(boot_ts).strftime("%Y-%m-%d %H:%M:%S"),
            "uptime_seconds": int(now_ts - boot_ts),
        }

    def get_cpu_info(self, per_core: bool = False) -> dict:
        """获取 CPU 信息"""
        overall = psutil.cpu_percent(interval=0.5)
        result = {
            "percent": overall,
            "count_logical": psutil.cpu_count(logical=True),
            "count_physical": psutil.cpu_count(logical=False),
        }

        try:
            freq = psutil.cpu_freq()
            if freq:
                result["freq_current_mhz"] = freq.current
                result["freq_min_mhz"] = freq.min
                result["freq_max_mhz"] = freq.max
        except Exception:
            pass

        if per_core:
            result["percent_per_core"] = psutil.cpu_percent(interval=0, percpu=True)

        return result

    def get_memory_info(self) -> dict:
        """获取内存使用信息"""
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {
            "virtual": {
                "total": vm.total,
                "used": vm.used,
                "available": vm.available,
                "percent": vm.percent,
            },
            "swap": {
                "total": swap.total,
                "used": swap.used,
                "free": swap.free,
                "percent": swap.percent,
            },
        }

    def get_disk_info(self) -> dict:
        """获取磁盘使用信息（所有分区）"""
        partitions = []
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                partitions.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                    "percent": usage.percent,
                })
            except PermissionError:
                continue

        return {"partitions": partitions}

    def get_network_info(self) -> dict:
        """获取网络流量信息"""
        io = psutil.net_io_counters(pernic=False)
        io_per_nic = psutil.net_io_counters(pernic=True)
        if_stats = psutil.net_if_stats()

        interfaces = {}
        for name, stats in if_stats.items():
            interfaces[name] = {
                "isup": stats.isup,
                "speed": stats.speed,
                "mtu": stats.mtu,
            }

        return {
            "total": {
                "bytes_sent": io.bytes_sent,
                "bytes_recv": io.bytes_recv,
                "packets_sent": io.packets_sent,
                "packets_recv": io.packets_recv,
            },
            "per_interface_io": {
                name: {"bytes_sent": nic.bytes_sent, "bytes_recv": nic.bytes_recv}
                for name, nic in io_per_nic.items()
            },
            "interfaces": interfaces,
        }
