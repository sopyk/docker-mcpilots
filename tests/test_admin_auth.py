"""管理员认证模块测试"""
from __future__ import annotations
import pytest
from pathlib import Path
from core.admin_auth import AdminAuth, AdminConfig, SessionManager


def test_admin_config_roundtrip(tmp_path):
    """AdminConfig YAML 读写"""
    p = str(tmp_path / "admin.yaml")
    config = AdminConfig(username="test", password_hash="fakehash")
    config.to_yaml(p)
    loaded = AdminConfig.from_yaml(p)
    assert loaded.username == "test"
    assert loaded.password_hash == "fakehash"


def test_admin_auth_set_and_verify_password(tmp_path):
    """设置密码并验证成功/失败"""
    p = str(tmp_path / "admin.yaml")
    auth = AdminAuth(admin_yaml=p, session_secret="test")
    auth.set_password("admin", "secure123")
    assert auth.verify("admin", "secure123") is True
    assert auth.verify("admin", "wrong") is False
    assert auth.verify("wronguser", "secure123") is False


def test_admin_auth_verify_fails_with_empty_hash(tmp_path):
    """空密码 hash 直接拒绝"""
    p = str(tmp_path / "admin.yaml")
    config = AdminConfig(username="admin", password_hash="")
    config.to_yaml(p)
    auth = AdminAuth(admin_yaml=p, session_secret="test")
    assert auth.verify("admin", "any") is False


def test_session_manager_roundtrip(tmp_path):
    """会话创建和验证"""
    sm = SessionManager(secret="test", timeout=3600)
    token = sm.create_token("admin")
    assert sm.validate_token(token) == "admin"


def test_session_manager_invalid_token(tmp_path):
    """无效令牌返回 None"""
    sm = SessionManager(secret="test", timeout=3600)
    assert sm.validate_token("garbage") is None
    assert sm.validate_token("") is None
