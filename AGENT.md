# AGENT 上下文（供 opencode 会话参考）

> 记录本项目的凭证存储位置和关键环境信息，**不包含实际密钥值**。每个新会话需自行通过对应文件读取。

## 🔑 凭证存储位置

| 用途 | 存储文件 | 读取方式 | 说明 |
|------|---------|---------|------|
| Git 代码推送（GitHub / Gitee） | `~/.git-credentials` | `git credential fill host=gitee.com` 或 `host=github.com` | 存储 username + token |
| Docker 镜像推送（Docker Hub / GHCR） | `~/.docker/config.json` | `cat ~/.docker/config.json` | base64 编码的 auth |
| Gitee REST API token | `~/.git-credentials` | `git credential fill host=gitee.com` | 同上，取 password 字段 |

### 示例：读取 Gitee 凭证
```bash
git credential fill <<EOF
protocol=https
host=gitee.com
EOF
```

## 🐳 Docker 镜像

| 仓库 | 镜像地址 |
|------|---------|
| Docker Hub | `sopyk/docker-mcpilots` |
| GHCR | `ghcr.io/sopyk/docker-mcpilots` |
| 稳定版标签 | `:v2.1.2`（滚动标签 `:latest`） |

## 🌐 远程仓库

| 名称 | 地址 |
|------|------|
| origin (GitHub) | `https://github.com/sopyk/docker-mcpilots.git` |
| gitee (Gitee) | `https://gitee.com/sopyk/docker-mcpilots.git` |

## 🧪 测试

- 单元测试：`pytest tests/`（138 个测试用例）
- 集成测试：`python3 scripts/integration_test.py`（15 个检查项，需要 Docker 可用）
- CI 流水线：`.github/workflows/ci.yml`

## ⚠️ 安全提醒

- **不要将实际 token / password 提交到 Git 仓库**，即使 `.gitignore` 了也不要提交。
- `~/.git-credentials` 和 `~/.docker/config.json` 含敏感信息，不要拷贝到项目目录。
