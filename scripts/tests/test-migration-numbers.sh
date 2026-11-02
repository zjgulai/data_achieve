#!/usr/bin/env bash
# Deterministic test for scripts/check_migration_numbers.py.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$ROOT/scripts/check_migration_numbers.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/versions" "$TMP/docs"

cat >"$TMP/versions/202601010001_a.py" <<'PY'
revision = "202601010001"
down_revision = None
PY
cat >"$TMP/versions/202601010002_b.py" <<'PY'
revision = "202601010002"
down_revision = "202601010001"
PY
cat >"$TMP/docs/plan.md" <<'MD'
Migration: down_revision = "202601010002"
MD

echo "case 1: consistent chain and plan"
out="$(python3 "$SCRIPT" --versions "$TMP/versions" --docs "$TMP/docs" --expect-head 202601010002)"
grep -q "migration number check OK" <<<"$out" || {
  echo "FAIL: expected OK"
  echo "$out"
  exit 1
}

echo "case 2: plan references a revision outside the chain"
cat >"$TMP/docs/plan.md" <<'MD'
Migration: down_revision = "202512310099"
MD
set +e
out="$(python3 "$SCRIPT" --versions "$TMP/versions" --docs "$TMP/docs" 2>&1)"
code=$?
set -e
[[ "$code" == "1" ]] || {
  echo "FAIL: expected exit 1, got $code"
  echo "$out"
  exit 1
}
grep -q "is not in the chain" <<<"$out" || {
  echo "FAIL: expected a chain warning"
  echo "$out"
  exit 1
}

echo "case 3: multiple heads"
cat >"$TMP/versions/202601010003_c.py" <<'PY'
revision = "202601010003"
down_revision = "202601010001"
PY
set +e
out="$(python3 "$SCRIPT" --versions "$TMP/versions" --docs "$TMP/docs" 2>&1)"
code=$?
set -e
[[ "$code" == "1" ]] || {
  echo "FAIL: multiple heads must exit 1, got $code"
  echo "$out"
  exit 1
}
grep -q "multiple heads" <<<"$out" || {
  echo "FAIL: expected a multiple-heads warning"
  echo "$out"
  exit 1
}
rm "$TMP/versions/202601010003_c.py"

echo "case 4: allowlisted historical reference passes"
cat >"$TMP/docs/plan.md" <<'MD'
Migration: down_revision = "202512310099"
MD
cat >"$TMP/allowlist.json" <<JSON
{"entries":[{"path":"$TMP/docs/plan.md","revision":"202512310099","owner":"test","reason":"historical","expires":"2026-12-31"}]}
JSON
out="$(python3 "$SCRIPT" --versions "$TMP/versions" --docs "$TMP/docs" --allowlist "$TMP/allowlist.json")"
grep -q "migration number check OK" <<<"$out" || {
  echo "FAIL: allowlisted reference should pass"
  echo "$out"
  exit 1
}

echo "case 5: a new unlisted reference still fails"
cat >"$TMP/docs/plan.md" <<'MD'
Migration: down_revision = "202512310098"
MD
set +e
out="$(python3 "$SCRIPT" --versions "$TMP/versions" --docs "$TMP/docs" --allowlist "$TMP/allowlist.json" 2>&1)"
code=$?
set -e
[[ "$code" == "1" ]] || {
  echo "FAIL: unlisted reference must fail, got $code"
  echo "$out"
  exit 1
}

echo "migration numbers test OK"