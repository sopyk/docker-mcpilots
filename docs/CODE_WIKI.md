# DockerMaintainer MCP Server - Code Wiki

> 版本: 0.1.3  
> 最后更新: 2026-07-04

---

## 目录

1. [项目概述](#1-项目概述)
2. [整体架构](#2-整体架构)
3. [目录结构](#3-目录结构)
4. [核心模块详解](#4-核心模块详解)
5. [工具模块详解](#5-工具模块详解)
6. [权限模型 (RBAC)](#6-权限模型-rbac)
7. [配置说明](#7-配置说明)
8. [部署与运行](#8-部署与运行)
9. [测试体系](#9-测试体系)
10. [关键设计决策](#10-关键设计决策)
11. [依赖关系图](#11-依赖关系图)

---

## 1. 项目概述

### 1.1 项目定位

DockerMaintainer MCP Server 是一个运行在 Docker 容器中的 MCP (Model Context Protocol) 服务端，专为群晖 (Synology) NAS 环境设计。它通过标准化的 MCP 协议向 AI Agent 提供 Docker 容器/镜像管理能力和系统诊断功能，并内置 RBAC 权限控制体系。

### 1.2 核心功能

| 类别 | 能力 | 说明 |
|---|---|---|
| 容器管理 | 列出/查看/启停/重启/删除容器 | 支持按状态过滤 |
| 容器管理 | 查看容器日志 | 支持限制返回行数 |
| 容器管理 | 查看容器资源占用 | CPU、内存、网络实时统计 |
| 镜像管理 | 列出/拉取/删除镜像 | 支持名称过滤 |
| 系统诊断 | CPU/内存/磁盘/网络 | 基于 psutil 采集 |
| 系统诊断 | 系统概览 | 主机名、OS、内核、运行时间 |

### 1.3 技术栈

- **语言**: Python 3.11
- **MCP 框架**: FastMCP 3.x
- **Docker SDK**: docker Python SDK 7.x
- **系统监控**: psutil 7.x
- **配置格式**: YAML
- **容器化**: Docker + Docker Compose

---

## 2. 整体架构

### 2.1 架构分层

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
│  │  entrypoint.sh (PUID/PGID 调整 + 降权运行)        │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │  Docker Daemon (NAS)   │
              └────────────────────────┘
```

### 2.2 关键设计原则

1. **单容器架构**: 所有功能打包在单个容器中，最小化资源占用
2. **延迟连接**: DockerClient 采用懒加载，避免启动时因 socket 权限问题阻塞
3. **配置与密钥分离**: config/ 存放非敏感配置，secrets/ 存放 API Key 等敏感信息
4. **权限前置**: 认证中间件在 Tool 执行前完成身份验证和权限检查
5. **NAS 友好**: 支持 PUID/PGID 调整解决群晖挂载卷权限问题

---

## 3. 目录结构

```
dockermaintainer/
├── main.py                    # FastMCP 应用入口与认证中间件
├── core/                      # 核心业务模块
│   ├── __init__.py
│   ├── config.py              # 配置加载与数据类定义
│   ├── auth.py                # RBAC 权限检查器
│   ├── docker_client.py       # Docker SDK 封装层
│   └── system_diag.py         # 系统诊断信息采集
├── tools/                     # MCP Tool 注册模块
│   ├── __init__.py
│   ├── container_tools.py     # 容器管理 + 容器诊断 Tools
│   ├── image_tools.py         # 镜像管理 + 镜像诊断 Tools
│   ├── diag_tools.py          # 系统诊断 Tools
│   └── docker_diag_tools.py   # 网络和卷诊断 Tools
├── templates/                 # 默认配置模板
│   ├── settings.yaml          # 服务配置模板
│   └── auth.yaml              # 权限配置模板
├── tests/                     # 单元测试
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_auth.py
│   ├── test_docker_client.py
│   ├── test_system_diag.py
│   └── test_integration.py
├── scripts/                   # 辅助脚本
│   ├── e2e_test.py            # 端到端测试（24 个工具）
│   └── integration_test.py    # 容器级集成测试脚本
├── docker/                    # Docker 相关文件（隔离）
│   ├── Dockerfile             # 镜像构建定义
│   ├── entrypoint.sh          # 容器入口脚本 (UID/GID 调整)
│   ├── .dockerignore          # Docker 构建忽略规则
│   ├── docker-compose.yml     # 通用 Compose（自己 build）
│   └── nas/
│       └── docker-compose.yml # 群晖 NAS 部署用 Compose
├── docs/                      # 文档
│   ├── CODE_WIKI.md           # 本文档
│   ├── deploy-vps.md          # VPS 直装部署指南
│   ├── plans/                 # 实施计划
│   └── specs/                 # 设计规格书
├── requirements.txt           # Python 依赖
├── pytest.ini                 # pytest 配置
├── CHANGELOG.md               # 变更日志
└── README.md                  # 项目说明
```

---

## 4. 核心模块详解

### 4.1 main.py - 应用入口

**文件路径**: [main.py](file:///Users/song/Documents/trae_projects/dockermaintainer/main.py)

**核心职责**:
- 初始化配置文件（首次启动自动生成模板）
- 创建并配置 FastMCP 应用实例
- 注册认证中间件
- 注册各类 MCP Tools
- 提供健康检查端点

**关键组件**:

#### 4.1.1 `AuthMiddleware` 类

**位置**: [main.py#L28-L61](file:///Users/song/Documents/trae_projects/dockermaintainer/main.py#L28-L61)

认证中间件，实现 FastMCP 的 `Middleware` 接口。

**工作流程**:
1. 尝试从 session state 获取已缓存的认证信息
2. 从 HTTP 请求头提取 `Authorization: Bearer <api_key>`
3. 调用 `PermissionChecker.authenticate()` 验证 API Key
4. 将认证结果存入 session state（同会话内缓存）
5. 认证失败抛出 `McpError` (code: -32001)

**关键实现细节**:
- 使用 `get_http_headers(include={"authorization"})` 显式请求 authorization 头（FastMCP 默认过滤）
- 认证结果通过 `ctx.set_state("auth_key_config", ...)` 缓存到会话
- 必须在每个 Tool 调用前执行

#### 4.1.2 `_init_config_files()` 函数

**位置**: [main.py#L64-L128](file:///Users/song/Documents/trae_projects/dockermaintainer/main.py#L64-L128)

首次启动时自动生成默认配置模板。

**执行步骤**:
1. 创建 config/ 和 secrets/ 目录（如不存在）
2. 若 settings.yaml 不存在，从模板复制
3. 若 auth.yaml 不存在，从模板复制并设置权限 600
4. 统一修正 secrets/ 下所有文件权限为 600

**错误处理**:
- 权限不足时给出明确的 PUID/PGID 排查提示
- 兼容各种 NAS 挂载卷权限场景

#### 4.1.3 `create_app()` 函数

**位置**: [main.py#L131-L180](file:///Users/song/Documents/trae_projects/dockermaintainer/main.py#L131-L180)

应用工厂函数，创建并配置完整的 FastMCP 实例。

**配置顺序**:
1. 初始化配置文件
2. 加载 Settings 和 AuthConfig
3. 创建 PermissionChecker
4. 配置日志级别
5. 创建 FastMCP 实例 (name="DockerMaintainer", version="0.1.3")
6. 注册 AuthMiddleware
7. 创建 DockerClient 和 SystemDiag
8. 根据功能开关注册对应 Tools
9. 注册 /health 健康检查端点

#### 4.1.4 健康检查端点

**位置**: [main.py#L170-L173](file:///Users/song/Documents/trae_projects/dockermaintainer/main.py#L170-L173)

```python
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    return JSONResponse({"status": "ok", "version": "0.1.3"})
```

无需认证，用于容器健康检查和版本验证。

---

### 4.2 core/config.py - 配置模块

**文件路径**: [core/config.py](file:///Users/song/Documents/trae_projects/dockermaintainer/core/config.py)

**核心职责**:
- 定义所有配置相关的数据类 (dataclass)
- 提供从 YAML 文件加载配置的能力
- 维护 API Key 查找索引

#### 4.2.1 `Settings` 类

**位置**: [core/config.py#L11-L47](file:///Users/song/Documents/trae_projects/dockermaintainer/core/config.py#L11-L47)

服务端主配置。

**字段**:

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `host` | str | "0.0.0.0" | 监听地址 |
| `port` | int | 8900 | 监听端口 |
| `log_level` | str | "info" | 日志级别 |
| `socket_path` | str | "/var/run/docker.sock" | Docker socket 路径 |
| `container_management` | bool | True | 启用容器管理功能 |
| `image_management` | bool | True | 启用镜像管理功能 |
| `system_diagnostics` | bool | True | 启用系统诊断功能 |

**方法**:
- `from_yaml(path: str) -> Settings`: 从 YAML 文件加载，文件不存在则返回默认值

**YAML 结构**:
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

#### 4.2.2 `ScopeConfig` 类

**位置**: [core/config.py#L50-L65](file:///Users/song/Documents/trae_projects/dockermaintainer/core/config.py#L50-L65)

容器级作用域配置，支持通配符匹配。

**字段**:

| 字段 | 类型 | 说明 |
|---|---|---|
| `containers_include` | list[str] | 白名单模式，仅允许匹配的容器 |
| `containers_exclude` | list[str] | 黑名单模式，排除匹配的容器 |

**优先级**: include 先检查，exclude 后检查（exclude 优先）

#### 4.2.3 `RoleConfig` 类

**位置**: [core/config.py#L68-L80](file:///Users/song/Documents/trae_projects/dockermaintainer/core/config.py#L68-L80)

角色配置。

**字段**:

| 字段 | 类型 | 说明 |
|---|---|---|
| `description` | str | 角色描述 |
| `permissions` | list[str] | 权限列表，格式 "resource:action" |

#### 4.2.4 `KeyConfig` 类

**位置**: [core/config.py#L83-L99](file:///Users/song/Documents/trae_projects/dockermaintainer/core/config.py#L83-L99)

单个 API Key 的配置。

**字段**:

| 字段 | 类型 | 说明 |
|---|---|---|
| `key` | str | API Key 字符串 |
| `name` | str | Key 标识名 |
| `role` | str | 关联角色名 |
| `scope` | ScopeConfig \| None | 容器级作用域限制 |

#### 4.2.5 `AuthConfig` 类

**位置**: [core/config.py#L102-L141](file:///Users/song/Documents/trae_projects/dockermaintainer/core/config.py#L102-L141)

完整的权限配置（auth.yaml 的内存表示）。

**字段**:

| 字段 | 类型 | 说明 |
|---|---|---|
| `roles` | dict[str, RoleConfig] | 角色定义字典 |
| `keys` | list[KeyConfig] | API Key 列表 |
| `_key_lookup` | dict[str, KeyConfig] | Key 字符串 → KeyConfig 快速查找索引 |

**方法**:
- `from_yaml(path: str) -> AuthConfig`: 从 YAML 文件加载
- `find_key(api_key: str) -> KeyConfig | None`: 通过 key 字符串查找配置

**YAML 结构**:
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

### 4.3 core/auth.py - 权限检查模块

**文件路径**: [core/auth.py](file:///Users/song/Documents/trae_projects/dockermaintainer/core/auth.py)

**核心职责**:
- API Key 认证
- 角色权限验证（支持通配符）
- 容器级 Scope 检查

#### 4.3.1 异常类

| 异常 | 位置 | 说明 |
|---|---|---|
| `AuthenticationError` | [auth.py#L9-L11](file:///Users/song/Documents/trae_projects/dockermaintainer/core/auth.py#L9-L11) | API Key 认证失败 |
| `PermissionDeniedError` | [auth.py#L14-L16](file:///Users/song/Documents/trae_projects/dockermaintainer/core/auth.py#L14-L16) | 权限不足 |

#### 4.3.2 `PermissionChecker` 类

**位置**: [core/auth.py#L19-L108](file:///Users/song/Documents/trae_projects/dockermaintainer/core/auth.py#L19-L108)

权限检查器，所有权限判断的统一入口。

**核心方法**:

##### `authenticate(api_key: str) -> KeyConfig`

**位置**: [auth.py#L25-L32](file:///Users/song/Documents/trae_projects/dockermaintainer/core/auth.py#L25-L32)

验证 API Key，返回对应的 KeyConfig。

- 空 key → 抛出 `AuthenticationError`
- 未找到 key → 抛出 `AuthenticationError`
- 成功 → 返回 `KeyConfig` 对象

##### `check_permission(key_config: KeyConfig, permission: str) -> None`

**位置**: [auth.py#L34-L56](file:///Users/song/Documents/trae_projects/dockermaintainer/core/auth.py#L34-L56)

检查角色是否拥有指定权限。

- 角色不存在 → 抛出 `PermissionDeniedError`
- 权限不足 → 抛出 `PermissionDeniedError`
- 有权限 → 正常返回（无返回值）

##### `check_scope(key_config: KeyConfig, container_name: str) -> None`

**位置**: [auth.py#L58-L87](file:///Users/song/Documents/trae_projects/dockermaintainer/core/auth.py#L58-L87)

检查容器是否在 scope 允许范围内。

- 无 scope 配置 → 直接放行
- 有 include 列表但不匹配 → 拒绝
- 匹配 exclude 列表 → 拒绝
- 使用 `fnmatch.fnmatch()` 进行通配符匹配

##### `check(key_config: KeyConfig, permission: str, container_name: str | None = None) -> None`

**位置**: [auth.py#L89-L93](file:///Users/song/Documents/trae_projects/dockermaintainer/core/auth.py#L89-L93)

便捷方法，一次性检查权限和 scope。

##### `_has_permission(permissions: list[str], required: str) -> bool`

**位置**: [auth.py#L95-L108](file:///Users/song/Documents/trae_projects/dockermaintainer/core/auth.py#L95-L108)

静态方法，判断权限列表是否包含所需权限。

**通配符规则**:
- `"*"` 匹配所有权限
- `"resource:*"` 匹配某资源下所有操作
- `"*:action"` 匹配所有资源的某操作
- 精确匹配 `"resource:action"`

---

### 4.4 core/docker_client.py - Docker 客户端封装

**文件路径**: [core/docker_client.py](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py)

**核心职责**:
- 封装 Docker Python SDK
- 提供延迟连接（懒加载）
- 统一错误处理和返回格式
- 隔离底层 SDK 变更影响

#### 4.4.1 `DockerClient` 类

**位置**: [core/docker_client.py#L13-L210](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L13-L210)

**构造参数**:
- `socket_path: str = "/var/run/docker.sock"` - Docker socket 路径

**设计要点**:
- 延迟连接：`_ensure_connected()` 仅在首次调用时建立连接
- 导入容错：docker 模块未安装时不立即报错，仅在实例化时报错

##### 容器操作方法

| 方法 | 位置 | 说明 |
|---|---|---|
| `list_containers(status, all)` | [docker_client.py#L32-L43](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L32-L43) | 列出容器，支持状态过滤 |
| `get_container(container_id)` | [docker_client.py#L45-L49](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L45-L49) | 获取容器详情 |
| `start_container(container_id)` | [docker_client.py#L51-L62](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L51-L62) | 启动容器 |
| `stop_container(container_id)` | [docker_client.py#L64-L75](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L64-L75) | 停止容器 |
| `restart_container(container_id)` | [docker_client.py#L77-L88](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L77-L88) | 重启容器 |
| `remove_container(container_id, force)` | [docker_client.py#L90-L100](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L90-L100) | 删除容器 |
| `get_container_logs(container_id, tail)` | [docker_client.py#L102-L112](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L102-L112) | 获取容器日志 |
| `get_container_stats(container_id)` | [docker_client.py#L114-L146](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L114-L146) | 获取容器资源统计（单次采样） |

##### 镜像操作方法

| 方法 | 位置 | 说明 |
|---|---|---|
| `list_images(name_filter)` | [docker_client.py#L150-L154](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L150-L154) | 列出镜像，支持名称过滤 |
| `pull_image(image_name, tag)` | [docker_client.py#L156-L167](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L156-L167) | 拉取镜像 |
| `remove_image(image_id, force)` | [docker_client.py#L169-L178](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L169-L178) | 删除镜像 |

##### 内部格式化方法

| 方法 | 位置 | 输出字段 |
|---|---|---|
| `_format_container(container)` | [docker_client.py#L182-L189](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L182-L189) | id, name, status, image |
| `_format_container_detail(container)` | [docker_client.py#L191-L201](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L191-L201) | id, name, status, image, created, ports, labels |
| `_format_image(image)` | [docker_client.py#L203-L210](file:///Users/song/Documents/trae_projects/dockermaintainer/core/docker_client.py#L203-L210) | id, tags, size, created |

**错误处理模式**:
- 操作类方法返回 `{"success": bool, ...}` 格式
- 成功时包含结果数据，失败时包含 `error` 字段
- 统一捕获 `DockerNotFound` 和 `DockerAPIError`

---

### 4.5 core/system_diag.py - 系统诊断模块

**文件路径**: [core/system_diag.py](file:///Users/song/Documents/trae_projects/dockermaintainer/core/system_diag.py)

**核心职责**:
- 采集系统级诊断信息
- 基于 psutil 跨平台实现
- 提供结构化数据输出

#### 4.5.1 `SystemDiag` 类

**位置**: [system_diag.py#L11-L115](file:///Users/song/Documents/trae_projects/dockermaintainer/core/system_diag.py#L11-L115)

无状态的信息采集器，所有方法均为即时采集。

##### 方法说明

| 方法 | 位置 | 返回字段 |
|---|---|---|
| `get_system_info()` | [system_diag.py#L14-L25](file:///Users/song/Documents/trae_projects/dockermaintainer/core/system_diag.py#L14-L25) | hostname, os, kernel, architecture, boot_time, uptime_seconds |
| `get_cpu_info(per_core)` | [system_diag.py#L27-L48](file:///Users/song/Documents/trae_projects/dockermaintainer/core/system_diag.py#L27-L48) | percent, count_logical, count_physical, freq_*, percent_per_core |
| `get_memory_info()` | [system_diag.py#L50-L67](file:///Users/song/Documents/trae_projects/dockermaintainer/core/system_diag.py#L50-L67) | virtual (total/used/available/percent), swap (total/used/free/percent) |
| `get_disk_info()` | [system_diag.py#L69-L87](file:///Users/song/Documents/trae_projects/dockermaintainer/core/system_diag.py#L69-L87) | partitions[] (device/mountpoint/fstype/total/used/free/percent) |
| `get_network_info()` | [system_diag.py#L89-L115](file:///Users/song/Documents/trae_projects/dockermaintainer/core/system_diag.py#L89-L115) | total, per_interface_io, interfaces |

**注意事项**:
- CPU 使用率使用 0.5s 间隔采样（`interval=0.5`）
- 磁盘分区读取失败时跳过（权限不足等）
- 网络信息包含总流量、单网卡流量、网卡状态

---

## 5. 工具模块详解

### 5.1 概述

工具模块位于 `tools/` 目录下，负责将核心业务能力注册为 MCP Tools。每个模块提供一个 `register_*_tools(mcp, client)` 函数，在应用启动时被调用。

**设计模式**: 注册器模式 + 闭包
- 注册函数接收 MCP 实例和业务客户端
- 内部定义 Tool 函数，通过闭包访问客户端
- 使用 `@mcp.tool` 装饰器注册

---

### 5.2 tools/container_tools.py - 容器管理 Tools

**文件路径**: [tools/container_tools.py](file:///Users/song/Documents/trae_projects/dockermaintainer/tools/container_tools.py)

**注册函数**: `register_container_tools(mcp: FastMCP, docker_client: DockerClient)`

**已注册 Tools**:

| Tool 名称 | 参数 | 说明 | 所需权限 |
|---|---|---|---|
| `list_containers` | status?: str | 列出容器 | （读操作） |
| `inspect_container` | container_id: str | 容器详情 | （读操作） |
| `start_container` | container_id: str | 启动容器 | container:start |
| `stop_container` | container_id: str | 停止容器 | container:stop |
| `restart_container` | container_id: str | 重启容器 | container:restart |
| `get_container_logs` | container_id: str, tail?: int | 容器日志 | container:logs |
| `get_container_stats` | container_id: str | 资源统计 | container:stats |
| `remove_container` | container_id: str, force?: bool | 删除容器 | container:remove |

---

### 5.3 tools/image_tools.py - 镜像管理 Tools

**文件路径**: [tools/image_tools.py](file:///Users/song/Documents/trae_projects/dockermaintainer/tools/image_tools.py)

**注册函数**: `register_image_tools(mcp: FastMCP, docker_client: DockerClient)`

**已注册 Tools**:

| Tool 名称 | 参数 | 说明 | 所需权限 |
|---|---|---|---|
| `list_images` | name_filter?: str | 列出镜像 | （读操作） |
| `pull_image` | image_name: str, tag?: str | 拉取镜像 | image:pull |
| `remove_image` | image_id: str, force?: bool | 删除镜像 | image:remove |

---

### 5.4 tools/diag_tools.py - 系统诊断 Tools

**文件路径**: [tools/diag_tools.py](file:///Users/song/Documents/trae_projects/dockermaintainer/tools/diag_tools.py)

**注册函数**: `register_diag_tools(mcp: FastMCP, system_diag: SystemDiag)`

**已注册 Tools**:

| Tool 名称 | 参数 | 说明 | 所需权限 |
|---|---|---|---|
| `get_system_info` | - | 系统概览 | system:info |
| `get_cpu_info` | per_core?: bool | CPU 信息 | system:cpu |
| `get_memory_info` | - | 内存信息 | system:memory |
| `get_disk_info` | - | 磁盘信息 | system:disk |
| `get_network_info` | - | 网络信息 | system:network |

---

## 6. 权限模型 (RBAC)

### 6.1 角色定义

| 角色 | 权限 | 说明 |
|---|---|---|
| **admin** | `container:*`, `image:*`, `system:*`, `exec:*` | 完全控制 |
| **operator** | `container:list/inspect/start/stop/restart/logs/stats`<br>`image:list/pull`<br>`system:*` | 标准管理 |
| **observer** | `container:list/inspect/logs/stats`<br>`image:list`<br>`system:*` | 只读 |

### 6.2 权限命名规范

格式: `resource:action`

**资源类别**:
- `container` - 容器操作
- `image` - 镜像操作
- `system` - 系统诊断
- `exec` - 执行命令（预留）

### 6.3 Scope 作用域控制

每个 API Key 可配置容器级别的访问范围：

```yaml
keys:
  - key: "sk-dm-xxx"
    name: "home-assistant"
    role: operator
    scope:
      containers:
        include: ["home-*", "nginx"]    # 仅允许操作这些容器
        exclude: ["home-db"]            # 排除这些（优先级更高）
```

**匹配规则**:
- 使用 `fnmatch` 通配符语法（`*`, `?`, `[seq]`）
- 无 scope → 无限制
- 仅 include → 白名单模式
- 仅 exclude → 黑名单模式
- 同时存在 → 先过 include，再过 exclude

### 6.4 认证流程

```
MCP Request
    │
    ▼
AuthMiddleware.on_request()
    │
    ├─► 检查 session state 缓存
    │     ├─ 已缓存 → 跳过，继续执行
    │     └─ 未缓存 → 继续
    │
    ├─► 从 Authorization 头提取 Bearer Token
    │
    ├─► PermissionChecker.authenticate(api_key)
    │     ├─ 无效 → 抛出 McpError(-32001)
    │     └─ 有效 → 存入 session state
    │
    ▼
Tool 执行
```

---

## 7. 配置说明

### 7.1 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `MCP_CONFIG_DIR` | /app/config | 配置文件目录 |
| `MCP_SECRETS_DIR` | /app/secrets | 密钥文件目录 |
| `PUID` | 1000 | 运行用户 UID（entrypoint 调整） |
| `PGID` | 1000 | 运行用户 GID（entrypoint 调整） |
| `TZ` | - | 时区，建议 Asia/Shanghai |

### 7.2 settings.yaml 配置项

```yaml
server:
  host: "0.0.0.0"        # 监听地址
  port: 8900             # 监听端口
  log_level: "info"      # debug / info / warning / error

docker:
  socket_path: "/var/run/docker.sock"  # Docker socket 路径

features:
  container_management: true    # 启用容器管理
  image_management: true        # 启用镜像管理
  system_diagnostics: true      # 启用系统诊断
```

### 7.3 auth.yaml 配置项

参见 [6. 权限模型](#6-权限模型-rbac) 和 [AuthConfig 类](#425-authconfig-类)。

---

## 8. 部署与运行

### 8.1 本地开发运行

**安装依赖**:
```bash
pip install -r requirements.txt
```

**直接运行**:
```bash
python main.py
```

**使用 Docker Compose**:
```bash
docker compose up -d --build
```

### 8.2 群晖 NAS 部署

#### 8.2.1 准备工作

1. 在本地构建 x86_64 镜像（群晖通常为 AMD64）:
```bash
docker build --platform linux/amd64 -t docker-mcp-server:v0.1.3 -t docker-mcp-server:latest .
```

2. 导出并压缩镜像:
```bash
docker save docker-mcp-server:v0.1.3 docker-mcp-server:latest | gzip > docker-mcp-server-v0.1.3.tar.gz
```

3. 传输到 NAS 并加载:
```bash
docker load -i docker-mcp-server-v0.1.3.tar.gz
```

#### 8.2.2 创建目录和配置

```bash
mkdir -p /volume1/docker/docker-mcp/{config,secrets}
# 将 docker-compose.nas.yml 复制到该目录
```

#### 8.2.3 启动

```bash
cd /volume1/docker/docker-mcp
docker-compose -f docker-compose.nas.yml up -d
```

首次启动会自动生成配置模板，编辑 `secrets/auth.yaml` 设置你的 API Key，然后重启。

### 8.3 健康检查

```bash
curl http://localhost:8900/health
# 返回: {"status":"ok","version":"0.1.3"}
```

### 8.4 MCP 连接配置

在 MCP 客户端中配置 HTTP 传输:

```json
{
  "mcpServers": {
    "docker-maintainer": {
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

## 9. 测试体系

### 9.1 测试结构

| 测试文件 | 覆盖范围 | 测试类型 |
|---|---|---|
| `tests/test_config.py` | 配置加载、数据类 | 单元测试 |
| `tests/test_auth.py` | 认证、权限、Scope | 单元测试 |
| `tests/test_docker_client.py` | Docker 客户端封装 | 单元测试 (mock) |
| `tests/test_system_diag.py` | 系统诊断 | 单元测试 (mock) |
| `tests/test_integration.py` | 应用启动、Tool 注册 | 集成测试 (mock) |
| `scripts/integration_test.py` | 容器级端到端验证 | E2E 测试 |

### 9.2 运行单元测试

```bash
pytest tests/ -v
```

### 9.3 运行容器集成测试

```bash
python scripts/integration_test.py
```

**测试项**:
1. 版本号一致性检查
2. 镜像大小合理性检查
3. 容器启动与功能验证 (健康检查、MCP 握手、Tool 调用)
4. .dockerignore 规则检查
5. entrypoint.sh 权限检查

---

## 10. 关键设计决策

### 10.1 延迟连接 (Lazy Connection)

**决策**: DockerClient 在首次调用时才连接 Docker daemon。

**原因**:
- 避免启动时因 socket 权限/路径问题导致容器无法启动
- 健康检查等非 Docker 操作不受影响
- 更优雅的错误提示（在实际调用时报错）

### 10.2 配置与密钥分离

**决策**: 使用两个独立目录 config/ 和 secrets/ 分别存放非敏感配置和敏感信息。

**原因**:
- 安全最佳实践：敏感信息与普通配置分开管理
- 不同的备份策略和权限控制
- secrets/ 下文件自动设置 600 权限

### 10.3 PUID/PGID 支持

**决策**: entrypoint.sh 中支持通过环境变量调整运行用户的 UID/GID。

**原因**:
- 群晖 NAS 挂载卷权限问题是常见痛点
- 以 root 启动，调整 UID/GID 后用 gosu 降权运行
- 兼容 Docker 官方镜像的常见做法

**0.1.3 修复要点**:
- `gosu` 降权运行时会清除所有补充组，导致 `docker-compose.yml` 中的 `group_add` 配置无效
- 解决方案：entrypoint.sh 启动时以 root 身份将 `/var/run/docker.sock` 的组改为 mcpuser 的主组（PGID）
- entrypoint 末行从 `gosu mcpuser "$@"` 改为 `exec gosu mcpuser "$@"`（更干净的进程替换）
- DockerClient 改用显式 `unix://` socket 路径连接，避免 `docker.from_env()` 在非 root 环境下的不稳定性

### 10.4 单容器架构

**决策**: 所有功能打包在单个容器中。

**原因**:
- 最小化资源占用（NAS 环境资源有限）
- 简化部署和管理
- 功能耦合度高，分拆无明显收益

### 10.5 .dockerignore 优化

**决策**: 排除 *.tar.gz、config/、secrets/ 等大文件和运行时数据。

**效果**:
- 镜像大小从 ~1.2GB 降至 ~75MB
- 构建速度更快，传输成本更低

### 10.6 Session 级认证缓存

**决策**: 认证结果存入 FastMCP session state，同一会话内复用。

**原因**:
- MCP 协议是有会话的，同一会话多次调用无需重复认证
- 减少 auth.yaml 读取次数
- 提升性能（虽然开销很小）

---

## 11. 依赖关系图

### 11.1 模块依赖

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
  └── docker (第三方 SDK)

core.system_diag
  └── psutil (第三方库)
```

### 11.2 第三方依赖

| 包名 | 版本要求 | 用途 |
|---|---|---|
| fastmcp | >=3.0.0 | MCP 服务框架 |
| docker | >=7.0.0 | Docker API 客户端 |
| psutil | >=7.0.0 | 系统信息采集 |
| pyyaml | >=6.0 | YAML 配置解析 |

### 11.3 运行时依赖

- Docker daemon (通过 unix socket 通信)
- Linux 环境（psutil 跨平台，但主要目标是 NAS Linux）

---

## 附录：版本历史

| 版本 | 日期 | 主要变更 |
|---|---|---|
| 0.1.3 | 2026-07-04 | 修复 docker.sock 组权限（gosu 清除补充组问题）、Docker SDK 显式 socket 连接 |
| 0.1.2 | 2026-07-03 | 修复版本号一致性、添加 .dockerignore、优化镜像大小 |
| 0.1.1 | 2026-07-03 | 添加 PUID/PGID 支持、修复 NAS 权限问题 |
| 0.1.0 | 2026-07-03 | 初始版本，核心功能完整 |

---

*本文档由代码分析自动生成，最后更新于 2026-07-04*
