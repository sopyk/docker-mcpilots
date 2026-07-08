![Docker-MCPilotS Banner](assets/banner.jpg)

# 🐳 Docker-MCPilotS

> 🌐 [English](README_EN.md) | 简体中文

给 AI Agent 一双管理 Docker 的手（MCP Server）——群晖 NAS 上的容器管得好，任何装了 Docker 的机器都能用。

## 📦 支持的架构

| 架构 | 状态 | 适用设备 |
|------|------|----------|
| **linux/amd64 (x86_64)** | ✅ 已支持 | 群晖/威联通等 Intel/AMD 架构 NAS、大多数 VPS、普通 PC 服务器 |
| **linux/arm64** | 🚧 计划中 | 树莓派、Mac M 系列、部分 ARM 架构 NAS |
| **linux/arm/v7** | ❌ 暂不支持 | 老款树莓派等 32 位 ARM 设备 |

> 💡 目前版本仅提供 amd64 架构镜像。ARM 设备请自行从源码构建镜像。

## 🤔 为什么做这个？

日常使用群晖 NAS，上面跑了几十个 Docker 容器：PT 下载、媒体服务、照片备份、代码仓库……部署新服务的时候、升级更新的时候、甚至正常跑着用着，总会遇到各种问题：容器起不来了、权限不对了、连不上网了、占用资源高了……

以前排查问题要么 SSH 进去敲命令。群晖这种 NAS 系统跟标准的 Linux 服务器差别很大，命令、路径、权限体系都是定制过的，万一敲错轻则操作失败，重则把整个 NAS 搞坏。更要命的是，NAS 上往往还跑着照片备份、文件同步这些重要功能——搞坏了可不止几个容器不能用的问题，是整个家都瘫了。

要么打开群晖那个难用的 Docker 界面，点来点去找半天。

现在 Agent 很发达了，我想：**能不能让 AI 来帮我管这些容器？** 让它帮我排查问题、看看日志、启停服务，出了问题也不用心惊胆战的。

但又不能真的把 SSH 权限交给 Agent，NAS 系统太特殊了，万一出岔子代价太大。

所以就想到了 MCP（Model Context Protocol）——把 Docker 的管理能力通过 MCP 接口暴露出去，Agent 只能做我们允许的操作，不会误伤系统。本质上就是一个**沙箱里的 Docker 管理工具**。

有了这些念头，说干就干。这个项目是通过 **Vibe Coding** 方式做的。

## ✨ 功能一览

### ✅ 能做的

| 类别 | 能做什么 |
|------|----------|
| 🖼️ **Web UI** | 图形化管理界面，不用 AI 也能直观查看和管理容器 |
| 📦 容器管理 | 查看列表、查看详情、启动、停止、重启、删除 |
| 📜 容器日志 | 看日志，支持按时间段筛选（过去 1 小时、最近 30 分钟……） |
| 📊 容器资源 | CPU、内存、网络占用实时查看 |
| 🔍 容器诊断 | 进程列表、健康状态、网络连接、挂载卷、文件系统变更、镜像信息 |
| 🌐 网络拓扑 | 查看所有 Docker 网络和它们连接的容器 |
| 💾 卷清单 | 查看所有数据卷和它们的挂载点 |
| 🖥️ 系统诊断 | 宿主机 CPU、内存、磁盘、网络信息 |
| 🔐 权限控制 | 三种角色：管理员、操作员、观察者，可以按容器设置权限 |
| 🗝️ 管理工具 | Web UI 支持创建/编辑/删除 API Key，修改管理员密码，编辑系统设置 |

### ❌ 做不了的

| 限制 | 原因 |
|------|------|
| 🚫 **Compose 项目管理**（`docker compose up/down`） | Docker SDK 不支持 Compose 操作，只能管单个容器 |
| 🚫 **编辑 Compose 文件** | 容器内无法访问宿主机上的 compose 文件 |
| 🚫 **构建镜像** | 出于安全考虑，未开放 `docker build` 能力 |
| 🚫 **执行任意命令** | 不提供 `docker exec` 能力，避免命令注入风险 |
| 🚫 **修改 Docker 网络配置** | 只读查看，不能创建/删除/修改网络 |

## 📖 使用方法

### 📋 前置准备

1. 把这个 MCP Server 部署到你的 NAS 上（见下文部署方式）
2. 在 AI 客户端（OpenClaw、Hermes、Trae、Cursor、Claude Code、Codex……）里添加 MCP Server，填入地址和 API Key
3. 开始对话，让 Agent 帮你管理容器

### 💬 典型场景

**排查容器为什么起不来：**
> "帮我看看 jellyfin 容器怎么回事？怎么没起来？"

Agent 会自动调用 `inspect_container` 查看详情、`get_container_logs` 查看错误日志，告诉你原因。

**查看容器资源占用：**
> "帮我看看所有容器的 CPU 和内存占用情况"

**启停容器：**
> "把 jellyfin 停一下，我要升级"

**查看日志：**
> "看看最近 30 分钟的 jellyfin 日志"

**排查网络问题：**
> "帮我看看 jellyfin 容器的网络配置，端口映射是什么"

## 🚀 部署方式

### 🟢 方式一：使用预构建镜像（推荐，NAS / 通用 Linux）

适合群晖/威联通等 NAS、普通 Linux 服务器，开箱即用。

**步骤：**

1. 创建项目目录：
   ```bash
   mkdir docker-mcpilots && cd docker-mcpilots
   mkdir config secrets
   ```

2. 把 `docker/docker-compose.yml` 放到当前目录

3. 在 `docker-compose.yml` 中修改环境变量：
   - 修改 `ADMIN_PASSWORD` 为你想要的管理员密码
   - 修改 `PUID`/`PGID` 为你的用户 ID（群晖用户通常是 1026/100，其他系统用 `id` 命令查看）
   - 可选：设置 `INITIAL_API_KEYS` 初始 API Key（格式：name1:key1:role1,name2:key2:role2）
   - 可选：设置 `ADMIN_USERNAME` 修改默认管理员用户名

4. 启动：
   ```bash
   docker compose up -d
   ```

**配置文件说明：**

| 文件 | 作用 |
|------|------|
| `config/settings.yaml` | 服务端口、Docker socket 路径、功能开关 |
| `secrets/auth.yaml` | API Key、角色权限、容器范围（敏感文件） |
| `secrets/admin.yaml` | Web UI 管理员账号密码（敏感文件） |

**环境变量说明：**

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `TZ` | 时区 | `Asia/Shanghai` |
| `PUID` | 运行容器的用户 UID | `1000` |
| `PGID` | 运行容器的用户 GID | `1000` |
| `ADMIN_USERNAME` | Web UI 管理员用户名 | `admin` |
| `ADMIN_PASSWORD` | Web UI 管理员密码（首次启动时设置） | 随机生成并警告 |
| `INITIAL_API_KEYS` | 初始 API Key 列表，格式：`name1:key1:role1,name2:key2:role2` | 无 |
| `MCP_CONFIG_DIR` | 配置文件目录 | `/app/config` |
| `MCP_SECRETS_DIR` | 敏感文件目录 | `/app/secrets` |

### 🟡 方式二：从源码构建镜像（开发者 / ARM 设备）

适合开发者本地调试，或者 ARM 架构设备（目前暂不提供 ARM 预构建镜像）。

```bash
git clone https://github.com/sopyk/docker-mcpilots.git
cd docker-mcpilots
docker compose -f docker/docker-compose-build.yml up -d --build
```

默认端口 8900，记得改 `secrets/auth.yaml` 里的 API Key。

### 🔵 方式三：VPS 宿主机直装

适合追求最低资源占用的场景，不需要 Docker 嵌套。详见 [docs/deploy-vps.md](docs/deploy-vps.md)。

## ⚙️ 配置说明

### 🔑 API Key 和权限

`secrets/auth.yaml` 示例：

```yaml
keys:
  - key: "你的-secret-api-key"
    role: admin  # admin / operator / observer
```

- **admin**：所有操作权限
- **operator**：启动、停止、重启容器，查看日志和状态（不能删除）
- **observer**：只读，只能查看不能操作

### 🎯 容器范围控制

可以限制某个 API Key 只能操作特定容器：

```yaml
keys:
  - key: "只管下载容器"
    role: operator
    scope:
      include: ["qbittorrent", "aria2*", "transmission"]
      exclude: ["*"]
```

## 📁 文件结构

```
docker-mcpilots/
├── main.py                    # 入口
├── core/                      # 核心模块
│   ├── config.py             # 配置加载
│   ├── auth.py               # 权限检查
│   ├── docker_client.py      # Docker SDK 封装
│   └── system_diag.py        # 系统诊断
├── tools/                    # MCP 工具
│   ├── container_tools.py    # 容器管理
│   ├── image_tools.py        # 镜像管理
│   ├── docker_diag_tools.py # 网络/卷诊断
│   └── diag_tools.py        # 系统诊断
├── templates/                 # 配置模板
│   ├── settings.yaml
│   └── auth.yaml
├── docker/                   # Docker 相关
│   ├── Dockerfile
│   ├── entrypoint.sh        # 入口脚本
│   ├── docker-compose.yml    # 预构建镜像版（推荐）
│   └── docker-compose-build.yml  # 源码构建版
└── tests/                    # 测试用例（开发用，部署可忽略）
```

## 🛠️ 技术栈

- Python 3.11 + FastMCP 3.x
- docker Python SDK 7.x
- psutil 7.x
- 单容器架构，资源占用极低（约 50MB 内存）

## 🧪 测试

```bash
# 单元测试
pytest tests/

# 端到端测试
docker run -d --name dm-e2e-test alpine sh -c 'while true; do echo heartbeat; sleep 5; done'
MCP_CONFIG_DIR=./config MCP_SECRETS_DIR=./secrets python main.py &
python scripts/e2e_test.py
docker rm -f dm-e2e-test
```

## 🖼️ Web UI 使用说明

部署后访问 `http://<your-ip>:8900/ui/` 即可进入 Web 界面：

- **仪表盘**：查看 CPU 内存使用率、容器/镜像计数、最近审计日志
- **容器列表**：查看所有容器、启停/删除/查看详情
- **用户管理**：创建/编辑/删除 API Key，支持修改 Key 名称、角色、权限和范围
- **审计日志**：查看所有操作记录
- **系统设置**：编辑系统设置（端口、时区、功能开关）、修改管理员密码
- **关于页**：查看项目介绍、配置示例、版本信息

### 💡 首次登录

- 默认用户名：`admin`
- 默认密码：详见首次启动时的配置文件（首次启动会初始化 `secrets/admin.yaml`）
- 登录后建议立即修改密码

## 🗺️ 后续计划

- 🍓 **ARM 架构支持**：提供 arm64 预构建镜像，覆盖树莓派、Mac M 系列等设备
- 📈 **更多诊断能力**：容器事件流、资源占用历史曲线、异常告警
- 🔗 **多节点管理**：一个 MCP Server 管理多台机器上的 Docker

## ⚠️ 风险提示

**使用本项目即表示你理解并接受以下风险：**

1. **容器操作有风险**：停止、删除容器等操作可能导致数据丢失或服务中断，请确保了解操作后果
2. **权限配置需谨慎**：admin 角色拥有完整权限，请妥善保管 API Key
3. **仅限内网使用**：默认配置仅监听本地回环地址，请勿直接暴露到公网
4. **自担风险**：本项目开源提供，使用者需自行评估风险，作者不对使用过程中造成的任何损失负责
5. **建议做好备份**：对重要数据和配置做好备份，操作前确认

**🔒 安全建议：**
- 生产环境务必修改默认 API Key
- 限制容器 scope 权限，只给必要的权限
- 通过反向代理加 TLS 访问（详见 VPS 部署文档）
- 定期检查日志，发现异常及时排查

## 📄 开源协议

MIT License - 详见 [LICENSE](LICENSE) 文件。

## 🔗 链接

- 🐙 GitHub：https://github.com/sopyk/docker-mcpilots
- 🐛 问题反馈：https://github.com/sopyk/docker-mcpilots/issues
- 📦 镜像地址：
  - GHCR：`ghcr.io/sopyk/docker-mcpilots`
  - Docker Hub：`sopyk/docker-mcpilots`
