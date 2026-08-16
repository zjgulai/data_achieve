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
import re
import sys
from urllib.parse import urlsplit


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(2)


if os.environ.get("WORKFLOW_EXECUTION_POSTGRES_TEST_AUTHORIZED") != "true":
    fail("WORKFLOW_EXECUTION_POSTGRES_TEST_AUTHORIZED=true is required")

database_url = os.environ.get("WORKFLOW_EXECUTION_TEST_DATABASE_URL")
if not database_url:
    fail("WORKFLOW_EXECUTION_TEST_DATABASE_URL is required")
authorized_target = os.environ.get("WORKFLOW_EXECUTION_AUTHORIZED_TARGET")
if not authorized_target:
    fail("WORKFLOW_EXECUTION_AUTHORIZED_TARGET is required")
if any(character.isspace() for character in database_url):
    fail("WORKFLOW_EXECUTION_TEST_DATABASE_URL must not contain whitespace")
if any(character.isspace() for character in authorized_target):
    fail("WORKFLOW_EXECUTION_AUTHORIZED_TARGET must not contain whitespace")

try:
    parsed = urlsplit(database_url)
except ValueError:
    fail("WORKFLOW_EXECUTION_TEST_DATABASE_URL is invalid")

if parsed.scheme != "postgresql+asyncpg":
    fail("WORKFLOW_EXECUTION_TEST_DATABASE_URL must use postgresql+asyncpg")
if parsed.query or parsed.fragment:
    fail("WORKFLOW_EXECUTION_TEST_DATABASE_URL must not contain query or fragment")

raw_authority = parsed.netloc.rsplit("@", 1)[-1]
if "%" in raw_authority or "%" in parsed.path:
    fail("WORKFLOW_EXECUTION_TEST_DATABASE_URL must not contain encoded parts")

try:
    hostname = parsed.hostname
    port = parsed.port
except ValueError:
    fail("WORKFLOW_EXECUTION_TEST_DATABASE_URL host or port is invalid")

if hostname not in {"localhost", "127.0.0.1"}:
    fail("WORKFLOW_EXECUTION_TEST_DATABASE_URL must target localhost")
if port is None:
    fail("WORKFLOW_EXECUTION_TEST_DATABASE_URL must include an explicit port")
if not parsed.path.startswith("/") or parsed.path.count("/") != 1:
    fail("WORKFLOW_EXECUTION_TEST_DATABASE_URL must name exactly one database")

database_name = parsed.path.removeprefix("/")
if re.fullmatch(r"[A-Za-z0-9_]+", database_name) is None:
    fail("WORKFLOW_EXECUTION_TEST_DATABASE_URL database name is invalid")
if not database_name.endswith("_workflow_execution_test"):
    fail(
        "WORKFLOW_EXECUTION_TEST_DATABASE_URL database must end with "
        "_workflow_execution_test"
    )

exact_target = f"{hostname}:{port}/{database_name}"
if authorized_target != exact_target:
    fail("WORKFLOW_EXECUTION_AUTHORIZED_TARGET must exactly match the database URL")
PY

printf '%s\n' \
  "migration guard passed: exact local disposable workflow execution PostgreSQL database"

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
if [ "$head_count" -ne 1 ] || ! printf '%s\n' "$heads_output" | grep -Eq '^202607170034 \(head\)$'; then
  printf '%s\n' "error: expected exactly one Alembic head at 202607170034" >&2
  exit 1
fi

printf '%s\n' "alembic source head check passed: 202607170034"
export DATABASE_URL="$WORKFLOW_EXECUTION_TEST_DATABASE_URL"
uv run pytest tests/postgres_workflow_execution -q
