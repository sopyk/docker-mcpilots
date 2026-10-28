"""应用版本号单一数据源。

发版时只改这里，main.py（MCP 元信息、/health）与 Web UI 模板会自动同步。
测试 tests/test_version_consistency.py 会阻止在别处重新硬编码版本号。
"""
from __future__ import annotations

VERSION = "2.1.3-rc.2"
