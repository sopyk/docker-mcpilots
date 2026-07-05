"""AppState 热加载模块测试"""
import pytest
from core.app_state import AppState
from core.config import Settings, AuthConfig


def _write_auth_yaml(path, key_name, key_value):
    path.write_text(f"""
roles:
  admin:
    description: "admin"
    permissions: ["*"]
keys:
  - key: "{key_value}"
    name: "{key_name}"
    role: admin
""", encoding="utf-8")


def test_app_state_reload_auth_updates_permission_checker(tmp_path):
    """热加载后，新 Key 生效，旧 Key 失效"""
    auth_yaml = tmp_path / "auth.yaml"
    _write_auth_yaml(auth_yaml, "old", "sk-old")

    state = AppState(settings=Settings(), auth_config=AuthConfig.from_yaml(str(auth_yaml)))
    assert state.permission_checker.authenticate("sk-old").name == "old"

    _write_auth_yaml(auth_yaml, "new", "sk-new")
    state.reload_auth(str(auth_yaml))

    assert state.permission_checker.authenticate("sk-new").name == "new"
    with pytest.raises(Exception):
        state.permission_checker.authenticate("sk-old")


def test_app_state_reload_settings(tmp_path):
    """热加载 settings 后，新配置生效"""
    settings_yaml = tmp_path / "settings.yaml"
    settings_yaml.write_text("""
server:
  host: "127.0.0.1"
  port: 9999
  log_level: "debug"
docker:
  socket_path: "/tmp/docker.sock"
features:
  container_management: false
  image_management: false
  system_diagnostics: false
""", encoding="utf-8")

    state = AppState(settings=Settings(), auth_config=_minimal_auth(tmp_path))
    state.reload_settings(str(settings_yaml))

    assert state.settings.host == "127.0.0.1"
    assert state.settings.port == 9999
    assert state.settings.container_management is False


def test_app_state_permission_checker_compatible_with_auth_config(tmp_path):
    """PermissionChecker 兼容直接传 AuthConfig（向后兼容）"""
    from core.auth import PermissionChecker
    auth_yaml = tmp_path / "auth.yaml"
    _write_auth_yaml(auth_yaml, "test", "sk-test")
    auth_config = AuthConfig.from_yaml(str(auth_yaml))

    checker = PermissionChecker(auth_config)
    assert checker.authenticate("sk-test").name == "test"


def _minimal_auth(tmp_path):
    """生成最小 AuthConfig 供测试用"""
    p = tmp_path / "auth.yaml"
    _write_auth_yaml(p, "seed", "sk-seed")
    return AuthConfig.from_yaml(str(p))
