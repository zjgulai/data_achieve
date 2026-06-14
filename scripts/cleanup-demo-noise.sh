#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USE_DOCKER="${SCRAPY_CLEANUP_USE_DOCKER:-0}"
ENV_FILE="${ENV_FILE:-../.env.production}"
COMPOSE_FILE="${COMPOSE_FILE:-configs/deploy/scrapy/docker-compose.yml}"

usage() {
  cat <<'EOF'
Usage: scripts/cleanup-demo-noise.sh [--execute]

Audits non-curated runtime data in the curated demo workspace. Without
--execute, the command is dry-run and does not write to the database.

Set SCRAPY_CLEANUP_USE_DOCKER=1 to run through production docker compose.
EOF
}

args=("--cleanup-demo-noise")
while [[ $# -gt 0 ]]; do
  case "$1" in
    --execute)
      args+=("--execute")
      shift
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

if [[ "$USE_DOCKER" == "1" ]]; then
  cd "$ROOT_DIR"
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm api \
    python -m data_intelligence_hub.seed.demo_data "${args[@]}"
else
  cd "$ROOT_DIR/apps/api"
  uv run python -m data_intelligence_hub.seed.demo_data "${args[@]}"
fi
