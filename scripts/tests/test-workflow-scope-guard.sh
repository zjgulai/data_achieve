#!/usr/bin/env bash
# Tests for scripts/workflow_scope_guard.py.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GUARD="$ROOT/scripts/workflow_scope_guard.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }
run() { python3 "$GUARD" --root "$TMP" "$@"; }

cd "$TMP"
git init -q
git config user.email test@example.com
git config user.name Test
git commit -q --allow-empty -m init
mkdir -p staging/a staging/b staging/d staging/e

run claim --id wf-a --write staging/a >/dev/null || fail "claim wf-a"
run claim --id wf-b --write staging/b >/dev/null || fail "claim wf-b"
if run claim --id wf-c --write staging/a/nested >/dev/null 2>&1; then
  fail "overlapping claim was accepted"
fi
if run claim --id wf-a --write staging/a >/dev/null 2>&1; then
  fail "duplicate active claim was accepted"
fi

printf 'x\n' >staging/a/file.txt
run audit --claim wf-a >/dev/null || fail "in-scope change was rejected"
printf 'x\n' >other.txt
if run audit --claim wf-a >/dev/null 2>&1; then
  fail "out-of-scope change was accepted"
fi
rm other.txt
git add -A
git commit -q -m files

if run claim --id wf-d --write staging/d --read .env >/dev/null 2>&1; then
  :
else
  fail "claim wf-d"
fi
if run audit --claim wf-d >/dev/null 2>&1; then
  fail "secret read was accepted"
fi
run audit --claim wf-d --allow-secret-read >/dev/null || fail "allowed secret read was rejected"

run claim --id wf-e --write staging/e --paid-calls >/dev/null || fail "claim wf-e"
if run audit --claim wf-e >/dev/null 2>&1; then
  fail "paid calls without approval were accepted"
fi
ALLOW_PAID_API=1 run audit --claim wf-e >/dev/null || fail "approved paid calls were rejected"

python3 - <<'PY'
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
claims = Path("tmp/workflow-claims")
claims.mkdir(parents=True, exist_ok=True)
(claims / "old.json").write_text(json.dumps({
    "id": "old",
    "created_at": (datetime.now(UTC) - timedelta(hours=5)).isoformat(),
    "write": [str(Path("staging/old").resolve())],
    "read": [],
    "paid_calls": False,
}), encoding="utf-8")
PY
run claim --id wf-f --write staging/old >/dev/null || fail "stale claim blocked a new claim"
run clean >/dev/null || fail "clean failed"
[ ! -e tmp/workflow-claims/old.json ] || fail "stale claim was not removed"

echo "PASS: workflow scope guard claims, audits, and cleans"