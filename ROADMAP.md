# Roadmap

## 1. ~~exec_container demux 兼容性修复~~ ✅ 已修复

- **文件**: `core/docker_client.py`
- **修复**: 去掉 `demux` 参数，新增 `_demux_frames()` 手动解码多路复用字节流，兼容 Docker API < 1.42。
- **提交**: `d03bf0d` + 后续修复提交

## 2. ~~list_containers Image 字段截断~~ ✅ 已修复

- **文件**: `core/docker_client.py` (`_format_container`, `_format_container_detail`)
- **修复**: `container.image.id[:12]` → `container.image.short_id`，不再显示无意义的截断哈希。

## 3. ~~版本号联动检查~~ ✅ 已修复（v2.0.3）

- **问题**: `web/templates/about.html` 显示 `v2.0.1`，`main.py` 已为 `2.0.2`，遗漏未改。
- **修复**: `about.html` 同步至 `v2.0.3`（随本版更新）。集成测试覆盖已补齐：版本号统一收敛到 `core/version.py`，模板通过 `{{ app_version }}` 注入，`tests/test_version_consistency.py` + `tests/test_e2e_web_ui.py::TestAboutPage` 防止再次漏改（跟踪 issue #2，已修复）。v2.1.3 起进一步收敛：`main.py`、`/health`、Web 模板全部引用单一常量，并新增 Web 层硬编码守卫测试。

## 4. ~~Web UI 手机端适配~~ ✅ 已完成（v2.1.0）

- **目标**: 使管理面板在手机浏览器上可用（响应式布局、触控友好）
- **策略**: 纯 CSS（`mobile.css`）+ 约 30 行 JS 汉堡菜单，桌面版零影响
- **覆盖页面**: 仪表盘、容器管理、容器详情、镜像管理、用户管理、审计日志、设置、关于、登录

## 5. ~~关于页「复制」按钮在 HTTP 局域访问下无效~~ ✅ 已修复（v2.1.3，issue #1）

- **文件**: `web/templates/about.html`（`copyMcpConfig()`）
- **现象**: 通过 `http://<NAS内网IP>:8900/ui/about` 访问时，点「📋 复制」没有任何反应（按钮文字不变，剪贴板无内容）。
- **根因**: `navigator.clipboard` 只在安全上下文（HTTPS / `localhost`）存在。内网 HTTP 访问时它是 `undefined`，`navigator.clipboard.writeText(...)` 同步抛 `TypeError: Cannot read properties of undefined (reading 'writeText')`，走不到 `.catch()`，因此 `document.execCommand('copy')` 兜底逻辑从未执行。
- **复现**（Playwright + 内网 HTTP）: `isSecureContext === false`、`typeof navigator.clipboard === 'undefined'`，点击后页面报上述 TypeError，按钮仍显示「📋 复制」；同一页面在 `localhost` 下点击正常显示「✅ 已复制」。
- **修复方案**: 参照 `web/templates/users.html` 的 `copyKey()`，先判断 `navigator.clipboard && navigator.clipboard.writeText` 再调用，并把兜底包在 try/catch 中；兜底 textarea 补 `readonly` 以兼容 iOS。同时补一条 E2E 用例（可用 `Object.defineProperty(navigator, 'clipboard', {value: undefined})` 模拟非安全上下文）。
- **修复**: 新增 `web/static/clipboard.js`（`copyToClipboard()`：能力检测 + try/catch + textarea 兜底，永不 reject），`base.html` 引入，`about.html` / `users.html` 统一调用；复制失败也会给出「❌ 复制失败」反馈。E2E 见 `tests/e2e/test_about_copy.py`（非安全上下文走兜底 + 安全上下文剪贴板内容校验）。

## 后续计划（产品 / 发布向）

### 6. 多架构镜像（linux/arm64）

- **现状**: 仅构建 `linux/amd64`，ARM 架构 NAS（部分群晖/威联通型号、树莓派）无法直接运行。
- **目标**: 用 `docker buildx build --platform linux/amd64,linux/arm64` 发布 manifest list，并校验两个架构都能通过 `/health` + MCP `initialize`。
- **注意**: `psutil` / `cryptography` 在 arm64 需要编译工具链（builder 阶段已装 `build-base`），需实机验证。

> 说明：测试/CI 类改进（`scripts/audit.sh` 视觉基线修通或移除、CI 增加 E2E 用例、发布流程自动化）不属于使用者可见的产品能力，不在本 Roadmap 中跟踪。
