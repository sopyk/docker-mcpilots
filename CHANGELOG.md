> 🌐 [English](CHANGELOG_EN.md) | 简体中文

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [v2.0.0] - 2026-07-07

### 新增

- **Web UI 界面**：完整的图形化管理界面（`/ui/`）
  - 仪表盘：CPU 内存使用率环形图、容器/镜像计数、最近审计日志
  - 容器列表：查看所有容器、启停/删除/查看详情
  - 用户管理：创建/编辑/删除 API Key，支持修改 Key 名称、角色、权限和范围
  - 审计日志：查看所有操作记录（筛选功能）
  - 系统设置：编辑系统设置（端口、时区、功能开关）、修改管理员密码
  - 关于页：项目介绍、Agent 配置示例、版本信息
- **Admin 认证系统**：Web UI 用户名密码登录（bcrypt 加密存储）
- **CSRF 防护**：所有 POST 请求需要 CSRF Token
- **审计日志**：记录所有 MCP 和 Web UI 操作
- **时区支持**：配置时区选项，显示本地化时间
- **静态资源**：支持子目录（/static/assets），正确识别图片 mime 类型

### 改进

- 模板安全优化：使用条件块代替未加引号的 Jinja2 表达式
- 完整的单元/集成/端到端测试（130+ 个用例，100% 覆盖核心模块）

### 修复

- 修复静态文件路由不支持子目录问题
- 修复 semgrep 发现的安全隐患（subprocess shell 仅用于测试、模板安全加固）

## [1.0.0] - 2026-07-04

首次正式发布。

---

## v1.0.0 首次正式发布

### 新增

- **MCP Server 核心功能**：基于 FastMCP 3.x 的 Docker 管理服务
  - 容器管理：`list_containers` / `inspect_container` / `start_container` / `stop_container` / `restart_container` / `remove_container`
  - 容器日志：`get_container_logs`（支持 tail / since / until / timestamps 时间段排查）
  - 容器资源：`get_container_stats`（CPU / 内存 / 网络实时占用）
  - 容器诊断（新增 8 个工具）：
    - `get_container_processes`：容器内进程列表（排查"卡死"）
    - `get_container_health`：健康检查状态 + 失败日志（排查"不健康"）
    - `get_container_networks`：IP / 网关 / DNS / 端口映射（排查"连不上网"）
    - `get_container_mounts`：挂载卷 / 绑定路径 / 读写权限（排查"数据丢失/权限不对"）
    - `get_container_changes`：文件系统增删改（排查"容器里改了什么"）
  - 镜像管理：`list_images` / `pull_image` / `remove_image` / `inspect_image`
  - 网络拓扑：`list_networks`（所有 Docker 网络及连接的容器）
  - 卷清单：`list_volumes`（所有卷及挂载点）
  - 系统诊断：`get_system_info` / `get_cpu_info` / `get_memory_info` / `get_disk_info` / `get_network_info`

- **权限模型**：RBAC 三角色（admin / operator / observer），支持容器级 scope（include/exclude 通配符）

- **认证系统**：API Key 认证，支持 YAML 配置或环境变量，认证状态跨请求持久化

- **群晖 NAS 适配**：
  - PUID/PGID 环境变量自动调整运行用户权限
  - gosu 降权安全运行
  - 提供两种部署 compose（预构建镜像版 / 源码构建版），适用于群晖等 NAS 及通用 Linux
  - Docker socket 权限问题根因修复

- **VPS 宿主机直装支持**：无需 Docker 嵌套，资源占用最低，支持 systemd / nginx 反代 / TLS

### 改进

- Docker 相关文件统一隔离到 `docker/` 子目录
- 镜像体积优化（.dockerignore 排除干扰，75MB vs 原 1.2GB）
- VPS 部署文档（含 systemd / nginx 反代 / TLS / 防火墙）
- 日志功能增强：RFC3339 时间格式 + 相对时间（"1h"/"30m"/"2d"）
- FastMCP 3.4.2 API 兼容性修复

### 修复

- Docker socket 权限问题（gosu 降权清除补充组）
- Docker SDK 连接不稳定（显式指定 unix socket 路径）
- `get_container_changes` 使用正确的 SDK 方法 `diff()`
- Auth 中间件请求头过滤（authorization 头需显式保留）
- Auth 状态跨请求持久化（`serializable=True`）

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
- `since`/`until` relative time parsing to datetime before传给 Docker SDK
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
