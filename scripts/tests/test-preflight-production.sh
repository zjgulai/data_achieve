#!/usr/bin/env bash
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SOURCE_SCRIPT="$REPO_ROOT/scripts/preflight-production.sh"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/preflight-production-test.XXXXXX")"
SANDBOX="$TMP_ROOT/repo"
FAKE_BIN="$TMP_ROOT/bin"
CASES_DIR="$TMP_ROOT/cases"
PASS_COUNT=0
FAIL_COUNT=0
LAST_CASE=""
LAST_RC=0
LAST_OUTPUT=""

cleanup() {
  rm -rf "$TMP_ROOT"
  rm -f /tmp/scrapy_preflight_remote.txt
}
trap cleanup EXIT

mkdir -p "$SANDBOX/scripts" "$FAKE_BIN" "$CASES_DIR"
cp "$SOURCE_SCRIPT" "$SANDBOX/scripts/preflight-production.sh"
chmod +x "$SANDBOX/scripts/preflight-production.sh"

cat > "$FAKE_BIN/git" <<'FAKE_GIT'
#!/usr/bin/env bash
set -u
case "${1:-}" in
  status)
    exit 0
    ;;
  fetch)
    exit 0
    ;;
  rev-list)
    printf '0\n'
    ;;
  *)
    printf 'unexpected fake git call: %s\n' "$*" >&2
    exit 2
    ;;
esac
FAKE_GIT

cat > "$FAKE_BIN/curl" <<'FAKE_CURL'
#!/usr/bin/env bash
set -u
url="${!#}"
if [[ "${CURL_MODE:-ok}" == "timeout" ]]; then
  exit 28
fi
case "$url" in
  */api/health)
    printf '200'
    ;;
  */api/tiktok/tools)
    printf '401'
    ;;
  *)
    printf 'unexpected fake curl URL: %s\n' "$url" >&2
    exit 2
    ;;
esac
FAKE_CURL

cat > "$FAKE_BIN/ssh" <<'FAKE_SSH'
#!/usr/bin/env bash
set -u
cat <<EOF_REMOTE
HEAD ${REMOTE_HEAD:-abc1234}
STATUS clean
EDGE ${REMOTE_EDGE_IP:-172.20.0.16}
API ${REMOTE_API_HEALTH:-Up 1 hour (healthy)}
VAULT_KEY_LEN ${REMOTE_VAULT_KEY_LEN:-44}
TOOL_COUNT 16
SCHEMA {"schema_revision":"${REMOTE_SCHEMA_REVISION:-202610220056}","schema_head":"${REMOTE_SCHEMA_HEAD:-202610220056}","schema":"${REMOTE_SCHEMA:-current}"}
EOF_REMOTE
FAKE_SSH

chmod +x "$FAKE_BIN/git" "$FAKE_BIN/curl" "$FAKE_BIN/ssh"

run_case() {
  local name="$1"
  shift
  local output_file="$CASES_DIR/$name.out"

  LAST_CASE="$name"
  env \
    PATH="$FAKE_BIN:/usr/bin:/bin" \
    SCRAPY_PROD_HOST="offline.invalid" \
    SCRAPY_PROD_KEY="$TMP_ROOT/offline-key" \
    SCRAPY_PUBLIC_URL="http://offline.invalid" \
    "$@" \
    /bin/bash "$SANDBOX/scripts/preflight-production.sh" >"$output_file" 2>&1
  LAST_RC=$?
  LAST_OUTPUT="$(<"$output_file")"
}

assert_rc() {
  local expected="$1"
  local actual="$2"
  local label="$3"

  if [[ "$actual" -eq "$expected" ]]; then
    printf 'PASS  %s: rc=%s\n' "$label" "$actual"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    printf 'FAIL  %s: expected rc=%s, got rc=%s\n' "$label" "$expected" "$actual"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  local label="$3"

  if [[ "$haystack" == *"$needle"* ]]; then
    printf 'PASS  %s: contains %q\n' "$label" "$needle"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    printf 'FAIL  %s: missing %q\n' "$label" "$needle"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
}

run_case all_good
assert_rc 0 "$LAST_RC" "all-good case passes"
assert_contains "$LAST_OUTPUT" "ALL CHECKS PASSED" "all-good result"

run_case schema_revision_differs REMOTE_SCHEMA_HEAD=202610220055
assert_rc 1 "$LAST_RC" "schema_revision != schema_head fails"

run_case schema_not_current REMOTE_SCHEMA=stale
assert_rc 1 "$LAST_RC" "schema != current fails"

run_case api_unhealthy REMOTE_API_HEALTH='Up 1 hour (unhealthy)'
assert_rc 1 "$LAST_RC" "API_HEALTH unhealthy fails"

run_case edge_ip_prefix REMOTE_EDGE_IP=172.20.0.160
assert_rc 1 "$LAST_RC" "EDGE_IP 172.20.0.160 fails"

run_case vault_key_prefix REMOTE_VAULT_KEY_LEN=440
assert_rc 1 "$LAST_RC" "VAULT_KEY_LEN 440 fails"

run_case invalid_head REMOTE_HEAD=not-a-sha
assert_rc 1 "$LAST_RC" "HEAD not-a-sha fails"

run_case curl_timeout CURL_MODE=timeout
assert_rc 1 "$LAST_RC" "curl failure/timeout fails"
assert_contains "$LAST_OUTPUT" "CHECKS FAILED" "curl failure result"

printf '\nAssertions: %s passed, %s failed\n' "$PASS_COUNT" "$FAIL_COUNT"
[[ "$FAIL_COUNT" -eq 0 ]]
