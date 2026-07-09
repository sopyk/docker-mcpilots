"""权限检查模块 - API Key 认证、角色权限验证、容器级 Scope 检查"""
from __future__ import annotations

import fnmatch

from core.config import AuthConfig, KeyConfig


class AuthenticationError(Exception):
    """API Key 认证失败"""
    pass


class PermissionDeniedError(Exception):
    """权限不足"""
    pass


class PermissionChecker:
    """权限检查器"""

    def __init__(self, auth_config: AuthConfig):
        self._auth_config = auth_config

    def authenticate(self, api_key: str) -> KeyConfig:
        """验证 API Key，返回 KeyConfig 或抛出 AuthenticationError"""
        if not api_key:
            raise AuthenticationError("API key is required")
        key_config = self._auth_config.find_key(api_key)
        if key_config is None:
            raise AuthenticationError("Invalid API key")
        return key_config

    def check_permission(self, key_config: KeyConfig | dict, permission: str) -> None:
        """检查 KeyConfig 对应的角色是否拥有指定权限

        Args:
            key_config: 已认证的 KeyConfig 或 dict
            permission: 权限标识，格式 "resource:action"，如 "container:start"

        Raises:
            PermissionDeniedError: 权限不足
        """
        # 兼容 dict 格式
        if isinstance(key_config, dict):
            role_name = key_config.get("role")
            key_name = key_config.get("name")
        else:
            role_name = getattr(key_config, "role", None)
            key_name = getattr(key_config, "name", None)
            
        role = self._auth_config.roles.get(role_name)
        if role is None:
            raise PermissionDeniedError(
                f"Role '{role_name}' not found for key '{key_name}'"
            )

        if self._has_permission(role.permissions, permission):
            return

        raise PermissionDeniedError(
            f"Key '{key_name}' (role: {role_name}) "
            f"lacks permission '{permission}'"
        )

    def check_scope(self, key_config: KeyConfig | dict, container_name: str) -> None:
        """检查 KeyConfig 的 scope 是否允许操作指定容器

        Args:
            key_config: 已认证的 KeyConfig 或 dict
            container_name: 目标容器名称

        Raises:
            PermissionDeniedError: scope 限制不允许操作该容器
        """
        # 兼容 dict 格式
        if isinstance(key_config, dict):
            scope = key_config.get("scope")
            key_name = key_config.get("name")
        else:
            scope = getattr(key_config, "scope", None)
            key_name = getattr(key_config, "name", None)
            
        if scope is None:
            return  # 无 scope 限制

        # scope 可能也是 dict（如果被序列化了）
        include = None
        exclude = None
        if isinstance(scope, dict):
            include = scope.get("containers_include")
            exclude = scope.get("containers_exclude")
        else:
            include = getattr(scope, "containers_include", None)
            exclude = getattr(scope, "containers_exclude", None)

        if include:
            matched = any(fnmatch.fnmatch(container_name, pattern) for pattern in include)
            if not matched:
                raise PermissionDeniedError(
                    f"Key '{key_name}' scope does not include container '{container_name}'"
                )

        if exclude:
            matched = any(fnmatch.fnmatch(container_name, pattern) for pattern in exclude)
            if matched:
                raise PermissionDeniedError(
                    f"Key '{key_name}' scope excludes container '{container_name}'"
                )

    def check(self, key_config: KeyConfig, permission: str, container_name: str | None = None) -> None:
        """一次性检查权限和 scope（便捷方法）"""
        self.check_permission(key_config, permission)
        if container_name is not None:
            self.check_scope(key_config, container_name)

    @staticmethod
    def _has_permission(permissions: list[str], required: str) -> bool:
        """检查权限列表是否包含所需权限（支持通配符）"""
        resource, action = required.split(":", 1)

        for perm in permissions:
            if perm == "*":
                return True
            perm_resource, perm_action = perm.split(":", 1)
            if perm_resource == "*" or perm_resource == resource:
                if perm_action == "*" or perm_action == action:
                    return True

        return False
