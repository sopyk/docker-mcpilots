# Synology NAS MCP Server 设计规格书

> **项目名称：** DockerMaintainer MCP Server
> **版本：** v1.0
> **日期：** 2026-07-01
> **状态：** 待审核

---

## 1. 项目概述

### 1.1 目标

在群晖 NAS 中以 Docker 容器方式部署一个 MCP (Model Context Protocol) Server，使局域网内任意机器的 AI Agent 能通过该服务器安全地管理 NAS 上的 Docker 容器、镜像，并获取系统诊断信息。

### 1.2 核心需求

- 暴露 Docker 容器和镜像的管理能力给 AI Agent
- 提供系统资源诊断（CPU、内存、磁盘、网络）
- 基于 API Key 的安全认证
- 多角色分级权限（RBAC）+ 容器级细粒度访问控制
- 配置与敏感数据（Secrets）分离
- 单容器极简部署，低资源占用

### 1.3 分阶段交付

| 阶段 | 内容 | 状态 |
|---|---|---|
| Phase 1 | MCP Server 核心（容器/镜像管理 + 系统诊断 + RBAC 权限） | 本次实施 |
| Phase 2 | 可选 Web 管理面板（权限管理 + 状态概览 + 资源监控） | 未来扩展 |

---

## 2. 技术栈

| 组件 | 技术选型 | 理由 |
|---|---|---|
| 运行时 | Python 3.11 slim | 系统运维生态成熟，Docker SDK 官方支持 |
| MCP 框架 | FastMCP | 官方推荐，轻量高效 |
| Docker 交互 | docker Python SDK | 官方维护，API 覆盖完整 |
| 系统诊断 | psutil | 跨平台系统信息采集 |
| 配置格式 | YAML | 人类可读，适合手动编辑 |
| 容器基础镜像 | python:3.11-slim | 体积小，资源占用低 |

---

## 3. 架构设计

### 3.1 整体架构

采用**单体轻量架构**，所有功能集成在单个 Python 进程内，通过 Docker Socket 与宿主机 Docker 引擎通信。

```
┌─────────────────────────────────────────────────┐
│              Docker Container                     │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ FastMCP  │──│ Auth     │──│ Docker Client│───┼──► Docker Socket
│  │ Server   │  │ Module   │  │ (SDK)        │   │    /var/run/docker.sock
│  └────┬─────┘  └──────────┘  └──────────────┘   │
│       │                                           │
│  ┌────┴──────────────────────┐                    │
│  │       MCP Tools           │                    │
│  │  ├─ Container Tools       │                    │
│  │  ├─ Image Tools           │                    │
│  │  └─ System Diag Tools      │                    │
│  └───────────────────────────┘                    │
│                                                   │
│  ┌──────────┐  ┌──────────┐                      │
│  │ config/  │  │ secrets/ │  (挂载自宿主机)        │
│  │settings  │  │auth.yaml│                      │
│  └──────────┘  └──────────┘                      │
└─────────────────────────────────────────────────┘
         ▲
         │ MCP Protocol (HTTP/SSE)
         │
    AI Agents (局域网内)
```

### 3.2 项目文件结构

```
docker-mcp-server/
├── Dockerfile
├── docker-compose.yml
├── main.py                  # FastMCP 入口，注册所有 MCP Tools
├── config/
│   └── settings.yaml       # 服务端配置（端口、日志级别等）
├── core/
│   ├── docker_client.py     # Docker SDK 封装，所有 Docker 操作
│   ├── system_diag.py       # 系统诊断（psutil + 群晖适配）
│   └── auth.py              # API Key 验证与权限检查
├── tools/
│   ├── container_tools.py   # 容器管理 MCP Tools
│   ├── image_tools.py       # 镜像管理 MCP Tools
│   └── diag_tools.py        # 系统诊断 MCP Tools
├── templates/
│   ├── settings.yaml        # 默认配置模板
│   └── auth.yaml            # 默认权限配置模板
└── requirements.txt
```

---

## 4. 数据持久化策略

### 4.1 Secrets 分离设计

配置与敏感数据通过两个独立挂载点分离：

```yaml
volumes:
  - /volume1/docker/mcp-server/config:/app/config      # 普通配置
  - /volume1/docker/mcp-server/secrets:/app/secrets    # 敏感数据
```

**文件分离：**

| 路径 | 内容 | 敏感度 |
|---|---|---|
| `/app/config/settings.yaml` | 端口、日志级别、功能开关 | 低 |
| `/app/secrets/auth.yaml` | API Key 与权限映射 | 高 |

### 4.2 安全措施

- 容器启动时自动将 `secrets/` 内文件权限设为 `600`（仅所有者可读写）
- 支持环境变量注入 API Key（`MCP_AUTH_KEYS=key1:role1,key2:role2`），适合不想挂载 secrets 文件的场景
- 群晖 File Station 可对 `secrets` 文件夹单独设置访问权限

### 4.3 首次启动行为

1. 若 `config/` 为空 → 自动从 `templates/settings.yaml` 复制默认配置
2. 若 `secrets/` 为空且未配置环境变量 → 自动从 `templates/auth.yaml` 复制默认模板，输出安全警告日志
3. 用户编辑 `auth.yaml` 添加自己的 API Key 后重启服务生效

### 4.4 备份与迁移

- 备份 `/volume1/docker/mcp-server` 文件夹即备份全部配置
- 迁移到新机器只需复制该文件夹并调整 `docker-compose.yml` 中的路径

---

## 5. RBAC 权限系统

### 5.1 模型概述

采用 **角色 + 作用域 (Scope)** 双层模型：

- **角色 (Role)：** 定义一组操作权限（能做什么）
- **作用域 (Scope)：** 限定操作的目标范围（能操作哪些容器）
- **API Key → 绑定角色 + 可选 scope**

### 5.2 预定义角色

| 角色 | 说明 | 权限范围 |
|---|---|---|
| `admin` | 完全控制 | 所有操作（包括删除容器/镜像、容器内执行命令） |
| `operator` | 标准管理 | 启停容器、查看日志/状态、拉取镜像，不能删除或执行命令 |
| `observer` | 只读观测 | 查看容器/镜像状态、日志、资源占用，不能修改 |

### 5.3 auth.yaml 配置格式

```yaml
# --- 角色定义 ---
roles:
  admin:
    description: "完全控制权限"
    permissions:
      - container:*
      - image:*
      - system:*
      - exec:*
  operator:
    description: "标准管理权限"
    permissions:
      - container:list
      - container:start
      - container:stop
      - container:restart
      - container:logs
      - container:stats
      - image:list
      - image:pull
      - system:*
  observer:
    description: "只读权限"
    permissions:
      - container:list
      - container:logs
      - container:stats
      - image:list
      - system:*

# --- API Key 绑定 ---
keys:
  - key: "sk-dm-admin-xxxxxxxx"
    name: "admin-agent"
    role: admin

  - key: "sk-dm-op-001-xxxxxxxx"
    name: "home-agent"
    role: operator
    scope:
      containers:
        include: ["home-assistant", "homebridge"]

  - key: "sk-dm-op-002-xxxxxxxx"
    name: "media-agent"
    role: operator
    scope:
      containers:
        include: ["plex", "jellyfin", "transmission"]

  - key: "sk-dm-op-003-xxxxxxxx"
    name: "general-agent"
    role: operator
    # 不写 scope → 无容器限制

  - key: "sk-dm-obs-monitor-xxxxxxxx"
    name: "monitoring-agent"
    role: observer
```

### 5.4 权限检查流程

```
请求到达
  → 提取 API Key
  → 查找 Key 对应的角色和 scope
    → Key 不存在？ → 拒绝 (401 Unauthorized)
    → 角色权限不包含该操作？ → 拒绝 (403 Forbidden)
    → scope 限制了目标容器？ → 拒绝 (403 Forbidden)
    → 全部通过 → 执行操作
```

### 5.5 Scope 匹配规则

- `include` / `exclude` 支持**通配符**（`*` 匹配任意字符序列）
- 只写 `include`：白名单模式（仅匹配的容器可操作）
- 只写 `exclude`：黑名单模式（匹配的容器不可操作）
- 同时写 `include` + `exclude`：先 include 再 exclude
- 不写 `scope`：无限制（由角色权限决定）

**Scope 配置策略示例：**

```yaml
# 策略一：按前缀匹配（需要容器命名有规律）
scope:
  containers:
    include: ["home-*"]

# 策略二：精确指定容器名（不依赖命名规范）
scope:
  containers:
    include: ["home-assistant", "homebridge", "plex"]

# 策略三：排除敏感容器，其余均可操作
scope:
  containers:
    exclude: ["nas-core", "docker-mcp-server"]
```

### 5.6 MCP Tools 与权限映射

| MCP Tool | 权限标识 | admin | operator | observer |
|---|---|---|---|---|
| 列出所有容器 | container:list | Y | Y | Y |
| 获取容器详情 | container:inspect | Y | Y | Y |
| 启动容器 | container:start | Y | Y | - |
| 停止容器 | container:stop | Y | Y | - |
| 重启容器 | container:restart | Y | Y | - |
| 查看容器日志 | container:logs | Y | Y | Y |
| 查看容器资源占用 | container:stats | Y | Y | Y |
| 删除容器 | container:remove | Y | - | - |
| 列出所有镜像 | image:list | Y | Y | Y |
| 拉取镜像 | image:pull | Y | Y | - |
| 删除镜像 | image:remove | Y | - | - |
| 系统概览信息 | system:info | Y | Y | Y |
| CPU 使用率 | system:cpu | Y | Y | Y |
| 内存使用率 | system:memory | Y | Y | Y |
| 磁盘使用率 | system:disk | Y | Y | Y |
| 网络流量 | system:network | Y | Y | Y |
| 容器内执行命令 | exec:* | Y | - | - |

### 5.7 环境变量备选方案

不挂载 secrets 文件时，可通过环境变量注入：

```yaml
environment:
  # 格式：key:role,key:role
  - MCP_AUTH_KEYS=sk-dm-admin-xxx:admin,sk-dm-op-xxx:operator
  # 格式：key:scope.path=value
  - MCP_AUTH_SCOPES=sk-dm-op-xxx:containers.include=home-*
```

适合快速启动或 CI 测试场景。

---

## 6. MCP Tools 详细设计

### 6.1 容器管理 Tools

| Tool 名称 | 功能描述 | 参数 |
|---|---|---|
| `list_containers` | 列出容器（支持 all/running/stopped 过滤） | `status?: str` |
| `inspect_container` | 获取单个容器详细信息 | `container_id: str` |
| `start_container` | 启动指定容器 | `container_id: str` |
| `stop_container` | 停止指定容器 | `container_id: str` |
| `restart_container` | 重启指定容器 | `container_id: str` |
| `get_container_logs` | 获取容器日志（支持行数限制和尾部追踪） | `container_id: str, tail?: int, since?: str` |
| `get_container_stats` | 获取容器实时资源占用 | `container_id: str` |
| `remove_container` | 删除指定容器 | `container_id: str, force?: bool` |

### 6.2 镜像管理 Tools

| Tool 名称 | 功能描述 | 参数 |
|---|---|---|
| `list_images` | 列出本地镜像 | `name_filter?: str` |
| `pull_image` | 从 Docker Hub 拉取镜像 | `image_name: str, tag?: str` |
| `remove_image` | 删除本地镜像 | `image_id: str, force?: bool` |

### 6.3 系统诊断 Tools

| Tool 名称 | 功能描述 | 参数 |
|---|---|---|
| `get_system_info` | 获取系统概览（主机名、OS、内核、运行时间） | 无 |
| `get_cpu_info` | 获取 CPU 使用率（支持 per-core） | `per_core?: bool` |
| `get_memory_info` | 获取内存使用情况（总量/已用/可用） | 无 |
| `get_disk_info` | 获取磁盘使用情况（所有挂载点） | 无 |
| `get_network_info` | 获取网络接口流量统计 | 无 |

---

## 7. 部署方案

### 7.1 docker-compose.yml 示例

```yaml
version: "3.8"

services:
  docker-mcp-server:
    image: docker-mcp-server:latest
    container_name: docker-mcp-server
    restart: unless-stopped
    ports:
      - "8900:8900"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /volume1/docker/mcp-server/config:/app/config
      - /volume1/docker/mcp-server/secrets:/app/secrets
    environment:
      - TZ=Asia/Shanghai
      - LOG_LEVEL=info
    # 可选：不挂载 secrets 时用环境变量注入
    # environment:
    #   - MCP_AUTH_KEYS=sk-dm-xxx:admin
```

### 7.2 首次部署步骤

1. 将项目构建为 Docker 镜像
2. 在群晖上创建目录 `/volume1/docker/mcp-server/config` 和 `/volume1/docker/mcp-server/secrets`
3. 启动容器，自动生成默认配置模板
4. 编辑 `/volume1/docker/mcp-server/secrets/auth.yaml`，添加自己的 API Key
5. 重启容器，权限配置生效

### 7.3 Agent 端连接配置

AI Agent 通过 MCP 协议连接时需提供：
- 服务地址：`http://<NAS_IP>:8900`
- API Key：在请求头或 MCP 握手中携带

---

## 8. 错误处理

| 场景 | 处理方式 |
|---|---|
| API Key 缺失或无效 | 返回 401，附带清晰错误信息 |
| 权限不足 | 返回 403，说明缺少的权限 |
| 容器不存在 | 返回 404，附带可用容器列表提示 |
| Docker Socket 不可用 | 启动时检测，日志输出明确错误并拒绝启动 |
| 配置文件格式错误 | 启动时校验，日志输出具体错误行和修复建议 |

---

## 9. Phase 2 扩展（Web 管理面板）

以下功能作为 Phase 2 规划，不在本次实施范围内：

- **API Key 可视化管理**：Web 界面增删改 API Key 和权限
- **容器/镜像状态概览**：实时显示所有容器运行状态
- **系统资源监控仪表盘**：CPU、内存、磁盘、网络图表
- **服务健康状态**：MCP Server 自身运行状态监控

Phase 2 将基于 FastAPI + 静态页面实现，与 MCP Server 共容器或独立容器部署，共享 `auth.yaml` 和 Docker Socket。
