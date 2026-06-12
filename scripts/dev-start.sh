#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_MIGRATIONS=0

usage() {
  cat <<'EOF'
Usage: scripts/dev-start.sh [--migrate]

Starts the local PostgreSQL container and waits until it is ready.

Options:
  --migrate  Run API Alembic migrations after PostgreSQL is ready.
EOF
}

for arg in "$@"; do
  case "$arg" in
    --migrate)
      RUN_MIGRATIONS=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      usage >&2
      exit 2
      ;;
  esac
done

# shellcheck source=scripts/lib/docker-db.sh
source "$ROOT_DIR/scripts/lib/docker-db.sh"

check_docker_daemon
start_db "$ROOT_DIR"
wait_for_db "$ROOT_DIR"

if [[ "$RUN_MIGRATIONS" == "1" ]]; then
  cd "$ROOT_DIR/apps/api"
  uv run alembic upgrade head
fi

echo "PostgreSQL is ready on localhost:${POSTGRES_PORT:-5432}"
echo "Backend: cd apps/api && uv sync && uv run alembic upgrade head && uv run uvicorn data_intelligence_hub.main:app --reload --host 0.0.0.0 --port 8000"
echo "Frontend: cd apps/web && pnpm install && pnpm dev"
