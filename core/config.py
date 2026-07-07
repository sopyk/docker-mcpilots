"""配置加载模块 - 负责加载和验证 settings.yaml 和 auth.yaml"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Settings:
    """服务端配置"""

    host: str = "0.0.0.0"
    port: int = 8900
    log_level: str = "info"
    socket_path: str = "/var/run/docker.sock"
    container_management: bool = True
    image_management: bool = True
    system_diagnostics: bool = True
    timezone: str = "Asia/Shanghai"
    web: dict = None  # type: ignore # web 配置段，默认 None

    @classmethod
    def from_yaml(cls, path: str) -> Settings:
        """从 YAML 文件加载配置"""
        p = Path(path)
        if not p.exists():
            return cls()
        with open(p, "r", encoding="utf-8") as f:
            try:
                data = yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML in {path}: {e}")

        server = data.get("server", {})
        docker_cfg = data.get("docker", {})
        features = data.get("features", {})
        web = data.get("web")

        return cls(
            host=server.get("host", cls.host),
            port=int(server.get("port", cls.port)),
            log_level=server.get("log_level", cls.log_level),
            socket_path=docker_cfg.get("socket_path", cls.socket_path),
            container_management=features.get("container_management", True),
            image_management=features.get("image_management", True),
            system_diagnostics=features.get("system_diagnostics", True),
            timezone=data.get("timezone", cls.timezone),
            web=web
        )

    def get(self, key: str, default=None):
        """支持类似字典的 get 调用，兼容性用"""
        if key == "server":
            return {
                "host": self.host,
                "port": self.port,
                "log_level": self.log_level
            }
        if key == "docker":
            return {"socket_path": self.socket_path}
        if key == "features":
            return {
                "container_management": self.container_management,
                "image_management": self.image_management,
                "system_diagnostics": self.system_diagnostics
            }
        if key == "web":
            return self.web if self.web else {}
        if key == "timezone":
            return self.timezone
        return default


@dataclass
class ScopeConfig:
    """容器级作用域配置"""

    containers_include: list[str] = field(default_factory=list)
    containers_exclude: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict | None) -> ScopeConfig | None:
        if not data:
            return None
        containers = data.get("containers", {})
        return cls(
            containers_include=containers.get("include", []),
            containers_exclude=containers.get("exclude", []),
        )


@dataclass
class RoleConfig:
    """角色配置"""

    description: str = ""
    permissions: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> RoleConfig:
        return cls(
            description=data.get("description", ""),
            permissions=data.get("permissions", []),
        )


@dataclass
class KeyConfig:
    """API Key 配置"""

    key: str = ""
    name: str = ""
    role: str = ""
    scope: ScopeConfig | None = None

    @classmethod
    def from_dict(cls, data: dict) -> KeyConfig:
        return cls(
            key=data.get("key", ""),
            name=data.get("name", ""),
            role=data.get("role", ""),
            scope=ScopeConfig.from_dict(data.get("scope")),
        )


@dataclass
class AuthConfig:
    """权限配置（auth.yaml 的完整内容）"""

    roles: dict[str, RoleConfig] = field(default_factory=dict)
    keys: list[KeyConfig] = field(default_factory=list)
    _key_lookup: dict[str, KeyConfig] = field(default_factory=dict, repr=False)

    @classmethod
    def from_yaml(cls, path: str) -> AuthConfig:
        """从 YAML 文件加载权限配置"""
        p = Path(path)
        if not p.exists():
            raise ValueError(f"Auth config file not found: {path}")

        with open(p, "r", encoding="utf-8") as f:
            try:
                data = yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML in {path}: {e}")

        roles_data = data.get("roles", {})
        keys_data = data.get("keys", [])

        if not roles_data or not keys_data:
            raise ValueError(
                f"Auth config must contain 'roles' and 'keys' sections: {path}"
            )

        roles = {
            name: RoleConfig.from_dict(cfg) for name, cfg in roles_data.items()
        }
        keys = [KeyConfig.from_dict(k) for k in keys_data]
        key_lookup = {k.key: k for k in keys}

        return cls(roles=roles, keys=keys, _key_lookup=key_lookup)

    def find_key(self, api_key: str) -> KeyConfig | None:
        """通过 API Key 字符串查找 KeyConfig"""
        return self._key_lookup.get(api_key)
