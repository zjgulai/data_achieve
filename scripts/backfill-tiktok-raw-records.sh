#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USE_DOCKER="${SCRAPY_CLEANUP_USE_DOCKER:-0}"
ENV_FILE="${ENV_FILE:-../.env.production}"
COMPOSE_FILE="${COMPOSE_FILE:-configs/deploy/scrapy/docker-compose.yml}"

usage() {
  cat <<'EOF'
用法: scripts/backfill-tiktok-raw-records.sh [参数] [--execute]

把历史 TikTok RawRecord 回填到内容与电商规范表。
默认 dry-run，只报告，不写库。

常用参数：
  --execute                 写库执行
  --project-id UUID         只回填指定项目
  --run-id UUID             只回填指定运行
  --endpoint-type TYPE      只回填指定端点，可重复
  --since ISO8601           起始时间，必须带时区
  --until ISO8601           结束时间，必须带时区
  --batch-size N            每批运行数，默认 200
  --limit N                 最多处理多少个运行
  --include-phase0-tikhub   额外纳入 Phase 0 旧内容端点
  --fail-on-error           有失败时退出码为 1

设置 SCRAPY_CLEANUP_USE_DOCKER=1 时走生产 docker compose。
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ "$USE_DOCKER" == "1" ]]; then
  cd "$ROOT_DIR"
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm api \
    python -m data_intelligence_hub.maintenance.tiktok_raw_record_backfill "$@"
else
  cd "$ROOT_DIR/apps/api"
  uv run python -m data_intelligence_hub.maintenance.tiktok_raw_record_backfill "$@"
fi
