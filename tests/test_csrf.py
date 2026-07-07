"""CSRF 模块测试"""
from __future__ import annotations
from core.csrf import CSRFProtection


def test_csrf_roundtrip():
    """CSRF 令牌生成和验证"""
    csrf = CSRFProtection(secret="test", timeout=3600)
    token = csrf.generate_token()
    assert csrf.validate_token(token) is True


def test_csrf_invalid_token():
    """无效令牌返回 False"""
    csrf = CSRFProtection(secret="test", timeout=3600)
    assert csrf.validate_token("garbage") is False
    assert csrf.validate_token("") is False
