# Docker-MCPilotS MCP Server - Code Wiki

> 🌐 English | [简体中文](CODE_WIKI.md)

> Version: 1.0.0  
> Last Updated: 2026-07-05

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Overall Architecture](#2-overall-architecture)
3. [Directory Structure](#3-directory-structure)
4. [Core Modules](#4-core-modules)
5. [Tool Modules](#5-tool-modules)
6. [Permission Model (RBAC)](#6-permission-model-rbac)
7. [Configuration](#7-configuration)
8. [Deployment & Running](#8-deployment--running)
9. [Testing System](#9-testing-system)
10. [Key Design Decisions](#10-key-design-decisions)
11. [Dependency Graph](#11-dependency-graph)

---

## 1. Project Overview

### 1.1 Project Positioning

Docker-MCPilotS MCP Server is an MCP (Model Context Protocol) server running inside a Docker container, designed specifically for Synology NAS environments. It provides AI Agents with Docker container/image management capabilities and system diagnostics via the standardized MCP protocol, with a built-in RBAC permission control system.

### 1.2 Core Features

| Category | Capability | Description |
|---|---|---|
| Container Management | List/View/Start-Stop/Restart/Delete containers | Supports status filtering |
| Container Management | View container logs | Supports line count limit |
| Container Management | View container resource usage | Real-time CPU, memory, network stats |
| Image Management | List/Pull/Delete images | Supports name filtering |
| System Diagnostics | CPU/Memory/Disk/Network | Collected via psutil |
| System Diagnostics | System overview | Hostname, OS, kernel, uptime |

### 1.3 Tech Stack

- **Language**: Python 3.11
- **MCP Framework**: FastMCP 3.x
- **Docker SDK**: docker Python SDK 7.x
- **System Monitoring**: psutil 7.x
- **Config Format**: YAML
- **Containerization**: Docker + Docker Compose

---

## 2. Overall Architecture

### 2.1 Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│                    MCP Client (AI Agent)                 │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP + JSON-RPC
                           ▼
┌─────────────────────────────────────────────────────────┐
│  ┌───────────────────────────────────────────────────┐  │
│  │              FastMCP HTTP Server                   │  │
│  │  ┌─────────────┐  ┌────────────────────────────┐ │  │
│  │  │ Auth Middle │  │     MCP Tool Registry      │ │  │
│  │  └──────┬──────┘  └──────────┬─────────────────┘ │  │
│  └─────────┼────────────────────┼───────────────────┘  │
│            │                    │                      │
│  ┌─────────▼──────────┐  ┌─────▼──────────┐           │
│  │  PermissionChecker │  │  ContainerTools │           │
│  │  (RBAC + Scope)    │  │  ImageTools     │           │
│  │                    │  │  DiagTools      │           │
│  └─────────┬──────────┘  └─────┬──────────┘           │
│            │                    │                      │
│  ┌─────────▼──────────┐  ┌─────▼──────────┐           │
│  │    AuthConfig      │  │  DockerClient  │           │
│  │    Settings        │  │  SystemDiag    │           │
│  └────────────────────┘  └────────────────┘           │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  entrypoint.sh (PUID/PGID adjust + drop privs)   │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │  Docker Daemon (NAS)   │
              └────────────────────────┘
```

### 2.2 Key Design Principles

1. **Single-Container Architecture**: All features packaged in a single container to minimize resource usage
2. **Lazy Connection**: DockerClient uses lazy loading to avoid blocking on socket permission issues at startup
3. **Config-Secret Separation**: config/ holds non-sensitive config, secrets/ holds sensitive info like API Keys
4. **Permission First**: Auth middleware completes authentication and permission checks before Tool execution
5. **NAS Friendly**: Supports PUID/PGID adjustment to solve Synology volume mount permission issues

---

## 3. Directory Structure

```
docker-mcpilots/
├── main.py                    # FastMCP app entry & auth middleware
├── core/                      # Core business modules
│   ├── __init__.py
│   ├── config.py              # Config loading & dataclass definitions
│   ├── auth.py                # RBAC permission checker
│   ├── docker_client.py       # Docker SDK wrapper layer
│   └── system_diag.py         # System diagnostics collection
├── tools/                     # MCP Tool registration modules
│   ├── __init__.py
│   ├── container_tools.py     # Container management + container diagnostics Tools
│   ├── image_tools.py         # Image management + image diagnostics Tools
│   ├── diag_tools.py          # System diagnostics Tools
│   └── docker_diag_tools.py   # Network and volume diagnostics Tools
├── templates/                 # Default config templates
│   ├── settings.yaml          # Service config template
│   └── auth.yaml              # Permission config template
├── tests/                     # Unit tests
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_auth.py
│   ├── test_docker_client.py
│   ├── test_system_diag.py
│   └── test_integration.py
├── scripts/                   # Helper scripts
│   ├── e2e_test.py            # End-to-end test (24 tools)
│   └── integration_test.py    # Container-level integration test script
├── docker/                    # Docker-related files (isolated)
│   ├── Dockerfile             # Image build definition
│   ├── entrypoint.sh          # Container entry script (UID/GID adjustment)
│   ├── .dockerignore          # Docker build ignore rules
│   ├── docker-compose.yml     # Pre-built image version (recommended)
│   └── docker-compose-build.yml  # Source build version
├── docs/                      # Documentation
│   ├── CODE_WIKI.md           # This document (Chinese)
│   ├── CODE_WIKI_EN.md        # English code wiki
│   ├── deploy-vps.md          # VPS direct install guide (Chinese)
│   ├── deploy-vps_EN.md       # VPS direct install guide (English)
│   ├── plans/                 # Implementation plans
│   └── specs/                 # Design specs
├── requirements.txt           # Python dependencies
├── pytest.ini                 # pytest config
├── CHANGELOG.md               # Changelog (Chinese)
├── CHANGELOG_EN.md            # Changelog (English)
├── LICENSE                    # MIT License
├── README.md                  # Project README (Chinese)
└── README_EN.md               # Project README (English)
```

---

## 4. Core Modules

### 4.1 main.py - Application Entry

**File Path**: [main.py](file:///Users/song/Documents/trae_projects/dockermaintainer/main.py)

**Core Responsibilities**:
- Initialize config files (auto-generate template on first startup)
- Create and configure FastMCP application instance
- Register auth middleware
- Register various MCP Tools
- Provide health check endpoint

**Key Components**:

#### 4.1.1 `AuthMiddleware` Class

**Location**: [main.py#L28-L61](file:///Users/song/Documents/trae_projects/dockermaintainer/main.py#L28-L61)

Auth middleware, implements FastMCP's `Middleware` interface.

**Workflow**:
1. Try to get cached auth info from session state
2. Extract `Authorization: Bearer <api_key>` from HTTP request headers
3. Call `PermissionChecker.authenticate()` to verify the API Key
4. Store auth result into session state (cached within session)
5. On auth failure, raise `McpError` (code: -32001)

**Key Implementation Details**:
- Uses `get_http_headers(include={"authorization"})` to explicitly request authorization header (filtered by FastMCP by default)
- Auth result cached to session via `ctx.set_state("auth_key_config", ...)`
- Must execute before every Tool call

#### 4.1.2 `_init_config_files()` Function

**Location**: [main.py#L64-L128](file:///Users/song/Documents/trae_projects/dockermaintainer/main.py#L64-L128)

Auto-generates default config templates on first startup.

**Execution Steps**:
1. Create config/ and secrets/ directories (if not exist)
2. If settings.yaml doesn't exist, copy from template
3. If auth.yaml doesn't exist, copy from template and set permissions to 600
4. Unify and fix all file permissions under secrets/ to 600

**Error Handling**:
- Provides clear PUID/PGID troubleshooting hints on insufficient permissions
- Compatible with various NAS volume mount permission scenarios

#### 4.1.3 `create_app()` Function

**Location**: [main.py#L131-L180](file:///Users/song/Documents/trae_projects/dockermaintainer/main.py#L131-L180)

Application factory function, creates and configures the complete FastMCP instance.

**Configuration Order**:
1. Initialize config files
2. Load Settings and AuthConfig
3. Create PermissionChecker
4. Configure log level
5. Create FastMCP instance (name="Docker-MCPilotS", version="1.0.0")
6. Register AuthMiddleware
7. Create DockerClient and SystemDiag
8. Register corresponding Tools based on feature toggles
9. Register /health health check endpoint

#### 4.1.4 Health Check Endpoint

**Location**: [main.py#L170-L173](file:///Users/song/Documents/trae_projects/dockermaintainer/main.py#L170-L173)

```python
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    return JSONResponse({"status": "ok", "version": "1.0.0"})
```

No authentication required, used for container health checks and version verification.

---

### 4.2 core/config.py - Configuration Module

**File Path**: [core/config.py](file:///Users/song/Documents/trae_projects/dockermaintainer/core/config.py)

**Core Responsibilities**:
- Define all configuration-related dataclasses
- Provide ability to load config from YAML files
- Maintain API Key lookup index

#### 4.2.1 `Settings` Class

**Location**: [core/config.py#L11-L47](file:///Users/song/Documents/trae_projects/dockermaintainer/core/config.py#L11-L47)

Server main configuration.

**Fields**:

| Field | Type | Default | Description |
|---|---|---|---|
| `host` | str | "0.0.0.0" | Listen address |
| `port` | int | 8900 | Listen port |
| `log_level` | str | "info" | Log level |
| `socket_path` | str | "/var/run/docker.sock" | Docker socket path |
| `container_management` | bool | True | Enable container management |
| `image_management` | bool | True | Enable image management |
| `system_diagnostics` | bool | True | Enable system diagnostics |

**Methods**:
- `from_yaml(path: str) -> Settings`: Load from YAML file; returns default values if file doesn't exist

**YAML Structure**:
```yaml
server:
  host: "0.0.0.0"
  port: 8900
  log_level: "info"
docker:
  socket_path: "/var/run/docker.sock"
features:
  container_management: true
  image_management: true
  system_diagnostics: true
```

#### 4.2.2 `ScopeConfig` Class

**Location**: [core/config.py#L50-L65](file:///Users/song/Documents/trae_projects/dockermaintainer/core/config.py#L50-L65)

Container-level scope configuration, supports wildcard matching.

**Fields**:

| Field | Type | Description |
|---|---|---|
| `containers_include` | list[str] | Whitelist mode, only allow matching containers |
| `containers_exclude` | list[str] | Blacklist mode, exclude matching containers |

**Priority**: include checked first, then exclude (exclude takes priority)

#### 4.2.3 `RoleConfig` Class

**Location**: [core/config.py#L68-L80](file:///Users/song/Documents/trae_projects/dockermaintainer/core/config.py#L68-L80)

Role configuration.

**Fields**:

| Field | Type | Description |
|---|---|---|
| `description` | str | Role description |
| `permissions` | list[str] | Permission list, format "resource:action" |

#### 4.2.4 `KeyConfig` Class

**Location**: [core/config.py#L83-L99](file:///Users/song/Documents/trae_projects/dockermaintainer/core/config.py#L83-L99)

Configuration for a single API Key.

**Fields**:

| Field | Type | Description |
|---|---|---|
| `key` | str | API Key string |
| `name` | str | Key identifier name |
| `role` | str | Associated role name |
| `scope` | ScopeConfig \| None | Container-level scope restriction |

#### 4.2.5 `AuthConfig` Class

**Location**: [core/config.py#L102-L141](file:///Users/song/Documents/trae_projects/dockermaintainer/core/config.py#L102-L141)

Complete permission configuration (in-memory representation of auth.yaml).

**Fields**:

| Field | Type | Description |
|---|---|---|
| `roles` | dict[str, RoleConfig] | Role definition dict |
| `keys` | list[KeyConfig] | API Key list |
| `_key_lookup` | dict[str, KeyConfig] | Key string → KeyConfig fast lookup index |

**Methods**:
- `from_yaml(path: str) -> AuthConfig`: Load from YAML file
- `find_key(api_key: str) -> KeyConfig | None`: Lookup config by key string

**YAML Structure**:
```yaml
roles:
  admin:
    description: "完全控制权限"
    permissions: ["container:*", "image:*", "system:*"]
keys:
  - key: "sk-dm-xxx"
    name: "my-agent"
    role: admin
    scope:
      containers:
        include: ["web-*"]
        exclude: ["web-db"]
```

---

### 4.3 core/auth.py - Permission Check Module

**File Path**: [core/auth.py](file:///Users/song/Documents/trae_projects/dockermaintainer/core/auth.py)

**Core Responsibilities**:
- API Key authentication
- Role permission verification (supports wildcards)
- Container-level Scope checking

#### 4.3.1 Exception Classes

| Exception | Location | Description |
|---|---|---|
| `AuthenticationError` | [auth.py#L9-L11](file:///Users/song/Documents/trae_projects/dockermaintainer/core/auth.py#L9-L11) | API Key authentication failed |
| `PermissionDeniedError` | [auth.py#L14-L16](file:///Users/song/Documents/trae_projects/dockermaintainer/core/auth.py#L14-L16) | Insufficient permissions |

#### 4.3.2 `PermissionChecker` Class

**Location**: [core/auth.py#L19-L108](file:///Users/song/Documents/trae_projects/dockermaintainer/core/auth.py#L19-L108)

Permission checker, the unified entry for all permission decisions.

**Core Methods**:

##### `authenticate(api_key: str) -> KeyConfig`

**Location**: [auth.py#L25-L32](file:///Users/song/Documents/trae_projects/dockermaintainer/core/auth.py#L25-L32)

Verifies API Key, returns the corresponding KeyConfig.

- Empty key → raise `AuthenticationError`
- Key not found → raise `AuthenticationError`
- Success → return `KeyConfig` object

##### `check_permission(key_config: KeyConfig, permission: str) -> None`

**Location**: [auth.py#L34-L56](file:///Users/song/Documents/trae_projects/dockermaintainer/core/auth.py#L34-L56)

Checks whether the role has the specified permission.

- Role doesn't exist → raise `PermissionDeniedError`
- Insufficient permission → raise `PermissionDeniedError`
- Has permission → return normally (no return value)

##### `check_scope(key_config: KeyConfig, container_name: str) -> None`

**Location**: [auth.py#L58-L87](file:///Users/song/Documents/trae_projects/dockermaintainer/core/auth.py#L58-L87)

Checks whether the container is within the allowed scope.

- No scope config → allow directly
- Has include list but doesn't match → deny
- Matches exclude list → deny
- Uses `fnmatch.fnmatch()` for wildcard matching

##### `check(key_config: KeyConfig, permission: str, container_name: str | None = None) -> None`

**Location**: [auth.py#L89-L93](file:///Users/song/Documents/trae_projects/dockermaintainer/core/auth.py#L89-L93)

Convenience method, checks permission and scope in one call.

##### `_has_permission(permissions: list[str], required: str) -> bool`

**Location**: [auth.py#L95-L108](file:///Users/song/Documents/trae_projects/dockermaintainer/core/auth.py#L95-L108)

Static method, determines whether the permission list contains the required permission.

**Wildcard Rules**:
- `"*"` matches all permissions
- `"resource:*"` matches all actions under a resource
- `"*:action"` matches a specific action across all resources
- Exact match `"resource:action"`

---

### 4.4 core/docker_client.py - Docker Client Wrapper

**File Path**: [core/docker_client.py](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py)

**Core Responsibilities**:
- Wrap Docker Python SDK
- Provide lazy connection
- Unify error handling and return format
- Isolate impact of underlying SDK changes

#### 4.4.1 `DockerClient` Class

**Location**: [core/docker_client.py#L13-L210](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L13-L210)

**Constructor Parameters**:
- `socket_path: str = "/var/run/docker.sock"` - Docker socket path

**Design Points**:
- Lazy connection: `_ensure_connected()` only establishes connection on first call
- Import fault tolerance: doesn't error immediately when docker module is missing, only errors on instantiation

##### Container Operation Methods

| Method | Location | Description |
|---|---|---|
| `list_containers(status, all)` | [docker_client.py#L32-L43](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L32-L43) | List containers, supports status filtering |
| `get_container(container_id)` | [docker_client.py#L45-L49](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L45-L49) | Get container details |
| `start_container(container_id)` | [docker_client.py#L51-L62](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L51-L62) | Start container |
| `stop_container(container_id)` | [docker_client.py#L64-L75](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L64-L75) | Stop container |
| `restart_container(container_id)` | [docker_client.py#L77-L88](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L77-L88) | Restart container |
| `remove_container(container_id, force)` | [docker_client.py#L90-L100](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L90-L100) | Remove container |
| `get_container_logs(container_id, tail)` | [docker_client.py#L102-L112](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L102-L112) | Get container logs |
| `get_container_stats(container_id)` | [docker_client.py#L114-L146](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L114-L146) | Get container resource stats (single sample) |

##### Image Operation Methods

| Method | Location | Description |
|---|---|---|
| `list_images(name_filter)` | [docker_client.py#L150-L154](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L150-L154) | List images, supports name filtering |
| `pull_image(image_name, tag)` | [docker_client.py#L156-L167](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L156-L167) | Pull image |
| `remove_image(image_id, force)` | [docker_client.py#L169-L178](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L169-L178) | Remove image |

##### Internal Formatting Methods

| Method | Location | Output Fields |
|---|---|---|
| `_format_container(container)` | [docker_client.py#L182-L189](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L182-L189) | id, name, status, image |
| `_format_container_detail(container)` | [docker_client.py#L191-L201](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L191-L201) | id, name, status, image, created, ports, labels |
| `_format_image(image)` | [docker_client.py#L203-L210](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L203-L210) | id, tags, size, created |

**Error Handling Pattern**:
- Operation methods return `{"success": bool, ...}` format
- Includes result data on success, includes `error` field on failure
- Uniformly catches `DockerNotFound` and `DockerAPIError`

---

### 4.5 core/system_diag.py - System Diagnostics Module

**File Path**: [core/system_diag.py](file:///Users/song/Documents/trae_projects/dockermaintainer/core/system_diag.py)

**Core Responsibilities**:
- Collect system-level diagnostic info
- Cross-platform implementation based on psutil
- Provide structured data output

#### 4.5.1 `SystemDiag` Class

**Location**: [system_diag.py#L11-L115](file:///Users/song/Documents/trae_projects/dockermaintainer/core/system_diag.py#L11-L115)

Stateless info collector, all methods perform immediate collection.

##### Method Descriptions

| Method | Location | Return Fields |
|---|---|---|
| `get_system_info()` | [system_diag.py#L14-L25](file:///Users/song/Documents/trae_projects/dockermaintainer/core/system_diag.py#L14-L25) | hostname, os, kernel, architecture, boot_time, uptime_seconds |
| `get_cpu_info(per_core)` | [system_diag.py#L27-L48](file:///Users/song/Documents/trae_projects/dockermaintainer/core/system_diag.py#L27-L48) | percent, count_logical, count_physical, freq_*, percent_per_core |
| `get_memory_info()` | [system_diag.py#L50-L67](file:///Users/song/Documents/trae_projects/dockermaintainer/core/system_diag.py#L50-L67) | virtual (total/used/available/percent), swap (total/used/free/percent) |
| `get_disk_info()` | [system_diag.py#L69-L87](file:///Users/song/Documents/trae_projects/dockermaintainer/core/system_diag.py#L69-L87) | partitions[] (device/mountpoint/fstype/total/used/free/percent) |
| `get_network_info()` | [system_diag.py#L89-L115](file:///Users/song/Documents/trae_projects/dockermaintainer/core/system_diag.py#L89-L115) | total, per_interface_io, interfaces |

**Notes**:
- CPU usage sampled with 0.5s interval (`interval=0.5`)
- Disk partition read failures are skipped (e.g. insufficient permissions)
- Network info includes total traffic, per-NIC traffic, NIC status

---

## 5. Tool Modules

### 5.1 Overview

Tool modules are located in the `tools/` directory, responsible for registering core business capabilities as MCP Tools. Each module provides a `register_*_tools(mcp, client)` function called at application startup.

**Design Pattern**: Registrar pattern + closures
- Registration function receives MCP instance and business client
- Tool functions defined internally access client via closure
- Registered using `@mcp.tool` decorator

---

### 5.2 tools/container_tools.py - Container Management Tools

**File Path**: [tools/container_tools.py](file:///Users/song/Documents/trae_projects/dockermaintainer/tools/container_tools.py)

**Registration Function**: `register_container_tools(mcp: FastMCP, docker_client: DockerClient)`

**Registered Tools**:

| Tool Name | Parameters | Description | Required Permission |
|---|---|---|---|
| `list_containers` | status?: str | List containers | (read operation) |
| `inspect_container` | container_id: str | Container details | (read operation) |
| `start_container` | container_id: str | Start container | container:start |
| `stop_container` | container_id: str | Stop container | container:stop |
| `restart_container` | container_id: str | Restart container | container:restart |
| `get_container_logs` | container_id: str, tail?: int | Container logs | container:logs |
| `get_container_stats` | container_id: str | Resource stats | container:stats |
| `remove_container` | container_id: str, force?: bool | Remove container | container:remove |

---

### 5.3 tools/image_tools.py - Image Management Tools

**File Path**: [tools/image_tools.py](file:///Users/song/Documents/trae_projects/dockermaintainer/tools/image_tools.py)

**Registration Function**: `register_image_tools(mcp: FastMCP, docker_client: DockerClient)`

**Registered Tools**:

| Tool Name | Parameters | Description | Required Permission |
|---|---|---|---|
| `list_images` | name_filter?: str | List images | (read operation) |
| `pull_image` | image_name: str, tag?: str | Pull image | image:pull |
| `remove_image` | image_id: str, force?: bool | Remove image | image:remove |

---

### 5.4 tools/diag_tools.py - System Diagnostics Tools

**File Path**: [tools/diag_tools.py](file:///Users/song/Documents/trae_projects/dockermaintainer/tools/diag_tools.py)

**Registration Function**: `register_diag_tools(mcp: FastMCP, system_diag: SystemDiag)`

**Registered Tools**:

| Tool Name | Parameters | Description | Required Permission |
|---|---|---|---|
| `get_system_info` | - | System overview | system:info |
| `get_cpu_info` | per_core?: bool | CPU info | system:cpu |
| `get_memory_info` | - | Memory info | system:memory |
| `get_disk_info` | - | Disk info | system:disk |
| `get_network_info` | - | Network info | system:network |

---

## 6. Permission Model (RBAC)

### 6.1 Role Definitions

| Role | Permissions | Description |
|---|---|---|
| **admin** | `container:*`, `image:*`, `system:*`, `exec:*` | Full control |
| **operator** | `container:list/inspect/start/stop/restart/logs/stats`<br>`image:list/pull`<br>`system:*` | Standard management |
| **observer** | `container:list/inspect/logs/stats`<br>`image:list`<br>`system:*` | Read-only |

### 6.2 Permission Naming Convention

Format: `resource:action`

**Resource Categories**:
- `container` - Container operations
- `image` - Image operations
- `system` - System diagnostics
- `exec` - Execute commands (reserved)

### 6.3 Scope Control

Each API Key can configure container-level access scope:

```yaml
keys:
  - key: "sk-dm-xxx"
    name: "home-assistant"
    role: operator
    scope:
      containers:
        include: ["home-*", "nginx"]    # Only allow operating these containers
        exclude: ["home-db"]            # Exclude these (higher priority)
```

**Matching Rules**:
- Uses `fnmatch` wildcard syntax (`*`, `?`, `[seq]`)
- No scope → no restriction
- Only include → whitelist mode
- Only exclude → blacklist mode
- Both present → pass include first, then exclude

### 6.4 Authentication Flow

```
MCP Request
    │
    ▼
AuthMiddleware.on_request()
    │
    ├─► Check session state cache
    │     ├─ Cached → skip, continue execution
    │     └─ Not cached → continue
    │
    ├─► Extract Bearer Token from Authorization header
    │
    ├─► PermissionChecker.authenticate(api_key)
    │     ├─ Invalid → raise McpError(-32001)
    │     └─ Valid → store into session state
    │
    ▼
Tool execution
```

---

## 7. Configuration

### 7.1 Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MCP_CONFIG_DIR` | /app/config | Config file directory |
| `MCP_SECRETS_DIR` | /app/secrets | Secret file directory |
| `PUID` | 1000 | Run user UID (adjusted by entrypoint) |
| `PGID` | 1000 | Run user GID (adjusted by entrypoint) |
| `TZ` | - | Timezone, recommend Asia/Shanghai |

### 7.2 settings.yaml Options

```yaml
server:
  host: "0.0.0.0"        # Listen address
  port: 8900             # Listen port
  log_level: "info"      # debug / info / warning / error

docker:
  socket_path: "/var/run/docker.sock"  # Docker socket path

features:
  container_management: true    # Enable container management
  image_management: true        # Enable image management
  system_diagnostics: true      # Enable system diagnostics
```

### 7.3 auth.yaml Options

See [6. Permission Model](#6-permission-model-rbac) and [AuthConfig Class](#425-authconfig-class).

---

## 8. Deployment & Running

### 8.1 Local Development

**Install Dependencies**:
```bash
pip install -r requirements.txt
```

**Run Directly**:
```bash
python main.py
```

**Using Docker Compose**:
```bash
docker compose up -d --build
```

### 8.2 Synology NAS Deployment

#### 8.2.1 Preparation

1. Build x86_64 image locally (Synology is usually AMD64):
```bash
docker build --platform linux/amd64 -t docker-mcpilots:v1.0.0 -t docker-mcpilots:latest .
```

2. Export and compress the image:
```bash
docker save docker-mcpilots:v1.0.0 docker-mcpilots:latest | gzip > docker-mcpilots-v1.0.0.tar.gz
```

3. Transfer to NAS and load:
```bash
docker load -i docker-mcpilots-v1.0.0.tar.gz
```

#### 8.2.2 Create Directories and Config

```bash
mkdir -p /volume1/docker/docker-mcpilots/{config,secrets}
# Copy docker-compose.yml to this directory
```

#### 8.2.3 Start

```bash
cd /volume1/docker/docker-mcpilots
docker compose up -d
```

On first startup, config templates are auto-generated. Edit `secrets/auth.yaml` to set your API Key, then restart.

### 8.3 Health Check

```bash
curl http://localhost:8900/health
# Returns: {"status":"ok","version":"1.0.0"}
```

### 8.4 MCP Connection Config

Configure HTTP transport in the MCP client:

```json
{
  "mcpServers": {
    "docker-mcpilots": {
      "transport": "http",
      "url": "http://nas-ip:8900/mcp",
      "headers": {
        "Authorization": "Bearer sk-dm-your-api-key"
      }
    }
  }
}
```

---

## 9. Testing System

### 9.1 Test Structure

| Test File | Coverage | Test Type |
|---|---|---|
| `tests/test_config.py` | Config loading, dataclasses | Unit test |
| `tests/test_auth.py` | Authentication, permissions, scope | Unit test |
| `tests/test_docker_client.py` | Docker client wrapper | Unit test (mock) |
| `tests/test_system_diag.py` | System diagnostics | Unit test (mock) |
| `tests/test_integration.py` | App startup, Tool registration | Integration test (mock) |
| `scripts/integration_test.py` | Container-level end-to-end validation | E2E test |

### 9.2 Run Unit Tests

```bash
pytest tests/ -v
```

### 9.3 Run Container Integration Tests

```bash
python scripts/integration_test.py
```

**Test Items**:
1. Version number consistency check
2. Image size reasonableness check
3. Container startup and feature verification (health check, MCP handshake, Tool calls)
4. .dockerignore rules check
5. entrypoint.sh permission check

---

## 10. Key Design Decisions

### 10.1 Lazy Connection

**Decision**: DockerClient only connects to Docker daemon on first call.

**Reasons**:
- Avoid container startup failure due to socket permission/path issues
- Non-Docker operations like health checks are unaffected
- More graceful error reporting (errors surface on actual calls)

### 10.2 Config-Secret Separation

**Decision**: Use two separate directories config/ and secrets/ for non-sensitive config and sensitive info respectively.

**Reasons**:
- Security best practice: separate sensitive info from regular config
- Different backup strategies and permission controls
- Files under secrets/ are automatically set to 600 permissions

### 10.3 PUID/PGID Support

**Decision**: entrypoint.sh supports adjusting the running user's UID/GID via environment variables.

**Reasons**:
- Synology NAS volume mount permission issues are a common pain point
- Start as root, adjust UID/GID, then drop privileges with gosu
- Compatible with common practices of official Docker images

**0.1.3 Fix Highlights**:
- `gosu` privilege dropping clears all supplementary groups, causing `group_add` config in `docker-compose.yml` to be ineffective
- Solution: at entrypoint.sh startup, as root, change the group of `/var/run/docker.sock` to mcpuser's primary group (PGID)
- Last line of entrypoint changed from `gosu mcpuser "$@"` to `exec gosu mcpuser "$@"` (cleaner process replacement)
- DockerClient switched to explicit `unix://` socket path connection, avoiding instability of `docker.from_env()` in non-root environments

### 10.4 Single-Container Architecture

**Decision**: All features packaged in a single container.

**Reasons**:
- Minimize resource usage (NAS environments have limited resources)
- Simplify deployment and management
- High feature coupling, splitting brings no clear benefit

### 10.5 .dockerignore Optimization

**Decision**: Exclude *.tar.gz, config/, secrets/, and other large files and runtime data.

**Effects**:
- Image size reduced from ~1.2GB to ~75MB
- Faster builds, lower transfer cost

### 10.6 Session-Level Auth Cache

**Decision**: Auth result stored in FastMCP session state, reused within the same session.

**Reasons**:
- MCP protocol is session-based, no need to re-authenticate multiple calls within the same session
- Reduces auth.yaml read count
- Improves performance (though overhead is small)

---

## 11. Dependency Graph

### 11.1 Module Dependencies

```
main.py
  ├── core.config (Settings, AuthConfig)
  ├── core.auth (PermissionChecker, AuthenticationError)
  ├── core.docker_client (DockerClient)
  ├── core.system_diag (SystemDiag)
  ├── tools.container_tools (register_container_tools)
  ├── tools.image_tools (register_image_tools)
  └── tools.diag_tools (register_diag_tools)

tools.container_tools
  └── core.docker_client (DockerClient)

tools.image_tools
  └── core.docker_client (DockerClient)

tools.diag_tools
  └── core.system_diag (SystemDiag)

core.auth
  └── core.config (AuthConfig, KeyConfig)

core.docker_client
  └── docker (third-party SDK)

core.system_diag
  └── psutil (third-party library)
```

### 11.2 Third-Party Dependencies

| Package | Version Requirement | Purpose |
|---|---|---|
| fastmcp | >=3.0.0 | MCP service framework |
| docker | >=7.0.0 | Docker API client |
| psutil | >=7.0.0 | System info collection |
| pyyaml | >=6.0 | YAML config parsing |

### 11.3 Runtime Dependencies

- Docker daemon (communicates via unix socket)
- Linux environment (psutil is cross-platform, but the main target is NAS Linux)

---

## Appendix: Version History

| Version | Date | Major Changes |
|---|---|---|
| 1.0.0 | 2026-07-05 | First official release: project renamed to Docker-MCPilotS, complete bilingual docs, amd64 image build, LICENSE/MIT |
| 0.1.3 | 2026-07-04 | Fix docker.sock group permission (gosu clearing supplementary groups), Docker SDK explicit socket connection |
| 0.1.2 | 2026-07-03 | Fix version number consistency, add .dockerignore, optimize image size |
| 0.1.1 | 2026-07-03 | Add PUID/PGID support, fix NAS permission issues |
| 0.1.0 | 2026-07-03 | Initial version, core features complete |

---

*This document is auto-generated from code analysis, last updated 2026-07-05*
