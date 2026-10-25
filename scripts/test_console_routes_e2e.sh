#!/usr/bin/env bash
#
# Browser Harness：控制台前后端工作台的端到端冒烟测试入口。
#
# 默认行为：由 Playwright 自己拉起 Console 开发服务器（127.0.0.1:3001），
# 不需要事先手动启动控制台。
#
# 若要指向已在运行的实例（本地另开的端口，或远端环境），显式设置
# PLAYWRIGHT_BASE_URL；此时 Playwright 不再启动 dev server，只做断言。
#
# 用法：
#   bash scripts/test_console_routes_e2e.sh              # 全量冒烟
#   bash scripts/test_console_routes_e2e.sh --ui         # 交互式 UI 模式
#   PLAYWRIGHT_BASE_URL=http://127.0.0.1:3001 \
#     bash scripts/test_console_routes_e2e.sh            # 复用已有服务
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONSOLE_DIR="$ROOT_DIR/apps/scraper-console"

# 控制台在浏览器侧调用后端；Playwright 的 webServer 会把这个值注入 dev server。
export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-http://127.0.0.1:8000}"

echo "=============================================="
echo "  DIH Browser Harness：控制台 E2E 冒烟测试"
echo "=============================================="
echo "  后端 API 目标   : $NEXT_PUBLIC_API_URL"
if [[ -n "${PLAYWRIGHT_BASE_URL:-}" ]]; then
  echo "  控制台目标      : $PLAYWRIGHT_BASE_URL（复用已有服务）"
else
  echo "  控制台目标      : http://127.0.0.1:3001（由 Playwright 自动启动）"
fi
echo "=============================================="

cd "$CONSOLE_DIR"

if ! pnpm exec playwright --version >/dev/null 2>&1; then
  echo "Playwright 未安装，先执行依赖安装..."
  pnpm install --filter scraper-console
fi

echo "执行 Playwright 路由冒烟测试..."
exec pnpm exec playwright test "$@"
