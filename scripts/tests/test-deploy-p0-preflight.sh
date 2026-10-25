#!/usr/bin/env bash
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SOURCE_DEPLOY="$REPO_ROOT/scripts/deploy-p0.sh"
SOURCE_PREFLIGHT="$REPO_ROOT/scripts/preflight-production.sh"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/deploy-p0-preflight-test.XXXXXX")"
SANDBOX="$TMP_ROOT/repo"
FAKE_BIN="$TMP_ROOT/bin"
CASES_DIR="$TMP_ROOT/cases"
CALL_LOG="$TMP_ROOT/calls.log"
GRANTS_FILE="$TMP_ROOT/grants.json"
REAL_PYTHON3="$(command -v python3)"
PASS_COUNT=0
FAIL_COUNT=0
LAST_RC=0
LAST_STDOUT=""
LAST_STDERR=""

cleanup() {
  rm -rf "$TMP_ROOT"
}
trap cleanup EXIT

mkdir -p "$SANDBOX/scripts" "$FAKE_BIN" "$CASES_DIR"
cp "$SOURCE_DEPLOY" "$SANDBOX/scripts/deploy-p0.sh"
cp "$SOURCE_PREFLIGHT" "$SANDBOX/scripts/preflight-production.sh"
chmod +x "$SANDBOX/scripts/deploy-p0.sh" "$SANDBOX/scripts/preflight-production.sh"
: > "$SANDBOX/zhoujian_pachong.pem"
: > "$SANDBOX/DDDD.pem"
chmod 600 "$SANDBOX/zhoujian_pachong.pem" "$SANDBOX/DDDD.pem"

cat > "$GRANTS_FILE" <<'JSON'
[
  {
    "collector_type": "generic_web",
    "hosts": ["example.com"],
    "max_domains": 1,
    "max_requests": 10,
    "timeout_seconds": 30,
    "expires_at": "2099-01-01T00:00:00Z"
  }
]
JSON

cat > "$SANDBOX/scripts/preflight-production.sh" <<'FAKE_PREFLIGHT'
#!/usr/bin/env bash
set -uo pipefail
printf 'code-preflight\n' >> "${CALL_LOG:?}"
printf 'FAKE production preflight rc=%s\n' "${PREFLIGHT_RC:-0}"
exit "${PREFLIGHT_RC:-0}"
FAKE_PREFLIGHT

cat > "$FAKE_BIN/git" <<'FAKE_GIT'
#!/usr/bin/env bash
set -uo pipefail
printf 'git %s\n' "$*" >> "${CALL_LOG:?}"

if [[ "${1:-}" == "status" && "${2:-}" == "--porcelain" ]]; then
  exit 0
fi
if [[ "${1:-}" == "rev-parse" && "${2:-}" == "HEAD" ]]; then
  printf 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n'
  exit 0
fi
if [[ "${1:-}" == "rev-parse" && "${2:-}" == "--short" && "${3:-}" == "HEAD" ]]; then
  printf 'aaaaaaa\n'
  exit 0
fi
if [[ "${1:-}" == "ls-remote" && "${2:-}" == "--heads" && "${3:-}" == "origin" ]]; then
  printf 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\trefs/heads/%s\n' "${4:-unknown}"
  exit 0
fi

printf 'unexpected fake git call: %s\n' "$*" >&2
exit 2
FAKE_GIT

cat > "$FAKE_BIN/ssh" <<'FAKE_SSH'
#!/usr/bin/env bash
set -uo pipefail
printf 'ssh %s\n' "$*" >> "${CALL_LOG:?}"
printf 'unexpected SSH call in offline deploy test\n' >&2
exit 99
FAKE_SSH

cat > "$FAKE_BIN/scp" <<'FAKE_SCP'
#!/usr/bin/env bash
set -uo pipefail
printf 'scp %s\n' "$*" >> "${CALL_LOG:?}"
printf 'unexpected scp call in offline deploy test\n' >&2
exit 99
FAKE_SCP

cat > "$FAKE_BIN/curl" <<'FAKE_CURL'
#!/usr/bin/env bash
set -uo pipefail
printf 'curl %s\n' "$*" >> "${CALL_LOG:?}"

url="${!#}"
case "$url" in
  */api/collectors/catalog)
    printf '%s\n' '{"collectors":[{"endpoints":[{"policy_block_reason":null}]}]}'
    exit 0
    ;;
esac

previous=""
for arg in "$@"; do
  if [[ "$previous" == "-w" || "$previous" == "--write-out" ]]; then
    printf '200'
    exit 0
  fi
  previous="$arg"
done

# HTML and JavaScript bodies are empty in this offline sandbox.
exit 0
FAKE_CURL

cat > "$FAKE_BIN/python3" <<'FAKE_PYTHON'
#!/usr/bin/env bash
set -uo pipefail
printf 'python3 %s\n' "$*" >> "${CALL_LOG:?}"
exec "${REAL_PYTHON3:?}" "$@"
FAKE_PYTHON

chmod +x "$SANDBOX/scripts/preflight-production.sh" \
  "$FAKE_BIN/git" "$FAKE_BIN/ssh" "$FAKE_BIN/scp" \
  "$FAKE_BIN/curl" "$FAKE_BIN/python3"

record_pass() {
  printf 'PASS  %s\n' "$1"
  PASS_COUNT=$((PASS_COUNT + 1))
}

record_fail() {
  printf 'FAIL  %s\n' "$1"
  FAIL_COUNT=$((FAIL_COUNT + 1))
}

run_case() {
  local name="$1"
  shift
  local stdout_file="$CASES_DIR/$name.stdout"
  local stderr_file="$CASES_DIR/$name.stderr"
  local -a extra_env=()

  while [[ $# -gt 0 && "$1" == *=* ]]; do
    extra_env+=("$1")
    shift
  done
  if [[ "${1:-}" == "--" ]]; then
    shift
  fi

  : > "$CALL_LOG"
  if [[ "${#extra_env[@]}" -gt 0 ]]; then
    env \
      PATH="$FAKE_BIN:/usr/bin:/bin" \
      CALL_LOG="$CALL_LOG" \
      REAL_PYTHON3="$REAL_PYTHON3" \
      PREFLIGHT_RC=0 \
      KEY_DIR="$SANDBOX" \
      "${extra_env[@]}" \
      /bin/bash "$SANDBOX/scripts/deploy-p0.sh" "$@" \
      >"$stdout_file" 2>"$stderr_file"
  else
    env \
      PATH="$FAKE_BIN:/usr/bin:/bin" \
      CALL_LOG="$CALL_LOG" \
      REAL_PYTHON3="$REAL_PYTHON3" \
      PREFLIGHT_RC=0 \
      KEY_DIR="$SANDBOX" \
      /bin/bash "$SANDBOX/scripts/deploy-p0.sh" "$@" \
      >"$stdout_file" 2>"$stderr_file"
  fi
  LAST_RC=$?
  LAST_STDOUT="$(<"$stdout_file")"
  LAST_STDERR="$(<"$stderr_file")"
}

assert_rc() {
  local expected="$1"
  local label="$2"
  if [[ "$LAST_RC" -eq "$expected" ]]; then
    record_pass "$label: rc=$LAST_RC"
  else
    record_fail "$label: expected rc=$expected, got rc=$LAST_RC"
  fi
}

assert_nonzero_rc() {
  local label="$1"
  if [[ "$LAST_RC" -ne 0 ]]; then
    record_pass "$label: rc=$LAST_RC"
  else
    record_fail "$label: expected nonzero rc, got 0"
  fi
}

assert_contains() {
  local value="$1"
  local expected="$2"
  local label="$3"
  if [[ "$value" == *"$expected"* ]]; then
    record_pass "$label"
  else
    record_fail "$label: missing $(printf '%q' "$expected")"
  fi
}

assert_not_contains() {
  local value="$1"
  local unexpected="$2"
  local label="$3"
  if [[ "$value" != *"$unexpected"* ]]; then
    record_pass "$label"
  else
    record_fail "$label: found $(printf '%q' "$unexpected")"
  fi
}

assert_log_contains() {
  local expected="$1"
  local label="$2"
  local log
  log="$(<"$CALL_LOG")"
  assert_contains "$log" "$expected" "$label"
}

assert_log_absent() {
  local unexpected="$1"
  local label="$2"
  local log
  log="$(<"$CALL_LOG")"
  assert_not_contains "$log" "$unexpected" "$label"
}

assert_log_empty() {
  local label="$1"
  if [[ ! -s "$CALL_LOG" ]]; then
    record_pass "$label"
  else
    record_fail "$label: unexpected calls $(printf '%q' "$(<"$CALL_LOG")")"
  fi
}

first_line_number() {
  local expected="$1"
  local line number=0
  while IFS= read -r line; do
    number=$((number + 1))
    if [[ "$line" == *"$expected"* ]]; then
      printf '%s\n' "$number"
      return 0
    fi
  done < "$CALL_LOG"
  return 1
}

assert_log_order() {
  local first="$1"
  local second="$2"
  local third="$3"
  local label="$4"
  local first_line second_line third_line

  first_line="$(first_line_number "$first" || true)"
  second_line="$(first_line_number "$second" || true)"
  third_line="$(first_line_number "$third" || true)"

  if [[ -n "$first_line" && -n "$second_line" && -n "$third_line" ]] \
    && (( first_line < second_line && second_line < third_line )); then
    record_pass "$label"
  else
    record_fail "$label: positions ${first_line:-missing}/${second_line:-missing}/${third_line:-missing}"
  fi
}

assert_log_prefix_count() {
  local expected_count="$1"
  local prefix="$2"
  local label="$3"
  local line count=0

  while IFS= read -r line; do
    if [[ "$line" == "$prefix"* ]]; then
      count=$((count + 1))
    fi
  done < "$CALL_LOG"

  if [[ "$count" -eq "$expected_count" ]]; then
    record_pass "$label: count=$count"
  else
    record_fail "$label: expected count=$expected_count, got $count"
  fi
}

printf 'CASE  A dry-run orders production preflight before branch check\n'
run_case a_dry_run -- --host a --dry-run
assert_rc 0 "A dry-run succeeds"
assert_log_order \
  "git status --porcelain" \
  "code-preflight" \
  "git ls-remote --heads origin main" \
  "A dry-run order is local -> production preflight -> remote branch"

printf '\nCASE  A preflight failure stops all deployment work\n'
run_case a_preflight_failure PREFLIGHT_RC=1 -- --host a --dry-run
assert_nonzero_rc "A preflight failure propagates"
assert_log_contains "code-preflight" "A preflight failure case runs production preflight"
assert_log_absent "git ls-remote" "preflight failure skips remote branch check"
assert_log_absent "ssh " "preflight failure skips SSH"
assert_not_contains "$LAST_STDOUT" "-- 1/6 拉取源码" "preflight failure skips deploy_one"
assert_not_contains "$LAST_STDOUT" "构建镜像" "preflight failure skips build"
assert_not_contains "$LAST_STDOUT" "alembic upgrade head" "preflight failure skips alembic"
assert_not_contains "$LAST_STDOUT" "up -d" "preflight failure skips compose up"
assert_not_contains "$LAST_STDOUT" "restart edge" "preflight failure skips edge restart"

STABLE_B_ERROR="失败：生产 B 的 preflight 尚未接入。请使用 --host a，或先完成 B 门禁。"

printf '\nCASE  B code deploy fails before local/key/preflight checks\n'
run_case b_dry_run -- --host b --dry-run
assert_nonzero_rc "B dry-run is rejected"
assert_contains "$LAST_STDERR" "$STABLE_B_ERROR" "B dry-run uses stable target error"
assert_log_empty "B dry-run performs no local, key-dependent, or preflight calls"

printf '\nCASE  both code deploy uses the same stable gate\n'
run_case both_dry_run -- --host both --dry-run
assert_nonzero_rc "both dry-run is rejected"
assert_contains "$LAST_STDERR" "$STABLE_B_ERROR" "both dry-run uses stable target error"
assert_log_empty "both dry-run performs no local, key-dependent, or preflight calls"

printf '\nCASE  missing B key cannot mask the stable target error\n'
rm -f "$SANDBOX/DDDD.pem"
run_case b_missing_key -- --host b --dry-run
assert_nonzero_rc "B dry-run without key is rejected"
assert_contains "$LAST_STDERR" "$STABLE_B_ERROR" "B target error precedes missing-key error"
assert_not_contains "$LAST_STDERR" "找不到密钥" "missing B key is not inspected for unsupported code deploy"
assert_log_empty "B dry-run without key still performs no local or preflight calls"
: > "$SANDBOX/DDDD.pem"
chmod 600 "$SANDBOX/DDDD.pem"

run_grants_case() {
  local host="$1"
  local expected_a="$2"
  local expected_b="$3"

  printf '\nCASE  grants dry-run host=%s retains grants path\n' "$host"
  run_case "grants_$host" -- \
    --host "$host" --grants-file "$GRANTS_FILE" --dry-run
  assert_rc 0 "grants host=$host succeeds"
  assert_log_absent "code-preflight" "grants host=$host skips code production preflight"
  assert_log_absent "git ls-remote" "grants host=$host skips code branch check"
  assert_contains "$LAST_STDOUT" "批准文件结构有效" "grants host=$host validates grants file"
  assert_contains "$LAST_STDOUT" "-- 1/4 写入并验证批准" "grants host=$host retains grants apply path"

  if [[ "$expected_a" == "1" ]]; then
    assert_contains "$LAST_STDOUT" "== 生产 A：" "grants host=$host includes A"
  else
    assert_not_contains "$LAST_STDOUT" "== 生产 A：" "grants host=$host excludes A"
  fi
  if [[ "$expected_b" == "1" ]]; then
    assert_contains "$LAST_STDOUT" "== 生产 B：" "grants host=$host includes B"
  else
    assert_not_contains "$LAST_STDOUT" "== 生产 B：" "grants host=$host excludes B"
  fi
}

run_grants_case a 1 0
run_grants_case b 0 1
run_grants_case both 1 1

printf '\nCASE  code dry-run skips post-deploy public verification\n'
run_case dry_run_no_verify -- --host a --dry-run
assert_rc 0 "A code dry-run succeeds without post-deploy verification"
assert_log_prefix_count 0 "curl " "A code dry-run makes no verify_public curl calls"
assert_not_contains "$LAST_STDOUT" "-- 验收 " "A code dry-run prints no post-deploy verification phase"

printf '\nCASE  help describes the supported deployment policy\n'
run_case help -- --help
assert_rc 0 "help succeeds"
assert_contains "$LAST_STDOUT" "B 门禁" "help states the B deployment gate"
assert_contains "$LAST_STDOUT" "只读 preflight" "help states dry-run still performs read-only preflight"
assert_log_empty "help performs no external calls"

printf '\nAssertions: %s passed, %s failed\n' "$PASS_COUNT" "$FAIL_COUNT"
[[ "$FAIL_COUNT" -eq 0 ]]
