# Docker-MCPilotS — Code Wiki

> 🌐 English | [简体中文](CODE_WIKI.md)
>
> Version: 1.0.0 ｜ Last Updated: 2026-07-05 ｜ Code Baseline: `main` branch

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Overall Architecture](#2-overall-architecture)
3. [Directory Structure](#3-directory-structure)
4. [Core Modules (core/)](#4-core-modules-core)
5. [Tool Modules (tools/)](#5-tool-modules-tools)
6. [Application Entry & Middleware (main.py)](#6-application-entry--middleware-mainpy)
7. [Permission Model (RBAC + Scope)](#7-permission-model-rbac--scope)
8. [MCP Tools Overview](#8-mcp-tools-overview)
9. [Configuration](#9-configuration)
10. [Containerization & Deployment](#10-containerization--deployment)
11. [Testing System](#11-testing-system)
12. [Dependencies](#12-dependencies)
13. [Key Design Decisions](#13-key-design-decisions)
14. [Security Model & Capability Boundaries](#14-security-model--capability-boundaries)
15. [Version History](#15-version-history)

---

## 1. Project Overview

### 1.1 Positioning

**Docker-MCPilotS** is an MCP (Model Context Protocol) server running inside a Docker container, designed primarily for Synology NAS but usable on any Docker-capable machine. It exposes **controlled** Docker management and system diagnostic capabilities to AI Agents (OpenClaw, Hermes, Trae, Cursor, Claude Code, Codex, etc.) via the standardized MCP protocol.

The core philosophy is a "**Docker management tool in a sandbox**": don't hand over SSH access to the Agent — only expose allowed operations through the MCP interface, preventing accidental damage to the special NAS system. The project was developed through "Vibe Coding".

### 1.2 Core Capabilities

| Category | Capability | Notes |
|---|---|---|
| Container Management | List / Inspect / Start / Stop / Restart / Remove | Status filtering supported |
| Container Logs | View logs | Supports `tail` / `since` / `until` / `timestamps`, relative time (`1h`/`30m`/`2d`) and RFC3339 |
| Container Resources | Real-time CPU / Memory / Network | Single sample |
| Container Diagnostics | Processes / Health / Network / Mounts / Filesystem Changes / Image Details | Designed around "troubleshooting" |
| Image Management | List / Pull / Remove / Inspect | `docker build` not exposed |
| Network Topology | List all Docker networks and connected containers | Read-only |
| Volume Inventory | List all data volumes and mount points | Read-only |
| System Diagnostics | Host CPU / Memory / Disk / Network / Overview | Based on psutil |
| Access Control | RBAC three roles + container-level Scope | admin / operator / observer |

### 1.3 Tech Stack

- **Language**: Python 3.11
- **MCP Framework**: FastMCP 3.x (HTTP + JSON-RPC transport)
- **Docker SDK**: docker Python SDK 7.x
- **System Monitoring**: psutil 7.x
- **Config Format**: PyYAML 6.x
- **Containerization**: Docker + Docker Compose
- **Base Image**: `python:3.11-slim`, single-container architecture, ~50MB memory

---

## 2. Overall Architecture

### 2.1 Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   MCP Client (AI Agent)                      │
│   OpenClaw / Hermes / Trae / Cursor / Claude Code / Codex    │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP + JSON-RPC (Bearer Token)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  FastMCP HTTP Server (created by main.py)                    │
│  ┌──────────────────┐   ┌────────────────────────────────┐  │
│  │  AuthMiddleware   │   │       MCP Tool Registry        │  │
│  │ (Bearer extract   │   │  container / image / diag ...  │  │
│  │  + cache)         │   │                                │  │
│  └────────┬─────────┘   └─────────────┬──────────────────┘  │
│           │                           │                      │
│  ┌────────▼──────────┐   ┌────────────▼─────────────────┐   │
│  │ PermissionChecker │   │  DockerClient / SystemDiag    │   │
│  │ (RBAC + Scope)    │   │  (core business clients)      │   │
│  └────────┬──────────┘   └────────────┬─────────────────┘   │
│           │                           │                      │
│  ┌────────▼────────────────────────────▼─────────────────┐  │
│  │  AuthConfig / Settings (YAML loaded, in-memory dataclasses)│
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  entrypoint.sh (root adjusts UID/GID + docker.sock    │  │
│  │  group) → gosu drops to mcpuser, runs main.py         │  │
│  └───────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │ unix:///var/run/docker.sock
                           ▼
              ┌────────────────────────────┐
              │   Docker Daemon (NAS host)  │
              └────────────────────────────┘
```

### 2.2 Request Processing Flow

```
MCP HTTP Request
   │
   ▼
AuthMiddleware.on_request()
   ├─► Check session state cache (auth_key_config)
   │     ├─ Cached → skip auth, pass through
   │     └─ Not cached → continue
   ├─► Extract Bearer <api_key> from Authorization header
   │     └─ Missing/bad format → raise McpError(-32001)
   ├─► PermissionChecker.authenticate(api_key)
   │     ├─ Invalid → raise McpError(-32001)
   │     └─ Valid → store KeyConfig in session state (serializable)
   ▼
MCP Tool Execution (tools/call)
   ├─► Tool function calls DockerClient / SystemDiag
   │     └─ Business layer returns {"success": bool, ...}
   ▼
JSON-RPC Response (SSE / JSON)
```

> Note: In the current implementation, fine-grained RBAC/Scope checking is provided by `PermissionChecker`; authentication is done in the middleware. The permission matrix is declared in `auth.yaml`'s `roles` section.

### 2.3 Key Design Principles

1. **Single-container architecture** — All features in one container, minimal resource usage (~50MB memory)
2. **Lazy connection** — `DockerClient` uses lazy loading to avoid blocking on socket permission issues at startup
3. **Config-secret separation** — `config/` for non-sensitive config, `secrets/` for API Keys (auto 600 permissions)
4. **Permission-first** — Auth middleware completes authentication before Tool execution
5. **NAS friendly** — `entrypoint.sh` supports PUID/PGID adjustment, solving Synology volume mount permission pain points

---

## 3. Directory Structure

```
docker-mcpilots/
├── main.py                    # FastMCP app entry + AuthMiddleware + config init
├── core/                      # Core business modules
│   ├── __init__.py
│   ├── config.py              # Config dataclasses + YAML loading
│   ├── auth.py                # RBAC permission checker
│   ├── docker_client.py       # Docker SDK wrapper layer (lazy loading)
│   └── system_diag.py         # System diagnostics (psutil)
├── tools/                     # MCP Tool registration modules
│   ├── __init__.py
│   ├── container_tools.py     # Container management + diagnostics Tools (13)
│   ├── image_tools.py         # Image management + diagnostics Tools (4)
│   ├── diag_tools.py          # System diagnostics Tools (5)
│   └── docker_diag_tools.py   # Network/volume diagnostics Tools (2, always registered)
├── templates/                 # Default config templates (auto-copied on first start)
│   ├── settings.yaml
│   └── auth.yaml
├── tests/                     # Unit/integration tests
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_auth.py
│   ├── test_docker_client.py
│   ├── test_system_diag.py
│   └── test_integration.py
├── scripts/                   # Helper scripts
│   ├── e2e_test.py            # End-to-end test (24 tools)
│   └── integration_test.py    # Container-level integration test
├── docker/                    # Docker-related files (isolated)
│   ├── Dockerfile
│   ├── entrypoint.sh          # UID/GID adjustment + privilege drop entrypoint
│   ├── .dockerignore
│   ├── docker-compose.yml         # Pre-built image version (recommended)
│   └── docker-compose-build.yml   # Source build version
├── docs/                      # Documentation
│   ├── guides/               # User guides (deploy/access/toolbox/web-ui)
│   ├── en/                   # English docs
│   ├── wiki/                 # Code wiki
│   ├── plans/                # Implementation plans
│   ├── specs/                # Design specs
│   └── testing/              # Test plans & results
├── web/static/assets/        # Branding (banner / logo / favicon)
├── requirements.txt
├── pytest.ini
├── CHANGELOG.md / CHANGELOG_EN.md
├── LICENSE                    # MIT
├── README.md / README_EN.md
└── .gitignore
```

---

## 4. Core Modules (core/)

### 4.1 core/config.py — Configuration Loading & Dataclasses

**Responsibility**: Define all config-related `dataclass` types, provide YAML loading, maintain API Key lookup index.

#### 4.1.1 `Settings` Class

**Location**: [config.py](../../core/config.py)

Server main config, corresponds to `config/settings.yaml`.

| Field | Type | Default | Description |
|---|---|---|---|
| `host` | str | `"0.0.0.0"` | Listen address |
| `port` | int | `8900` | Listen port |
| `log_level` | str | `"info"` | Log level (debug/info/warning/error) |
| `socket_path` | str | `"/var/run/docker.sock"` | Docker socket path |
| `container_management` | bool | `True` | Enable container management Tools |
| `image_management` | bool | `True` | Enable image management Tools |
| `system_diagnostics` | bool | `True` | Enable system diagnostics Tools |

**Methods**:
- `from_yaml(path) -> Settings`: Load from YAML; returns defaults if file doesn't exist; raises `ValueError` on invalid YAML

#### 4.1.2 `ScopeConfig` Class

Container-level scope config, supports wildcard matching (`fnmatch` syntax).

| Field | Type | Description |
|---|---|---|
| `containers_include` | list[str] | Whitelist — only allow matching containers |
| `containers_exclude` | list[str] | Blacklist — exclude matching containers (higher priority than include) |

**Methods**: `from_dict(data) -> ScopeConfig | None` (returns None if no data, meaning no restriction)

#### 4.1.3 `RoleConfig` Class

Role configuration.

| Field | Type | Description |
|---|---|---|
| `description` | str | Role description |
| `permissions` | list[str] | Permission list, format `"resource:action"`, supports `*` wildcard |

#### 4.1.4 `KeyConfig` Class

Single API Key configuration.

| Field | Type | Description |
|---|---|---|
| `key` | str | API Key string |
| `name` | str | Key identifier (used in logs) |
| `role` | str | Associated role name |
| `scope` | ScopeConfig \| None | Container-level scope restriction |

#### 4.1.5 `AuthConfig` Class

Complete permission config (in-memory representation of `auth.yaml`).

| Field | Type | Description |
|---|---|---|
| `roles` | dict[str, RoleConfig] | Role definition dict |
| `keys` | list[KeyConfig] | API Key list |
| `_key_lookup` | dict[str, KeyConfig] | Key string → KeyConfig O(1) lookup index (`repr=False`) |

**Methods**:
- `from_yaml(path) -> AuthConfig`: Load and validate that both `roles` and `keys` exist, build lookup index
- `find_key(api_key) -> KeyConfig | None`: O(1) lookup

---

### 4.2 core/auth.py — Permission Check Module

**Responsibility**: API Key authentication, role permission verification (wildcards), container-level Scope checking.

#### 4.2.1 Exception Classes

| Exception | Description |
|---|---|
| `AuthenticationError` | API Key auth failed (empty/invalid) |
| `PermissionDeniedError` | Insufficient permission or Scope restriction |

#### 4.2.2 `PermissionChecker` Class

**Location**: [auth.py](../../core/auth.py)

Unified entry point for all permission decisions. Injected with `AuthConfig` at construction.

| Method | Signature | Behavior |
|---|---|---|
| `authenticate` | `(api_key: str) -> KeyConfig` | Empty/not found → `AuthenticationError`; success returns `KeyConfig` |
| `check_permission` | `(key_config, permission: str) -> None` | Role missing or insufficient → `PermissionDeniedError` |
| `check_scope` | `(key_config, container_name: str) -> None` | No scope → pass; include mismatch → deny; exclude match → deny |
| `check` | `(key_config, permission, container_name=None) -> None` | Convenience method, checks permission then scope |
| `_has_permission` *(static)* | `(permissions, required) -> bool` | Core wildcard matching logic |

**Wildcard rules** (`_has_permission`):
- `"*"` → matches all permissions
- `"resource:*"` → matches all actions under that resource
- `"*:action"` → matches that action across all resources
- `"resource:action"` → exact match

**Scope matching rules** (`check_scope`, using `fnmatch.fnmatch`):
- No scope → no restriction
- Only include → whitelist mode
- Only exclude → blacklist mode
- Both present → pass include first, then exclude (exclude takes priority)

---

### 4.3 core/docker_client.py — Docker Client Wrapper

**Responsibility**: Wrap Docker Python SDK with lazy connection, unified error handling, and structured return format; isolate underlying SDK changes.

#### 4.3.1 Module-level Helper Functions

| Function | Location | Description |
|---|---|---|
| `_parse_since_until(value)` | [docker_client.py](../../core/docker_client.py) | Parse log time params: relative (`1h`/`30m`/`2d`/`45s`) or RFC3339/ISO, returns timezone-aware datetime |
| `_extract_mounts(attrs)` | same file | Extract mount info list from container attrs |
| `_extract_health(state)` | same file | Extract health check info (status/failing_streak/log) from container state |
| `_change_kind_str(kind)` | same file | Docker filesystem change type `0/1/2` → `modified/added/deleted` |

#### 4.3.2 `DockerClient` Class

**Constructor**: `socket_path: str = "/var/run/docker.sock"`

**Design highlights**:
- **Lazy connection**: `_ensure_connected()` only connects on first call via `docker.DockerClient(base_url=f"unix://{socket_path}")`
- **Import fault tolerance**: `docker=None` when module not installed; `RuntimeError` only on instantiation
- **Unified error handling**: catches `DockerNotFound` / `DockerAPIError`, returns `{"success": False, "error": ...}`

##### Container Operations

| Method | Parameters | Returns |
|---|---|---|
| `list_containers` | `status?, all` | `list[dict]` (id/name/status/image) |
| `get_container` | `container_id` | Detail dict (state/health/config/network/mounts) |
| `start_container` | `container_id` | `{"success", "container"}` |
| `stop_container` | `container_id` | `{"success", "container"}` |
| `restart_container` | `container_id` | `{"success", "container"}` |
| `remove_container` | `container_id, force` | `{"success", "removed"}` |
| `get_container_logs` | `container_id, tail?, since?, until?, timestamps` | `{"success", "container_id", "logs"}` |
| `get_container_stats` | `container_id` | CPU/memory/network stats (single sample) |

##### Container Diagnostic Methods

| Method | Troubleshooting Scenario |
|---|---|
| `get_container_processes` | Container process list (`container.top()`) |
| `get_container_health` | Health check status + failure logs |
| `get_container_networks` | IP/gateway/MAC/DNS/port mappings |
| `get_container_mounts` | Volumes/bind paths/read-write permissions |
| `get_container_changes` | Filesystem additions/modifications/deletions (`container.diff()`, fallback None→[]) |

##### Image Operations

| Method | Parameters | Returns |
|---|---|---|
| `list_images` | `name_filter?` | `list[dict]` (id/tags/size/created) |
| `pull_image` | `image_name, tag?` | `{"success", "image", "message"}` |
| `remove_image` | `image_name, force` | `{"success", "removed"}` |
| `inspect_image` | `image_name` | Image details (cmd/entrypoint/env/ports/history etc.) |

##### Docker Resource Methods

| Method | Description |
|---|---|
| `list_networks` | All Docker networks (id/name/driver/scope/subnet/containers) |
| `list_volumes` | All Docker volumes (name/driver/mountpoint/created/in_use) |

##### Internal Formatting Methods (static)

| Method | Output Fields |
|---|---|
| `_format_container` | id, name, status, image |
| `_format_container_detail` | id, name, status, image, created, labels, state, health, config, network, mounts |
| `_format_image` | id, tags, size, created |

**Return format convention**: Operation methods uniformly return `{"success": bool, ...}`; result data on success, `error` field on failure.

---

### 4.4 core/system_diag.py — System Diagnostics Module

**Responsibility**: Collect host-level system diagnostic info via psutil. All methods are real-time collection, stateless.

#### `SystemDiag` Class

**Location**: [system_diag.py](../../core/system_diag.py)

| Method | Return Fields |
|---|---|
| `get_system_info()` | hostname, os, kernel, architecture, boot_time, uptime_seconds |
| `get_cpu_info(per_core=False)` | percent, count_logical, count_physical, freq_current/min/max_mhz, percent_per_core (optional) |
| `get_memory_info()` | virtual{total,used,available,percent}, swap{total,used,free,percent} |
| `get_disk_info()` | partitions[]{device,mountpoint,fstype,total,used,free,percent} |
| `get_network_info()` | total{bytes_sent/recv,packets_sent/recv}, per_interface_io, interfaces{isup,speed,mtu} |

**Notes**:
- CPU usage sampled with 0.5s interval (`psutil.cpu_percent(interval=0.5)`)
- Disk partition read failures (permission denied) are skipped
- Network info includes total traffic, per-NIC traffic, NIC status

---

## 5. Tool Modules (tools/)

### 5.1 Design Pattern: Registrar + Closure

Tool modules uniformly use the "registrar pattern + closures":
- Each module exports a `register_*_tools(mcp: FastMCP, client)` function
- Internally defines Tool functions via `@mcp.tool` decorator, accessing client via closure
- Called sequentially in `create_app()` based on feature toggles

```python
def register_container_tools(mcp: FastMCP, docker_client: DockerClient):
    @mcp.tool
    def list_containers(status: str | None = None, all: bool = False) -> list[dict]:
        """List Docker containers."""
        return docker_client.list_containers(status=status, all=all)
    # ... more Tools
```

### 5.2 tools/container_tools.py — Container Management Tools

**Registration function**: `register_container_tools(mcp, docker_client)` (13 Tools)

| Tool | Parameters | Description | Troubleshooting |
|---|---|---|---|
| `list_containers` | `status?, all` | List containers | — |
| `inspect_container` | `container_id` | Container details (state/health/config/network/mounts) | Won't start / status abnormal |
| `start_container` | `container_id` | Start container | — |
| `stop_container` | `container_id` | Stop container | — |
| `restart_container` | `container_id` | Restart container | — |
| `get_container_logs` | `container_id, tail?, since?, until?, timestamps` | Logs (time range support) | Error diagnosis |
| `get_container_stats` | `container_id` | CPU/memory/network | Resource usage |
| `remove_container` | `container_id, force?` | Remove container (admin only) | — |
| `get_container_processes` | `container_id` | Process list | Container stuck |
| `get_container_health` | `container_id` | Health check + failure logs | Container unhealthy |
| `get_container_networks` | `container_id` | IP/gateway/DNS/ports | Network issues |
| `get_container_mounts` | `container_id` | Volumes/read-write permissions | Data loss / permission issues |
| `get_container_changes` | `container_id` | Filesystem changes | What changed in container |

### 5.3 tools/image_tools.py — Image Management Tools

**Registration function**: `register_image_tools(mcp, docker_client)` (4 Tools)

| Tool | Parameters | Description |
|---|---|---|
| `list_images` | `name_filter?` | List local images |
| `pull_image` | `image_name, tag?` | Pull image (default latest) |
| `remove_image` | `image_name, force?` | Remove image (admin only) |
| `inspect_image` | `image_name` | Image details (entrypoint/env/ports/history) |

### 5.4 tools/diag_tools.py — System Diagnostics Tools

**Registration function**: `register_diag_tools(mcp, system_diag)` (5 Tools)

| Tool | Parameters | Description |
|---|---|---|
| `get_system_info` | — | Hostname/OS/kernel/uptime |
| `get_cpu_info` | `per_core?` | CPU usage and info |
| `get_memory_info` | — | Physical memory + Swap |
| `get_disk_info` | — | All partition usage |
| `get_network_info` | — | NIC traffic and status |

### 5.5 tools/docker_diag_tools.py — Docker Resource Diagnostics Tools

**Registration function**: `register_docker_diag_tools(mcp, docker_client)` (2 Tools, **always registered**, unaffected by feature toggles — needed for container troubleshooting)

| Tool | Description |
|---|---|
| `list_networks` | All Docker networks and connected containers (troubleshoot "can containers reach each other") |
| `list_volumes` | All Docker volumes and mount points (troubleshoot "where is data stored") |

---

## 6. Application Entry & Middleware (main.py)

**Location**: [main.py](../../main.py)

### 6.1 Constants & Environment Variables

```python
CONFIG_DIR   = Path(os.environ.get("MCP_CONFIG_DIR",   "/app/config"))
SECRETS_DIR  = Path(os.environ.get("MCP_SECRETS_DIR",  "/app/secrets"))
TEMPLATE_DIR = Path(__file__).parent / "templates"
```

### 6.2 `AuthMiddleware` Class

**Location**: [main.py](../../main.py) (`Middleware` subclass)

API Key auth middleware, implements FastMCP's `Middleware` interface.

**Workflow**:
1. Read `auth_key_config` from session state; if cached, pass through directly
2. Call `get_http_headers(include={"authorization"})` to explicitly extract authorization header (FastMCP filters this header by default — must explicitly include)
3. Validate `Bearer <api_key>` format, otherwise raise `McpError(-32001)`
4. Call `PermissionChecker.authenticate(api_key)` to verify
5. Store `KeyConfig` in session state (`serializable=True`, persisted across requests)

**Exception mapping**: `AuthenticationError` → `McpError(code=-32001, message=...)`

### 6.3 `_init_config_files()` Function

Auto-generates default config templates on first startup.

**Execution steps**:
1. Create `config/` and `secrets/` directories (if not exist)
2. If `settings.yaml` doesn't exist, copy from `templates/settings.yaml`
3. If `auth.yaml` doesn't exist, copy from template + `chmod 600`, print warning to change default key
4. Unify all file permissions under `secrets/` to `600`

**Error handling**: Provides clear PUID/PGID troubleshooting hints on permission errors (NAS volume mount compatibility).

### 6.4 `create_app()` Function

Application factory, creates and configures the complete FastMCP instance.

**Configuration order**:
1. `_init_config_files()` initialize config
2. Load `Settings` and `AuthConfig`
3. Create `PermissionChecker`
4. Configure log level
5. Create `FastMCP(name="Docker-MCPilotS", version="1.0.0")`
6. Register `AuthMiddleware`
7. Create `DockerClient` (lazy) and `SystemDiag`
8. **Register Tools based on feature toggles**:
   - `container_management` → `register_container_tools`
   - `image_management` → `register_image_tools`
   - `system_diagnostics` → `register_diag_tools`
   - `register_docker_diag_tools` **always registered** (network/volume diagnostics for troubleshooting)
9. Register `/health` health check endpoint
10. Log registered API Key count and roles

### 6.5 Health Check Endpoint

```python
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    return JSONResponse({"status": "ok", "version": "1.0.0"})
```

No authentication required, used for container health checks and version verification.

### 6.6 Startup Entry

```python
if __name__ == "__main__":
    mcp = create_app()
    settings = Settings.from_yaml(str(CONFIG_DIR / "settings.yaml"))
    mcp.run(transport="http", host=settings.host, port=settings.port)
```

---

## 7. Permission Model (RBAC + Scope)

### 7.1 Role Definitions (templates/auth.yaml defaults)

| Role | Permissions | Description |
|---|---|---|
| **admin** | `container:*`, `image:*`, `system:*`, `exec:*` | Full control (including delete) |
| **operator** | `container:list/inspect/start/stop/restart/logs/stats`<br>`image:list/pull`<br>`system:*` | Standard management (no delete) |
| **observer** | `container:list/inspect/logs/stats`<br>`image:list`<br>`system:*` | Read-only |

### 7.2 Permission Naming Convention

Format: `resource:action`
- Resource categories: `container` / `image` / `system` / `exec` (reserved)
- Wildcards: `*` (full wildcard) / `resource:*` (resource wildcard) / `*:action` (action wildcard)

### 7.3 Container-level Scope

Each API Key can configure container-level access scope:

```yaml
keys:
  - key: "sk-dm-xxx"
    name: "home-assistant"
    role: operator
    scope:
      containers:
        include: ["home-*", "nginx"]   # Whitelist
        exclude: ["home-db"]           # Blacklist (higher priority)
```

Matching uses `fnmatch` wildcards (`*` `?` `[seq]`).

### 7.4 Auth State Persistence

Auth result stored via `ctx.set_state("auth_key_config", key_config, serializable=True)` in FastMCP session state. The MCP protocol is session-based; reuse within the same session avoids repeated `auth.yaml` reads.

---

## 8. MCP Tools Overview

The project registers **24 MCP Tools** total, dynamically loaded based on feature toggles (`docker_diag_tools` always loaded):

| Module | Tool Count | Tool List |
|---|---|---|
| container_tools | 13 | list_containers, inspect_container, start_container, stop_container, restart_container, get_container_logs, get_container_stats, remove_container, get_container_processes, get_container_health, get_container_networks, get_container_mounts, get_container_changes |
| image_tools | 4 | list_images, pull_image, remove_image, inspect_image |
| diag_tools | 5 | get_system_info, get_cpu_info, get_memory_info, get_disk_info, get_network_info |
| docker_diag_tools | 2 | list_networks, list_volumes |
| **Total** | **24** | |

---

## 9. Configuration

### 9.1 Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MCP_CONFIG_DIR` | `/app/config` | Config file directory |
| `MCP_SECRETS_DIR` | `/app/secrets` | Secrets file directory |
| `PUID` | `1000` | Run user UID (adjusted by entrypoint) |
| `PGID` | `1000` | Run user GID (adjusted by entrypoint) |
| `TZ` | — | Timezone, recommend `Asia/Shanghai` |

### 9.2 settings.yaml (`config/settings.yaml`)

```yaml
server:
  host: "0.0.0.0"
  port: 8900
  log_level: "info"        # debug / info / warning / error
docker:
  socket_path: "/var/run/docker.sock"
features:
  container_management: true
  image_management: true
  system_diagnostics: true
```

### 9.3 auth.yaml (`secrets/auth.yaml`, permissions 600)

```yaml
roles:
  admin:
    description: "Full control"
    permissions: ["container:*", "image:*", "system:*", "exec:*"]
  operator:
    description: "Standard management"
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
    description: "Read-only"
    permissions:
      - "container:list"
      - "container:inspect"
      - "container:logs"
      - "container:stats"
      - "image:list"
      - "system:*"

keys:
  - key: "sk-dm-CHANGE-THIS-KEY-IMMEDIATELY"
    name: "default-admin"
    role: admin
    # scope:                         # Optional, container-level restriction
    #   containers:
    #     include: ["web-*"]
    #     exclude: ["web-db"]
```

---

## 10. Containerization & Deployment

### 10.1 Dockerfile Highlights

**Location**: [docker/Dockerfile](../../docker/Dockerfile)

- Base image `python:3.11-slim`
- Install `gosu` (for privilege dropping)
- Precise copy of `core/` `tools/` `main.py` `templates/`, avoiding `.venv/tests/docs/scripts` in the image
- Create `mcpuser` user, `/app/config` `/app/secrets` directories
- `EXPOSE 8900`, `ENTRYPOINT ["/app/entrypoint.sh"]`, `CMD ["python", "main.py"]`

### 10.2 entrypoint.sh Highlights

**Location**: [docker/entrypoint.sh](../../docker/entrypoint.sh)

Core script for solving NAS volume mount permission issues:

1. Read `PUID`/`PGID` (default 1000)
2. If current `mcpuser` UID/GID differs from target, use `usermod`/`groupmod` to adjust, and `chown` files under `/app`
3. `chown` mount directories `config/` `secrets/` to target UID/GID
4. **Key fix**: If `/var/run/docker.sock` exists, as root `chgrp` its group to `PGID` (because `gosu` privilege drop clears supplementary groups — `group_add` approach is ineffective)
5. `exec gosu mcpuser "$@"` drops privileges to run main program (`exec` for clean process replacement)

### 10.3 Three Deployment Methods

#### Method 1: Pre-built Image (Recommended, NAS / General Linux)

```bash
mkdir docker-mcpilots && cd docker-mcpilots
mkdir config secrets
# Copy templates/settings.yaml → config/settings.yaml
# Copy templates/auth.yaml   → secrets/auth.yaml (change API Key!)
# Place docker/docker-compose.yml
docker compose up -d
```

Image registries:
- GHCR: `ghcr.io/sopyk/docker-mcpilots:latest`
- Docker Hub: `sopyk/docker-mcpilots:latest`

#### Method 2: Source Build (Developers)

```bash
git clone https://github.com/sopyk/docker-mcpilots.git
cd docker-mcpilots
docker compose -f docker/docker-compose-build.yml up -d --build
```

#### Method 3: VPS Host Direct Install

No Docker nesting, lowest resource usage, supports systemd / nginx reverse proxy / TLS. See [docs/deploy-vps.md](deploy-vps.md).

### 10.4 Supported Architectures

| Architecture | Status | Applicable Devices |
|---|---|---|
| linux/amd64 | ✅ Supported | Synology/QNAP Intel/AMD NAS, most VPS, PC servers |
| linux/arm64 | ✅ Supported | Raspberry Pi, Mac M series, some ARM NAS |
| linux/arm/v7 | ❌ Not supported | Older 32-bit ARM devices |

### 10.5 Health Check

```bash
curl http://localhost:8900/health
# {"status":"ok","version":"1.0.0"}
```

### 10.6 MCP Client Connection Config

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

## 11. Testing System

### 11.1 Test Structure

| File | Coverage | Type |
|---|---|---|
| `tests/test_config.py` | Config loading, dataclasses | Unit test |
| `tests/test_auth.py` | Auth, permissions, Scope (including wildcards) | Unit test |
| `tests/test_docker_client.py` | Docker client wrapper (mock SDK) | Unit test |
| `tests/test_system_diag.py` | System diagnostics (mock psutil) | Unit test |
| `tests/test_integration.py` | App startup, Tool registration, config init | Integration test (mock) |
| `scripts/e2e_test.py` | Simulated MCP client calling all 24 tools | End-to-end test |
| `scripts/integration_test.py` | Image build/start/handshake/Tool calls | Container-level integration test |

### 11.2 Running Tests

```bash
# Unit tests
pytest tests/ -v

# End-to-end test (requires server running)
docker run -d --name dm-e2e-test alpine sh -c 'while true; do echo heartbeat; sleep 5; done'
MCP_CONFIG_DIR=./config MCP_SECRETS_DIR=./secrets python main.py &
python scripts/e2e_test.py
docker rm -f dm-e2e-test

# Container integration test (requires built image)
python scripts/integration_test.py
```

### 11.3 e2e_test.py Verification Items

1. MCP handshake (initialize / initialized)
2. Tool list (tools/list, expects 24)
3. 5 system diagnostic tools
4. Container tools (list / inspect / logs / stats + 5 diagnostic tools) + error paths for nonexistent containers
5. Image tools (list / inspect)
6. Docker resource diagnostics (list_networks / list_volumes)

### 11.4 integration_test.py Verification Items

1. Version number consistency (main.py vs health check)
2. Image size reasonableness (>1GB warns)
3. Container startup + health check + MCP handshake + Tool calls
4. `.dockerignore` rules check
5. `entrypoint.sh` execute permission check

---

## 12. Dependencies

### 12.1 Module Dependency Graph

```
main.py
  ├── core.config        (Settings, AuthConfig)
  ├── core.auth          (PermissionChecker, AuthenticationError)
  ├── core.docker_client (DockerClient)
  ├── core.system_diag   (SystemDiag)
  ├── tools.container_tools      (register_container_tools)
  ├── tools.image_tools          (register_image_tools)
  ├── tools.diag_tools           (register_diag_tools)
  └── tools.docker_diag_tools    (register_docker_diag_tools)

tools.container_tools   └── core.docker_client (DockerClient)
tools.image_tools       └── core.docker_client (DockerClient)
tools.docker_diag_tools └── core.docker_client (DockerClient)
tools.diag_tools        └── core.system_diag   (SystemDiag)

core.auth       └── core.config (AuthConfig, KeyConfig)
core.docker_client └── docker   (third-party SDK)
core.system_diag   └── psutil   (third-party library)
```

### 12.2 Third-party Dependencies (requirements.txt)

| Package | Version Requirement | Purpose |
|---|---|---|
| `fastmcp` | `>=3.0.0` | MCP service framework (HTTP transport + middleware) |
| `docker` | `>=7.0.0` | Docker Engine API client |
| `psutil` | `>=7.0.0` | Cross-platform system info collection |
| `pyyaml` | `>=6.0` | YAML config parsing |

### 12.3 Runtime Dependencies

- **Docker daemon**: communicates via `unix:///var/run/docker.sock`
- **Linux environment**: psutil is cross-platform, but the main target is NAS Linux
- **gosu**: in-container privilege dropping (installed by Dockerfile)

### 12.4 Call Chain (using `start_container` as example)

```
MCP Client
  → FastMCP HTTP Server
  → AuthMiddleware.on_request (Bearer extraction + PermissionChecker.authenticate)
  → tools/container_tools.py :: start_container (closure)
  → core/docker_client.py :: DockerClient.start_container
  → _ensure_connected() → docker.DockerClient(...).containers.get(id).start()
  → Returns {"success": true, "container": {...}}
  → JSON-RPC Response
```

---

## 13. Key Design Decisions

### 13.1 Lazy Connection

`DockerClient` only connects to Docker daemon on first call.
- Avoids container startup failure due to socket permission/path issues
- Non-Docker operations like health checks remain unaffected
- Errors surface on actual calls, making them more diagnosable

### 13.2 Config-Secret Separation

`config/` (non-sensitive) and `secrets/` (sensitive) in separate directories:
- Security best practice
- Files under `secrets/` auto `chmod 600`
- Different backup strategies and permission controls

### 13.3 PUID/PGID + gosu Privilege Drop

`entrypoint.sh` starts as root → adjusts `mcpuser` UID/GID → `chown`s mount volumes → `chgrp`s docker.sock → `exec gosu mcpuser` drops privileges and runs.
- Solves Synology NAS volume mount permission pain point
- **Key fix** (v0.1.3): `gosu` privilege drop clears supplementary groups, making `group_add` ineffective; solution is to change docker.sock group directly to `PGID` as root
- **Key fix** (v0.1.3): `docker.from_env()` is unstable in non-root environments; switched to explicit `unix://` socket connection

### 13.4 Single-Container Architecture

All features packaged in a single container:
- Minimal resource usage (NAS resources are limited, ~50MB memory)
- Simplified deployment and management
- High feature coupling, splitting brings no clear benefit

### 13.5 .dockerignore Optimization

Excluding `*.tar.gz`, `config/`, `secrets/`, `.git`, `__pycache__`, etc.:
- Image size reduced from ~1.2GB to ~75MB
- Faster builds, lower transfer cost

### 13.6 Session-Level Auth Cache

Auth result stored in FastMCP session state (`serializable=True`):
- MCP protocol is session-based, reuse auth within same session
- Reduces `auth.yaml` reads
- **Key fix** (v0.1.2): `get_state()` doesn't accept `default=None`; `get_http_headers()` filters `authorization` by default, needs `include={"authorization"}`; `set_state()` needs `serializable=True`

### 13.7 Always Register Docker Resource Diagnostics

`register_docker_diag_tools` (network/volume) is unaffected by feature toggles and always registered — because troubleshooting containers requires network and volume information.

---

## 14. Security Model & Capability Boundaries

### 14.1 What It Can Do (Controlled Exposure)

- Containers: list/inspect/start/stop/restart/remove
- Logs: time range filtering
- Resources: real-time CPU/memory/network
- Diagnostics: processes/health/network/mounts/filesystem changes/image details
- Networks & volumes: read-only view
- System: host CPU/memory/disk/network
- Access control: three roles + container-level Scope

### 14.2 What It Cannot Do (Security Limits)

| Limitation | Reason |
|---|---|
| Compose project management (`docker compose up/down`) | Docker SDK doesn't support Compose; only single containers |
| Edit Compose files | Container cannot access host compose files |
| Build images | `docker build` not exposed for security |
| Execute arbitrary commands | No `docker exec` — prevents command injection |
| Modify Docker network config | Read-only view; cannot create/delete/modify |

### 14.3 Security Recommendations

- Always change the default API Key in production
- Restrict container scope to only necessary permissions
- Access via reverse proxy with TLS
- Default listen is local loopback only — do not expose directly to public internet
- Regularly check logs

---

## 15. Version History

| Version | Date | Major Changes |
|---|---|---|
| 1.0.0 | 2026-07-04 | First official release: renamed to Docker-MCPilotS, bilingual docs, amd64 image, MIT LICENSE |
| 0.1.4 | 2026-07-04 | Added 8 container/image/network/volume diagnostic tools, log enhancement since/until/timestamps, VPS deploy guide |
| 0.1.3 | 2026-07-04 | Fixed docker.sock group permission (gosu clearing supplementary groups), Docker SDK explicit socket connection |
| 0.1.2 | 2026-07-03 | Fixed FastMCP 3.4.2 compatibility, auth middleware header filtering, auth state persistence; .dockerignore optimized image to 75MB |
| 0.1.1 | 2026-07-03 | PUID/PGID support, gosu privilege drop, Synology compose file |
| 0.1.0 | 2026-07-03 | Initial version: FastMCP MCP Server, container/image/system diagnostic Tools, RBAC, API Key auth, config/secrets separation, health check |

---

## Appendix: Common Troubleshooting Scenario → Tool Mapping

| User Question | Tools Agent Will Call |
|---|---|
| "Why won't jellyfin start?" | `inspect_container` + `get_container_logs` + `get_container_health` |
| "What's the CPU/memory usage of all containers?" | `list_containers` + `get_container_stats` (per container) |
| "Stop jellyfin" | `stop_container` |
| "Jellyfin logs from last 30 minutes" | `get_container_logs(since="30m")` |
| "Jellyfin network config / port mappings?" | `get_container_networks` + `list_networks` |
| "Data loss / permission issues?" | `get_container_mounts` + `list_volumes` |
| "What changed in the container?" | `get_container_changes` |
| "Container stuck?" | `get_container_processes` |

---

*This document is based on `main` branch source code analysis, last updated 2026-07-05.*
