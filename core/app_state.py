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

    def __init__(
        self,
        settings: Settings,
        auth_config: AuthConfig,
        audit_logger: "AuditLogger | None" = None,
        auth_yaml_path: str | None = None,
        settings_yaml_path: str | None = None,
        admin_yaml_path: str | None = None,
    ):
        self.settings = settings
        self.auth_config = auth_config
        self.audit_logger = audit_logger
        self.auth_yaml_path = auth_yaml_path
        self.settings_yaml_path = settings_yaml_path
        self.admin_yaml_path = admin_yaml_path
        self.docker_client: "DockerClient | None" = None
        self.system_diag: "SystemDiag | None" = None
        self.permission_checker = PermissionChecker(self.auth_config)

    def reload_auth(self, auth_yaml_path: str | None = None) -> None:
        """重新加载 auth.yaml，更新 PermissionChecker

        若未传路径，则使用初始化时保存的 auth_yaml_path。
        """
        path = auth_yaml_path or self.auth_yaml_path
        if not path:
            raise ValueError("auth_yaml_path 未设置，无法热加载")
        new_config = AuthConfig.from_yaml(path)
        self.auth_config = new_config
        self.permission_checker = PermissionChecker(new_config)

    def reload_settings(self, settings_yaml_path: str | None = None) -> None:
        """重新加载 settings.yaml

        若未传路径，则使用初始化时保存的 settings_yaml_path。
        """
        path = settings_yaml_path or self.settings_yaml_path
        if not path:
            raise ValueError("settings_yaml_path 未设置，无法热加载")
        self.settings = Settings.from_yaml(path)
