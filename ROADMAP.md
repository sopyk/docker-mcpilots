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
- **修复**: `about.html` 同步至 `v2.0.3`（随本版更新）。集成测试 `test_version_consistency` 仍只检查 `main.py` 内部一致性，未覆盖 HTML 模板——**待后续补充**。

## 4. Web UI 手机端适配

- **优先级**: 低（后期）
- **现状**: 当前 UI 用 Jinja2 模板 + 基础 CSS，未针对移动端优化
- **目标**: 使管理面板在手机浏览器上可用（响应式布局、触控友好）
- **待评估**:
  - 现有 CSS 框架和结构
  - 是否需要前端构建工具
  - 适配范围（仪表盘、容器列表、镜像列表、用户管理、审计日志、设置）
