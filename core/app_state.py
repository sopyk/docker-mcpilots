"""应用状态模块 - 持有可变配置引用，支持热加载"""
from __future__ import annotations

from typing import TYPE_CHECKING, Union

from core.config import Settings, AuthConfig
from core.auth import PermissionChecker

if TYPE_CHECKING:
    from core.audit import AuditLogger
    from core.docker_client import DockerClient
    from core.system_diag import SystemDiag


class AppState:
    """应用全局状态，持有可变配置引用

    通过 reload_auth() / reload_settings() 实现热加载，
    PermissionChecker 始终读取最新的 auth_config。
    """

    def __init__(self, settings: Settings, auth_config: AuthConfig, audit_logger: "AuditLogger | None" = None):
        self.settings = settings
        self.auth_config = auth_config
        self.audit_logger = audit_logger
        self.docker_client: "DockerClient | None" = None  # 后设置
        self.system_diag: "SystemDiag | None" = None       # 后设置
        self.permission_checker = PermissionChecker(self.auth_config)

    def reload_auth(self, auth_yaml_path: str) -> None:
        """重新加载 auth.yaml，更新 PermissionChecker"""
        new_config = AuthConfig.from_yaml(auth_yaml_path)
        self.auth_config = new_config
        self.permission_checker = PermissionChecker(new_config)

    def reload_settings(self, settings_yaml_path: str) -> None:
        """重新加载 settings.yaml"""
        self.settings = Settings.from_yaml(settings_yaml_path)
