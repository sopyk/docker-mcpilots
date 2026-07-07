# Web UI 设计文档

> 版本: 1.0 ｜ 日期: 2026-07-05 ｜ 状态: 待评审

---

## 1. 背景与目标

### 1.1 背景

Docker-MCPilotS 当前是纯 MCP API Server，只服务于 AI Agent。人类用户想查看容器状态、管理用户权限、排查问题，必须通过 AI Agent 间接操作，缺乏直接的可视化管理入口。

### 1.2 目标

为 Docker-MCPilotS 增加一个 Web UI，让人类管理员能够：

- 直观查看容器/镜像/系统状态
- 管理用户与 API Key（增删改）
- 查看审计日志（区分人类操作与 AI Agent 操作）
- 修改配置后热加载，无需重启 Docker

### 1.3 MVP 范围

采用极简 MVP 策略，**先做单管理员登录模式**：

- 单一管理员账号（用户名/密码），不支持多用户注册
- 所有页面需登录后访问
- 后续版本再扩展多用户/SSO

---

## 2. 功能模块

### 2.1 仪表盘首页（Dashboard）

**职责**: 一目了然展示系统全貌，**只做概览不做操作**，所有详情/操作进二级页

**信息分层**:
- 第一眼（系统健康度）：系统资源 + 容器状态
- 第二眼（资产盘点）：镜像规模 + 网络流量
- 第三眼（操作痕迹）：最近活动 + 快捷入口

**6 个区块布局**:

| 区块 | 展示内容 | 可视化形式 | 数据来源 | 点击行为 |
|---|---|---|---|---|
| 系统资源 | CPU/内存/磁盘占用率 | 3 个圆环进度条（蓝/绿/琥珀） | `get_cpu_info` / `get_memory_info` / `get_disk_info` | 悬停看趋势（预留） |
| 容器概览 | 运行/停止/其他计数 + 容器名色块 | 5×2 状态网格 + 计数摘要 | `list_containers(all=True)` | → 容器列表页 |
| 镜像概览 | 镜像总数 + 总大小 + 可清理数 | 大数字 + 副标签 | `list_images` | → 镜像列表页 |
| 最近活动 | 最近 5 条操作（区分人类/Agent） | 垂直时间轴，紫点=人类 蓝点=Agent | `AuditLogger.recent(5)` | → 审计日志页 |
| 网络流量 | 实时收发流量趋势 | sparkline 折线 + 收发字节数 | `get_network_info` | → 系统详情页 |
| 快捷入口 | 4 个二级页直达 | 2×2 图标按钮网格 | — | 直达各管理页 |

**交互原则**:
- 首页不承载任何写操作
- 所有卡片 hover 时边框高亮，提示可点击
- 卡片右上角 `→` 箭头 hover 变蓝

#### 2.1.1 视觉规范（暗色科技风）

**色彩系统**（全部抽成 CSS 变量，集中在 `web/static/tokens.css`）:

| 变量名 | 值 | 语义 |
|---|---|---|
| `--bg` | `#0d1117` | 页面背景 |
| `--bg-card` | `#161b22` | 卡片背景 |
| `--bg-card-hover` | `#1c2128` | 卡片 hover 背景 |
| `--border` | `#30363d` | 默认边框 |
| `--text` | `#e6edf3` | 主文字 |
| `--text-muted` | `#8b949e` | 次要文字 |
| `--text-dim` | `#6e7681` | 弱化文字 |
| `--neon-blue` | `#58a6ff` | 主强调色 / Agent 操作 |
| `--neon-green` | `#3fb950` | 正常状态 / 运行中 |
| `--neon-amber` | `#d29922` | 警告（如磁盘高占用） |
| `--neon-red` | `#f85149` | 异常 / 停止 |
| `--neon-purple` | `#bc8cff` | 人类操作 / 镜像数 |

**字体**:
- `--font-mono`: `"JetBrains Mono", "SF Mono", "Fira Code", Consolas, monospace` — 数据、标签、时间
- `--font-sans`: `-apple-system, "Segoe UI", Roboto, sans-serif` — 正文（保证中文可读性）

**动效**:
- 脉冲：2s `ease-in-out` 循环，透明度 1 ↔ 0.4（标题状态点、运行中容器指示灯）
- 卡片 hover：边框 `border-color` 过渡 0.2s
- 圆环/折线发光：`filter: drop-shadow(0 0 4px <color>)`
- 所有动效包裹 `@media (prefers-reduced-motion: reduce)` 无障碍兜底

**主题切换预留**:
```css
:root[data-theme="dark"] { /* 暗色科技风 - 默认 */ }
:root[data-theme="light"] { /* 浅色版 - 预留 */ }
```
将来换风格只需改 `tokens.css` 的变量值，组件 CSS 不动。

**换皮肤的成本**:
| 改动范围 | 工作量 |
|---|---|
| 换配色 | 改 tokens.css 颜色值，5 分钟 |
| 换字体 | 改 `--font-*` 变量，2 分钟 |
| 换整体风格（如浅色杂志风） | 改 tokens.css + 个别组件 background/border 写法，1-2 小时 |

### 2.2 容器管理页面

**展示内容**:
- 容器列表表格：名称、状态、镜像、CPU/内存占用、启动时间
- 点击容器查看详情：网络、挂载、健康、最近日志

**操作**:
- 启动 / 停止 / 重启
- 查看日志（支持时间段筛选）
- **不做**容器状态自身的可视化（现有 MCP 工具已覆盖）

**数据来源**: `list_containers` / `inspect_container` / `get_container_stats` / `get_container_logs`

### 2.3 用户权限管理页面

**展示内容**:
- 当前所有 API Key 列表：名称、角色、Scope、最后使用时间
- 角色列表：角色名、权限清单

**操作**:
- 新增 API Key（指定名称、角色、Scope）
- 编辑 API Key（修改角色、Scope）
- 删除 API Key
- 修改后**热加载**到运行中的服务，无需重启

**数据来源**: 读写 `secrets/auth.yaml`

### 2.4 审计日志模块

**展示内容**:
- 操作日志表格：时间、操作人、操作类型、目标对象、详情
- 区分操作来源：**人类（Web UI）** vs **AI Agent（MCP 调用）**
- 筛选：按时间、按操作人、按来源

**记录范围**:
- Web UI 的所有写操作（登录、用户管理、容器启停）
- MCP Tool 的所有调用（含调用方 Key 名称、Tool 名、参数、结果状态）

**存储**: 落盘到 `data/audit.log`（JSONL 格式），同时保留内存最近 N 条供首页展示

### 2.5 配置与热加载

**展示内容**:
- 当前 `settings.yaml` 配置
- 当前 `auth.yaml` 摘要（不显示完整 Key）

**操作**:
- 修改 `settings.yaml`（功能开关等）
- 修改后热加载：重新加载配置到内存，无需重启容器
- 部分配置项（如端口、host）仍需重启生效，UI 需明确提示

---

## 3. 技术架构

### 3.1 部署形态

**Web UI 与现有 MCP Server 同进程部署**，作为 FastMCP 的额外 HTTP 路由：

```
FastMCP HTTP Server (port 8900)
  ├── /mcp/*          MCP JSON-RPC 端点（现有，需 Bearer Token）
  ├── /health         健康检查（现有，无需认证）
  └── /ui/*           Web UI 路由（新增）
      ├── /ui/login   登录页
      ├── /ui/        仪表盘
      ├── /ui/containers
      ├── /ui/users
      ├── /ui/audit
      └── /ui/settings
  └── /api/ui/*       Web UI 后端 API（新增，需会话 Cookie）
```

**理由**:
- 单容器架构保持不变，不增加部署复杂度
- 复用现有 DockerClient / SystemDiag / AuthConfig 实例
- 避免跨进程通信

### 3.2 认证模型

**双轨认证**:

| 路径 | 认证方式 | 身份 |
|---|---|---|
| `/mcp/*` | Bearer Token（现有） | AI Agent（KeyConfig） |
| `/api/ui/*` | 会话 Cookie | 人类管理员 |
| `/ui/*` | 会话 Cookie（除登录页） | 人类管理员 |

**管理员账号**:
- 存储在 `secrets/admin.yaml`（权限 600）
- 用户名 + bcrypt 哈希密码
- 首次启动若不存在，从模板生成并提示修改默认密码

### 3.3 技术栈

**后端**:
- FastMCP 的 `custom_route` 注册 Web UI 路由（已有 `/health` 先例）
- Jinja2 模板渲染 HTML
- itsdangerous 生成签名 Cookie（会话令牌）

**前端**:
- 纯 HTML + CSS + 原生 JS（不引入构建工具链）
- HTMX（可选，用于无刷新交互）
- 极简 CSS（参考 Pico.css 或手写）

**理由**: 保持单容器轻量，避免 Node 构建链；NAS 环境资源有限

### 3.4 热加载机制

`AuthConfig` / `Settings` 改为**可变引用**：

```python
class AppState:
    settings: Settings
    auth_config: AuthConfig
    permission_checker: PermissionChecker
    audit_logger: AuditLogger
```

- Web UI 修改 `auth.yaml` 后，调用 `app_state.reload_auth()` 重新加载
- `PermissionChecker` 持有 `AppState` 引用，每次检查读取最新 `auth_config`
- MCP 中间件的 session 缓存改为缓存 `key` 字符串（而非 `KeyConfig` 对象），每次重新查找

---

## 4. 数据模型

### 4.1 审计日志条目

```python
@dataclass
class AuditEntry:
    timestamp: str          # ISO8601
    source: str             # "web" | "mcp"
    actor: str              # Web: 管理员用户名; MCP: KeyConfig.name
    action: str             # "container.start" / "user.create" / "auth.login" 等
    target: str             # 操作对象（容器名 / Key 名 / 配置项）
    detail: dict            # 附加详情（参数、结果状态等）
    success: bool
```

### 4.2 管理员账号

```yaml
# secrets/admin.yaml
username: "admin"
password_hash: "$2b$12$..."   # bcrypt
```

---

## 5. 安全考虑

1. **入口鉴权**: 外网访问需首页鉴权，未登录跳转 `/ui/login`
2. **CSRF 防护**: Web UI POST 请求需携带 CSRF Token
3. **会话超时**: 默认 8 小时，可配置
4. **审计日志不可删**: Web UI 不提供删除日志功能（只能查看）
5. **API Key 不回显**: 用户管理页面只显示 Key 的前 8 位 + `***`

---

## 6. 开发优先级

| 优先级 | 模块 | 理由 |
|---|---|---|
| P0 | 入口鉴权 + 管理员登录 | 所有功能的前置条件 |
| P1 | 仪表盘首页 | 用户第一眼看到的东西 |
| P2 | 容器管理页面 | 最常用功能 |
| P3 | 用户权限管理 + 热加载 | 核心管理需求 |
| P4 | 审计日志模块 | 贯穿所有模块，最后完善 |

---

## 7. 不在本次范围

- 多用户 / RBAC for Web UI（MVP 单管理员）
- 容器状态可视化图表（现有工具已覆盖）
- 镜像构建功能（安全考虑，永不开放）
- 移动端适配（后续版本）
- 多语言切换（先中文，后续 i18n）
