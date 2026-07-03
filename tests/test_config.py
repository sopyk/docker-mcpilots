"""配置加载模块测试"""
import os
import tempfile
import yaml
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import Settings, AuthConfig, RoleConfig, KeyConfig, ScopeConfig


class TestSettings:
    def test_load_settings_from_file(self):
        """从YAML文件加载服务配置"""
        data = {
            "server": {"host": "0.0.0.0", "port": 8900, "log_level": "info"},
            "docker": {"socket_path": "/var/run/docker.sock"},
            "features": {
                "container_management": True,
                "image_management": True,
                "system_diagnostics": True,
            },
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(data, f)
            f.flush()
            settings = Settings.from_yaml(f.name)

        assert settings.host == "0.0.0.0"
        assert settings.port == 8900
        assert settings.log_level == "info"
        assert settings.socket_path == "/var/run/docker.sock"
        assert settings.container_management is True

    def test_settings_defaults(self):
        """配置文件缺失时使用默认值"""
        settings = Settings()
        assert settings.host == "0.0.0.0"
        assert settings.port == 8900
        assert settings.log_level == "info"

    def test_settings_invalid_yaml_raises(self):
        """无效YAML抛出异常"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("{{{invalid")
            f.flush()
            with pytest.raises(ValueError):
                Settings.from_yaml(f.name)


class TestAuthConfig:
    def _write_auth_yaml(self, data: dict) -> str:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(data, f)
            return f.name

    def test_load_roles_and_keys(self):
        """加载角色和API Key配置"""
        data = {
            "roles": {
                "admin": {
                    "description": "完全控制",
                    "permissions": ["container:*", "image:*"],
                },
                "observer": {
                    "description": "只读",
                    "permissions": ["container:list", "image:list"],
                },
            },
            "keys": [
                {
                    "key": "sk-test-admin",
                    "name": "test-admin",
                    "role": "admin",
                },
                {
                    "key": "sk-test-obs",
                    "name": "test-observer",
                    "role": "observer",
                    "scope": {"containers": {"include": ["web-*"]}},
                },
            ],
        }
        path = self._write_auth_yaml(data)
        auth = AuthConfig.from_yaml(path)

        assert "admin" in auth.roles
        assert auth.roles["admin"].permissions == ["container:*", "image:*"]
        assert len(auth.keys) == 2
        assert auth.keys[0].key == "sk-test-admin"
        assert auth.keys[1].scope is not None

    def test_key_lookup(self):
        """通过API Key字符串查找配置"""
        data = {
            "roles": {"admin": {"description": "a", "permissions": ["*"]}},
            "keys": [
                {"key": "sk-findme", "name": "finder", "role": "admin"},
            ],
        }
        path = self._write_auth_yaml(data)
        auth = AuthConfig.from_yaml(path)

        found = auth.find_key("sk-findme")
        assert found is not None
        assert found.name == "finder"

        not_found = auth.find_key("sk-nonexist")
        assert not_found is None

    def test_empty_auth_raises(self):
        """空配置文件抛出异常"""
        path = self._write_auth_yaml({})
        with pytest.raises(ValueError):
            AuthConfig.from_yaml(path)
