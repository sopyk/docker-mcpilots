# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.1.4] - 2026-07-04

### Added
- **容器诊断能力增强**（围绕"排查容器问题"核心目标，新增 8 个诊断工具）
  - `get_container_processes`：容器内进程列表（排查"卡死"）
  - `get_container_health`：健康检查状态 + 失败日志（排查"不健康"）
  - `get_container_networks`：IP / 网关 / DNS / 端口映射（排查"连不上网"）
  - `get_container_mounts`：挂载卷 / 绑定路径 / 读写权限（排查"数据丢失/权限不对"）
  - `get_container_changes`：文件系统增删改（排查"容器里改了什么"）
  - `inspect_image`：入口命令 / 环境变量 / 历史构建层（排查"镜像有没有问题"）
  - `list_networks`：所有 Docker 网络及连接的容器（排查"容器之间通不通"）
  - `list_volumes`：所有卷及挂载点（排查"数据存储在哪里"）
- **日志功能增强**：`get_container_logs` 新增 `since`/`until`/`timestamps` 参数，支持 RFC3339 时间格式和相对时间（"1h"/"30m"/"2d"），支持按时间段排查
- `inspect_container` 返回更完整的诊断信息（state / health / config / network / mounts）
- VPS 宿主机直装部署指南（含 systemd / nginx 反代 / TLS / 防火墙）

### Changed
- Docker 相关文件统一隔离到 `docker/` 子目录，VPS用户看不到Docker干扰
  - `docker/Dockerfile`：改为精确 COPY，避免无关文件打入镜像
  - `docker/nas/docker-compose.yml`：NAS 专用 compose，文件名标准，群晖可自动识别
  - `docker/docker-compose.yml`：通用 build 版 compose
- `docs/superpowers/` 重命名为 `docs/specs/` 和 `docs/plans/`，命名更直观
- README 全面更新（功能表、部署方式、文件结构）

### Fixed
- `get_container_changes` 使用正确的 SDK 方法 `diff()`（原 `.changes()` 不存在）
- `diff()` 在某些 Docker 平台返回 None 时兜底为空列表
- `since`/`until` 字符串相对时间需解析为 datetime 后再传给 Docker SDK
- 单元测试 mock 断言与新增 `timestamps` 参数对齐

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
