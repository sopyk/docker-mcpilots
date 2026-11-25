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

    def _load_from_disk(self) -> list[AuditEntry]:
        """从磁盘 JSONL 文件加载所有审计日志"""
        items: list[AuditEntry] = []
        if not self.log_file.exists():
            return items
        try:
            with self.log_file.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        items.append(AuditEntry(**data))
                    except (json.JSONDecodeError, TypeError):
                        continue
        except OSError:
            pass
        return items

    def query(self, source: str | None = None, actor: str | None = None,
              limit: int = 100) -> list[AuditEntry]:
        """查询审计日志

        优先从磁盘读取历史持久化记录，再合并内存中的最新记录，
        确保容器重启后历史审计日志仍可查询。

        Args:
            source: 按来源筛选 ("web" or "mcp")
            actor: 按操作者筛选
            limit: 返回最大数量
        """
        disk_items = self._load_from_disk()
        memory_items = list(self._memory)
        # 合并：磁盘记录为基准，内存记录追加（避免重复）
        seen = set()
        items: list[AuditEntry] = []
        for e in disk_items:
            key = (e.timestamp, e.source, e.actor, e.action)
            if key not in seen:
                seen.add(key)
                items.append(e)
        for e in memory_items:
            key = (e.timestamp, e.source, e.actor, e.action)
            if key not in seen:
                seen.add(key)
                items.append(e)
        if source:
            items = [e for e in items if e.source == source]
        if actor:
            items = [e for e in items if e.actor == actor]
        return items[-limit:]
