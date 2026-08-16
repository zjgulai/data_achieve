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


if os.environ.get("WORKFLOW_LINEAGE_POSTGRES_TEST_AUTHORIZED") != "true":
    fail("WORKFLOW_LINEAGE_POSTGRES_TEST_AUTHORIZED=true is required")

database_url = os.environ.get("WORKFLOW_LINEAGE_TEST_DATABASE_URL")
if not database_url:
    fail("WORKFLOW_LINEAGE_TEST_DATABASE_URL is required")
authorized_target = os.environ.get("WORKFLOW_LINEAGE_AUTHORIZED_TARGET")
if not authorized_target:
    fail("WORKFLOW_LINEAGE_AUTHORIZED_TARGET is required")
if any(character.isspace() for character in database_url):
    fail("WORKFLOW_LINEAGE_TEST_DATABASE_URL must not contain whitespace")
if any(character.isspace() for character in authorized_target):
    fail("WORKFLOW_LINEAGE_AUTHORIZED_TARGET must not contain whitespace")

try:
    parsed = urlsplit(database_url)
except ValueError:
    fail("WORKFLOW_LINEAGE_TEST_DATABASE_URL is invalid")

if parsed.scheme != "postgresql+asyncpg":
    fail("WORKFLOW_LINEAGE_TEST_DATABASE_URL must use postgresql+asyncpg")
if parsed.query or parsed.fragment:
    fail("WORKFLOW_LINEAGE_TEST_DATABASE_URL must not contain query or fragment")

raw_authority = parsed.netloc.rsplit("@", 1)[-1]
if "%" in raw_authority or "%" in parsed.path:
    fail("WORKFLOW_LINEAGE_TEST_DATABASE_URL must not contain encoded parts")

try:
    hostname = parsed.hostname
    port = parsed.port
except ValueError:
    fail("WORKFLOW_LINEAGE_TEST_DATABASE_URL host or port is invalid")

if hostname not in {"localhost", "127.0.0.1"}:
    fail("WORKFLOW_LINEAGE_TEST_DATABASE_URL must target localhost")
if port is None:
    fail("WORKFLOW_LINEAGE_TEST_DATABASE_URL must include an explicit port")
if not parsed.path.startswith("/") or parsed.path.count("/") != 1:
    fail("WORKFLOW_LINEAGE_TEST_DATABASE_URL must name exactly one database")

database_name = parsed.path.removeprefix("/")
if re.fullmatch(r"[A-Za-z0-9_]+", database_name) is None:
    fail("WORKFLOW_LINEAGE_TEST_DATABASE_URL database name is invalid")
if not database_name.endswith("_workflow_lineage_test"):
    fail(
        "WORKFLOW_LINEAGE_TEST_DATABASE_URL database must end with "
        "_workflow_lineage_test"
    )

exact_target = f"{hostname}:{port}/{database_name}"
if authorized_target != exact_target:
    fail("WORKFLOW_LINEAGE_AUTHORIZED_TARGET must exactly match the database URL")
PY

printf '%s\n' \
  "migration guard passed: exact local disposable workflow lineage PostgreSQL database"

if [ "$check_only" = true ]; then
  exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
  printf '%s\n' "error: uv is required to run the PostgreSQL migration gate" >&2
  exit 2
fi

cd "$repository_root/apps/api"
export DATABASE_URL="$WORKFLOW_LINEAGE_TEST_DATABASE_URL"
heads_output="$(uv run alembic heads)"
head_count="$(printf '%s\n' "$heads_output" | awk 'NF { count += 1 } END { print count + 0 }')"
if [ "$head_count" -ne 1 ] || ! printf '%s\n' "$heads_output" | grep -Eq '^202607170034 \(head\)$'; then
  printf '%s\n' "error: expected exactly one Alembic head at 202607170034" >&2
  exit 1
fi

printf '%s\n' "alembic source head check passed: 202607170034"

cleanup_authorized_target() {
  uv run python - <<'PY' &&
import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def reset_public_schema() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            await connection.execute(text("CREATE SCHEMA public"))
    finally:
        await engine.dispose()


asyncio.run(reset_public_schema())
PY
  uv run alembic upgrade 202607170034 &&
  uv run python - <<'PY'
import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def verify_cleanup() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )
            counts = {
                "datasets": await connection.scalar(
                    text("SELECT COUNT(*) FROM datasets")
                ),
                "dataset_versions": await connection.scalar(
                    text("SELECT COUNT(*) FROM dataset_versions")
                ),
                "raw_records": await connection.scalar(
                    text("SELECT COUNT(*) FROM raw_records")
                ),
                "workflow_runs": await connection.scalar(
                    text("SELECT COUNT(*) FROM workflow_runs")
                ),
                "step_runs": await connection.scalar(
                    text("SELECT COUNT(*) FROM step_runs")
                ),
                "workflow_lineage_materialization_requests": await connection.scalar(
                    text(
                        "SELECT COUNT(*) FROM "
                        "workflow_lineage_materialization_requests"
                    )
                ),
            }
    finally:
        await engine.dispose()
    if revision != "202607170034" or any(counts.values()):
        raise SystemExit(1)


asyncio.run(verify_cleanup())
PY
}

cleanup_complete=false
cleanup_on_exit() {
  original_status="$?"
  trap - EXIT INT TERM
  if [ "$cleanup_complete" != true ]; then
    cleanup_status=0
    cleanup_authorized_target || cleanup_status="$?"
    if [ "$original_status" -ne 0 ]; then
      exit "$original_status"
    fi
    exit "$cleanup_status"
  fi
  exit "$original_status"
}

trap cleanup_on_exit EXIT
trap 'exit 130' INT TERM
uv run pytest tests/postgres_workflow_lineage -q
if cleanup_authorized_target; then
  cleanup_complete=true
  trap - EXIT INT TERM
  printf '%s\n' "authorized workflow lineage database cleanup passed: head 202607170034, zero rows"
  exit 0
fi

cleanup_complete=true
trap - EXIT INT TERM
printf '%s\n' "error: authorized workflow lineage database cleanup failed" >&2
exit 1
