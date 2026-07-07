"""审计日志模块测试"""
from __future__ import annotations
import json
import pytest
from pathlib import Path
from core.audit import AuditLogger, AuditEntry


def test_audit_logger_writes_jsonl(tmp_path):
    """日志写入 JSONL 格式"""
    log_file = tmp_path / "audit.log"
    logger = AuditLogger(log_file=str(log_file), memory_size=100)

    logger.log(AuditEntry(
        timestamp="2026-07-05T12:00:00Z",
        source="web",
        actor="admin",
        action="container:start",
        target="nginx",
        detail={"success": True},
        success=True
    ))

    logger.log(AuditEntry(
        timestamp="2026-07-05T12:01:00Z",
        source="mcp",
        actor="monitor",
        action="container:list",
        target="all",
        detail={"count": 8},
        success=True
    ))

    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    data1 = json.loads(lines[0])
    data2 = json.loads(lines[1])
    assert data1["source"] == "web"
    assert data2["source"] == "mcp"


def test_audit_logger_keeps_recent_in_memory(tmp_path):
    """内存缓存保留最近 N 条"""
    logger = AuditLogger(log_file=str(tmp_path / "audit.log"), memory_size=3)
    for i in range(5):
        logger.log(AuditEntry(
            timestamp=f"2026-07-05T12:0{i}:00Z",
            source="web",
            actor="admin",
            action=f"test:{i}",
            target=f"t{i}",
            detail={},
            success=True
        ))
    recent = logger.recent()
    assert len(recent) == 3
    assert recent[0].action == "test:2"
    assert recent[1].action == "test:3"
    assert recent[2].action == "test:4"


def test_audit_logger_query(tmp_path):
    """按 source 和 actor 筛选"""
    logger = AuditLogger(log_file=str(tmp_path / "audit.log"), memory_size=100)
    logger.log(AuditEntry(
        timestamp="2026-07-05T12:00:00Z",
        source="web",
        actor="admin",
        action="a",
        target="t",
        detail={},
        success=True
    ))
    logger.log(AuditEntry(
        timestamp="2026-07-05T12:00:01Z",
        source="web",
        actor="admin",
        action="b",
        target="t",
        detail={},
        success=True
    ))
    logger.log(AuditEntry(
        timestamp="2026-07-05T12:00:02Z",
        source="mcp",
        actor="monitor",
        action="c",
        target="t",
        detail={},
        success=True
    ))

    results1 = logger.query(source="web", limit=10)
    assert len(results1) == 2
    results2 = logger.query(actor="monitor", limit=10)
    assert len(results2) == 1
    results3 = logger.query(source="web", actor="admin", limit=1)
    assert len(results3) == 1
