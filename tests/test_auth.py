"""权限检查模块测试"""
import pytest

from core.config import AuthConfig, KeyConfig, RoleConfig, ScopeConfig
from core.auth import PermissionChecker, PermissionDeniedError, AuthenticationError


@pytest.fixture
def auth_config():
    """构建测试用权限配置"""
    return AuthConfig(
        roles={
            "admin": RoleConfig(
                description="完全控制",
                permissions=["container:*", "image:*", "system:*", "exec:*"],
            ),
            "operator": RoleConfig(
                description="标准管理",
                permissions=[
                    "container:list",
                    "container:start",
                    "container:stop",
                    "container:restart",
                    "container:logs",
                    "container:stats",
                    "image:list",
                    "image:pull",
                    "system:*",
                ],
            ),
            "observer": RoleConfig(
                description="只读",
                permissions=[
                    "container:list",
                    "container:logs",
                    "container:stats",
                    "image:list",
                    "system:*",
                ],
            ),
        },
        keys=[
            KeyConfig(key="sk-admin", name="admin", role="admin"),
            KeyConfig(
                key="sk-op-scoped",
                name="home-op",
                role="operator",
                scope=ScopeConfig(
                    containers_include=["home-*"],
                    containers_exclude=["home-db"],
                ),
            ),
            KeyConfig(key="sk-observer", name="monitor", role="observer"),
        ],
        _key_lookup={
            "sk-admin": None,
            "sk-op-scoped": None,
            "sk-observer": None,
        },
    )


class TestAuthenticate:
    def test_valid_key_returns_key_config(self, auth_config):
        """有效API Key返回KeyConfig"""
        auth_config._key_lookup["sk-admin"] = auth_config.keys[0]
        checker = PermissionChecker(auth_config)
        result = checker.authenticate("sk-admin")
        assert result.key == "sk-admin"
        assert result.role == "admin"

    def test_invalid_key_raises(self, auth_config):
        """无效API Key抛出AuthenticationError"""
        checker = PermissionChecker(auth_config)
        with pytest.raises(AuthenticationError, match="Invalid API key"):
            checker.authenticate("sk-nonexistent")

    def test_empty_key_raises(self, auth_config):
        """空Key抛出AuthenticationError"""
        checker = PermissionChecker(auth_config)
        with pytest.raises(AuthenticationError):
            checker.authenticate("")


class TestCheckPermission:
    def test_admin_has_all_permissions(self, auth_config):
        """admin角色拥有所有权限"""
        key_cfg = auth_config.keys[0]
        checker = PermissionChecker(auth_config)
        checker.check_permission(key_cfg, "container:remove")
        checker.check_permission(key_cfg, "exec:run")

    def test_operator_allowed_operations(self, auth_config):
        """operator角色允许标准操作"""
        key_cfg = auth_config.keys[1]
        checker = PermissionChecker(auth_config)
        checker.check_permission(key_cfg, "container:start")
        checker.check_permission(key_cfg, "system:cpu")
        checker.check_permission(key_cfg, "image:pull")

    def test_operator_denied_operations(self, auth_config):
        """operator角色拒绝高级操作"""
        key_cfg = auth_config.keys[1]
        checker = PermissionChecker(auth_config)
        with pytest.raises(PermissionDeniedError, match="container:remove"):
            checker.check_permission(key_cfg, "container:remove")
        with pytest.raises(PermissionDeniedError, match="exec:run"):
            checker.check_permission(key_cfg, "exec:run")

    def test_wildcard_permission_matches(self, auth_config):
        """通配符权限匹配"""
        key_cfg = auth_config.keys[1]  # operator, has system:*
        checker = PermissionChecker(auth_config)
        checker.check_permission(key_cfg, "system:cpu")
        checker.check_permission(key_cfg, "system:memory")
        checker.check_permission(key_cfg, "system:disk")

    def test_observer_read_only(self, auth_config):
        """observer只能读取"""
        key_cfg = auth_config.keys[2]
        checker = PermissionChecker(auth_config)
        checker.check_permission(key_cfg, "container:list")
        checker.check_permission(key_cfg, "container:logs")
        with pytest.raises(PermissionDeniedError):
            checker.check_permission(key_cfg, "container:start")


class TestCheckScope:
    def test_no_scope_allows_all(self, auth_config):
        """无scope配置允许所有容器"""
        key_cfg = auth_config.keys[0]  # admin, no scope
        checker = PermissionChecker(auth_config)
        checker.check_scope(key_cfg, "any-container")

    def test_include_wildcard_match(self, auth_config):
        """include通配符匹配"""
        key_cfg = auth_config.keys[1]  # scope: home-*
        checker = PermissionChecker(auth_config)
        checker.check_scope(key_cfg, "home-assistant")
        checker.check_scope(key_cfg, "home-bridge")

    def test_include_wildcard_reject(self, auth_config):
        """include通配符不匹配时拒绝"""
        key_cfg = auth_config.keys[1]  # scope: include=home-*
        checker = PermissionChecker(auth_config)
        with pytest.raises(PermissionDeniedError, match="scope"):
            checker.check_scope(key_cfg, "plex")

    def test_exclude_overrides_include(self, auth_config):
        """exclude优先于include"""
        key_cfg = auth_config.keys[1]  # include=home-*, exclude=home-db
        checker = PermissionChecker(auth_config)
        with pytest.raises(PermissionDeniedError, match="scope"):
            checker.check_scope(key_cfg, "home-db")

    def test_exact_name_include(self):
        """精确名称匹配（无通配符）"""
        scope = ScopeConfig(containers_include=["plex", "jellyfin"])
        key_cfg = KeyConfig(key="sk-test", name="test", role="operator", scope=scope)
        auth_cfg = AuthConfig(
            roles={"operator": RoleConfig(permissions=["container:*"])},
            keys=[key_cfg],
            _key_lookup={"sk-test": key_cfg},
        )
        checker = PermissionChecker(auth_cfg)
        checker.check_scope(key_cfg, "plex")
        checker.check_scope(key_cfg, "jellyfin")
        with pytest.raises(PermissionDeniedError):
            checker.check_scope(key_cfg, "transmission")
