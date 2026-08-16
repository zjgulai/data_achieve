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

EXPECTED_HOST = "127.0.0.1"
EXPECTED_PORT = 55443
EXPECTED_DATABASE = "uix09_phase_e_20260728_workflow_execution_test"
EXPECTED_USER = "phase_e_test"
EXPECTED_TARGET = f"{EXPECTED_HOST}:{EXPECTED_PORT}/{EXPECTED_DATABASE}"


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(2)


if os.environ.get("WORKFLOW_ACTION_POSTGRES_TEST_AUTHORIZED") != "true":
    fail("WORKFLOW_ACTION_POSTGRES_TEST_AUTHORIZED=true is required")

database_url = os.environ.get("WORKFLOW_ACTION_TEST_DATABASE_URL")
if not database_url:
    fail("WORKFLOW_ACTION_TEST_DATABASE_URL is required")
authorized_target = os.environ.get("WORKFLOW_ACTION_AUTHORIZED_TARGET")
if not authorized_target:
    fail("WORKFLOW_ACTION_AUTHORIZED_TARGET is required")
if any(character.isspace() for character in database_url):
    fail("WORKFLOW_ACTION_TEST_DATABASE_URL must not contain whitespace")
if any(character.isspace() for character in authorized_target):
    fail("WORKFLOW_ACTION_AUTHORIZED_TARGET must not contain whitespace")

try:
    parsed = urlsplit(database_url)
    port = parsed.port
except ValueError:
    fail("WORKFLOW_ACTION_TEST_DATABASE_URL host or port is invalid")

raw_authority = parsed.netloc.rsplit("@", 1)[-1]
if parsed.scheme != "postgresql+asyncpg":
    fail("WORKFLOW_ACTION_TEST_DATABASE_URL must use postgresql+asyncpg")
if parsed.hostname != EXPECTED_HOST or port != EXPECTED_PORT:
    fail("WORKFLOW_ACTION_TEST_DATABASE_URL must match the approved loopback endpoint")
if parsed.username != EXPECTED_USER or parsed.password is not None:
    fail("WORKFLOW_ACTION_TEST_DATABASE_URL must use the approved password-free test user")
if parsed.path != f"/{EXPECTED_DATABASE}":
    fail("WORKFLOW_ACTION_TEST_DATABASE_URL must match the approved database")
if parsed.query or parsed.fragment:
    fail("WORKFLOW_ACTION_TEST_DATABASE_URL must not contain query or fragment")
if "%" in raw_authority or "%" in parsed.path:
    fail("WORKFLOW_ACTION_TEST_DATABASE_URL must not contain encoded parts")
if authorized_target != EXPECTED_TARGET:
    fail("WORKFLOW_ACTION_AUTHORIZED_TARGET must exactly match the approved target")

exact_target = f"{parsed.hostname}:{port}/{parsed.path.removeprefix('/')}"
if exact_target != authorized_target:
    fail("WORKFLOW_ACTION_AUTHORIZED_TARGET must exactly match the database URL")
PY

printf '%s\n' \
  "migration guard passed: exact UIX-09 Phase E Workflow Action PostgreSQL target"

if [ "$check_only" = true ]; then
  exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
  printf '%s\n' "error: uv is required to run the PostgreSQL migration gate" >&2
  exit 2
fi

cd "$repository_root/apps/api"
heads_output="$(uv run alembic heads)"
head_count="$(printf '%s\n' "$heads_output" | awk 'NF { count += 1 } END { print count + 0 }')"
if [ "$head_count" -ne 1 ] || ! printf '%s\n' "$heads_output" | grep -Eq '^202607270043 \(head\)$'; then
  printf '%s\n' "error: expected exactly one Alembic head at 202607270043" >&2
  exit 1
fi

printf '%s\n' "alembic source head check passed: 202607270043"
export DATABASE_URL="$WORKFLOW_ACTION_TEST_DATABASE_URL"
uv run pytest tests/postgres_workflow_action -q
