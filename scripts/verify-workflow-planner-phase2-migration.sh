#!/usr/bin/env bash

set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
check_only=false

case "${1:-}" in
  "")
    ;;
  --check-only)
    check_only=true
    ;;
  *)
    printf '%s\n' "error: unsupported argument" >&2
    exit 2
    ;;
esac

if [ "$#" -gt 1 ]; then
  printf '%s\n' "error: unsupported argument" >&2
  exit 2
fi

python_bin="$(command -v python3 || command -v python || true)"
if [ -z "$python_bin" ]; then
  printf '%s\n' "error: Python is required for fail-closed URL validation" >&2
  exit 2
fi

"$python_bin" <<'PY'
from __future__ import annotations

import os
import sys
from urllib.parse import urlsplit


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(2)


if os.environ.get("ALLOW_DESTRUCTIVE_MIGRATION_TEST") != "true":
    fail("ALLOW_DESTRUCTIVE_MIGRATION_TEST=true is required")

database_url = os.environ.get("TEST_DATABASE_URL")
if not database_url:
    fail("TEST_DATABASE_URL is required")
if any(character.isspace() for character in database_url):
    fail("TEST_DATABASE_URL must not contain whitespace")

try:
    parsed = urlsplit(database_url)
except ValueError:
    fail("TEST_DATABASE_URL is invalid")

if parsed.scheme != "postgresql+asyncpg":
    fail("TEST_DATABASE_URL must use postgresql+asyncpg")
if parsed.query or parsed.fragment:
    fail("TEST_DATABASE_URL must not contain query or fragment overrides")

raw_authority = parsed.netloc.rsplit("@", 1)[-1]
if "%" in raw_authority or "%" in parsed.path:
    fail("TEST_DATABASE_URL must not contain encoded host or database parts")

try:
    hostname = parsed.hostname
    parsed.port
except ValueError:
    fail("TEST_DATABASE_URL host or port is invalid")

if hostname not in {"localhost", "127.0.0.1"}:
    fail("TEST_DATABASE_URL must target localhost or 127.0.0.1")
if not parsed.path.startswith("/") or parsed.path.count("/") != 1:
    fail("TEST_DATABASE_URL must name exactly one database")

database_name = parsed.path.removeprefix("/")
if not database_name.endswith("_workflow_plan_phase2_test"):
    fail("TEST_DATABASE_URL database must end with _workflow_plan_phase2_test")
PY

printf '%s\n' "migration guard passed: local disposable PostgreSQL database"

if [ "$check_only" = true ]; then
  exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
  printf '%s\n' "error: uv is required to run the PostgreSQL migration gate" >&2
  exit 2
fi

cd "$repository_root/apps/api"

heads_output="$(DATABASE_URL="$TEST_DATABASE_URL" uv run alembic heads)"
head_count="$(printf '%s\n' "$heads_output" | awk 'NF { count += 1 } END { print count + 0 }')"
if [ "$head_count" -ne 1 ] || ! printf '%s\n' "$heads_output" | grep -Eq '^202606110027 \(head\)$'; then
  printf '%s\n' "error: expected exactly one Alembic head at 202606110027" >&2
  exit 1
fi

printf '%s\n' "alembic head check passed: 202606110027"
DATABASE_URL="$TEST_DATABASE_URL" uv run pytest tests/postgres -q
