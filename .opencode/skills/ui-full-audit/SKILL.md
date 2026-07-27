---
name: ui-full-audit
description: 完整 UI 审计流水线 — Playwright 站内链接遍历 + visual-diff 像素对比，输出合并缺陷报告
license: MIT
compatibility: opencode
---

## 流程

### 步骤 1：校验本地服务

用 bash 检测服务是否运行：
```bash
PORT=8900
curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/ui/about"
```
若返回非 200 则中止并提示启动服务。

### 步骤 2：功能链接遍历测试（playwright MCP）

操作 `playwright` MCP 工具：

1. `browser_navigate` → 打开首页 `http://localhost:${PORT}/ui/login`
2. `browser_snapshot` → 获取 DOM 快照
3. 提取站内 `<a href="...">`，过滤外部域名、锚点、javascript:
4. 逐一访问，检查 `console_logs` 中 error/warning 及页面 404 关键词
5. 记录 `【功能-链接】{URL} → {问题}`

### 步骤 3：视觉布局校验（ui-visual-check MCP）

操作 `ui-visual-check` MCP 工具：

1. 若 `backstop_data/bitmaps_reference/` 不存在 → 调用 `visual_baseline`
2. 调用 `visual_check` 执行像素对比
3. 查找 "Mismatch"、"failed" 关键词
4. 记录 `【视觉-{视口}】{场景} → {差异%}`

### 步骤 4：输出合并缺陷报告

```
═══════════════════════════════════════
  UI 全面审计报告
═══════════════════════════════════════

【功能-链接】/some/broken/link → 404
【视觉-desktop】Login Page → 5.2% mismatch

--- 共发现 N 个缺陷 ---
```
无缺陷则输出 ✅ 全部通过。
