# DockerMaintainer MCP Server

在群晖 NAS 中以 Docker 容器方式运行的 MCP Server，提供 Docker 容器/镜像管理能力和系统诊断功能，支持 RBAC 权限控制。

## 功能概览

| 类别 | 能力 | 说明 |
|---|---|---|
| 容器管理 | 列出/查看/启停/重启/删除容器 | 支持按状态过滤 |
| 容器管理 | 查看容器日志 | 支持限制返回行数 |
| 容器管理 | 查看容器资源占用 | CPU、内存、网络实时统计 |
| 镜像管理 | 列出/拉取/删除镜像 | 支持名称过滤 |
| 系统诊断 | CPU/内存/磁盘/网络 | 基于 psutil 采集 |
| 系统诊断 | 系统概览 | 主机名、OS、内核、运行时间 |

## 权限模型

支持 **admin**、**operator**、**observer** 三个预定义角色，可按容器设置 `include/exclude` scope，支持通配符匹配。

## 快速部署

### 1. 构建镜像

```bash
docker build -t docker-mcp-server:latest .
```

### 2. 启动服务

```bash
mkdir -p config secrets
docker compose up -d
```

### 3. 配置 API Key

首次启动会自动生成配置模板，编辑 `secrets/auth.yaml` 设置你的 API Key：

```yaml
keys:
  - key: "sk-dm-your-secure-key"
    name: "my-agent"
    role: admin
```

### 4. 重启生效

```bash
docker compose restart
```

## 文件结构

```
docker-mcp-server/
├── main.py              # FastMCP 入口
├── core/
│   ├── config.py        # 配置加载
│   ├── auth.py          # RBAC 权限检查
│   ├── docker_client.py # Docker SDK 封装
│   └── system_diag.py   # 系统诊断
├── tools/
│   ├── container_tools.py
│   ├── image_tools.py
│   └── diag_tools.py
├── templates/
│   ├── settings.yaml    # 默认配置模板
│   └── auth.yaml        # 默认权限模板
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 技术栈

- Python 3.11 + FastMCP 3.x
- docker Python SDK 7.x
- psutil 7.x

## 设计文档

- [设计规格书](docs/superpowers/specs/2026-07-01-synology-mcp-server-design.md)
- [实施计划](docs/superpowers/plans/2026-07-01-synology-mcp-server.md)
- [版本管理策略](docs/superpowers/specs/2026-07-03-version-management.md)
