# DockerMaintainer MCP Server

以 MCP（Model Context Protocol）协议暴露 Docker 容器/镜像管理能力和系统诊断功能的轻量级服务，专为 AI agent 远程排查容器问题设计。

支持两种部署方式：
- **容器化部署**（推荐用于群晖 NAS 等脆弱系统）
- **宿主机直装**（推荐用于 VPS / 干净的 Linux 服务器）

## 功能概览

围绕"排查容器问题"核心目标，提供 24 个 MCP 工具：

| 类别 | 工具 | 排查场景 |
|---|---|---|
| 容器管理 | list_containers / inspect_container / start / stop / restart / remove | 基础查控 |
| 容器日志 | get_container_logs | 支持 tail / since / until / timestamps，按时间段排查 |
| 容器资源 | get_container_stats | CPU / 内存 / 网络实时占用 |
| 容器进程 | get_container_processes | 容器内进程列表（排查"卡死"） |
| 容器健康 | get_container_health | 健康检查状态 + 失败日志（排查"不健康"） |
| 容器网络 | get_container_networks | IP / 网关 / DNS / 端口映射（排查"连不上网"） |
| 容器挂载 | get_container_mounts | 挂载卷 / 绑定路径 / 读写权限（排查"数据丢失/权限不对"） |
| 容器变更 | get_container_changes | 文件系统增删改（排查"容器里改了什么"） |
| 镜像管理 | list_images / pull_image / remove_image | 基础查控 |
| 镜像诊断 | inspect_image | 入口命令 / 环境变量 / 历史构建层（排查"镜像有没有问题"） |
| 网络拓扑 | list_networks | 所有 Docker 网络及连接的容器（排查"容器之间通不通"） |
| 卷清单 | list_volumes | 所有卷及挂载点（排查"数据存储在哪里"） |
| 系统诊断 | get_system_info / get_cpu_info / get_memory_info / get_disk_info / get_network_info | 主机资源监控 |

## 权限模型

支持 **admin**、**operator**、**observer** 三个预定义角色，可按容器设置 `include/exclude` scope，支持通配符匹配。详见 [templates/auth.yaml](templates/auth.yaml)。

## 部署方式

### 方式一：Docker 容器部署（推荐用于 NAS）

适合群晖等脆弱系统，避免宿主机污染。

```bash
# 1. 构建镜像（本机预构建，避免在 NAS 上构建）
docker build --platform linux/amd64 -t docker-mcp-server:v0.1.3 .
docker save docker-mcp-server:v0.1.3 | gzip > docker-mcp-server-v0.1.3.tar.gz

# 2. 传到 NAS 后加载
docker load < docker-mcp-server-v0.1.3.tar.gz

# 3. 准备配置目录
mkdir -p config secrets

# 4. 启动（使用 NAS 专用 compose）
docker compose -f docker-compose.nas.yml up -d
```

NAS 部署通过 `PUID`/`PGID` 环境变量解决 docker.sock 和挂载卷的权限问题，详见 [docker-compose.nas.yml](docker-compose.nas.yml) 和 [entrypoint.sh](entrypoint.sh)。

### 方式二：宿主机直装（推荐用于 VPS）

适合干净的 Linux 服务器，省去容器嵌套，资源占用更低。

```bash
# 1. 安装 Python 依赖
pip install -r requirements.txt

# 2. 准备配置
mkdir -p config secrets
cp templates/settings.yaml config/
cp templates/auth.yaml secrets/
chmod 600 secrets/auth.yaml
# 编辑 secrets/auth.yaml 设置你自己的 API Key

# 3. 启动（默认监听 0.0.0.0:8900）
MCP_CONFIG_DIR=./config MCP_SECRETS_DIR=./secrets python main.py
```

**前置条件**：运行用户必须能访问 `/var/run/docker.sock`（加入 `docker` 组或用 sudo）。

**生产环境建议**：
- 用 systemd 托管进程
- 监听 `127.0.0.1` + nginx 反代 + TLS
- 用防火墙限制 8900 端口访问来源

## 配置说明

| 文件 | 位置 | 作用 |
|---|---|---|
| [templates/settings.yaml](templates/settings.yaml) | 复制到 `config/settings.yaml` | 服务监听地址、Docker socket 路径、功能开关 |
| [templates/auth.yaml](templates/auth.yaml) | 复制到 `secrets/auth.yaml` | API Key、角色、容器 scope（敏感，权限 600） |

敏感配置（auth.yaml）和非敏感配置（settings.yaml）分目录存放，便于备份和权限隔离。

## 文件结构

```
dockermaintainer/
├── main.py                       # FastMCP 入口
├── entrypoint.sh                 # 容器入口（PUID/PGID 调整 + docker.sock 权限）
├── core/
│   ├── config.py                 # 配置加载
│   ├── auth.py                   # RBAC 权限检查
│   ├── docker_client.py          # Docker SDK 封装（所有诊断方法）
│   └── system_diag.py            # 系统诊断（psutil）
├── tools/
│   ├── container_tools.py        # 容器管理 + 容器诊断 MCP 工具
│   ├── image_tools.py            # 镜像管理 + 镜像诊断 MCP 工具
│   ├── diag_tools.py             # 系统诊断 MCP 工具
│   └── docker_diag_tools.py      # 网络和卷诊断 MCP 工具
├── templates/
│   ├── settings.yaml             # 默认配置模板
│   └── auth.yaml                 # 默认权限模板
├── tests/                        # 单元测试（37 个用例）
├── scripts/
│   ├── e2e_test.py               # 端到端测试（模拟 MCP 客户端调 24 个工具）
│   └── integration_test.py
├── docs/
│   ├── CODE_WIKI.md              # 项目架构 Wiki
│   └── superpowers/              # 设计文档和实施计划
├── Dockerfile
├── docker-compose.yml            # 通用 compose（含 build）
├── docker-compose.nas.yml        # NAS 专用 compose（预加载镜像 + PUID/PGID）
├── requirements.txt
├── CHANGELOG.md
└── README.md
```

## 技术栈

- Python 3.11 + FastMCP 3.x
- docker Python SDK 7.x
- psutil 7.x
- 单容器架构，资源占用极低

## 测试

```bash
# 单元测试
pytest tests/

# 端到端测试（需启动一个真实容器作为测试目标）
docker run -d --name dm-e2e-test alpine sh -c 'while true; do echo heartbeat; sleep 5; done'
MCP_CONFIG_DIR=./config MCP_SECRETS_DIR=./secrets python main.py &
python scripts/e2e_test.py
docker rm -f dm-e2e-test
```

## 分支策略

- `main`：稳定基线，对应已发布版本
- `dev`：开发分支，新功能先合入 dev，验证后再合入 main 发版

## 设计文档

- [设计规格书](docs/superpowers/specs/2026-07-01-synology-mcp-server-design.md)
- [实施计划](docs/superpowers/plans/2026-07-01-synology-mcp-server.md)
- [版本管理策略](docs/superpowers/specs/2026-07-03-version-management.md)
- [项目架构 Wiki](docs/CODE_WIKI.md)
- [变更日志](CHANGELOG.md)
