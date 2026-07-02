# 版本管理策略

> **项目：** DockerMaintainer MCP Server
> **日期：** 2026-07-03

---

## 1. Git 分支策略

采用 **GitHub Flow**，轻量简洁，适合小型项目快速迭代。

```
main              ← 始终可部署的稳定版本
  │
  ├── feat/container-tools     ← 开发新功能
  ├── feat/auth-rbac           ← 开发新功能
  ├── fix/docker-socket-error  ← 修复 bug
  └── chore/update-deps        ← 依赖升级等杂项
```

- `main` 分支每次合并即代表一个可发布版本
- 功能开发在独立分支上进行，完成后合并回 `main`
- 分支命名约定：`类型/简短描述`

### 分支类型

| 前缀 | 用途 | 示例 |
|---|---|---|
| `feat/` | 新功能开发 | `feat/container-tools` |
| `fix/` | Bug 修复 | `fix/docker-socket-permission` |
| `chore/` | 依赖更新、构建配置等 | `chore/update-docker-sdk` |
| `docs/` | 文档更新 | `docs/deployment-guide` |
| `refactor/` | 代码重构（不改变功能） | `refactor/auth-module` |

---

## 2. 语义化版本号 (SemVer)

格式：`主版本.次版本.修订号` (如 `1.0.0`)

| 版本号 | 触发条件 | 示例 |
|---|---|---|
| 主版本 (1.x.x → 2.x.x) | 不兼容的 API 变更（如权限模型重构、MCP 协议升级） | 初次发布为 `1.0.0` |
| 次版本 (1.0.x → 1.1.x) | 新增 MCP Tool、新增角色、向后兼容的功能新增 | 新增网络管理 Tools → `1.1.0` |
| 修订号 (1.0.0 → 1.0.1) | Bug 修复、配置模板调整、文档更新、安全补丁 | 修复日志读取异常 → `1.0.1` |

### 版本号管理规则

- 初始发布版本为 `1.0.0`（Phase 1 完成时）
- 开发阶段使用 `0.x.y` 预发布版本号（如 `0.1.0`）
- 版本号由开发者在合并到 `main` 时手动指定，通过 Git tag 标记
- 严禁在 `main` 分支上直接修改代码，所有变更通过分支合并

---

## 3. Docker 镜像标签

每次合并到 `main` 后构建镜像，打双标签：

```bash
# 精确版本号标签（永久保留，用于生产环境锁定版本）
docker-mcp-server:1.0.0

# latest 标签（跟随 main 更新，用于开发/测试环境）
docker-mcp-server:latest
```

### 构建命令

```bash
# 构建并打双标签
docker build -t docker-mcp-server:1.0.0 -t docker-mcp-server:latest .

# 预发布版本额外加 -rc 后缀
docker build -t docker-mcp-server:0.9.0-rc1 .
```

---

## 4. 发布流程

```
1. 开发者在 feat/xxx 分支上完成功能开发与自测
2. 提交合并请求（Pull Request），附带变更说明
3. 代码审查通过后合并到 main
4. 在 main 上打 Git tag（如 v1.0.0）
5. 触发 Docker 镜像构建，打对应版本标签
6. 更新 docker-compose.yml 中的镜像版本号
7. 通知用户升级
```

### Git Tag 规范

```bash
# 正式版本
git tag -a v1.0.0 -m "release: v1.0.0 - Phase 1 complete"

# 预发布版本
git tag -a v0.9.0-rc1 -m "release: v0.9.0-rc1 - beta test"
```

---

## 5. Commit 规范

提交信息遵循 **Conventional Commits** 格式：

```
<type>(<scope>): <简短描述>

<可选的详细说明>
```

### Type 列表

| Type | 说明 | 示例 |
|---|---|---|
| `feat` | 新功能 | `feat(container): add start/stop/restart tools` |
| `fix` | Bug 修复 | `fix(auth): handle missing api key gracefully` |
| `docs` | 文档变更 | `docs: update deployment guide` |
| `chore` | 构建配置、依赖等杂项 | `chore: update docker SDK to v7.0` |
| `refactor` | 代码重构 | `refactor(auth): extract scope matcher` |
| `test` | 测试相关 | `test(container): add list_containers unit tests` |
| `ci` | CI/CD 配置 | `ci: add docker build pipeline` |

### Scope 列表

| Scope | 说明 |
|---|---|
| `container` | 容器管理相关 |
| `image` | 镜像管理相关 |
| `diag` | 系统诊断相关 |
| `auth` | 认证与权限相关 |
| `config` | 配置与持久化相关 |
| `deploy` | 部署与 Dockerfile 相关 |
| 省略 | 不涉及特定模块时省略 scope |

---

## 6. CHANGELOG 维护

每次发布在项目根目录 `CHANGELOG.md` 中记录变更：

```markdown
## [1.0.0] - 2026-07-03

### Added
- 容器管理 MCP Tools（列表/启停/重启/日志/资源占用/删除）
- 镜像管理 MCP Tools（列表/拉取/删除）
- 系统诊断 MCP Tools（CPU/内存/磁盘/网络/概览）
- RBAC 权限系统（admin/operator/observer 角色）
- 容器级 Scope 访问控制（include/exclude 通配符）
- API Key 认证（YAML 配置 + 环境变量备选）
- 配置与 Secrets 分离持久化
- Docker 容器化部署（docker-compose）
```

遵循 [Keep a Changelog](https://keepachangelog.com/) 格式，分类为 Added / Changed / Fixed / Deprecated / Removed / Security。

---

## 7. 远程仓库（未来扩展）

当前仅在本地 Git 管理，后续可接入远程仓库：

- **GitHub** — 公开项目协作
- **Gitea / GitLab** — 自建私有仓库（适合群晖内网部署）

接入远程仓库时，需额外配置：
- `.gitignore` 补充规则
- CI/CD 自动化构建流水线
- 镜像仓库推送（Docker Hub / 私有 Registry）
