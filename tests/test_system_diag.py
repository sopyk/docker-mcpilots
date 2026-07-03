"""系统诊断模块测试"""
import sys
from unittest.mock import patch, MagicMock

# 若 psutil 未安装，注入 mock 模块，使 core.system_diag 能正常导入
if 'psutil' not in sys.modules:
    _mock_psutil = MagicMock()
    sys.modules['psutil'] = _mock_psutil

import pytest
from core.system_diag import SystemDiag


class TestGetSystemInfo:
    @patch("core.system_diag.socket.gethostname", return_value="nas-server")
    @patch("core.system_diag.platform.system", return_value="Linux")
    @patch("core.system_diag.platform.release", return_value="5.15.0")
    @patch("core.system_diag.platform.machine", return_value="x86_64")
    @patch("core.system_diag.psutil.boot_time", return_value=1700000000.0)
    def test_returns_system_overview(self, *args):
        diag = SystemDiag()
        info = diag.get_system_info()
        assert info["hostname"] == "nas-server"
        assert info["os"] == "Linux"
        assert info["kernel"] == "5.15.0"
        assert info["architecture"] == "x86_64"
        assert "uptime_seconds" in info


class TestGetCpuInfo:
    @patch("core.system_diag.psutil.cpu_percent", return_value=25.5)
    @patch("core.system_diag.psutil.cpu_count", return_value=4)
    @patch("core.system_diag.psutil.cpu_freq")
    def test_cpu_overall(self, mock_freq, *args):
        mock_freq.return_value = MagicMock(current=2400.0, min=800.0, max=3500.0)
        diag = SystemDiag()
        info = diag.get_cpu_info(per_core=False)
        assert info["percent"] == 25.5
        assert info["count_logical"] == 4
        assert "freq_current_mhz" in info

    @patch("core.system_diag.psutil.cpu_percent", return_value=[10.0, 20.0, 30.0, 40.0])
    @patch("core.system_diag.psutil.cpu_count", return_value=4)
    def test_cpu_per_core(self, *args):
        diag = SystemDiag()
        info = diag.get_cpu_info(per_core=True)
        assert "percent_per_core" in info
        assert len(info["percent_per_core"]) == 4


class TestGetMemoryInfo:
    @patch("core.system_diag.psutil.swap_memory")
    @patch("core.system_diag.psutil.virtual_memory")
    def test_memory_info(self, mock_vm, mock_swap):
        mock_vm.return_value = MagicMock(total=8_000_000_000, available=4_000_000_000, percent=50.0, used=4_000_000_000)
        mock_swap.return_value = MagicMock(total=2_000_000_000, used=500_000_000, percent=25.0, free=1_500_000_000)
        diag = SystemDiag()
        info = diag.get_memory_info()
        assert info["virtual"]["total"] == 8_000_000_000
        assert info["virtual"]["percent"] == 50.0
        assert info["swap"]["total"] == 2_000_000_000


class TestGetDiskInfo:
    @patch("core.system_diag.psutil.disk_usage")
    @patch("core.system_diag.psutil.disk_partitions")
    def test_disk_info(self, mock_partitions, mock_usage):
        mock_partitions.return_value = [
            MagicMock(device="/dev/sda1", mountpoint="/", fstype="ext4", opts="rw"),
        ]
        mock_usage.return_value = MagicMock(total=100_000_000_000, used=40_000_000_000, free=60_000_000_000, percent=40.0)
        diag = SystemDiag()
        info = diag.get_disk_info()
        assert len(info["partitions"]) == 1
        assert info["partitions"][0]["mountpoint"] == "/"
        assert info["partitions"][0]["percent"] == 40.0


class TestGetNetworkInfo:
    @patch("core.system_diag.psutil.net_if_stats")
    @patch("core.system_diag.psutil.net_io_counters")
    def test_network_info(self, mock_io, mock_stats):
        mock_io.return_value = MagicMock(bytes_sent=1000000, bytes_recv=5000000)
        mock_stats.return_value = {
            "eth0": MagicMock(isup=True, speed=1000, mtu=1500),
            "lo": MagicMock(isup=True, speed=0, mtu=65536),
        }
        diag = SystemDiag()
        info = diag.get_network_info()
        assert info["total"]["bytes_sent"] == 1000000
        assert "eth0" in info["interfaces"]
