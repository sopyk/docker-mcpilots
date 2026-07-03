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

    def check_permission(self, key_config: KeyConfig, permission: str) -> None:
        """检查 KeyConfig 对应的角色是否拥有指定权限

        Args:
            key_config: 已认证的 KeyConfig
            permission: 权限标识，格式 "resource:action"，如 "container:start"

        Raises:
            PermissionDeniedError: 权限不足
        """
        role = self._auth_config.roles.get(key_config.role)
        if role is None:
            raise PermissionDeniedError(
                f"Role '{key_config.role}' not found for key '{key_config.name}'"
            )

        if self._has_permission(role.permissions, permission):
            return

        raise PermissionDeniedError(
            f"Key '{key_config.name}' (role: {key_config.role}) "
            f"lacks permission '{permission}'"
        )

    def check_scope(self, key_config: KeyConfig, container_name: str) -> None:
        """检查 KeyConfig 的 scope 是否允许操作指定容器

        Args:
            key_config: 已认证的 KeyConfig
            container_name: 目标容器名称

        Raises:
            PermissionDeniedError: scope 限制不允许操作该容器
        """
        scope = key_config.scope
        if scope is None:
            return  # 无 scope 限制

        include = scope.containers_include
        exclude = scope.containers_exclude

        if include:
            matched = any(fnmatch.fnmatch(container_name, pattern) for pattern in include)
            if not matched:
                raise PermissionDeniedError(
                    f"Key '{key_config.name}' scope does not include container '{container_name}'"
                )

        if exclude:
            matched = any(fnmatch.fnmatch(container_name, pattern) for pattern in exclude)
            if matched:
                raise PermissionDeniedError(
                    f"Key '{key_config.name}' scope excludes container '{container_name}'"
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
