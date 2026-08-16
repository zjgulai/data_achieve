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
  printf '%s\n' "error: Python is required for fail-closed authorization validation" >&2
  exit 2
fi

"$python_bin" <<'PY'
from __future__ import annotations

import os
import re
import sys
from urllib.parse import urlsplit

REVISION = "202607280044"
DATABASE_SUFFIX = "_workflow_executor_test"
CLEANUP_CONTRACT = "destroy_exact_runner_and_prove_port_closed"


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(2)


def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        fail(f"{name} is required")
    if any(character.isspace() for character in value):
        fail(f"{name} must not contain whitespace")
    return value


if os.environ.get("WORKFLOW_EXECUTOR_POSTGRES_TEST_AUTHORIZED") != "true":
    fail("WORKFLOW_EXECUTOR_POSTGRES_TEST_AUTHORIZED=true is required")

database_url = required("WORKFLOW_EXECUTOR_TEST_DATABASE_URL")
authorized_target = required("WORKFLOW_EXECUTOR_AUTHORIZED_TARGET")
runner_id = required("WORKFLOW_EXECUTOR_RUNNER_ID")
image = required("WORKFLOW_EXECUTOR_POSTGRES_IMAGE")
cleanup_contract = required("WORKFLOW_EXECUTOR_CLEANUP_CONTRACT")
authorization = required("WORKFLOW_EXECUTOR_AUTHORIZATION")

try:
    parsed = urlsplit(database_url)
    port = parsed.port
except ValueError:
    fail("WORKFLOW_EXECUTOR_TEST_DATABASE_URL host or port is invalid")

raw_authority = parsed.netloc.rsplit("@", 1)[-1]
database_name = parsed.path.removeprefix("/")
if parsed.scheme != "postgresql+asyncpg":
    fail("WORKFLOW_EXECUTOR_TEST_DATABASE_URL must use postgresql+asyncpg")
if parsed.hostname not in {"localhost", "127.0.0.1"}:
    fail("WORKFLOW_EXECUTOR_TEST_DATABASE_URL must target localhost")
if port is None:
    fail("WORKFLOW_EXECUTOR_TEST_DATABASE_URL must include an explicit port")
if parsed.username is None or parsed.password is not None:
    fail("WORKFLOW_EXECUTOR_TEST_DATABASE_URL must use a password-free test user")
if re.fullmatch(r"[A-Za-z0-9_]+", parsed.username) is None:
    fail("WORKFLOW_EXECUTOR_TEST_DATABASE_URL user is invalid")
if parsed.query or parsed.fragment:
    fail("WORKFLOW_EXECUTOR_TEST_DATABASE_URL must not contain query or fragment")
if "%" in raw_authority or "%" in parsed.path:
    fail("WORKFLOW_EXECUTOR_TEST_DATABASE_URL must not contain encoded parts")
if not parsed.path.startswith("/") or parsed.path.count("/") != 1:
    fail("WORKFLOW_EXECUTOR_TEST_DATABASE_URL must name exactly one database")
if re.fullmatch(r"[A-Za-z0-9_]+", database_name) is None:
    fail("WORKFLOW_EXECUTOR_TEST_DATABASE_URL database name is invalid")
if not database_name.endswith(DATABASE_SUFFIX):
    fail(f"WORKFLOW_EXECUTOR_TEST_DATABASE_URL database must end with {DATABASE_SUFFIX}")

exact_target = f"{parsed.hostname}:{port}/{database_name}"
if authorized_target != exact_target:
    fail("WORKFLOW_EXECUTOR_AUTHORIZED_TARGET must exactly match the database URL")
if re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,63}", runner_id) is None:
    fail("WORKFLOW_EXECUTOR_RUNNER_ID is invalid")

image_match = re.fullmatch(r"postgres:([0-9]{2})(?:\.[0-9]+)?", image)
if image_match is None or int(image_match.group(1)) < 15:
    fail("WORKFLOW_EXECUTOR_POSTGRES_IMAGE must pin PostgreSQL 15 or newer")
if cleanup_contract != CLEANUP_CONTRACT:
    fail("WORKFLOW_EXECUTOR_CLEANUP_CONTRACT is invalid")

expected_authorization = (
    "authorize-workflow-executor-postgres-candidate:"
    f"{exact_target}:revision-{REVISION}:runner-{runner_id}:"
    f"image-{image}:cleanup-{cleanup_contract}"
)
if authorization != expected_authorization:
    fail("WORKFLOW_EXECUTOR_AUTHORIZATION does not match the exact candidate tuple")
PY

printf '%s\n' \
  "workflow executor guard passed: exact authorization tuple; connection not attempted"

if [ "$check_only" = true ]; then
  exit 0
fi

if [ "${WORKFLOW_EXECUTOR_RUNTIME_AUTHORIZED:-}" != "true" ]; then
  printf '%s\n' "error: WORKFLOW_EXECUTOR_RUNTIME_AUTHORIZED=true is required" >&2
  exit 2
fi

if ! command -v uv >/dev/null 2>&1; then
  printf '%s\n' "error: uv is required to run the PostgreSQL candidate gate" >&2
  exit 2
fi

cd "$repository_root/apps/api"
heads_output="$(uv run alembic heads)"
head_count="$(printf '%s\n' "$heads_output" | awk 'NF { count += 1 } END { print count + 0 }')"
if [ "$head_count" -ne 1 ] || ! printf '%s\n' "$heads_output" | grep -Eq '^202607280044 \(head\)$'; then
  printf '%s\n' "error: expected exactly one Alembic head at 202607280044" >&2
  exit 1
fi

printf '%s\n' "alembic source head check passed: 202607280044"
export DATABASE_URL="$WORKFLOW_EXECUTOR_TEST_DATABASE_URL"
uv run pytest tests/postgres_workflow_executor -q
