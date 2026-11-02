#!/usr/bin/env bash
# Deterministic test for scripts/record_release.py.
# Uses RELEASE_LEDGER so it never touches docs/ops/releases.jsonl.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$ROOT/scripts/record_release.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
LEDGER="$TMP/ledger.jsonl"
COMMIT="0123456789abcdef0123456789abcdef01234567"

append() {
  RELEASE_LEDGER="$LEDGER" python3 "$SCRIPT" append \
    --host "$1" --commit "$COMMIT" --branch "$2" --subject "test $1" \
    --schema-revision 202610310068 --alembic-head 202610310068 \
    --verification health_ok --source test >/dev/null
}

echo "case 1: v2 records with required fields pass"
append a main
append b deploy/tiktok-cdo-codex
RELEASE_LEDGER="$LEDGER" python3 "$SCRIPT" verify >/dev/null

echo "case 2: v2 record missing schema fields fails"
python3 - "$LEDGER" "$COMMIT" <<'PY'
import json
import sys

path, commit = sys.argv[1], sys.argv[2]
with open(path, "a", encoding="utf-8") as handle:
    handle.write(
        json.dumps(
            {
                "schema_version": "release-ledger.v2",
                "host": "b",
                "commit": commit,
                "branch": "deploy/tiktok-cdo-codex",
                "verification": "health_ok",
            }
        )
        + "\n"
    )
PY
set +e
RELEASE_LEDGER="$LEDGER" python3 "$SCRIPT" verify >/dev/null 2>&1
code=$?
set -e
[[ "$code" == "1" ]] || {
  echo "FAIL: verify should exit 1 for missing v2 fields, got $code"
  exit 1
}

echo "case 3: legacy v1 records remain acceptable"
V1="$TMP/v1.jsonl"
python3 - "$V1" "$COMMIT" <<'PY'
import json
import sys

path, commit = sys.argv[1], sys.argv[2]
with open(path, "w", encoding="utf-8") as handle:
    for host, branch in (("a", "main"), ("b", "deploy/tiktok-cdo-codex")):
        handle.write(
            json.dumps(
                {
                    "schema_version": "release-ledger.v1",
                    "host": host,
                    "commit": commit,
                    "short_commit": commit[:7],
                    "branch": branch,
                    "subject": "legacy",
                }
            )
            + "\n"
        )
PY
RELEASE_LEDGER="$V1" python3 "$SCRIPT" verify >/dev/null

echo "record release test OK"