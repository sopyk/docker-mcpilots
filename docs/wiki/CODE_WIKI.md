# Docker-MCPilotS — Code Wiki

> 🌐 [English](CODE_WIKI_EN.md) | 简体中文
>
> 版本: 1.0.0 ｜ 最后更新: 2026-07-05 ｜ 代码基线: `main` 分支

---

## 目录

1. [项目概述](#1-项目概述)
2. [整体架构](#2-整体架构)
3. [目录结构](#3-目录结构)
4. [核心模块详解（core/）](#4-核心模块详解core)
5. [工具模块详解（tools/）](#5-工具模块详解tools)
6. [应用入口与中间件（main.py）](#6-应用入口与中间件mainpy)
7. [权限模型（RBAC + Scope）](#7-权限模型rbac--scope)
8. [MCP Tools 总览](#8-mcp-tools-总览)
9. [配置说明](#9-配置说明)
10. [容器化与部署](#10-容器化与部署)
11. [测试体系](#11-测试体系)
12. [依赖关系](#12-依赖关系)
13. [关键设计决策](#13-关键设计决策)
14. [安全模型与能力边界](#14-安全模型与能力边界)
15. [版本历史](#15-版本历史)

---

## 1. 项目概述

### 1.1 项目定位

**Docker-MCPilotS** 是一个运行在 Docker 容器中的 MCP（Model Context Protocol）服务端，专为群晖（Synology）NAS 设计，同时适用于任何装有 Docker 的机器。它通过标准化的 MCP 协议向 AI Agent（OpenClaw、Hermes、Trae、Cursor、Claude Code、Codex 等）暴露 **受控的** Docker 管理能力和系统诊断能力。

项目核心理念是「**沙箱里的 Docker 管理工具**」：不把 SSH 权限交给 Agent，而是通过 MCP 接口只暴露允许的操作，避免误伤特殊的 NAS 系统。项目以「Vibe Coding」方式开发。

### 1.2 核心能力

| 类别 | 能力 | 说明 |
|---|---|---|
| 容器管理 | 列出 / 查看 / 启停 / 重启 / 删除容器 | 支持按状态过滤 |
| 容器日志 | 查看日志 | 支持 `tail` / `since` / `until` / `timestamps`，相对时间（`1h`/`30m`/`2d`）与 RFC3339 |
| 容器资源 | CPU / 内存 / 网络实时占用 | 单次采样 |
| 容器诊断 | 进程 / 健康 / 网络 / 挂载 / 文件变更 / 镜像详情 | 围绕「排查问题」设计 |
| 镜像管理 | 列出 / 拉取 / 删除 / 详情 | 不开放 `docker build` |
| 网络拓扑 | 列出所有 Docker 网络及连接容器 | 只读 |
| 卷清单 | 列出所有数据卷及挂载点 | 只读 |
| 系统诊断 | 宿主机 CPU / 内存 / 磁盘 / 网络 / 概览 | 基于 psutil |
| 权限控制 | RBAC 三角色 + 容器级 Scope | admin / operator / observer |

### 1.3 技术栈

- **语言**: Python 3.11
- **MCP 框架**: FastMCP 3.x（HTTP + JSON-RPC 传输）
- **Docker SDK**: docker Python SDK 7.x
- **系统监控**: psutil 7.x
- **配置格式**: PyYAML 6.x
- **容器化**: Docker + Docker Compose
- **镜像基础**: `python:3.11-slim`，单容器架构，内存占用约 50MB

---

## 2. 整体架构

### 2.1 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                   MCP Client（AI Agent）                      │
│   OpenClaw / Hermes / Trae / Cursor / Claude Code / Codex    │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP + JSON-RPC (Bearer Token)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  FastMCP HTTP Server（main.py 创建）                          │
│  ┌──────────────────┐   ┌────────────────────────────────┐  │
│  │  AuthMiddleware   │   │       MCP Tool Registry        │  │
│  │ (Bearer 提取+缓存)│   │  container / image / diag ...  │  │
│  └────────┬─────────┘   └─────────────┬──────────────────┘  │
│           │                           │                      │
│  ┌────────▼──────────┐   ┌────────────▼─────────────────┐   │
│  │ PermissionChecker │   │  DockerClient / SystemDiag    │   │
│  │ (RBAC + Scope)    │   │  (core 业务客户端)             │   │
│  └────────┬──────────┘   └────────────┬─────────────────┘   │
│           │                           │                      │
│  ┌────────▼────────────────────────────▼─────────────────┐  │
│  │  AuthConfig / Settings（YAML 加载，内存数据类）         │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  entrypoint.sh（root 调整 UID/GID + docker.sock 组）   │  │
│  │  → gosu 降权为 mcpuser 运行 main.py                    │  │
│  └───────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │ unix:///var/run/docker.sock
                           ▼
              ┌────────────────────────────┐
              │   Docker Daemon（NAS 宿主）  │
              └────────────────────────────┘
```

### 2.2 请求处理流程

```
MCP HTTP 请求
   │
   ▼
AuthMiddleware.on_request()
   ├─► 检查 session state 缓存（auth_key_config）
   │     ├─ 已缓存 → 跳过认证，直接放行
   │     └─ 未缓存 → 继续
   ├─► 从 Authorization 头提取 Bearer <api_key>
   │     └─ 缺失/格式错 → 抛 McpError(-32001)
   ├─► PermissionChecker.authenticate(api_key)
   │     ├─ 无效 → 抛 McpError(-32001)
   │     └─ 有效 → KeyConfig 存入 session state（serializable）
   ▼
MCP Tool 执行（tools/call）
   ├─► Tool 函数调用 DockerClient / SystemDiag
   │     └─ 业务层返回 {"success": bool, ...}
   ▼
JSON-RPC 响应（SSE / JSON）
```

> 注：当前实现中，RBAC 权限/Scope 的细粒度校验由 `PermissionChecker` 提供，认证在中间件完成；Tool 内部主要做业务调用。权限矩阵在 `auth.yaml` 的 `roles` 中声明。

### 2.3 关键设计原则

1. **单容器架构** — 所有功能打包进一个容器，最小化资源占用（约 50MB 内存）
2. **延迟连接** — `DockerClient` 懒加载，避免启动时因 socket 权限问题阻塞
3. **配置与密钥分离** — `config/` 存非敏感配置，`secrets/` 存 API Key（自动 600 权限）
4. **权限前置** — 认证中间件在 Tool 执行前完成身份验证
5. **NAS 友好** — `entrypoint.sh` 支持 PUID/PGID 调整，解决群晖挂载卷权限痛点

---

## 3. 目录结构

```
docker-mcpilots/
├── main.py                    # FastMCP 应用入口 + AuthMiddleware + 配置初始化
├── core/                      # 核心业务模块
│   ├── __init__.py
│   ├── config.py              # 配置数据类 + YAML 加载
│   ├── auth.py                # RBAC 权限检查器
│   ├── docker_client.py       # Docker SDK 封装层（懒加载）
│   └── system_diag.py         # 系统诊断（psutil）
├── tools/                     # MCP Tool 注册模块
│   ├── __init__.py
│   ├── container_tools.py     # 容器管理 + 容器诊断 Tools（13 个）
│   ├── image_tools.py         # 镜像管理 + 镜像诊断 Tools（4 个）
│   ├── diag_tools.py          # 系统诊断 Tools（5 个）
│   └── docker_diag_tools.py   # 网络/卷诊断 Tools（2 个，始终注册）
├── templates/                 # 默认配置模板（首次启动自动复制）
│   ├── settings.yaml
│   └── auth.yaml
├── tests/                     # 单元/集成测试
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_auth.py
│   ├── test_docker_client.py
│   ├── test_system_diag.py
│   └── test_integration.py
├── scripts/                   # 辅助脚本
│   ├── e2e_test.py            # 端到端测试（24 个工具）
│   └── integration_test.py    # 容器级集成测试
├── docker/                    # Docker 相关文件（隔离）
│   ├── Dockerfile
│   ├── entrypoint.sh          # UID/GID 调整 + 降权入口
│   ├── .dockerignore
│   ├── docker-compose.yml         # 预构建镜像版（推荐）
│   └── docker-compose-build.yml   # 源码构建版
├── docs/                      # 文档
│   ├── CODE_WIKI.md / CODE_WIKI_EN.md
│   ├── deploy-vps.md / deploy-vps_EN.md
│   ├── plans/                 # 实施计划
│   └── specs/                 # 设计规格书
├── assets/                    # 品牌素材（banner / logo）
├── requirements.txt
├── pytest.ini
├── CHANGELOG.md / CHANGELOG_EN.md
├── LICENSE                    # MIT
├── README.md / README_EN.md
└── .gitignore
```

---

## 4. 核心模块详解（core/）

### 4.1 core/config.py — 配置加载与数据类

**职责**: 定义所有配置相关的 `dataclass`，提供从 YAML 加载的能力，维护 API Key 查找索引。

#### 4.1.1 `Settings` 类

**位置**: [config.py](../core/config.py)

服务端主配置，对应 `config/settings.yaml`。

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `host` | str | `"0.0.0.0"` | 监听地址 |
| `port` | int | `8900` | 监听端口 |
| `log_level` | str | `"info"` | 日志级别（debug/info/warning/error） |
| `socket_path` | str | `"/var/run/docker.sock"` | Docker socket 路径 |
| `container_management` | bool | `True` | 启用容器管理 Tools |
| `image_management` | bool | `True` | 启用镜像管理 Tools |
| `system_diagnostics` | bool | `True` | 启用系统诊断 Tools |

**方法**:
- `from_yaml(path) -> Settings`：从 YAML 加载；文件不存在则返回默认值；YAML 非法时抛 `ValueError`

#### 4.1.2 `ScopeConfig` 类

容器级作用域配置，支持通配符匹配（`fnmatch` 语法）。

| 字段 | 类型 | 说明 |
|---|---|---|
| `containers_include` | list[str] | 白名单，仅允许匹配的容器 |
| `containers_exclude` | list[str] | 黑名单，排除匹配的容器（优先级高于 include） |

**方法**: `from_dict(data) -> ScopeConfig | None`（无数据返回 None，表示无限制）

#### 4.1.3 `RoleConfig` 类

角色配置。

| 字段 | 类型 | 说明 |
|---|---|---|
| `description` | str | 角色描述 |
| `permissions` | list[str] | 权限列表，格式 `"resource:action"`，支持 `*` 通配 |

#### 4.1.4 `KeyConfig` 类

单个 API Key 配置。

| 字段 | 类型 | 说明 |
|---|---|---|
| `key` | str | API Key 字符串 |
| `name` | str | Key 标识名（用于日志） |
| `role` | str | 关联角色名 |
| `scope` | ScopeConfig \| None | 容器级作用域限制 |

#### 4.1.5 `AuthConfig` 类

完整的权限配置（`auth.yaml` 的内存表示）。

| 字段 | 类型 | 说明 |
|---|---|---|
| `roles` | dict[str, RoleConfig] | 角色定义字典 |
| `keys` | list[KeyConfig] | API Key 列表 |
| `_key_lookup` | dict[str, KeyConfig] | key 字符串 → KeyConfig 快速查找索引（`repr=False`） |

**方法**:
- `from_yaml(path) -> AuthConfig`：加载并校验 `roles`/`keys` 必须同时存在，构建查找索引
- `find_key(api_key) -> KeyConfig | None`：O(1) 查找

---

### 4.2 core/auth.py — 权限检查模块

**职责**: API Key 认证、角色权限验证（通配符）、容器级 Scope 检查。

#### 4.2.1 异常类

| 异常 | 说明 |
|---|---|
| `AuthenticationError` | API Key 认证失败（空/无效） |
| `PermissionDeniedError` | 权限不足或 Scope 限制 |

#### 4.2.2 `PermissionChecker` 类

**位置**: [auth.py](../core/auth.py)

所有权限判断的统一入口，构造时注入 `AuthConfig`。

| 方法 | 签名 | 行为 |
|---|---|---|
| `authenticate` | `(api_key: str) -> KeyConfig` | 空/未找到 → `AuthenticationError`；成功返回 `KeyConfig` |
| `check_permission` | `(key_config, permission: str) -> None` | 角色不存在或权限不足 → `PermissionDeniedError` |
| `check_scope` | `(key_config, container_name: str) -> None` | 无 scope 放行；include 不匹配拒绝；匹配 exclude 拒绝 |
| `check` | `(key_config, permission, container_name=None) -> None` | 便捷方法，依次检查权限和 scope |
| `_has_permission` *(静态)* | `(permissions, required) -> bool` | 通配符匹配核心逻辑 |

**通配符规则**（`_has_permission`）:
- `"*"` → 匹配所有权限
- `"resource:*"` → 匹配该资源下所有操作
- `"*:action"` → 匹配所有资源的该操作
- `"resource:action"` → 精确匹配

**Scope 匹配规则**（`check_scope`，使用 `fnmatch.fnmatch`）:
- 无 scope → 无限制
- 仅 include → 白名单模式
- 仅 exclude → 黑名单模式
- 同时存在 → 先过 include，再过 exclude（exclude 优先）

---

### 4.3 core/docker_client.py — Docker 客户端封装

**职责**: 封装 Docker Python SDK，提供延迟连接、统一错误处理、结构化返回格式，隔离底层 SDK 变更。

#### 4.3.1 模块级辅助函数

| 函数 | 位置 | 说明 |
|---|---|---|
| `_parse_since_until(value)` | [docker_client.py](../core/docker_client.py) | 解析日志时间参数：相对时间（`1h`/`30m`/`2d`/`45s`）或 RFC3339/ISO，返回 timezone-aware datetime |
| `_extract_mounts(attrs)` | 同上 | 从容器 attrs 提取挂载信息列表 |
| `_extract_health(state)` | 同上 | 从容器 state 提取健康检查信息（status/failing_streak/log） |
| `_change_kind_str(kind)` | 同上 | Docker 文件变更类型 `0/1/2` → `modified/added/deleted` |

#### 4.3.2 `DockerClient` 类

**构造参数**: `socket_path: str = "/var/run/docker.sock"`

**设计要点**:
- **延迟连接**：`_ensure_connected()` 仅在首次调用时通过 `docker.DockerClient(base_url=f"unix://{socket_path}")` 建立连接
- **导入容错**：`docker` 模块未安装时 `docker=None`，实例化才抛 `RuntimeError`
- **统一错误处理**：捕获 `DockerNotFound` / `DockerAPIError`，返回 `{"success": False, "error": ...}`

##### 容器操作方法

| 方法 | 参数 | 返回 |
|---|---|---|
| `list_containers` | `status?, all` | `list[dict]`（id/name/status/image） |
| `get_container` | `container_id` | 详情 dict（state/health/config/network/mounts） |
| `start_container` | `container_id` | `{"success", "container"}` |
| `stop_container` | `container_id` | `{"success", "container"}` |
| `restart_container` | `container_id` | `{"success", "container"}` |
| `remove_container` | `container_id, force` | `{"success", "removed"}` |
| `get_container_logs` | `container_id, tail?, since?, until?, timestamps` | `{"success", "container_id", "logs"}` |
| `get_container_stats` | `container_id` | CPU/内存/网络统计（单次采样） |

##### 容器诊断方法

| 方法 | 排查场景 |
|---|---|
| `get_container_processes` | 容器内进程列表（`container.top()`） |
| `get_container_health` | 健康检查状态 + 失败日志 |
| `get_container_networks` | IP/网关/MAC/DNS/端口映射 |
| `get_container_mounts` | 挂载卷/绑定路径/读写权限 |
| `get_container_changes` | 文件系统增删改（`container.diff()`，兜底 None→[]） |

##### 镜像操作方法

| 方法 | 参数 | 返回 |
|---|---|---|
| `list_images` | `name_filter?` | `list[dict]`（id/tags/size/created） |
| `pull_image` | `image_name, tag?` | `{"success", "image", "message"}` |
| `remove_image` | `image_name, force` | `{"success", "removed"}` |
| `inspect_image` | `image_name` | 镜像详情（cmd/entrypoint/env/ports/history 等） |

##### Docker 资源方法

| 方法 | 说明 |
|---|---|
| `list_networks` | 所有 Docker 网络（id/name/driver/scope/subnet/containers） |
| `list_volumes` | 所有 Docker 卷（name/driver/mountpoint/created/in_use） |

##### 内部格式化方法（静态）

| 方法 | 输出字段 |
|---|---|
| `_format_container` | id, name, status, image |
| `_format_container_detail` | id, name, status, image, created, labels, state, health, config, network, mounts |
| `_format_image` | id, tags, size, created |

**返回格式约定**: 操作类方法统一返回 `{"success": bool, ...}`；成功含结果数据，失败含 `error` 字段。

---

### 4.4 core/system_diag.py — 系统诊断模块

**职责**: 基于 psutil 采集宿主机系统级诊断信息，所有方法即时采集、无状态。

#### `SystemDiag` 类

**位置**: [system_diag.py](../core/system_diag.py)

| 方法 | 返回字段 |
|---|---|
| `get_system_info()` | hostname, os, kernel, architecture, boot_time, uptime_seconds |
| `get_cpu_info(per_core=False)` | percent, count_logical, count_physical, freq_current/min/max_mhz, percent_per_core（可选） |
| `get_memory_info()` | virtual{total,used,available,percent}, swap{total,used,free,percent} |
| `get_disk_info()` | partitions[]{device,mountpoint,fstype,total,used,free,percent} |
| `get_network_info()` | total{bytes_sent/recv,packets_sent/recv}, per_interface_io, interfaces{isup,speed,mtu} |

**注意**:
- CPU 使用率用 0.5s 间隔采样（`psutil.cpu_percent(interval=0.5)`）
- 磁盘分区读取失败（权限不足）时跳过该分区
- 网络信息包含总流量、单网卡流量、网卡状态

---

## 5. 工具模块详解（tools/）

### 5.1 设计模式：注册器 + 闭包

工具模块统一采用「注册器模式 + 闭包」：
- 每个模块导出 `register_*_tools(mcp: FastMCP, client)` 函数
- 内部用 `@mcp.tool` 装饰器定义 Tool 函数，通过闭包访问业务客户端
- 在 `create_app()` 中按功能开关依次调用

```python
def register_container_tools(mcp: FastMCP, docker_client: DockerClient):
    @mcp.tool
    def list_containers(status: str | None = None, all: bool = False) -> list[dict]:
        """列出 Docker 容器。"""
        return docker_client.list_containers(status=status, all=all)
    # ... 更多 Tool
```

### 5.2 tools/container_tools.py — 容器管理 Tools

**注册函数**: `register_container_tools(mcp, docker_client)`（13 个 Tool）

| Tool | 参数 | 说明 | 排查场景 |
|---|---|---|---|
| `list_containers` | `status?, all` | 列出容器 | — |
| `inspect_container` | `container_id` | 容器详情（state/health/config/network/mounts） | 起不来/状态异常 |
| `start_container` | `container_id` | 启动容器 | — |
| `stop_container` | `container_id` | 停止容器 | — |
| `restart_container` | `container_id` | 重启容器 | — |
| `get_container_logs` | `container_id, tail?, since?, until?, timestamps` | 日志（支持时间段） | 错误排查 |
| `get_container_stats` | `container_id` | CPU/内存/网络 | 资源占用 |
| `remove_container` | `container_id, force?` | 删除容器（仅 admin） | — |
| `get_container_processes` | `container_id` | 进程列表 | 容器卡住 |
| `get_container_health` | `container_id` | 健康检查 + 失败日志 | 容器不健康 |
| `get_container_networks` | `container_id` | IP/网关/DNS/端口 | 连不上网 |
| `get_container_mounts` | `container_id` | 挂载卷/读写权限 | 数据丢失/权限不对 |
| `get_container_changes` | `container_id` | 文件系统增删改 | 容器里改了什么 |

### 5.3 tools/image_tools.py — 镜像管理 Tools

**注册函数**: `register_image_tools(mcp, docker_client)`（4 个 Tool）

| Tool | 参数 | 说明 |
|---|---|---|
| `list_images` | `name_filter?` | 列出本地镜像 |
| `pull_image` | `image_name, tag?` | 拉取镜像（默认 latest） |
| `remove_image` | `image_name, force?` | 删除镜像（仅 admin） |
| `inspect_image` | `image_name` | 镜像详情（entrypoint/env/ports/history） |

### 5.4 tools/diag_tools.py — 系统诊断 Tools

**注册函数**: `register_diag_tools(mcp, system_diag)`（5 个 Tool）

| Tool | 参数 | 说明 |
|---|---|---|
| `get_system_info` | — | 主机名/OS/内核/运行时间 |
| `get_cpu_info` | `per_core?` | CPU 使用率与信息 |
| `get_memory_info` | — | 物理内存 + Swap |
| `get_disk_info` | — | 所有分区使用情况 |
| `get_network_info` | — | 网卡流量与状态 |

### 5.5 tools/docker_diag_tools.py — Docker 资源诊断 Tools

**注册函数**: `register_docker_diag_tools(mcp, docker_client)`（2 个 Tool，**始终注册**，不受功能开关控制，用于排查容器问题）

| Tool | 说明 |
|---|---|
| `list_networks` | 所有 Docker 网络及连接容器（排查「容器之间通不通」） |
| `list_volumes` | 所有 Docker 卷及挂载点（排查「数据存储在哪里」） |

---

## 6. 应用入口与中间件（main.py）

**位置**: [main.py](../main.py)

### 6.1 常量与环境变量

```python
CONFIG_DIR   = Path(os.environ.get("MCP_CONFIG_DIR",   "/app/config"))
SECRETS_DIR  = Path(os.environ.get("MCP_SECRETS_DIR",  "/app/secrets"))
TEMPLATE_DIR = Path(__file__).parent / "templates"
```

### 6.2 `AuthMiddleware` 类

**位置**: [main.py](../main.py)（`Middleware` 子类）

API Key 认证中间件，实现 FastMCP 的 `Middleware` 接口。

**工作流程**:
1. 从 session state 读取 `auth_key_config`，命中缓存则直接放行
2. 调用 `get_http_headers(include={"authorization"})` 显式提取 authorization 头（FastMCP 默认会过滤该头，必须显式 include）
3. 校验 `Bearer <api_key>` 格式，否则抛 `McpError(-32001)`
4. 调用 `PermissionChecker.authenticate(api_key)` 验证
5. 将 `KeyConfig` 存入 session state（`serializable=True`，跨请求持久化）

**异常映射**: `AuthenticationError` → `McpError(code=-32001, message=...)`

### 6.3 `_init_config_files()` 函数

首次启动时自动生成默认配置模板。

**执行步骤**:
1. 创建 `config/` 和 `secrets/` 目录（不存在时）
2. 若 `settings.yaml` 不存在，从 `templates/settings.yaml` 复制
3. 若 `auth.yaml` 不存在，从模板复制 + `chmod 600`，并打印警告提示改默认 Key
4. 统一将 `secrets/` 下所有文件权限设为 `600`

**错误处理**: 权限不足时给出明确的 PUID/PGID 排查提示（兼容 NAS 挂载卷场景）。

### 6.4 `create_app()` 函数

应用工厂，创建并配置完整的 FastMCP 实例。

**配置顺序**:
1. `_init_config_files()` 初始化配置
2. 加载 `Settings` 与 `AuthConfig`
3. 创建 `PermissionChecker`
4. 配置日志级别
5. 创建 `FastMCP(name="Docker-MCPilotS", version="1.0.0")`
6. 注册 `AuthMiddleware`
7. 创建 `DockerClient`（懒加载）与 `SystemDiag`
8. **按功能开关注册 Tools**:
   - `container_management` → `register_container_tools`
   - `image_management` → `register_image_tools`
   - `system_diagnostics` → `register_diag_tools`
   - `register_docker_diag_tools` **始终注册**（网络/卷诊断用于排查）
9. 注册 `/health` 健康检查端点
10. 日志输出注册的 API Key 数量与角色

### 6.5 健康检查端点

```python
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    return JSONResponse({"status": "ok", "version": "1.0.0"})
```

无需认证，用于容器健康检查与版本验证。

### 6.6 启动入口

```python
if __name__ == "__main__":
    mcp = create_app()
    settings = Settings.from_yaml(str(CONFIG_DIR / "settings.yaml"))
    mcp.run(transport="http", host=settings.host, port=settings.port)
```

---

## 7. 权限模型（RBAC + Scope）

### 7.1 角色定义（templates/auth.yaml 默认）

| 角色 | 权限 | 说明 |
|---|---|---|
| **admin** | `container:*`, `image:*`, `system:*`, `exec:*` | 完全控制（含删除） |
| **operator** | `container:list/inspect/start/stop/restart/logs/stats`<br>`image:list/pull`<br>`system:*` | 标准管理（不能删除） |
| **observer** | `container:list/inspect/logs/stats`<br>`image:list`<br>`system:*` | 只读 |

### 7.2 权限命名规范

格式: `resource:action`
- 资源类别: `container` / `image` / `system` / `exec`（预留）
- 通配: `*`（全通配）/ `resource:*`（资源通配）/ `*:action`（操作通配）

### 7.3 容器级 Scope

每个 API Key 可配置容器级访问范围：

```yaml
keys:
  - key: "sk-dm-xxx"
    name: "home-assistant"
    role: operator
    scope:
      containers:
        include: ["home-*", "nginx"]   # 白名单
        exclude: ["home-db"]           # 黑名单（优先级更高）
```

匹配使用 `fnmatch` 通配符（`*` `?` `[seq]`）。

### 7.4 认证状态持久化

认证结果通过 `ctx.set_state("auth_key_config", key_config, serializable=True)` 存入 FastMCP session state。MCP 协议是有会话的，同一会话内复用，避免重复读 `auth.yaml`。

---

## 8. MCP Tools 总览

项目共注册 **24 个 MCP Tools**，按功能开关动态加载（`docker_diag_tools` 始终加载）：

| 模块 | Tools 数 | Tool 列表 |
|---|---|---|
| container_tools | 13 | list_containers, inspect_container, start_container, stop_container, restart_container, get_container_logs, get_container_stats, remove_container, get_container_processes, get_container_health, get_container_networks, get_container_mounts, get_container_changes |
| image_tools | 4 | list_images, pull_image, remove_image, inspect_image |
| diag_tools | 5 | get_system_info, get_cpu_info, get_memory_info, get_disk_info, get_network_info |
| docker_diag_tools | 2 | list_networks, list_volumes |
| **合计** | **24** | |

---

## 9. 配置说明

### 9.1 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `MCP_CONFIG_DIR` | `/app/config` | 配置文件目录 |
| `MCP_SECRETS_DIR` | `/app/secrets` | 密钥文件目录 |
| `PUID` | `1000` | 运行用户 UID（entrypoint 调整） |
| `PGID` | `1000` | 运行用户 GID（entrypoint 调整） |
| `TZ` | — | 时区，建议 `Asia/Shanghai` |

### 9.2 settings.yaml（`config/settings.yaml`）

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

### 9.3 auth.yaml（`secrets/auth.yaml`，权限 600）

```yaml
roles:
  admin:
    description: "完全控制权限"
    permissions: ["container:*", "image:*", "system:*", "exec:*"]
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

keys:
  - key: "sk-dm-CHANGE-THIS-KEY-IMMEDIATELY"
    name: "default-admin"
    role: admin
    # scope:                         # 可选，容器级限制
    #   containers:
    #     include: ["web-*"]
    #     exclude: ["web-db"]
```

---

## 10. 容器化与部署

### 10.1 Dockerfile 要点

**位置**: [docker/Dockerfile](../docker/Dockerfile)

- 基础镜像 `python:3.11-slim`
- 安装 `gosu`（用于降权运行）
- 精确复制 `core/` `tools/` `main.py` `templates/`，避免把 `.venv/tests/docs/scripts` 打入镜像
- 创建 `mcpuser` 用户，`/app/config` `/app/secrets` 目录
- `EXPOSE 8900`，`ENTRYPOINT ["/app/entrypoint.sh"]`，`CMD ["python", "main.py"]`

### 10.2 entrypoint.sh 要点

**位置**: [docker/entrypoint.sh](../docker/entrypoint.sh)

解决 NAS 挂载卷权限问题的核心脚本：

1. 读取 `PUID`/`PGID`（默认 1000）
2. 若当前 `mcpuser` 的 UID/GID 与目标不符，用 `usermod`/`groupmod` 调整，并 `chown` 修正 `/app` 下文件属主
3. `chown` 挂载目录 `config/` `secrets/` 为目标 UID/GID
4. **关键修复**：若 `/var/run/docker.sock` 存在，以 root 身份 `chgrp` 将其组改为 `PGID`（因为 `gosu` 降权会清除补充组，`group_add` 方案无效）
5. `exec gosu mcpuser "$@"` 降权运行主程序（`exec` 实现干净进程替换）

### 10.3 三种部署方式

#### 方式一：预构建镜像（推荐，NAS / 通用 Linux）

```bash
mkdir docker-mcpilots && cd docker-mcpilots
mkdir config secrets
# 复制 templates/settings.yaml → config/settings.yaml
# 复制 templates/auth.yaml   → secrets/auth.yaml（改 API Key！）
# 放入 docker/docker-compose.yml
docker compose up -d
```

镜像地址：
- GHCR: `ghcr.io/sopyk/docker-mcpilots:latest`
- Docker Hub: `sopyk/docker-mcpilots:latest`

#### 方式二：源码构建（开发者）

```bash
git clone https://github.com/sopyk/docker-mcpilots.git
cd docker-mcpilots
docker compose -f docker/docker-compose-build.yml up -d --build
```

#### 方式三：VPS 宿主机直装

无需 Docker 嵌套，资源占用最低，支持 systemd / nginx 反代 / TLS。详见 [docs/deploy-vps.md](deploy-vps.md)。

### 10.4 支持架构

| 架构 | 状态 | 适用设备 |
|---|---|---|
| linux/amd64 | ✅ 已支持 | 群晖/威联通 Intel/AMD NAS、多数 VPS、PC 服务器 |
| linux/arm64 | ✅ 已支持 | 树莓派、Mac M 系列、部分 ARM NAS |
| linux/arm/v7 | ❌ 暂不支持 | 老款 32 位 ARM 设备 |

### 10.5 健康检查

```bash
curl http://localhost:8900/health
# {"status":"ok","version":"1.0.0"}
```

### 10.6 MCP 客户端连接配置

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

## 11. 测试体系

### 11.1 测试结构

| 文件 | 覆盖范围 | 类型 |
|---|---|---|
| `tests/test_config.py` | 配置加载、数据类 | 单元测试 |
| `tests/test_auth.py` | 认证、权限、Scope（含通配符） | 单元测试 |
| `tests/test_docker_client.py` | Docker 客户端封装（mock SDK） | 单元测试 |
| `tests/test_system_diag.py` | 系统诊断（mock psutil） | 单元测试 |
| `tests/test_integration.py` | 应用启动、Tool 注册、配置初始化 | 集成测试（mock） |
| `scripts/e2e_test.py` | 模拟 MCP 客户端调用全部 24 个工具 | 端到端测试 |
| `scripts/integration_test.py` | 镜像构建/启动/握手/Tool 调用 | 容器级集成测试 |

### 11.2 运行测试

```bash
# 单元测试
pytest tests/ -v

# 端到端测试（需先启动 server）
docker run -d --name dm-e2e-test alpine sh -c 'while true; do echo heartbeat; sleep 5; done'
MCP_CONFIG_DIR=./config MCP_SECRETS_DIR=./secrets python main.py &
python scripts/e2e_test.py
docker rm -f dm-e2e-test

# 容器集成测试（需先构建镜像）
python scripts/integration_test.py
```

### 11.3 e2e_test.py 验证项

1. MCP 握手（initialize / initialized）
2. 工具列表（tools/list，期望 24 个）
3. 5 个系统诊断工具
4. 容器工具（list / inspect / logs / stats + 5 个诊断工具）+ 不存在容器的错误路径
5. 镜像工具（list / inspect）
6. Docker 资源诊断（list_networks / list_volumes）

### 11.4 integration_test.py 验证项

1. 版本号一致性（main.py 与 health check）
2. 镜像大小合理性（>1GB 报警）
3. 容器启动 + 健康检查 + MCP 握手 + Tool 调用
4. `.dockerignore` 规则检查
5. `entrypoint.sh` 执行权限检查

---

## 12. 依赖关系

### 12.1 模块依赖图

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
core.docker_client └── docker   (第三方 SDK)
core.system_diag   └── psutil   (第三方库)
```

### 12.2 第三方依赖（requirements.txt）

| 包名 | 版本要求 | 用途 |
|---|---|---|
| `fastmcp` | `>=3.0.0` | MCP 服务框架（HTTP 传输 + 中间件） |
| `docker` | `>=7.0.0` | Docker Engine API 客户端 |
| `psutil` | `>=7.0.0` | 跨平台系统信息采集 |
| `pyyaml` | `>=6.0` | YAML 配置解析 |

### 12.3 运行时依赖

- **Docker daemon**：通过 `unix:///var/run/docker.sock` 通信
- **Linux 环境**：psutil 跨平台，但主要目标是 NAS Linux
- **gosu**：容器内降权运行（Dockerfile 安装）

### 12.4 调用链路（以 `start_container` 为例）

```
MCP Client
  → FastMCP HTTP Server
  → AuthMiddleware.on_request (Bearer 提取 + PermissionChecker.authenticate)
  → tools/container_tools.py :: start_container (闭包)
  → core/docker_client.py :: DockerClient.start_container
  → _ensure_connected() → docker.DockerClient(...).containers.get(id).start()
  → 返回 {"success": true, "container": {...}}
  → JSON-RPC 响应
```

---

## 13. 关键设计决策

### 13.1 延迟连接（Lazy Connection）

`DockerClient` 在首次调用时才连接 Docker daemon。
- 避免启动时因 socket 权限/路径问题导致容器无法启动
- 健康检查等非 Docker 操作不受影响
- 在实际调用时报错，错误更可定位

### 13.2 配置与密钥分离

`config/`（非敏感）与 `secrets/`（敏感）分目录：
- 安全最佳实践
- `secrets/` 下文件自动 `chmod 600`
- 不同的备份策略和权限控制

### 13.3 PUID/PGID + gosu 降权

`entrypoint.sh` 以 root 启动 → 调整 `mcpuser` 的 UID/GID → `chown` 挂载卷 → `chgrp` docker.sock → `exec gosu mcpuser` 降权运行。
- 解决群晖 NAS 挂载卷权限痛点
- **关键修复**（v0.1.3）：`gosu` 降权会清除补充组，`group_add` 无效；改为以 root 将 docker.sock 组直接改为 `PGID`
- **关键修复**（v0.1.3）：`docker.from_env()` 在非 root 环境不稳定，改用显式 `unix://` socket 连接

### 13.4 单容器架构

所有功能打包进单容器：
- 最小化资源占用（NAS 资源有限，约 50MB 内存）
- 简化部署和管理
- 功能耦合度高，分拆无明显收益

### 13.5 .dockerignore 优化

排除 `*.tar.gz`、`config/`、`secrets/`、`.git`、`__pycache__` 等：
- 镜像大小从 ~1.2GB 降至 ~75MB
- 构建更快，传输更低

### 13.6 Session 级认证缓存

认证结果存入 FastMCP session state（`serializable=True`）：
- MCP 协议有会话，同会话内复用认证
- 减少 `auth.yaml` 读取
- **关键修复**（v0.1.2）：`get_state()` 不接受 `default=None`；`get_http_headers()` 默认过滤 `authorization`，需 `include={"authorization"}`；`set_state()` 需 `serializable=True`

### 13.7 始终注册 Docker 资源诊断

`register_docker_diag_tools`（网络/卷）不受功能开关控制，始终注册——因为排查容器问题离不开网络和卷信息。

---

## 14. 安全模型与能力边界

### 14.1 能做的（受控开放）

- 容器：列出/查看/启停/重启/删除
- 日志：按时间段筛选
- 资源：CPU/内存/网络实时查看
- 诊断：进程/健康/网络/挂载/文件变更/镜像详情
- 网络与卷：只读查看
- 系统：宿主机 CPU/内存/磁盘/网络
- 权限：三角色 + 容器级 Scope

### 14.2 做不了的（安全限制）

| 限制 | 原因 |
|---|---|
| Compose 项目管理（`docker compose up/down`） | Docker SDK 不支持 Compose，只能管单容器 |
| 编辑 Compose 文件 | 容器内无法访问宿主机 compose 文件 |
| 构建镜像 | 出于安全考虑，未开放 `docker build` |
| 执行任意命令 | 不提供 `docker exec`，避免命令注入 |
| 修改 Docker 网络配置 | 只读查看，不能创建/删除/修改 |

### 14.3 安全建议

- 生产环境务必修改默认 API Key
- 限制容器 scope，只给必要权限
- 通过反向代理加 TLS 访问
- 默认仅监听本地回环，勿直接暴露公网
- 定期检查日志

---

## 15. 版本历史

| 版本 | 日期 | 主要变更 |
|---|---|---|
| 1.0.0 | 2026-07-04 | 首个正式发布：项目改名 Docker-MCPilotS、中英双语文档、amd64 镜像、MIT LICENSE |
| 0.1.4 | 2026-07-04 | 新增 8 个容器/镜像/网络/卷诊断工具，日志增强 since/until/timestamps，VPS 部署指南 |
| 0.1.3 | 2026-07-04 | 修复 docker.sock 组权限（gosu 清除补充组）、Docker SDK 显式 socket 连接 |
| 0.1.2 | 2026-07-03 | 修复 FastMCP 3.4.2 兼容性、Auth 中间件请求头过滤、认证状态持久化；.dockerignore 优化镜像至 75MB |
| 0.1.1 | 2026-07-03 | PUID/PGID 支持、gosu 降权、群晖 compose 文件 |
| 0.1.0 | 2026-07-03 | 初始版本：FastMCP MCP Server、容器/镜像/系统诊断 Tools、RBAC、API Key 认证、配置/密钥分离、健康检查 |

---

## 附录：常用排查场景对应工具

| 用户问题 | Agent 会调用的工具 |
|---|---|
| "jellyfin 怎么没起来？" | `inspect_container` + `get_container_logs` + `get_container_health` |
| "所有容器 CPU/内存占用？" | `list_containers` + `get_container_stats`（逐个） |
| "把 jellyfin 停一下" | `stop_container` |
| "最近 30 分钟 jellyfin 日志" | `get_container_logs(since="30m")` |
| "jellyfin 网络配置/端口映射？" | `get_container_networks` + `list_networks` |
| "数据丢失/权限不对？" | `get_container_mounts` + `list_volumes` |
| "容器里改了什么？" | `get_container_changes` |
| "容器卡住了？" | `get_container_processes` |

---

*本文档基于 `main` 分支源码分析生成，最后更新于 2026-07-05。*
