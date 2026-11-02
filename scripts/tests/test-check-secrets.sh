#!/usr/bin/env bash
# Tests for scripts/check_secrets.py. Uses fake credentials only.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCANNER="$ROOT/scripts/check_secrets.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }

cat >"$TMP/leak.txt" <<'EOF'
apify_api_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
-----BEGIN PRIVATE KEY-----
eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature1234567890
EOF

if python3 "$SCANNER" --path "$TMP/leak.txt" >"$TMP/out" 2>&1; then
  fail "fake credentials were not detected"
fi
grep -q "apify_token" "$TMP/out" || fail "apify token not reported"
grep -q "private_key" "$TMP/out" || fail "private key not reported"
grep -q "jwt" "$TMP/out" || fail "JWT not reported"

cat >"$TMP/ok.txt" <<'EOF'
apify_apiexampleaaaaaaaaaaaaaaaaaaaa
this line has secret-scan: allow and apify_api_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
EOF

python3 "$SCANNER" --path "$TMP/ok.txt" >"$TMP/ok-out" 2>&1 \
  || fail "allowlisted fake credentials were reported: $(cat "$TMP/ok-out")"

if python3 "$SCANNER" --path "$TMP/missing.txt" >"$TMP/missing-out" 2>&1; then
  fail "missing path should exit 2"
else
  status=$?
  [[ "$status" == "2" ]] || fail "missing path exit $status, expected 2"
fi

echo "PASS: secret scanner detects fake credentials and honors allowlist"