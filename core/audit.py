"""审计日志模块 - 记录人类操作与AI Agent调用"""
from __future__ import annotations
import json
from collections import deque
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Union


@dataclass
class AuditEntry:
    """审计日志条目"""
    timestamp: str
    source: str          # "web" or "mcp"
    actor: str           # 用户名或 Key 名称
    action: str
    target: str
    detail: dict
    success: bool


class AuditLogger:
    """审计日志记录器

    - 记录 JSONL 格式到磁盘
    - 内存缓存最近 memory_size 条用于仪表盘
    """

    def __init__(self, log_file: str, memory_size: int = 200):
        self.log_file = Path(log_file)
        self._memory: deque[AuditEntry] = deque(maxlen=memory_size)
        self.memory_size = memory_size
        # 确保父目录存在
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log(self, entry: AuditEntry) -> None:
        """记录一条审计日志"""
        self._memory.append(entry)
        with self.log_file.open("a", encoding="utf-8") as f:
            line = json.dumps(asdict(entry), ensure_ascii=False)
            f.write(line + "\n")

    def recent(self, n: int | None = None) -> list[AuditEntry]:
        """获取最近 N 条审计日志（内存缓存）"""
        items = list(self._memory)
        return items[-n:] if n else items

    def query(self, source: str | None = None, actor: str | None = None,
              limit: int = 100) -> list[AuditEntry]:
        """查询审计日志

        Args:
            source: 按来源筛选 ("web" or "mcp")
            actor: 按操作者筛选
            limit: 返回最大数量
        """
        items = list(self._memory)
        if source:
            items = [e for e in items if e.source == source]
        if actor:
            items = [e for e in items if e.actor == actor]
        return items[-limit:]
