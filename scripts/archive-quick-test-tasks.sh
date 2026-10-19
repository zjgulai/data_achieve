#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USE_DOCKER="${SCRAPY_CLEANUP_USE_DOCKER:-0}"
ENV_FILE="${ENV_FILE:-../.env.production}"
COMPOSE_FILE="${COMPOSE_FILE:-configs/deploy/scrapy/docker-compose.yml}"
EXECUTE=0

usage() {
  cat <<'EOF'
用法: scripts/archive-quick-test-tasks.sh [--execute]

归档 demo workspace 内的 [quick] 测试任务。
默认 dry-run。只报告，不写库。
加 --execute 才写库。写入时把 status 批量置为 paused。
重复执行不会重复计数。
设置 SCRAPY_CLEANUP_USE_DOCKER=1 时走生产 docker compose。
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --execute)
      EXECUTE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

args=()
if [[ "$EXECUTE" == "1" ]]; then
  args+=("--execute")
fi

if [[ "$USE_DOCKER" == "1" ]]; then
  cd "$ROOT_DIR"
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm api \
    python -m data_intelligence_hub.maintenance.quick_task_archive ${args[@]+"${args[@]}"}
else
  cd "$ROOT_DIR/apps/api"
  uv run python -m data_intelligence_hub.maintenance.quick_task_archive ${args[@]+"${args[@]}"}
fi
