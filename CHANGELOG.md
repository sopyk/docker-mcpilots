# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.1.3] - 2026-07-04

### Fixed
- **Docker socket 权限问题**：`gosu` 降权运行时会清除所有补充组，导致 `docker-compose.yml` 中的 `group_add` 配置无效。改为在 `entrypoint.sh` 启动时以 root 身份将 `docker.sock` 的组改为 mcpuser 的主组（PGID），从根本上解决权限问题。
- **Docker SDK 连接不稳定**：`docker.from_env()` 在非 root 用户环境下可能无法正确识别 socket 路径。改为显式指定 `unix:///var/run/docker.sock` 建立 Docker 客户端连接。

## [0.1.2] - 2026-07-03

### Fixed
- **FastMCP 3.4.2 API 兼容性**：`get_state()` 方法不接受 `default=None` 参数，移除后正常工作。
- **Auth 中间件请求头过滤**：`get_http_headers()` 默认过滤 `authorization` 头，必须显式通过 `include={"authorization"}` 参数保留，否则认证无法生效。
- **Auth 状态跨请求持久化**：`set_state()` 的 `serializable` 参数需设为 `True`，否则认证状态不跨请求保存，每次工具调用都需要重新认证。

### Changed
- 添加 `.dockerignore` 排除 `*.tar.gz`、`config/`、`secrets/`，镜像体积从 1.2GB 降至 75MB。
- 统一镜像 tag 与内部版本号，均为 0.1.2。

## [0.1.1] - 2026-07-03

### Added
- **PUID/PGID 环境变量支持**：容器启动时通过 `entrypoint.sh` 自动调整运行用户的 UID/GID，解决群晖 NAS 上挂载卷的权限问题。
- **gosu 降权运行**：容器以 root 启动完成权限修正后，通过 `gosu` 降权为普通用户运行主程序。
- **群晖专用 Compose 文件**：新增 `docker-compose.nas.yml`，去除 build 步骤，直接使用预加载镜像。

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
