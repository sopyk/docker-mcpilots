> 🌐 English | [简体中文](CHANGELOG.md)

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [v2.0.2] - 2026-07-09

### Added
- **Auto Permission Migration**: Automatically adds missing permissions (network:list / volume:list) to the three standard roles on first startup
- **Favicon Display**: Uses dedicated favicon icon, shows project logo in browser tabs
- **Consistent Back Button Placement**: Both back buttons at the top and bottom of the container detail page are right-aligned for consistency

### Fixed
- **RBAC Fully Disabled**: Added permission checks to all MCP tools (previously only exec_container had)
- **exec_container Crashes**: Compatible with KeyConfig being serialized to dict (adapts to fastmcp behavior)
- **list_volumes NoneType**: Fixed access error when Volume Options is None
- **Navbar Fixed**: Changed to position: fixed, fully anchored at page top
- **Hot Reload URL Params**: Auto removes ?success/error params to avoid refresh issues
- **Settings Page Button Rename**: "保存设置" → "应用设置" (Save Settings → Apply Settings)
- **Settings Page Raw Content Removed**: No longer shows raw settings.yaml content
- **Dashboard Cards Clickable**: Click container card to go to container page, click image card to go to image page
- **Favicon Issue**: Uses separate favicon.jpg without affecting page logo

## [v2.0.1] - 2026-07-08

### Added

- **Container Exec**: Secure `exec_container` MCP tool for executing commands inside containers
  - Feature toggle control (disabled by default)
  - Admin role only
  - Supports container scope restriction, recommended for dedicated tool containers
- **Toolbox Container Example**: Provides `docker/docker-compose-toolbox.yml` config for isolated exec operations
- **Image Management Page**: New Web UI image list page (`/ui/images`) showing repository, tag, size, creation time
- **Container Status Colors**: Color-coded status badges (Running green, Restarting/dead red, Exited/Created gray)

### Changed

- **Host Origin Protection Removed**: Removed `host_origin_protection` and `allowed_hosts` config items to prevent accidental blocking of reverse proxy access
- **About Page Fixed**: Fixed navigation bar and 500 error issues
- **Login Page Enhanced**: Added logo and slogan "Give AI Agent hands to manage Docker"
- **Settings Page Enhanced**: Added feature toggle configuration and password change functionality

## [v2.0.0] - 2026-07-07

### Added

- **Web UI Interface**: Complete graphical management interface (`/ui/`)
  - Dashboard: CPU/memory usage ring charts, container/image counts, recent audit logs
  - Container List: View all containers, start/stop/delete/inspect
  - User Management: Create/edit/delete API Keys, support updating key name, role, permissions and scope
  - Audit Log: View all operation records (filter supported)
  - System Settings: Edit system settings (port, timezone, feature toggles), change admin password
  - About Page: Project introduction, Agent configuration example, version info
- **Admin Auth System**: Web UI username/password login (bcrypt encrypted storage)
- **CSRF Protection**: All POST requests require CSRF Token
- **Audit Log**: Logs all MCP and Web UI operations
- **Timezone Support**: Timezone configuration option, displays local time
- **Static Assets**: Supports subdirectories (`/static/assets`), correct image mime types

### Changed

- Template security optimization: Use conditional blocks instead of unquoted Jinja2 expressions
- Complete unit/integration/e2e test suite (130+ tests, 100% coverage on core modules)

### Fixed

- Fixed static file routing not supporting subdirectories
- Fixed semgrep-reported security issues (subprocess shell only for tests, template security hardening)

## [1.0.0] - 2026-07-04

First official release.

---

## v1.0.0 First Official Release

### Added

- **MCP Server Core Features**: Docker management service based on FastMCP 3.x
  - Container management: `list_containers` / `inspect_container` / `start_container` / `stop_container` / `restart_container` / `remove_container`
  - Container logs: `get_container_logs` (supports tail / since / until / timestamps for time-range troubleshooting)
  - Container resources: `get_container_stats` (real-time CPU / memory / network usage)
  - Container diagnostics (8 new tools):
    - `get_container_processes`: process list inside container (troubleshooting "stuck" state)
    - `get_container_health`: health check status + failure logs (troubleshooting "unhealthy" state)
    - `get_container_networks`: IP / gateway / DNS / port mappings (troubleshooting "no network access")
    - `get_container_mounts`: mounted volumes / bind paths / read-write permissions (troubleshooting "data loss/permission issues")
    - `get_container_changes`: filesystem additions, deletions and modifications (troubleshooting "what changed in container")
  - Image management: `list_images` / `pull_image` / `remove_image` / `inspect_image`
  - Network topology: `list_networks` (all Docker networks and connected containers)
  - Volume inventory: `list_volumes` (all volumes and mount points)
  - System diagnostics: `get_system_info` / `get_cpu_info` / `get_memory_info` / `get_disk_info` / `get_network_info`

- **Permission Model**: RBAC three roles (admin / operator / observer), supports container-level scope (include/exclude wildcards)

- **Authentication System**: API Key authentication, supports YAML config or environment variables, auth state persisted across requests

- **Synology NAS Adaptation**:
  - PUID/PGID environment variables auto-adjust runtime user permissions
  - gosu privilege drop for secure execution
  - Provides two deployment compose files (pre-built image version / source build version), suitable for Synology NAS and general Linux
  - Root cause fix for Docker socket permission issue

- **VPS Host Direct Installation Support**: No nested Docker required, minimal resource footprint, supports systemd / nginx reverse proxy / TLS

### Changed

- Docker-related files uniformly isolated to `docker/` subdirectory
- Image size optimization (.dockerignore excludes interference, 75MB vs original 1.2GB)
- VPS deployment docs (including systemd / nginx reverse proxy / TLS / firewall)
- Logging enhancement: RFC3339 time format + relative time ("1h"/"30m"/"2d")
- FastMCP 3.4.2 API compatibility fix

### Fixed

- Docker socket permission issue (gosu privilege drop clears supplementary groups)
- Docker SDK connection instability (explicitly specify unix socket path)
- `get_container_changes` uses correct SDK method `diff()`
- Auth middleware header filtering (authorization header must be explicitly preserved)
- Auth state persistence across requests (`serializable=True`)

---

## [0.1.4] - 2026-07-04

### Added

- Enhanced container diagnostics (8 new tools around core "troubleshooting" goal)
  - `get_container_processes`: container process list (debugging "stuck" containers)
  - `get_container_health`: health check status + failure logs (debugging "unhealthy" containers)
  - `get_container_networks`: IP / gateway / DNS / port mappings (debugging "network issues")
  - `get_container_mounts`: volumes / bind mounts / rw permissions (debugging "data loss/permissions")
  - `get_container_changes`: filesystem diff (debugging "what changed in container")
  - `inspect_image`: entrypoint / env vars / build layers (debugging "image issues")
  - `list_networks`: all Docker networks and connected containers
  - `list_volumes`: all volumes and mount points
- Enhanced logs: `since`/`until`/`timestamps` params with RFC3339 and relative time support
- `inspect_container` returns complete diagnostic info (state / health / config / network / mounts)
- VPS host deployment guide (systemd / nginx reverse proxy / TLS / firewall)

### Changed

- Docker files isolated to `docker/` subdirectory
- `docs/superpowers/` renamed to `docs/specs/` and `docs/plans/`
- README fully updated (features, deployment, file structure)

### Fixed

- `get_container_changes` using correct SDK method `diff()`
- `diff()` returns None on some Docker platforms (now defaults to empty list)
- `since`/`until` relative time parsing to datetime before passing to Docker SDK
- Unit test mocks aligned with new `timestamps` param

## [0.1.3] - 2026-07-04

### Fixed

- **Docker socket permission issue**: `gosu` drops supplementary groups, making `group_add` in compose ineffective. Root identity now changes docker.sock group to mcpuser's primary group (PGID) in entrypoint.sh.
- **Docker SDK connection instability**: `docker.from_env()` may fail to recognize socket path. Changed to explicit `unix:///var/run/docker.sock`.

## [0.1.2] - 2026-07-03

### Fixed

- **FastMCP 3.4.2 API compatibility**: `get_state()` doesn't accept `default=None` param.
- **Auth middleware header filtering**: `get_http_headers()` filters `authorization` by default; must explicitly use `include={"authorization"}`.
- **Auth state persistence across requests**: `set_state()` requires `serializable=True`.

### Changed

- `.dockerignore` reduced image size from 1.2GB to 75MB.
- Unified image tag and internal version number.

## [0.1.1] - 2026-07-03

### Added

- **PUID/PGID support**: entrypoint.sh auto-adjusts UID/GID for NAS mount permissions.
- **gosu privilege drop**: container runs as root for permission fix, then drops to normal user.
- **Synology NAS compose file**: separate file without build step, uses pre-loaded images.

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
