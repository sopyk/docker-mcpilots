# DockerMaintainer MCP Server 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在群晖 NAS 中以 Docker 容器方式部署 MCP Server，提供 Docker 容器/镜像管理和系统诊断能力，支持 RBAC 权限控制。

**Architecture:** 单体 Python 应用，基于 FastMCP v3.x 框架，通过 Docker Socket 与宿主机通信。自定义 Middleware 实现 API Key 认证和 RBAC 权限检查，权限配置通过 YAML 文件管理，config/secrets 分离挂载。

**Tech Stack:** Python 3.11, FastMCP 3.x, docker Python SDK 7.x, psutil 7.x, PyYAML

---

## Task 1: 项目脚手架与配置模板

**Files:**
- Create: `requirements.txt`
- Create: `templates/settings.yaml`
- Create: `templates/auth.yaml`
- Create: `.gitignore`
- Create: `.dockerignore`

- [ ] **Step 1: 创建 requirements.txt**

```txt
fastmcp>=3.0.0
docker>=7.0.0
psutil>=7.0.0
pyyaml>=6.0
```

- [ ] **Step 2: 创建 templates/settings.yaml**

```yaml
# DockerMaintainer MCP Server 配置文件
# 将此文件复制到 /app/config/settings.yaml 后编辑

server:
  host: "0.0.0.0"
  port: 8900
  log_level: "info"  # debug / info / warning / error

docker:
  socket_path: "/var/run/docker.sock"  # 通常不需要修改

features:
  container_management: true
  image_management: true
  system_diagnostics: true
```

- [ ] **Step 3: 创建 templates/auth.yaml**

```yaml
# DockerMaintainer MCP Server 权限配置文件
# 将此文件复制到 /app/secrets/auth.yaml 后编辑
# 警告：此文件包含敏感信息，请确保文件权限为 600

# --- 角色定义 ---
roles:
  admin:
    description: "完全控制权限"
    permissions:
      - "container:*"
      - "image:*"
      - "system:*"
      - "exec:*"
  operator:
    description: "标准管理权限"
    permissions:
      - "container:list"
      - "container:inspect"
      - "container:start"
      - "container:stop"
      - "container:restart"
      - "container:logs"
      - "container:stats"
      - "image:list"
      - "image:pull"
      - "system:*"
  observer:
    description: "只读权限"
    permissions:
      - "container:list"
      - "container:inspect"
      - "container:logs"
      - "container:stats"
      - "image:list"
      - "system:*"

# --- API Key 绑定 ---
# 每个Key包含: key(密钥), name(标识), role(角色名), scope(可选，容器级限制)
keys:
  - key: "sk-dm-CHANGE-THIS-KEY-IMMEDIATELY"
    name: "default-admin"
    role: admin
    # 请修改上面的key为你自己的安全密钥，格式建议: sk-dm-<用途>-<随机字符串>
```

- [ ] **Step 4: 创建 .gitignore**

```
__pycache__/
*.pyc
*.pyo
.pytest_cache/
*.egg-info/
dist/
build/
.env
config/settings.yaml
secrets/auth.yaml
*.log
.DS_Store
```

- [ ] **Step 5: 创建 .dockerignore**

```
.git
.gitignore
docs/
__pycache__
*.pyc
.pytest_cache
.env
.DS_Store
```

- [ ] **Step 6: Commit**

```bash
git add requirements.txt templates/ .gitignore .dockerignore
git commit -m "chore: add project scaffolding and config templates"
```

---

## Task 2: 配置加载模块

**Files:**
- Create: `core/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: 编写失败的测试**

```python
# tests/test_config.py
"""配置加载模块测试"""
import os
import tempfile
import yaml
import pytest
from pathlib import Path
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
        assert auth.keys[1].scope.containers.include == ["web-*"]

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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/song/Documents/trae_projects/dockermaintainer && python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core'`

- [ ] **Step 3: 实现 core/config.py**

```python
# core/config.py
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

        return cls(
            host=server.get("host", cls.host),
            port=int(server.get("port", cls.port)),
            log_level=server.get("log_level", cls.log_level),
            socket_path=docker_cfg.get("socket_path", cls.socket_path),
            container_management=features.get("container_management", True),
            image_management=features.get("image_management", True),
            system_diagnostics=features.get("system_diagnostics", True),
        )


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

    @property
    def containers_include(self) -> list[str]:
        return self._containers_include

    @containers_include.setter
    def containers_include(self, value: list[str]):
        self._containers_include = value

    @property
    def containers_exclude(self) -> list[str]:
        return self._containers_exclude

    @containers_exclude.setter
    def containers_exclude(self, value: list[str]):
        self._containers_exclude = value


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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/song/Documents/trae_projects/dockermaintainer && python -m pytest tests/test_config.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/__init__.py core/config.py tests/__init__.py tests/test_config.py
git commit -m "feat(config): add settings and auth config loading module"
```

---

## Task 3: 权限检查模块

**Files:**
- Create: `core/auth.py`
- Create: `tests/test_auth.py`

- [ ] **Step 1: 编写失败的测试**

```python
# tests/test_auth.py
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
        # 不应抛出异常
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/song/Documents/trae_projects/dockermaintainer && python -m pytest tests/test_auth.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现 core/auth.py**

```python
# core/auth.py
"""权限检查模块 - API Key 认证、角色权限验证、容器级 Scope 检查"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass

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
            raise AuthenticationError(f"Invalid API key")
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/song/Documents/trae_projects/dockermaintainer && python -m pytest tests/test_auth.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/auth.py tests/test_auth.py
git commit -m "feat(auth): add permission checker with RBAC and scope support"
```

---

## Task 4: Docker 客户端封装

**Files:**
- Create: `core/docker_client.py`
- Create: `tests/test_docker_client.py`

- [ ] **Step 1: 编写失败的测试**

```python
# tests/test_docker_client.py
"""Docker 客户端封装测试（mock Docker SDK）"""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from core.docker_client import DockerClient


@pytest.fixture
def mock_docker_sdk():
    """Mock docker.from_env()"""
    with patch("core.docker_client.docker") as mock_docker_module:
        mock_client = MagicMock()
        mock_docker_module.from_env.return_value = mock_client
        mock_docker_module.errors.NotFound = Exception
        mock_docker_module.errors.APIError = Exception
        yield mock_client


class TestListContainers:
    def test_list_running_containers(self, mock_docker_sdk):
        """列出运行中的容器"""
        mock_container = MagicMock()
        mock_container.name = "web-server"
        mock_container.status = "running"
        mock_container.image.tags = ["nginx:latest"]
        mock_container.id = "abc123"
        mock_docker_sdk.containers.list.return_value = [mock_container]

        client = DockerClient()
        result = client.list_containers(status="running")

        assert len(result) == 1
        assert result[0]["name"] == "web-server"
        assert result[0]["status"] == "running"

    def test_list_all_containers(self, mock_docker_sdk):
        """列出所有容器"""
        c1 = MagicMock()
        c1.name = "web"
        c1.status = "running"
        c1.image.tags = ["nginx"]
        c1.id = "a"
        c2 = MagicMock()
        c2.name = "db"
        c2.status = "exited"
        c2.image.tags = ["postgres"]
        c2.id = "b"
        mock_docker_sdk.containers.list.return_value = [c1, c2]

        client = DockerClient()
        result = client.list_containers(all=True)

        assert len(result) == 2
        mock_docker_sdk.containers.list.assert_called_with(all=True)


class TestContainerOperations:
    def test_start_container(self, mock_docker_sdk):
        """启动容器"""
        mock_container = MagicMock()
        mock_docker_sdk.containers.get.return_value = mock_container

        client = DockerClient()
        result = client.start_container("web-server")

        mock_container.start.assert_called_once()
        assert result["success"] is True

    def test_stop_container(self, mock_docker_sdk):
        """停止容器"""
        mock_container = MagicMock()
        mock_docker_sdk.containers.get.return_value = mock_container

        client = DockerClient()
        result = client.stop_container("web-server")

        mock_container.stop.assert_called_once()
        assert result["success"] is True

    def test_container_not_found(self, mock_docker_sdk):
        """容器不存在时返回错误"""
        from docker.errors import NotFound
        mock_docker_sdk.containers.get.side_effect = NotFound("not found")

        client = DockerClient()
        result = client.start_container("nonexistent")

        assert result["success"] is False
        assert "not found" in result["error"].lower()


class TestContainerLogs:
    def test_get_logs(self, mock_docker_sdk):
        """获取容器日志"""
        mock_container = MagicMock()
        mock_container.logs.return_value = b"line1\nline2\n"
        mock_docker_sdk.containers.get.return_value = mock_container

        client = DockerClient()
        result = client.get_container_logs("web-server", tail=10)

        mock_container.logs.assert_called_with(tail="10", stdout=True, stderr=True)
        assert result == "line1\nline2\n"


class TestContainerStats:
    def test_get_stats(self, mock_docker_sdk):
        """获取容器资源统计"""
        mock_container = MagicMock()
        mock_container.stats.return_value = {
            "cpu_stats": {"cpu_usage": {"total_usage": 1000000}, "system_cpu_usage": 5000000, "online_cpus": 4},
            "memory_stats": {"usage": 104857600, "limit": 524288000},
            "networks": {"eth0": {"rx_bytes": 1000, "tx_bytes": 2000}},
        }
        mock_docker_sdk.containers.get.return_value = mock_container

        client = DockerClient()
        result = client.get_container_stats("web-server")

        assert "cpu_percent" in result
        assert "memory_percent" in result
        assert result["memory_percent"] == 20.0


class TestImageOperations:
    def test_list_images(self, mock_docker_sdk):
        """列出镜像"""
        mock_image = MagicMock()
        mock_image.id = "sha256:abc123"
        mock_image.tags = ["nginx:latest"]
        mock_image.attrs = {"Size": 142000000}
        mock_docker_sdk.images.list.return_value = [mock_image]

        client = DockerClient()
        result = client.list_images()

        assert len(result) == 1
        assert result[0]["tags"] == ["nginx:latest"]

    def test_pull_image(self, mock_docker_sdk):
        """拉取镜像"""
        mock_image = MagicMock()
        mock_image.tags = ["nginx:latest"]
        mock_docker_sdk.images.pull.return_value = mock_image

        client = DockerClient()
        result = client.pull_image("nginx", tag="latest")

        mock_docker_sdk.images.pull.assert_called_with("nginx", tag="latest")
        assert result["success"] is True
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/song/Documents/trae_projects/dockermaintainer && python -m pytest tests/test_docker_client.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 core/docker_client.py**

```python
# core/docker_client.py
"""Docker SDK 封装 - 统一 Docker 容器和镜像操作的接口层"""
from __future__ import annotations

import docker
from docker.errors import NotFound as DockerNotFound, APIError as DockerAPIError


class DockerClient:
    """Docker 客户端封装"""

    def __init__(self, socket_path: str = "/var/run/docker.sock"):
        self._client = docker.from_env()

    # ── 容器操作 ──

    def list_containers(self, status: str | None = None, all: bool = False) -> list[dict]:
        """列出容器"""
        filters = {}
        if status:
            filters["status"] = status
        if all or status == "all":
            containers = self._client.containers.list(all=True, filters=filters if status != "all" else {})
        else:
            containers = self._client.containers.list(filters=filters)

        return [self._format_container(c) for c in containers]

    def get_container(self, container_id: str) -> dict:
        """获取单个容器详情"""
        container = self._client.containers.get(container_id)
        return self._format_container_detail(container)

    def start_container(self, container_id: str) -> dict:
        """启动容器"""
        try:
            container = self._client.containers.get(container_id)
            container.start()
            container.reload()
            return {"success": True, "container": self._format_container(container)}
        except DockerNotFound:
            return {"success": False, "error": f"Container '{container_id}' not found"}
        except DockerAPIError as e:
            return {"success": False, "error": str(e)}

    def stop_container(self, container_id: str) -> dict:
        """停止容器"""
        try:
            container = self._client.containers.get(container_id)
            container.stop()
            container.reload()
            return {"success": True, "container": self._format_container(container)}
        except DockerNotFound:
            return {"success": False, "error": f"Container '{container_id}' not found"}
        except DockerAPIError as e:
            return {"success": False, "error": str(e)}

    def restart_container(self, container_id: str) -> dict:
        """重启容器"""
        try:
            container = self._client.containers.get(container_id)
            container.restart()
            container.reload()
            return {"success": True, "container": self._format_container(container)}
        except DockerNotFound:
            return {"success": False, "error": f"Container '{container_id}' not found"}
        except DockerAPIError as e:
            return {"success": False, "error": str(e)}

    def remove_container(self, container_id: str, force: bool = False) -> dict:
        """删除容器"""
        try:
            container = self._client.containers.get(container_id)
            container.remove(force=force)
            return {"success": True, "removed": container_id}
        except DockerNotFound:
            return {"success": False, "error": f"Container '{container_id}' not found"}
        except DockerAPIError as e:
            return {"success": False, "error": str(e)}

    def get_container_logs(
        self, container_id: str, tail: int | None = None, since: str | None = None
    ) -> str:
        """获取容器日志"""
        container = self._client.containers.get(container_id)
        kwargs = {"stdout": True, "stderr": True}
        if tail is not None:
            kwargs["tail"] = str(tail)
        if since is not None:
            kwargs["since"] = since
        logs = container.logs(**kwargs)
        return logs.decode("utf-8", errors="replace") if isinstance(logs, bytes) else str(logs)

    def get_container_stats(self, container_id: str) -> dict:
        """获取容器实时资源统计（单次采样）"""
        container = self._client.containers.get(container_id)
        raw = container.stats(stream=False, decode=True)

        cpu_percent = 0.0
        cpu_usage = raw.get("cpu_stats", {}).get("cpu_usage", {})
        system_cpu = raw.get("cpu_stats", {}).get("system_cpu_usage", 0)
        online_cpus = raw.get("cpu_stats", {}).get("online_cpus", 1)
        total_usage = cpu_usage.get("total_usage", 0)

        if system_cpu > 0:
            cpu_percent = round((total_usage / system_cpu) * online_cpus * 100.0, 2)

        mem_stats = raw.get("memory_stats", {})
        mem_usage = mem_stats.get("usage", 0)
        mem_limit = mem_stats.get("limit", 1)
        mem_percent = round((mem_usage / mem_limit) * 100.0, 2)

        networks = raw.get("networks", {})
        net_rx = sum(n.get("rx_bytes", 0) for n in networks.values())
        net_tx = sum(n.get("tx_bytes", 0) for n in networks.values())

        return {
            "container_id": container_id,
            "cpu_percent": cpu_percent,
            "memory_usage": mem_usage,
            "memory_limit": mem_limit,
            "memory_percent": mem_percent,
            "network_rx_bytes": net_rx,
            "network_tx_bytes": net_tx,
        }

    # ── 镜像操作 ──

    def list_images(self, name_filter: str | None = None) -> list[dict]:
        """列出镜像"""
        images = self._client.images.list(name=name_filter)
        return [self._format_image(img) for img in images]

    def pull_image(self, image_name: str, tag: str | None = None) -> dict:
        """拉取镜像"""
        try:
            image = self._client.images.pull(image_name, tag=tag or "latest")
            return {
                "success": True,
                "image": self._format_image(image),
                "message": f"Pulled {image_name}:{tag or 'latest'}",
            }
        except DockerAPIError as e:
            return {"success": False, "error": str(e)}

    def remove_image(self, image_id: str, force: bool = False) -> dict:
        """删除镜像"""
        try:
            self._client.images.remove(image_id, force=force)
            return {"success": True, "removed": image_id}
        except DockerNotFound:
            return {"success": False, "error": f"Image '{image_id}' not found"}
        except DockerAPIError as e:
            return {"success": False, "error": str(e)}

    # ── 内部格式化方法 ──

    @staticmethod
    def _format_container(container) -> dict:
        return {
            "id": container.short_id,
            "name": container.name,
            "status": container.status,
            "image": container.image.tags[0] if container.image.tags else str(container.image.id[:12]),
        }

    @staticmethod
    def _format_container_detail(container) -> dict:
        return {
            "id": container.short_id,
            "name": container.name,
            "status": container.status,
            "image": container.image.tags[0] if container.image.tags else str(container.image.id[:12]),
            "created": container.attrs.get("Created", ""),
            "ports": container.attrs.get("NetworkSettings", {}).get("Ports", {}),
            "labels": container.labels,
        }

    @staticmethod
    def _format_image(image) -> dict:
        return {
            "id": image.short_id,
            "tags": image.tags,
            "size": image.attrs.get("Size", 0),
            "created": image.attrs.get("Created", ""),
        }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/song/Documents/trae_projects/dockermaintainer && python -m pytest tests/test_docker_client.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/docker_client.py tests/test_docker_client.py
git commit -m "feat(docker): add Docker client wrapper for container and image operations"
```

---

## Task 5: 系统诊断模块

**Files:**
- Create: `core/system_diag.py`
- Create: `tests/test_system_diag.py`

- [ ] **Step 1: 编写失败的测试**

```python
# tests/test_system_diag.py
"""系统诊断模块测试"""
import pytest
from unittest.mock import patch, MagicMock
from core.system_diag import SystemDiag


class TestGetSystemInfo:
    @patch("core.system_diag.socket.gethostname", return_value="nas-server")
    @patch("core.system_diag.platform.system", return_value="Linux")
    @patch("core.system_diag.platform.release", return_value="5.15.0")
    @patch("core.system_diag.platform.machine", return_value="x86_64")
    @patch("core.system_diag.psutil.boot_time", return_value=1700000000.0)
    def test_returns_system_overview(self, *args):
        diag = SystemDiag()
        info = diag.get_system_info()
        assert info["hostname"] == "nas-server"
        assert info["os"] == "Linux"
        assert info["kernel"] == "5.15.0"
        assert info["architecture"] == "x86_64"
        assert "uptime_seconds" in info


class TestGetCpuInfo:
    @patch("core.system_diag.psutil.cpu_percent", return_value=25.5)
    @patch("core.system_diag.psutil.cpu_count", return_value=4)
    @patch("core.system_diag.psutil.cpu_freq")
    def test_cpu_overall(self, mock_freq, *args):
        mock_freq.return_value = MagicMock(current=2400.0, min=800.0, max=3500.0)
        diag = SystemDiag()
        info = diag.get_cpu_info(per_core=False)
        assert info["percent"] == 25.5
        assert info["count_logical"] == 4
        assert "freq_current_mhz" in info

    @patch("core.system_diag.psutil.cpu_percent", return_value=[10.0, 20.0, 30.0, 40.0])
    @patch("core.system_diag.psutil.cpu_count", return_value=4)
    def test_cpu_per_core(self, *args):
        diag = SystemDiag()
        info = diag.get_cpu_info(per_core=True)
        assert "percent_per_core" in info
        assert len(info["percent_per_core"]) == 4


class TestGetMemoryInfo:
    @patch("core.system_diag.psutil.swap_memory")
    @patch("core.system_diag.psutil.virtual_memory")
    def test_memory_info(self, mock_vm, mock_swap):
        mock_vm.return_value = MagicMock(total=8_000_000_000, available=4_000_000_000, percent=50.0, used=4_000_000_000)
        mock_swap.return_value = MagicMock(total=2_000_000_000, used=500_000_000, percent=25.0, free=1_500_000_000)
        diag = SystemDiag()
        info = diag.get_memory_info()
        assert info["virtual"]["total"] == 8_000_000_000
        assert info["virtual"]["percent"] == 50.0
        assert info["swap"]["total"] == 2_000_000_000


class TestGetDiskInfo:
    @patch("core.system_diag.psutil.disk_usage")
    @patch("core.system_diag.psutil.disk_partitions")
    def test_disk_info(self, mock_partitions, mock_usage):
        mock_partitions.return_value = [
            MagicMock(device="/dev/sda1", mountpoint="/", fstype="ext4", opts="rw"),
        ]
        mock_usage.return_value = MagicMock(total=100_000_000_000, used=40_000_000_000, free=60_000_000_000, percent=40.0)
        diag = SystemDiag()
        info = diag.get_disk_info()
        assert len(info["partitions"]) == 1
        assert info["partitions"][0]["mountpoint"] == "/"
        assert info["partitions"][0]["percent"] == 40.0


class TestGetNetworkInfo:
    @patch("core.system_diag.psutil.net_if_stats")
    @patch("core.system_diag.psutil.net_io_counters")
    def test_network_info(self, mock_io, mock_stats):
        mock_io.return_value = MagicMock(bytes_sent=1000000, bytes_recv=5000000)
        mock_stats.return_value = {
            "eth0": MagicMock(isup=True, speed=1000, mtu=1500),
            "lo": MagicMock(isup=True, speed=0, mtu=65536),
        }
        diag = SystemDiag()
        info = diag.get_network_info()
        assert info["total"]["bytes_sent"] == 1000000
        assert "eth0" in info["interfaces"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/song/Documents/trae_projects/dockermaintainer && python -m pytest tests/test_system_diag.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 core/system_diag.py**

```python
# core/system_diag.py
"""系统诊断模块 - 通过 psutil 采集 CPU、内存、磁盘、网络信息"""
from __future__ import annotations

import datetime
import platform
import socket

import psutil


class SystemDiag:
    """系统诊断信息采集器"""

    def get_system_info(self) -> dict:
        """获取系统概览信息"""
        boot_ts = psutil.boot_time()
        now_ts = datetime.datetime.now().timestamp()
        return {
            "hostname": socket.gethostname(),
            "os": platform.system(),
            "kernel": platform.release(),
            "architecture": platform.machine(),
            "boot_time": datetime.datetime.fromtimestamp(boot_ts).strftime("%Y-%m-%d %H:%M:%S"),
            "uptime_seconds": int(now_ts - boot_ts),
        }

    def get_cpu_info(self, per_core: bool = False) -> dict:
        """获取 CPU 信息"""
        overall = psutil.cpu_percent(interval=0.5)
        result = {
            "percent": overall,
            "count_logical": psutil.cpu_count(logical=True),
            "count_physical": psutil.cpu_count(logical=False),
        }

        try:
            freq = psutil.cpu_freq()
            if freq:
                result["freq_current_mhz"] = freq.current
                result["freq_min_mhz"] = freq.min
                result["freq_max_mhz"] = freq.max
        except Exception:
            pass

        if per_core:
            result["percent_per_core"] = psutil.cpu_percent(interval=0, per_core=True)

        return result

    def get_memory_info(self) -> dict:
        """获取内存使用信息"""
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {
            "virtual": {
                "total": vm.total,
                "used": vm.used,
                "available": vm.available,
                "percent": vm.percent,
            },
            "swap": {
                "total": swap.total,
                "used": swap.used,
                "free": swap.free,
                "percent": swap.percent,
            },
        }

    def get_disk_info(self) -> dict:
        """获取磁盘使用信息（所有分区）"""
        partitions = []
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                partitions.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                    "percent": usage.percent,
                })
            except PermissionError:
                continue

        return {"partitions": partitions}

    def get_network_info(self) -> dict:
        """获取网络流量信息"""
        io = psutil.net_io_counters(pernic=False)
        io_per_nic = psutil.net_io_counters(pernic=True)
        if_stats = psutil.net_if_stats()

        interfaces = {}
        for name, stats in if_stats.items():
            interfaces[name] = {
                "isup": stats.isup,
                "speed": stats.speed,
                "mtu": stats.mtu,
            }

        return {
            "total": {
                "bytes_sent": io.bytes_sent,
                "bytes_recv": io.bytes_recv,
                "packets_sent": io.packets_sent,
                "packets_recv": io.packets_recv,
            },
            "per_interface_io": {
                name: {"bytes_sent": nic.bytes_sent, "bytes_recv": nic.bytes_recv}
                for name, nic in io_per_nic.items()
            },
            "interfaces": interfaces,
        }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/song/Documents/trae_projects/dockermaintainer && python -m pytest tests/test_system_diag.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/system_diag.py tests/test_system_diag.py
git commit -m "feat(diag): add system diagnostics module for CPU/memory/disk/network"
```

---

## Task 6: MCP Tools 定义（容器管理）

**Files:**
- Create: `tools/container_tools.py`

- [ ] **Step 1: 实现 tools/container_tools.py**

```python
# tools/container_tools.py
"""容器管理 MCP Tools"""
from __future__ import annotations

from fastmcp import FastMCP

from core.auth import PermissionChecker, PermissionDeniedError, AuthenticationError
from core.docker_client import DockerClient


def register_container_tools(
    mcp: FastMCP,
    docker_client: DockerClient,
    permission_checker: PermissionChecker,
):
    """注册容器管理相关的 MCP Tools"""

    @mcp.tool
    def list_containers(status: str | None = None) -> list[dict]:
        """列出 Docker 容器。

        Args:
            status: 过滤状态，可选 "running"、"exited"、"all"，不传则返回运行中的容器。
        """
        all_containers = status == "all"
        return docker_client.list_containers(status=status, all=all_containers)

    @mcp.tool
    def inspect_container(container_id: str) -> dict:
        """获取指定容器的详细信息。

        Args:
            container_id: 容器 ID 或名称。
        """
        return docker_client.get_container(container_id)

    @mcp.tool
    def start_container(container_id: str) -> dict:
        """启动指定容器。需要 container:start 权限。

        Args:
            container_id: 容器 ID 或名称。
        """
        result = docker_client.start_container(container_id)
        return result

    @mcp.tool
    def stop_container(container_id: str) -> dict:
        """停止指定容器。需要 container:stop 权限。

        Args:
            container_id: 容器 ID 或名称。
        """
        return docker_client.stop_container(container_id)

    @mcp.tool
    def restart_container(container_id: str) -> dict:
        """重启指定容器。需要 container:restart 权限。

        Args:
            container_id: 容器 ID 或名称。
        """
        return docker_client.restart_container(container_id)

    @mcp.tool
    def get_container_logs(
        container_id: str,
        tail: int | None = None,
    ) -> str:
        """获取容器日志。需要 container:logs 权限。

        Args:
            container_id: 容器 ID 或名称。
            tail: 返回最后 N 行日志，不传则返回全部。
        """
        return docker_client.get_container_logs(container_id, tail=tail)

    @mcp.tool
    def get_container_stats(container_id: str) -> dict:
        """获取容器实时资源占用（CPU、内存、网络）。需要 container:stats 权限。

        Args:
            container_id: 容器 ID 或名称。
        """
        return docker_client.get_container_stats(container_id)

    @mcp.tool
    def remove_container(container_id: str, force: bool = False) -> dict:
        """删除指定容器。需要 container:remove 权限（仅 admin 角色）。

        Args:
            container_id: 容器 ID 或名称。
            force: 是否强制删除运行中的容器。
        """
        return docker_client.remove_container(container_id, force=force)
```

- [ ] **Step 2: Commit**

```bash
git add tools/__init__.py tools/container_tools.py
git commit -m "feat(container): add container management MCP tools"
```

---

## Task 7: MCP Tools 定义（镜像管理 + 系统诊断）

**Files:**
- Create: `tools/image_tools.py`
- Create: `tools/diag_tools.py`

- [ ] **Step 1: 实现 tools/image_tools.py**

```python
# tools/image_tools.py
"""镜像管理 MCP Tools"""
from __future__ import annotations

from fastmcp import FastMCP
from core.docker_client import DockerClient


def register_image_tools(mcp: FastMCP, docker_client: DockerClient):
    """注册镜像管理相关的 MCP Tools"""

    @mcp.tool
    def list_images(name_filter: str | None = None) -> list[dict]:
        """列出本地 Docker 镜像。

        Args:
            name_filter: 按镜像名称过滤，如 "nginx"。
        """
        return docker_client.list_images(name_filter=name_filter)

    @mcp.tool
    def pull_image(image_name: str, tag: str | None = None) -> dict:
        """从 Docker Hub 拉取镜像。需要 image:pull 权限。

        Args:
            image_name: 镜像名称，如 "nginx"。
            tag: 镜像标签，如 "alpine"，不传默认为 "latest"。
        """
        return docker_client.pull_image(image_name, tag=tag)

    @mcp.tool
    def remove_image(image_id: str, force: bool = False) -> dict:
        """删除本地镜像。需要 image:remove 权限（仅 admin 角色）。

        Args:
            image_id: 镜像 ID 或名称（如 "nginx:latest"）。
            force: 是否强制删除。
        """
        return docker_client.remove_image(image_id, force=force)
```

- [ ] **Step 2: 实现 tools/diag_tools.py**

```python
# tools/diag_tools.py
"""系统诊断 MCP Tools"""
from __future__ import annotations

from fastmcp import FastMCP
from core.system_diag import SystemDiag


def register_diag_tools(mcp: FastMCP, system_diag: SystemDiag):
    """注册系统诊断相关的 MCP Tools"""

    @mcp.tool
    def get_system_info() -> dict:
        """获取系统概览信息（主机名、操作系统、内核版本、运行时间）。"""
        return system_diag.get_system_info()

    @mcp.tool
    def get_cpu_info(per_core: bool = False) -> dict:
        """获取 CPU 使用率和信息。

        Args:
            per_core: 是否返回每个逻辑核心的使用率。
        """
        return system_diag.get_cpu_info(per_core=per_core)

    @mcp.tool
    def get_memory_info() -> dict:
        """获取内存使用情况（物理内存和 Swap）。"""
        return system_diag.get_memory_info()

    @mcp.tool
    def get_disk_info() -> dict:
        """获取所有磁盘分区的使用情况。"""
        return system_diag.get_disk_info()

    @mcp.tool
    def get_network_info() -> dict:
        """获取网络接口流量统计。"""
        return system_diag.get_network_info()
```

- [ ] **Step 3: Commit**

```bash
git add tools/image_tools.py tools/diag_tools.py
git commit -m "feat(tools): add image management and system diagnostics MCP tools"
```

---

## Task 8: FastMCP 主入口 + 认证中间件

**Files:**
- Create: `main.py`

- [ ] **Step 1: 实现 main.py**

```python
# main.py
"""DockerMaintainer MCP Server 主入口"""
from __future__ import annotations

import os
import sys
import shutil
import logging
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware, MiddlewareContext

from core.config import Settings, AuthConfig
from core.auth import PermissionChecker, AuthenticationError, PermissionDeniedError
from core.docker_client import DockerClient
from core.system_diag import SystemDiag
from tools.container_tools import register_container_tools
from tools.image_tools import register_image_tools
from tools.diag_tools import register_diag_tools

logger = logging.getLogger("docker-mcp-server")

# ── 常量 ──
CONFIG_DIR = Path(os.environ.get("MCP_CONFIG_DIR", "/app/config"))
SECRETS_DIR = Path(os.environ.get("MCP_SECRETS_DIR", "/app/secrets"))
TEMPLATE_DIR = Path(__file__).parent / "templates"


class AuthMiddleware(Middleware):
    """API Key 认证中间件 — 从 HTTP 请求头提取 Bearer Token 并存入 session state"""

    def __init__(self, permission_checker: PermissionChecker):
        self._checker = permission_checker

    async def on_request(self, context: MiddlewareContext, call_next):
        ctx = context.fastmcp_context
        if ctx and ctx.request_context:
            # 尝试从 session state 获取已认证的 key（同一会话内缓存）
            cached = await ctx.get_state("auth_key_config", default=None)
            if cached is not None:
                return await call_next(context)

            # 从 HTTP 请求头提取 API Key
            try:
                from fastmcp.server.dependencies import get_http_headers
                headers = get_http_headers()
                auth_header = headers.get("authorization", "")
                if not auth_header.startswith("Bearer "):
                    from mcp import McpError
                    from mcp.types import ErrorData
                    raise McpError(ErrorData(code=-32001, message="Missing or invalid authorization header. Format: Bearer <api_key>"))

                api_key = auth_header[7:]
                key_config = self._checker.authenticate(api_key)
                await ctx.set_state("auth_key_config", key_config, serializable=False)
            except AuthenticationError as e:
                from mcp import McpError
                from mcp.types import ErrorData
                raise McpError(ErrorData(code=-32001, message=str(e)))

        return await call_next(context)


def _init_config_files() -> None:
    """首次启动时自动生成默认配置模板"""
    # 确保 config 目录存在
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)

    settings_file = CONFIG_DIR / "settings.yaml"
    if not settings_file.exists():
        template = TEMPLATE_DIR / "settings.yaml"
        shutil.copy2(template, settings_file)
        logger.info(f"Generated default settings: {settings_file}")

    auth_file = SECRETS_DIR / "auth.yaml"
    if not auth_file.exists():
        template = TEMPLATE_DIR / "auth.yaml"
        shutil.copy2(template, auth_file)
        logger.warning(
            f"Generated default auth config: {auth_file}. "
            "IMPORTANT: Edit this file immediately to set your own API keys!"
        )
        # 设置文件权限为 600
        try:
            os.chmod(auth_file, 0o600)
        except OSError:
            logger.warning(f"Could not set permissions on {auth_file}")

    # 确保 secrets 目录下所有文件权限为 600
    for f in SECRETS_DIR.iterdir():
        if f.is_file():
            try:
                os.chmod(f, 0o600)
            except OSError:
                pass


def create_app() -> FastMCP:
    """创建并配置 FastMCP 应用"""
    # 初始化配置文件
    _init_config_files()

    # 加载配置
    settings = Settings.from_yaml(str(CONFIG_DIR / "settings.yaml"))
    auth_config = AuthConfig.from_yaml(str(SECRETS_DIR / "auth.yaml"))
    permission_checker = PermissionChecker(auth_config)

    # 配置日志
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 创建 FastMCP 实例
    mcp = FastMCP(
        name="DockerMaintainer",
        instructions="Docker container and image management server with system diagnostics for Synology NAS.",
        version="0.1.0",
    )

    # 注册认证中间件
    mcp.add_middleware(AuthMiddleware(permission_checker))

    # 创建客户端
    docker_client = DockerClient(socket_path=settings.socket_path)
    system_diag = SystemDiag()

    # 注册 MCP Tools
    if settings.container_management:
        register_container_tools(mcp, docker_client, permission_checker)
    if settings.image_management:
        register_image_tools(mcp, docker_client)
    if settings.system_diagnostics:
        register_diag_tools(mcp, system_diag)

    # 健康检查端点
    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request):
        from starlette.responses import JSONResponse
        return JSONResponse({"status": "ok", "version": "0.1.0"})

    logger.info(f"DockerMaintainer MCP Server ready on {settings.host}:{settings.port}")
    logger.info(f"Registered {len(auth_config.keys)} API key(s)")
    for key_cfg in auth_config.keys:
        logger.info(f"  - {key_cfg.name} (role: {key_cfg.role})")

    return mcp


if __name__ == "__main__":
    mcp = create_app()
    settings = Settings.from_yaml(str(CONFIG_DIR / "settings.yaml"))
    mcp.run(transport="http", host=settings.host, port=settings.port)
```

- [ ] **Step 2: Commit**

```bash
git add main.py
git commit -m "feat: add FastMCP server entry point with auth middleware"
```

---

## Task 9: Dockerfile 与 docker-compose.yml

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`

- [ ] **Step 1: 创建 Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源代码和模板
COPY . .

# 创建数据目录
RUN mkdir -p /app/config /app/secrets

# 非 root 用户运行
RUN groupadd -r mcpuser && useradd -r -g mcpuser -d /app mcpuser
RUN chown -R mcpuser:mcpuser /app
USER mcpuser

EXPOSE 8900

CMD ["python", "main.py"]
```

- [ ] **Step 2: 创建 docker-compose.yml**

```yaml
version: "3.8"

services:
  docker-mcp-server:
    build: .
    image: docker-mcp-server:latest
    container_name: docker-mcp-server
    restart: unless-stopped
    ports:
      - "8900:8900"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./config:/app/config
      - ./secrets:/app/secrets
    environment:
      - TZ=Asia/Shanghai
      - MCP_CONFIG_DIR=/app/config
      - MCP_SECRETS_DIR=/app/secrets
    # 可选：通过环境变量注入 API Key（不挂载 secrets 时使用）
    # environment:
    #   - MCP_AUTH_KEYS=sk-dm-xxx:admin,sk-dm-yyy:operator
```

- [ ] **Step 3: 本地构建测试**

Run: `cd /Users/song/Documents/trae_projects/dockermaintainer && docker build -t docker-mcp-server:latest .`
Expected: Build successful

- [ ] **Step 4: Commit**

```bash
git add Dockerfile docker-compose.yml
git commit -m "feat(deploy): add Dockerfile and docker-compose.yml for deployment"
```

---

## Task 10: 集成测试 + 最终验证

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: 编写集成测试**

```python
# tests/test_integration.py
"""集成测试 - 启动完整 MCP Server 并测试工具调用"""
import pytest
from unittest.mock import patch, MagicMock


class TestServerStartup:
    @patch("main.DockerClient")
    @patch("main.SystemDiag")
    @patch("main.Path")
    @patch("main.os.chmod")
    @patch("main.os.environ.get")
    @patch("builtins.open", create=True)
    def test_create_app_initializes_successfully(
        self, mock_open, mock_env, mock_chmod, mock_path, mock_diag, mock_docker
    ):
        """验证服务启动不报错"""
        from main import create_app

        # Mock 文件系统
        mock_config_dir = MagicMock()
        mock_config_dir.__truediv__ = MagicMock(return_value=MagicMock(exists=lambda: True))
        mock_secrets_dir = MagicMock()
        mock_secrets_dir.__truediv__ = MagicMock(return_value=MagicMock(exists=lambda: True))
        mock_path.return_value.__truediv__ = lambda self, other: MagicMock(
            exists=lambda: True, iterdir=lambda: iter([]), mkdir=MagicMock(), exists=MagicMock(return_value=True)
        )
        mock_path.return_value.mkdir = MagicMock()
        mock_path.return_value.iterdir = MagicMock(return_value=iter([]))

        # Mock 配置加载 - 需要有效的 YAML
        import yaml
        test_settings = {"server": {"host": "0.0.0.0", "port": 8900, "log_level": "info"}}
        test_auth = {
            "roles": {"admin": {"description": "a", "permissions": ["*"]}},
            "keys": [{"key": "sk-test", "name": "test", "role": "admin"}],
        }

        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)
        mock_file.read.return_value = yaml.dump(test_settings)

        mcp = create_app()
        assert mcp.name == "DockerMaintainer"
```

- [ ] **Step 2: 运行全部测试**

Run: `cd /Users/song/Documents/trae_projects/dockermaintainer && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 3: 本地启动验证**

Run: `cd /Users/song/Documents/trae_projects/dockermaintainer && MCP_CONFIG_DIR=./config MCP_SECRETS_DIR=./secrets python main.py`
Expected: Server starts on port 8900, logs show registered API keys

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration tests for server startup"
```

---

## Task 11: 文档收尾 + CHANGELOG

**Files:**
- Create: `CHANGELOG.md`
- Create: `README.md`

- [ ] **Step 1: 创建 CHANGELOG.md**

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] - 2026-07-03

### Added
- FastMCP-based MCP Server running in Docker container
- Container management MCP Tools (list/inspect/start/stop/restart/logs/stats/remove)
- Image management MCP Tools (list/pull/remove)
- System diagnostics MCP Tools (CPU/memory/disk/network/system info)
- RBAC permission system with admin/operator/observer roles
- Container-level scope access control (include/exclude wildcard patterns)
- API Key authentication via YAML config or environment variables
- Config and Secrets separation with persistent volume mounts
- Auto-generation of default config templates on first startup
- Health check endpoint (/health)
- Dockerfile and docker-compose.yml for Synology NAS deployment
```

- [ ] **Step 2: 创建 README.md**

```markdown
# DockerMaintainer MCP Server

在群晖 NAS 中以 Docker 容器方式运行的 MCP Server，提供 Docker 容器/镜像管理能力和系统诊断功能。

## 快速部署

1. 构建镜像：
```bash
docker build -t docker-mcp-server:latest .
```

2. 启动服务：
```bash
docker compose up -d
```

3. 首次启动会自动生成配置模板，编辑 `secrets/auth.yaml` 设置你的 API Key。

4. 重启服务使配置生效：
```bash
docker compose restart
```

## MCP Tools

| 类别 | 工具 | 说明 |
|---|---|---|
| 容器 | `list_containers` | 列出容器 |
| 容器 | `start/stop/restart_container` | 启停重启容器 |
| 容器 | `get_container_logs` | 查看日志 |
| 容器 | `get_container_stats` | 资源占用 |
| 容器 | `remove_container` | 删除容器 |
| 镜像 | `list_images` | 列出镜像 |
| 镜像 | `pull_image` | 拉取镜像 |
| 镜像 | `remove_image` | 删除镜像 |
| 诊断 | `get_system_info` | 系统概览 |
| 诊断 | `get_cpu/memory/disk/network_info` | 资源详情 |

## 权限配置

编辑 `secrets/auth.yaml`，支持 admin/operator/observer 三个预定义角色，可按容器设置 include/exclude scope。

详见 [设计规格书](docs/superpowers/specs/2026-07-01-synology-mcp-server-design.md)。
```

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md README.md
git commit -m "docs: add CHANGELOG and README"
```

- [ ] **Step 4: 打标签**

```bash
git tag -a v0.1.0 -m "release: v0.1.0 - Phase 1 complete"
```
