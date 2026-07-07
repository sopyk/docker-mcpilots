"""系统设置管理工具函数测试"""
from __future__ import annotations

import yaml
import pytest
from pathlib import Path
from tools.settings_tools import update_settings_from_form


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
