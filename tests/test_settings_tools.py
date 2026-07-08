"""系统设置管理工具函数测试"""
from __future__ import annotations

import bcrypt
import yaml
import pytest
from pathlib import Path
from tools.settings_tools import update_settings_from_form, change_admin_password


@pytest.fixture
def seed_settings(tmp_path):
    def _write(extra=None):
        path = tmp_path / "settings.yaml"
        data = {
            "server": {"host": "0.0.0.0", "port": 8900, "log_level": "info"},
            "docker": {"socket_path": "/var/run/docker.sock"},
            "features": {
                "container_management": True,
                "image_management": True,
                "system_diagnostics": True,
            },
            "timezone": "Asia/Shanghai",
        }
        if extra:
            data.update(extra)
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        return str(path)
    return _write


@pytest.fixture
def seed_admin(tmp_path):
    def _write(username="admin", password="testpass"):
        path = tmp_path / "admin.yaml"
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        data = {"username": username, "password_hash": hashed}
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        return str(path)
    return _write


class TestUpdateSettingsFromForm:
    def test_update_log_level(self, seed_settings):
        path = seed_settings()
        result = update_settings_from_form(path, {"log_level": "debug"})
        assert result["success"] is True
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        assert data["server"]["log_level"] == "debug"

    def test_update_port(self, seed_settings):
        path = seed_settings()
        result = update_settings_from_form(path, {"port": "9000"})
        assert result["success"] is True
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        assert data["server"]["port"] == 9000

    def test_invalid_port(self, seed_settings):
        path = seed_settings()
        result = update_settings_from_form(path, {"port": "abc"})
        assert result["success"] is False
        assert "数字" in result["error"]

    def test_invalid_log_level(self, seed_settings):
        path = seed_settings()
        result = update_settings_from_form(path, {"log_level": "invalid"})
        assert result["success"] is False
        assert "日志级别" in result["error"]

    def test_update_timezone(self, seed_settings):
        path = seed_settings()
        result = update_settings_from_form(path, {"timezone": "UTC"})
        assert result["success"] is True
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        assert data["timezone"] == "UTC"

    def test_toggle_features_off(self, seed_settings):
        path = seed_settings()
        result = update_settings_from_form(path, {
            "container_management": "off",
            "image_management": "off",
            "system_diagnostics": "off",
        })
        assert result["success"] is True
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        assert data["features"]["container_management"] is False
        assert data["features"]["image_management"] is False
        assert data["features"]["system_diagnostics"] is False

    def test_toggle_features_on(self, seed_settings):
        path = seed_settings()
        result = update_settings_from_form(path, {
            "container_management": "on",
            "image_management": "on",
            "system_diagnostics": "on",
        })
        assert result["success"] is True
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        assert data["features"]["container_management"] is True

    def test_update_host_and_socket(self, seed_settings):
        path = seed_settings()
        result = update_settings_from_form(path, {
            "host": "127.0.0.1",
            "socket_path": "/tmp/docker.sock",
        })
        assert result["success"] is True
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        assert data["server"]["host"] == "127.0.0.1"
        assert data["docker"]["socket_path"] == "/tmp/docker.sock"


class TestChangeAdminPassword:
    def test_change_password_success(self, seed_admin):
        path = seed_admin(password="oldpass")
        result = change_admin_password(path, old_password="oldpass", new_password="newpass123")
        assert result["success"] is True
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        assert bcrypt.checkpw(b"newpass123", data["password_hash"].encode()) is True

    def test_change_password_with_new_username(self, seed_admin):
        path = seed_admin(username="olduser", password="testpass")
        result = change_admin_password(path, old_password="testpass", new_password="testpass", new_username="newuser")
        assert result["success"] is True
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        assert data["username"] == "newuser"
        assert bcrypt.checkpw(b"testpass", data["password_hash"].encode()) is True

    def test_fail_wrong_old_password(self, seed_admin):
        path = seed_admin(password="correct")
        result = change_admin_password(path, old_password="wrong", new_password="newpass")
        assert result["success"] is False
        assert "旧密码" in result["error"]

    def test_fail_new_password_too_short(self, seed_admin):
        path = seed_admin(password="testpass")
        result = change_admin_password(path, old_password="testpass", new_password="ab")
        assert result["success"] is False
        assert "6 位" in result["error"]

    def test_change_only_username(self, seed_admin):
        path = seed_admin(username="oldname", password="pass123")
        result = change_admin_password(path, old_password="pass123", new_password="", new_username="newname")
        assert result["success"] is True
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        assert data["username"] == "newname"
        assert bcrypt.checkpw(b"pass123", data["password_hash"].encode()) is True

    def test_change_nothing_returns_success(self, seed_admin):
        path = seed_admin(username="admin", password="pass123")
        result = change_admin_password(path, old_password="pass123", new_password="", new_username="admin")
        assert result["success"] is True