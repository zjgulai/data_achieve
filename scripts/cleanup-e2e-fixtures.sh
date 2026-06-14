#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USE_DOCKER="${SCRAPY_CLEANUP_USE_DOCKER:-0}"
ENV_FILE="${ENV_FILE:-../.env.production}"
COMPOSE_FILE="${COMPOSE_FILE:-configs/deploy/scrapy/docker-compose.yml}"
OLDER_THAN_HOURS="${OLDER_THAN_HOURS:-168}"
EXECUTE=0

usage() {
  cat <<'EOF'
Usage: scripts/cleanup-e2e-fixtures.sh [--execute] [--older-than-hours HOURS]

Audits isolated real E2E users matching e2e-*@example.com. Without --execute,
the command is dry-run and does not write to the database.

Set SCRAPY_CLEANUP_USE_DOCKER=1 to run through production docker compose.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --execute)
      EXECUTE=1
      shift
      ;;
    --older-than-hours)
      if [[ $# -lt 2 ]]; then
        echo "--older-than-hours requires a value" >&2
        usage >&2
        exit 2
      fi
      OLDER_THAN_HOURS="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

args=("--older-than-hours" "$OLDER_THAN_HOURS")
if [[ "$EXECUTE" == "1" ]]; then
  args+=("--execute")
fi

if [[ "$USE_DOCKER" == "1" ]]; then
  cd "$ROOT_DIR"
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm api \
    python -m data_intelligence_hub.maintenance.e2e_cleanup "${args[@]}"
else
  cd "$ROOT_DIR/apps/api"
  uv run python -m data_intelligence_hub.maintenance.e2e_cleanup "${args[@]}"
fi
