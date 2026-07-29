#!/bin/bash
set -e

# ──────────────────────────────────────────────────────────
# Docker-MCPilotS — UI 审计脚本
# 零 token 成本，一键验证前端的 UI 变化
# 用法: bash scripts/audit.sh [pytest 参数]
# ──────────────────────────────────────────────────────────

cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Docker-MCPilotS — UI 审计"
echo "  项目: $PROJECT_ROOT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. 确保依赖
pip3 install -q pytest-playwright 2>/dev/null || true
playwright install chromium --with-deps 2>/dev/null || true

# 2. E2E 交互测试
echo ""
echo "→ E2E 交互测试..."
python3 -m pytest tests/e2e/ -v --strict-markers "$@"
E2E_EXIT=$?

# 3. 视觉审计（如果配置了 ui-visual-check.json）
if [ -f ui-visual-check.json ]; then
    echo ""
    echo "→ 视觉像素对比..."
    if command -v npx &> /dev/null; then
        npx backstop test --config=ui-visual-check.json 2>/dev/null || true
    else
        echo "   (跳过: 未安装 Node.js / BackstopJS)"
    fi
fi

# 汇总
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $E2E_EXIT -eq 0 ]; then
    echo "✅ 全部 E2E 测试通过"
else
    echo "❌ 部分 E2E 测试失败（exit code: $E2E_EXIT）"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
exit $E2E_EXIT
