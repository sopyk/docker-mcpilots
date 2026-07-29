# Docker-MCPilotS 测试约定

## E2E 测试
- **位置**: `tests/e2e/`
- **运行**: `bash scripts/audit.sh`
- **依赖**: `pytest-playwright`, Chromium
- **前提**: 本地开发服务运行中（`http://localhost:8900`）

## 注意事项
- 修改前端代码（JS / HTML / 模板）时，**必须同步更新或补充** `tests/e2e/` 中的对应测试用例
- 新增交互功能时，补充对应的 Playwright 测试用例
- 运行 `bash scripts/audit.sh` 一键验证全部 UI 变更
