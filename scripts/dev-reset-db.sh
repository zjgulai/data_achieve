#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_MIGRATIONS=0

usage() {
  cat <<'EOF'
Usage: CONFIRM_RESET=1 scripts/dev-reset-db.sh [--migrate]

Recreates the local PostgreSQL Docker volume.

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

if [[ "${CONFIRM_RESET:-}" != "1" ]]; then
  echo "Refusing to reset the development database without CONFIRM_RESET=1."
  echo "Run: CONFIRM_RESET=1 scripts/dev-reset-db.sh"
  exit 1
fi

# shellcheck source=scripts/lib/docker-db.sh
source "$ROOT_DIR/scripts/lib/docker-db.sh"

check_docker_daemon
docker compose --project-directory "$ROOT_DIR" down -v
start_db "$ROOT_DIR"
wait_for_db "$ROOT_DIR"

if [[ "$RUN_MIGRATIONS" == "1" ]]; then
  cd "$ROOT_DIR/apps/api"
  uv run alembic upgrade head
fi

echo "Development database volume has been recreated."
