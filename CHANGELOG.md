> 🌐 [English](CHANGELOG_EN.md) | 简体中文

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [v2.1.3-rc.5] - 2026-10-28

> 测试版（Release Candidate），修复 rc.4 实景发现的 **MCP 客户端会话过期**（`transport session expired` / tools 为空）。

### 修复
- **MCP HTTP 会话空闲过期（Critical）**：`fastmcp` 4.1.0 起，Streamable HTTP 会话默认空闲 **1800 秒**即销毁（4.0.x 是永不过期）。由于依赖只做了范围锁定，rc.4 镜像装到 fastmcp 4.1.4，v2.1.2 镜像装到 4.0.3——**代码没改、行为变了**。长连接客户端（Hermes 等）空闲后会收到 `404 Session not found`，表现为 `transport session expired`、`outcome_uncertain`、tools 列表为空、反复重连。新增 `core/mcp_session.py`，默认把 `http_session_idle_timeout` 设为 `None`（恢复 4.0.x 行为）；可用 `MCP_SESSION_IDLE_TIMEOUT=<秒数|none>` 覆盖（如需内存有界可设 `86400`）。
- **依赖锁定到传递依赖**：`requirements.txt` 改为精确版本（`fastmcp==4.1.4`、`mcp==2.3.0`、`docker==7.2.0` 等），新增 `requirements.lock`（全部 71 个包锁定），Docker 构建改用 lock。此前 starlette（1.6.0 → 1.10.0）、uvicorn（0.52.4 → 0.54.0）等传递依赖会随构建时间漂移。

### 说明
- `Missing session ID`（400）是 MCP 规范行为，v2.1.2 使用的 mcp 2.2.0 同样如此，非本次回归；客户端必须保存 `mcp-session-id` 并在后续请求携带。
- **容器重启会让所有 MCP 会话失效**：会话表保存在服务端内存中，重启后客户端带着旧 `mcp-session-id` 请求会收到一次 `404 Session not found`，服务端日志为 `Rejected request with unknown or expired session ID: <id>`，客户端自动重新 `initialize` 即恢复。**这属于预期行为，不是故障**；rc.4 → rc.5 切换时看到的该行日志正是重启导致，而非 1800 秒空闲过期。重启后需重新初始化是 MCP stateful 模式的固有特性。
- **`MCP_SESSION_IDLE_TIMEOUT` 的覆盖已验证有效**：设为 `2` 的容器空闲 5 秒后 `tools/list` 返回 `404`；默认容器空闲 65 秒仍 `200`；只设 fastmcp 原生 `FASTMCP_HTTP_SESSION_IDLE_TIMEOUT=5`（不设本项目变量）的容器空闲 20 秒仍 `200`——说明本项目的显式覆盖生效且优先级更高。设为 `86400` 时只会回收**既无在途请求、也无打开的 GET/SSE 流**的会话，回收时记 INFO 日志 `Session <id> idle timeout`（已实测：`MCP_SESSION_IDLE_TIMEOUT=5` 的容器在空闲 ~9 秒后该行出现，随后同一 session 的请求返回 404）；并发会话另有 SDK 默认上限 10000（超出时 WARNING `Refusing to open a new session`）。详见部署指南「MCP 会话生命周期」。
- 查看容器日志请用 `get_container_logs(container_id, tail, since)`（底层 `docker logs`），不要 `exec cat /proc/1/fd/1`——后者会阻塞并拖死 SSE 流。

## [v2.1.3-rc.4] - 2026-10-28

> 测试版（Release Candidate），用于实测内网 HTTP 下的复制按钮、版本号单一数据源、`INITIAL_API_KEYS` 初始化；MCP HTTP 会话挂死问题定位修复（本次移除请求级超时中间件接线，恢复至 rc.2 行为）。

### 修复
- **关于页「复制」按钮在内网 HTTP 下失效**：`navigator.clipboard` 仅在安全上下文（HTTPS / localhost）存在，内网 `http://<NAS-IP>:8900` 访问时为 `undefined`，原实现同步抛 `TypeError` 导致兜底逻辑从未执行。新增 `web/static/clipboard.js`（能力检测 + `execCommand` 兜底 + 永不 reject），关于页与用户页统一调用，失败时给出「复制失败」提示。
- **静态文件路由路径穿越（安全）**：`/ui/static/{path}` 未做归一化校验，编码后的 `..%2f` 可越界读取仓库内任意文件（如 `secrets/auth.yaml`）。现已 `resolve()` 后校验必须位于 static 目录内，越界一律 404。
- **INITIAL_API_KEYS 幂等更新**：已存在同名 key 时应以环境变量中的 `name:key:role` 覆盖为本次初始化值，而不是静默跳过（此前设置同名 key（如 `default-admin`）完全不生效）。
- **MCP HTTP 会话挂死回归定位**：本次从 `mcp.run()` 中移除 `middleware` 注入（恢复至 rc.2 行为，即不再注入 `RequestTimeoutMiddleware`），作为 v2.1.3-rc.4 的定位修复；待 rc.4 实景复测确认会话是否恢复稳定。

### 改进
- **版本号单一数据源**：新增 `core/version.py`，`main.py`（FastMCP 元信息、`/health`）与 Web 模板（`{{ app_version }}`）统一引用，不再硬编码；新增一致性测试防止发版漏改。

## [v2.1.2] - 2026-09-10

### 修复
- **MCP 接口全部不可用（Critical）**：v2.1.1 构建时 `fastmcp>=3.0.0` 未锁上界，pip 解析到 fastmcp 4.x，后者依赖 mcp SDK 2.x。mcp 2.0 将 `McpError` 重命名为 `MCPError`，导致所有 MCP 协议请求在应用层报 `cannot import name 'McpError' from 'mcp'`。**现象**：容器 healthy、端口监听正常、健康检查返回 200，但每个 MCP 工具调用都返回错误，服务完全不可用。本次锁定 fastmcp>=4.0.0 + mcp>=2.0.0 并完成 SDK v2 迁移。
- **依赖未锁定**：所有依赖（fastmcp/docker/psutil 等）均无版本上界，pip 可在构建时解析到不兼容的大版本。本次为所有依赖添加主版本上界约束，防止未来滚动构建被上游 breaking change 打崩。

### 改进
- **MCP SDK v2 迁移**：适配 fastmcp 4.x — `McpError`→`MCPError`、`CurrentContext` 导入路径更新、auth 中间件从 session 缓存改为每请求认证（适配 sessionless 协议）
- **CI 流水线**：新增 GitHub Actions，含 pytest + Docker 构建 + MCP initialize 冒烟测试，防止"容器活着但服务不可用"的版本再次发布

## [v2.1.1] - 2026-09-01

### 修正
- **关于页**：删除"不提供 exec 能力"（exec 已支持，设置中开启即可）
- **关于页**：功能列表补充 exec 说明
- **菜单"审计"→"操作日志"**：更直观的命名，与容器日志区分

### 改进
- **优化了桌面版和手机端的 UI**：嵌入 Noto Sans SC 中文字体（去除 Google Fonts CDN 依赖）、统一 UI 元素字号（body 14px，最小 13px）、手机端登录框居中
- **集成测试增强**：`test_version_consistency` 新增对 `base.html` 和 `about.html` 版本号的检查，防止改版本漏改模板

## [v2.1.0] - 2026-07-29

### 新增
- **Web UI 手机端适配**：响应式布局纯 CSS（`mobile.css`），桌面版零影响
  - 汉堡菜单折叠导航
  - `.table-wrap` 水平滚动支持长表格
  - 容器操作切换为 `<select>` 下拉 + 执行按钮
  - 设置页、登录页、关于页全部适配
  - 触控友好（`touch-action`、`min-height` 按钮）
  - JS 加载失败内联备用 CSS 兜底
- **批量栏功能增强**：容器页批量栏「全选/全部不选」独立一行 + **表格底部复制相同批量栏**
- **API Key 复制按钮**：用户页每个 Key 输入框旁加复制按钮，点按变「已复制!」
- **密码持久化保护**：通过 UI 设置密码后容器重启不会被 `ADMIN_PASSWORD` 环境变量覆盖
- **设置页说明**：新增密码持久化说明及恢复默认密码操作步骤

### 优化
- **构建速度**：新增 `.dockerignore`，排除 `.opencode/`、`.git/`、`docs/`、`tests/` 等，构建上下文从 ~70MB 降至 ~1MB

### 修复
- **Docker SDK 兼容性**：修复 `images.list()` 不支持 `limit` 参数的兼容问题
- **移动端下拉宽度**：容器操作下拉菜单 `max-width: 90px` → `min-width: 120px`
- **用户页角色下拉**：手机端 `select[name="role"]` 添加 `min-width: 80px`

## [v2.0.4] - 2026-07-29

### 新增
- **UI 改进**：关于页 MCP 配置代码块添加一键复制按钮，点击直接复制配置
- **UI 改进**：用户页名称表头添加「点击可直接编辑」提示
- **list_images 新增 limit 参数**：支持限制返回镜像数量

### 修复
- **audit.sh 兼容性**：修复 pip/python → pip3/python3 命令

## [v2.0.3] - 2026-07-25

### 修复
- **exec_container Docker API 兼容性**：去掉 `demux` 参数，新增 `_demux_frames()` 手动解码多路复用字节流，兼容 Docker API < 1.42（群晖 NAS Docker v20.x）
- **list_containers Image 字段截断**：无标签的镜像不再显示截断哈希 `sha256:abc`，改为标准的 `short_id`
- **模板-测试对齐**：修复 `test_web_routes.py` 中 3 个因模板重构未同步的用例（容器详情 mock 数据嵌套结构、settings 断言已删除的重载按钮）

### 新增
- **UI 测试基础设施**: 引入 `project-audit-init`，包含 Playwright E2E 配置、BackstopJS 视觉对比、`scripts/audit.sh` 一键审计

## [v2.0.2] - 2026-07-09

### 新增
- **自动权限迁移**：首次启动时自动为三个标准角色补充缺失的权限
  - 为 admin 角色添加 `network:*`、`volume:*`
  - 为 operator/observer 角色添加 `network:list`、`volume:list`
  - 自动更新持久化的 auth.yaml 配置文件
- **favicon显示**：使用专用 favicon 图标，浏览器标签页显示项目 logo（使用用户提供的图片）
- **容器详情页顶部返回按钮**：在页面顶部也添加返回列表按钮
- **返回按钮统一位置**：容器详情页顶部和底部返回按钮均靠右对齐，保持一致
- **容器页批量操作**：支持复选框选择容器，批量启动/停止/重启
  - 每行开头复选框 + 表头全选
  - 顶部批量操作栏：已选计数 + 批量启动/停止/重启 + 全选/全部不选
  - 支持二次确认
- **用户页批量删除 API Key**：支持复选框选择多个 Key 批量删除
  - 每行开头复选框 + 表头全选
  - 顶部批量操作栏：已选计数 + 批量删除 + 全选/全部不选
  - 支持二次确认
- **用户页内联添加 API Key**：移除独立「新增 API Key」块，改为列表底部「+ 添加 API Key」按钮，点击插入一行空白（名称/角色/Key/作用域/保存/取消）
- **多架构镜像支持**：同时发布 linux/amd64 和 linux/arm64 镜像，兼容群晖 NAS（amd64）和 Mac M 系列（arm64）等设备

### 修复
#### Critical级修复
- **RBAC权限完全失效**：所有 MCP 工具均添加权限检查（此前仅有 exec_container 工具有权限检查！）
  - container_tools：list_containers / inspect_container / start_container / stop_container / restart_container / get_container_logs / get_container_stats / remove_container / get_container_processes / get_container_health / get_container_networks / get_container_mounts / get_container_changes
  - image_tools：list_images / inspect_image / pull_image / remove_image
  - docker_diag_tools：list_networks / list_volumes
  - diag_tools：get_system_info / get_cpu_info / get_memory_info / get_disk_info / get_network_info
- **exec_container 100%崩溃**：兼容 KeyConfig 被 fastmcp 序列化为 dict 的情况（修改 core/auth.py 兼容判断）
- **list_volumes NoneType错误**：修复 Volume 的 Options 为 None 时的访问错误（使用 `(options or {})` 兜底）

#### Web UI 修复
- **导航栏固定问题**：从 position: sticky 改成 position: fixed，完全固定在页面顶部，添加 left: 0 和 width: 100%，同时在 body 上添加 padding-top: 72px 避免内容被遮挡
- **热加载后URL参数问题**：在 base.html 中添加 JS 脚本，加载完成后自动去除 ?success/error 参数，避免刷新问题
- **设置页面按钮改名**：“保存设置” → “应用设置”
- **设置页面移除原始内容**：不再显示 settings.yaml 原始内容
- **仪表盘卡片可点击**：点击容器统计卡片跳转到容器页，点击镜像统计卡片跳转到镜像页
- **favicon问题**：使用独立的 favicon.jpg，不影响页面上的 logo（页面 logo 继续用 logo.jpg）
- **设置页面按钮位置正确**

#### 工具注册函数优化
- 所有 MCP 工具注册函数均添加 app_state 参数，用于权限检查
- 所有工具函数均改为 async 函数，正确使用 await ctx.get_state() 获取认证状态

## [v2.0.1] - 2026-07-08

### 新增

- **容器执行命令**：安全的 `exec_container` MCP 工具，支持在容器内执行命令
  - 功能开关控制（默认关闭）
  - 仅 admin 角色可用
  - 支持容器 scope 限制，建议配合专用工具容器使用
- **工具容器示例**：提供 `docker/docker-compose-toolbox.yml` 配置，创建隔离的工具容器用于 exec 操作
- **镜像管理页面**：Web UI 新增镜像列表页（`/ui/images`），查看镜像仓库、标签、大小、创建时间
- **容器状态颜色**：Web UI 容器列表状态徽章颜色区分（Running 绿色、Restarting/dead 红色、Exited/Created 灰色）

### 改进

- **Host 头保护移除**：移除 `host_origin_protection` 和 `allowed_hosts` 配置项，避免误操作导致反代访问被阻断
- **关于页修复**：修复导航栏和 500 错误问题
- **登录页优化**：添加 logo 和标语"给 Agent 一双管理 Docker 的手"
- **设置页面优化**：添加功能开关配置、密码修改功能

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
