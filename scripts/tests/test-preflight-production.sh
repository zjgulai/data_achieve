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
LAST_STDOUT=""
LAST_STDERR=""
SSH_MARKER="$TMP_ROOT/ssh-called"

cleanup() {
  rm -rf "$TMP_ROOT"
  rm -f /tmp/scrapy_preflight_remote.txt /tmp/scrapy_preflight_remote.err
}
trap cleanup EXIT

mkdir -p "$SANDBOX/scripts" "$FAKE_BIN" "$CASES_DIR"
cp "$SOURCE_SCRIPT" "$SANDBOX/scripts/preflight-production.sh"
chmod +x "$SANDBOX/scripts/preflight-production.sh"
touch "$TMP_ROOT/offline-key"

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

has_arg() {
  local expected="$1"
  shift
  local arg
  for arg in "$@"; do
    [[ "$arg" == "$expected" ]] && return 0
  done
  return 1
}

has_pair() {
  local expected_key="$1"
  local expected_value="$2"
  shift 2
  local previous=""
  local arg
  for arg in "$@"; do
    if [[ "$previous" == "$expected_key" && "$arg" == "$expected_value" ]]; then
      return 0
    fi
    previous="$arg"
  done
  return 1
}

has_pair --connect-timeout 5 "$@" || {
  printf 'curl missing --connect-timeout 5\n' >&2
  exit 2
}
has_pair --max-time 15 "$@" || {
  printf 'curl missing --max-time 15\n' >&2
  exit 2
}
has_arg -fsS "$@" || {
  printf 'curl missing -fsS\n' >&2
  exit 2
}

url="${!#}"
if [[ "${CURL_MODE:-ok}" == "timeout" ]]; then
  exit 28
fi
case "$url" in
  */api/health)
    printf '{"status":"%s","database":"%s","schema":"%s","schema_revision":"%s","schema_head":"%s"}\n' \
      "${PUBLIC_STATUS:-ok}" \
      "${PUBLIC_DATABASE:-connected}" \
      "${PUBLIC_SCHEMA:-current}" \
      "${PUBLIC_SCHEMA_REVISION:-202610220056}" \
      "${PUBLIC_SCHEMA_HEAD:-202610220056}"
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

has_arg() {
  local expected="$1"
  shift
  local arg
  for arg in "$@"; do
    [[ "$arg" == "$expected" ]] && return 0
  done
  return 1
}

has_arg BatchMode=yes "$@" || {
  printf 'ssh missing BatchMode=yes\n' >&2
  exit 2
}
has_arg ConnectTimeout=10 "$@" || {
  printf 'ssh missing ConnectTimeout=10\n' >&2
  exit 2
}
has_arg StrictHostKeyChecking=no "$@" || {
  printf 'ssh missing StrictHostKeyChecking=no\n' >&2
  exit 2
}

remote_command="${!#}"
[[ "$remote_command" == *"docker inspect -f '{{.State.Health.Status}}' data_achieve_scrapy_api"* ]] || {
  printf 'remote command missing exact API health inspect\n' >&2
  exit 2
}
[[ "$remote_command" == *'lighthouse_ai_video_net'* ]] || {
  printf 'remote command missing exact edge network lookup\n' >&2
  exit 2
}

: > "${SSH_MARKER:?}"
printf 'HEAD %s\n' "${REMOTE_HEAD:-abc1234}"
printf 'EDGE_IP %s\n' "${REMOTE_EDGE_IP:-172.20.0.16}"
printf 'API_HEALTH %s\n' "${REMOTE_API_HEALTH:-healthy}"
printf 'VAULT_KEY_LEN %s\n' "${REMOTE_VAULT_KEY_LEN:-44}"
printf 'TIKTOK_TOOL_COUNT %s\n' "${REMOTE_TIKTOK_TOOL_COUNT:-16}"
FAKE_SSH

chmod +x "$FAKE_BIN/git" "$FAKE_BIN/curl" "$FAKE_BIN/ssh"

run_case() {
  local name="$1"
  shift
  local stdout_file="$CASES_DIR/$name.stdout"
  local stderr_file="$CASES_DIR/$name.stderr"

  LAST_CASE="$name"
  rm -f "$SSH_MARKER"
  env \
    PATH="$FAKE_BIN:/usr/bin:/bin" \
    SSH_MARKER="$SSH_MARKER" \
    SCRAPY_PROD_HOST="offline.invalid" \
    SCRAPY_PROD_KEY="$TMP_ROOT/offline-key" \
    SCRAPY_PUBLIC_URL="http://offline.invalid" \
    "$@" \
    /bin/bash "$SANDBOX/scripts/preflight-production.sh" >"$stdout_file" 2>"$stderr_file"
  LAST_RC=$?
  LAST_STDOUT="$(<"$stdout_file")"
  LAST_STDERR="$(<"$stderr_file")"
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

assert_empty() {
  local value="$1"
  local label="$2"

  if [[ -z "$value" ]]; then
    printf 'PASS  %s: empty\n' "$label"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    printf 'FAIL  %s: expected empty, got %q\n' "$label" "$value"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
}

assert_file_absent() {
  local path="$1"
  local label="$2"

  if [[ ! -e "$path" ]]; then
    printf 'PASS  %s: absent\n' "$label"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    printf 'FAIL  %s: expected absent\n' "$label"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
}

run_case all_good
assert_rc 0 "$LAST_RC" "all-good case passes"
assert_contains "$LAST_STDOUT" "ALL CHECKS PASSED" "all-good result"
assert_empty "$LAST_STDERR" "all-good stderr"

run_case public_status_bad PUBLIC_STATUS=degraded
assert_rc 1 "$LAST_RC" "public status != ok fails"

run_case public_database_bad PUBLIC_DATABASE=disconnected
assert_rc 1 "$LAST_RC" "public database != connected fails"

run_case public_schema_revision_differs PUBLIC_SCHEMA_HEAD=202610220055
assert_rc 1 "$LAST_RC" "public schema_revision != schema_head fails"

run_case public_schema_not_current PUBLIC_SCHEMA=stale
assert_rc 1 "$LAST_RC" "public schema != current fails"

run_case api_unhealthy REMOTE_API_HEALTH=unhealthy
assert_rc 1 "$LAST_RC" "API_HEALTH unhealthy fails"

run_case edge_ip_prefix REMOTE_EDGE_IP=172.20.0.160
assert_rc 1 "$LAST_RC" "EDGE_IP 172.20.0.160 fails"

run_case custom_edge_fixed_ip SCRAPY_EDGE_FIXED_IP=10.0.0.2 REMOTE_EDGE_IP=10.0.0.2
assert_rc 0 "$LAST_RC" "SCRAPY_EDGE_FIXED_IP controls exact expected IP"

run_case vault_key_prefix REMOTE_VAULT_KEY_LEN=440
assert_rc 1 "$LAST_RC" "VAULT_KEY_LEN 440 fails"

run_case tiktok_tool_count_prefix REMOTE_TIKTOK_TOOL_COUNT=160
assert_rc 1 "$LAST_RC" "TIKTOK_TOOL_COUNT 160 fails"

run_case invalid_head REMOTE_HEAD=ABC1234
assert_rc 1 "$LAST_RC" "uppercase HEAD fails"

run_case short_head REMOTE_HEAD=abc123
assert_rc 1 "$LAST_RC" "short HEAD fails"

run_case curl_timeout CURL_MODE=timeout
assert_rc 1 "$LAST_RC" "curl failure/timeout fails"
assert_contains "$LAST_STDOUT" "CHECKS FAILED" "curl failure result"

run_case missing_key SCRAPY_PROD_KEY=
assert_rc 1 "$LAST_RC" "missing SSH key fails"
assert_contains "$LAST_STDOUT" "production SSH key missing" "missing key result"
assert_file_absent "$SSH_MARKER" "missing key skips SSH"

printf '\nAssertions: %s passed, %s failed\n' "$PASS_COUNT" "$FAIL_COUNT"
[[ "$FAIL_COUNT" -eq 0 ]]
