#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WITH_DB=0

usage() {
  cat <<'EOF'
Usage: scripts/verify-mvp.sh [--with-db]

Runs the MVP quality gate:
  - API ruff, mypy, pytest, Alembic head check
  - Web lint, unit tests, production build, Playwright E2E

Options:
  --with-db  Also start PostgreSQL with Docker Compose and run alembic upgrade head.
EOF
}

for arg in "$@"; do
  case "$arg" in
    --with-db)
      WITH_DB=1
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

run_step() {
  local label="$1"
  shift
  echo
  echo "==> $label"
  "$@"
}

if [[ "$WITH_DB" == "1" ]]; then
  # shellcheck source=scripts/lib/docker-db.sh
  source "$ROOT_DIR/scripts/lib/docker-db.sh"
  run_step "Checking Docker daemon" check_docker_daemon
  run_step "Starting PostgreSQL" start_db "$ROOT_DIR"
  run_step "Waiting for PostgreSQL" wait_for_db "$ROOT_DIR"
fi

cd "$ROOT_DIR/apps/api"
run_step "API ruff" uv run ruff check .
run_step "API mypy" uv run mypy src tests
run_step "API pytest" uv run pytest
run_step "API Alembic heads" uv run alembic heads

if [[ "$WITH_DB" == "1" ]]; then
  run_step "API PostgreSQL migration" uv run alembic upgrade head
fi

cd "$ROOT_DIR/apps/web"
run_step "Web lint" pnpm lint
run_step "Web unit tests" pnpm test
run_step "Web build" pnpm build
run_step "Web Playwright E2E" pnpm test:e2e

echo
echo "MVP verification complete."
