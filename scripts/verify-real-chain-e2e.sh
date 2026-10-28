#!/usr/bin/env bash
#
# 真实链路 E2E 门禁。见 docs/architecture/decisions/ADR-008-real-chain-e2e-gate.md
#
# 做三件事：起一次性栈 → 跑真实链路 spec → 无论成败都 down -v。
#
# 清理放在 trap 里而不是脚本末尾：门禁失败时最需要清理，而末尾的那行
# 在失败路径上根本走不到。留下的卷会让下一次运行带着脏数据，
# 那时「种子可重复」这个前提已经悄悄失效了。
#
# 退出码：0 通过；1 链路或测试失败；2 环境不满足（Docker 不可用等）。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STACK="$ROOT_DIR/scripts/e2e-real-stack.sh"
HTTP_PORT="${E2E_HTTP_PORT:-8090}"
BASE_URL="http://127.0.0.1:$HTTP_PORT"

cleanup() {
  local rc=$?
  echo
  echo "== 清理（无条件） =="
  if ! bash "$STACK" down; then
    echo "警告：清理未完整完成，请手工核对 docker ps -a | grep data_achieve_e2e_" >&2
  fi
  return "$rc"
}
trap cleanup EXIT

command -v docker >/dev/null 2>&1 || {
  echo "失败：找不到 docker。真实链路门禁需要 Docker。" >&2
  exit 2
}
docker info >/dev/null 2>&1 || {
  echo "失败：Docker 守护进程不可用。" >&2
  exit 2
}

echo "== 1/3 起一次性真实栈 =="
bash "$STACK" up

echo
echo "== 2/3 栈是非 mock 的？ =="
# 两个最容易配错的点，错了就没有必要继续跑。
health="$(curl -fsS --max-time 10 "$BASE_URL/api/health")"
printf '  health: %s\n' "$(printf '%s' "$health" | head -c 200)"

code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$BASE_URL/api/projects")"
if [[ "$code" != "401" ]]; then
  echo "失败：/api/projects 无 cookie 返回 $code，期望 401。" >&2
  echo "     返回 200 说明 demo 回退没关，门禁会测到一条生产不存在的路径。" >&2
  exit 1
fi
echo "  demo 回退：已关闭"

# 构建产物必须是 mock 关闭的版本。web 容器里跑的是编译后的 bundle，
# 光看环境变量不够——NEXT_PUBLIC_MOCK_API 是构建期常量。
if ! curl -fsS --max-time 10 "$BASE_URL/login" | grep -q '登录'; then
  echo "失败：/login 未返回登录页。" >&2
  exit 1
fi
echo "  登录页：可访问"

echo
echo "== 3/3 跑真实链路 spec =="
cd "$ROOT_DIR/apps/web"
PLAYWRIGHT_BASE_URL="$BASE_URL" pnpm exec playwright test \
  -c playwright.real-chain.config.ts --project=desktop

echo
echo "真实链路门禁通过"
