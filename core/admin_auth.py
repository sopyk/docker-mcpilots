"""管理员认证模块 - 管理用户账号与会话签名"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import bcrypt
import yaml
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired


@dataclass
class AdminConfig:
    """管理员账号配置"""
    username: str
    password_hash: str

    @classmethod
    def from_yaml(cls, path: str) -> "AdminConfig":
        p = Path(path)
        if not p.exists():
            raise ValueError(f"Admin config not found: {path}")
        with p.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            return cls(
                username=data.get("username", ""),
                password_hash=data.get("password_hash", "")
            )

    def to_yaml(self, path: str) -> None:
        data = {"username": self.username, "password_hash": self.password_hash}
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True)
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass  # 非关键，不抛错


class AdminAuth:
    """管理员认证器"""

    def __init__(self, admin_yaml: str, session_secret: str):
        self.admin_yaml = admin_yaml
        self._session_secret = session_secret

    def verify(self, username: str, password: str) -> bool:
        """验证用户名密码"""
        try:
            config = AdminConfig.from_yaml(self.admin_yaml)
        except ValueError:
            return False
        if username != config.username:
            return False
        if not config.password_hash:
            return False
        return bcrypt.checkpw(
            password.encode("utf-8"),
            config.password_hash.encode("utf-8")
        )

    def set_password(self, username: str, password: str) -> None:
        """设置管理员密码（首次初始化或重置用）"""
        hashed = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")
        config = AdminConfig(username=username, password_hash=hashed)
        config.to_yaml(self.admin_yaml)


class SessionManager:
    """会话管理 - 签名会话 token"""

    def __init__(self, secret: str, timeout: int = 28800):
        self.serializer = URLSafeTimedSerializer(secret, salt="web-session")
        self.timeout = timeout

    def create_token(self, username: str) -> str:
        """创建会话 token"""
        return self.serializer.dumps({"u": username})

    def validate_token(self, token: str) -> Optional[str]:
        """验证 token 并返回 username，失败返回 None"""
        try:
            data = self.serializer.loads(token, max_age=self.timeout)
            return data.get("u")
        except (BadSignature, SignatureExpired):
            return None
