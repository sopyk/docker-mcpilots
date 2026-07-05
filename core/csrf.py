"""CSRF 防护模块"""
from __future__ import annotations
import secrets
from itsdangerous import URLSafeTimedSerializer, BadSignature


class CSRFProtection:
    """CSRF 防护器"""

    def __init__(self, secret: str, timeout: int = 86400):
        self.serializer = URLSafeTimedSerializer(secret, salt="csrf")
        self.timeout = timeout

    def generate_token(self) -> str:
        """生成 CSRF token"""
        data = {"r": secrets.token_hex(16)}
        return self.serializer.dumps(data)

    def validate_token(self, token: str) -> bool:
        """验证 CSRF token，成功返回 True"""
        try:
            self.serializer.loads(token, max_age=self.timeout)
            return True
        except BadSignature:
            return False
