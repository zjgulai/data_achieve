#!/usr/bin/env bash
# Read-only preflight for Production A (43.163.92.244).
# It never deploys, restarts, writes, or changes production state.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${SCRAPY_PROD_HOST:-ubuntu@43.163.92.244}"
KEY="${SCRAPY_PROD_KEY:-}"
APP_DIR="${SCRAPY_PROD_APP_DIR:-/opt/data-achieve-scrapy/app}"
PUBLIC_URL="${SCRAPY_PUBLIC_URL:-https://scrapy.luteos.com}"
EDGE_FIXED_IP="${SCRAPY_EDGE_FIXED_IP:-172.20.0.16}"
REMOTE_OUTPUT="/tmp/scrapy_preflight_remote.txt"
REMOTE_ERROR="/tmp/scrapy_preflight_remote.err"
FAIL=0

pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; FAIL=1; }
warn() { printf 'WARN  %s\n' "$1"; }

remote_value() {
  local key="$1"
  local line

  while IFS= read -r line; do
    if [[ "$line" == "$key "* ]]; then
      printf '%s\n' "${line#"$key "}"
      return 0
    fi
  done < "$REMOTE_OUTPUT"
  return 1
}

health_is_current() {
  python3 -c 'import json, sys; data=json.load(sys.stdin); ok=data.get("status") == "ok" and data.get("database") == "connected" and data.get("schema") == "current" and data.get("schema_revision") == data.get("schema_head"); raise SystemExit(0 if ok else 1)'
}

echo "== Local =="
cd "$ROOT_DIR"
if [[ -z "$(git status --porcelain)" ]]; then
  pass "worktree clean"
else
  warn "worktree has uncommitted changes"
fi
git fetch origin main --quiet 2>/dev/null || warn "git fetch failed"
BEHIND="$(git rev-list --count HEAD..origin/main 2>/dev/null || printf 'unknown\n')"
if [[ "$BEHIND" == "0" ]]; then
  pass "local branch contains origin/main"
else
  fail "local branch is behind origin/main by $BEHIND commit(s)"
fi

echo "== Public =="
PUBLIC_HEALTH="$(curl --connect-timeout 5 --max-time 15 -fsS "$PUBLIC_URL/api/health" 2>/dev/null || true)"
if [[ -n "$PUBLIC_HEALTH" ]] && printf '%s' "$PUBLIC_HEALTH" | health_is_current 2>/dev/null; then
  pass "public health and schema are current"
else
  fail "public health or schema is unhealthy"
fi
AUTH="$(curl --connect-timeout 5 --max-time 15 -fsS -o /dev/null -w '%{http_code}' "$PUBLIC_URL/api/tiktok/tools" 2>/dev/null || true)"
[[ "$AUTH" == "401" ]] && pass "TikTok tools require authentication" || fail "TikTok tools auth status ${AUTH:-unreachable} (expected 401)"

echo "== Remote =="
if [[ -z "$KEY" || ! -f "$KEY" ]]; then
  fail "production SSH key missing"
else
  if ! ssh -i "$KEY" \
    -o BatchMode=yes \
    -o ConnectTimeout=10 \
    -o StrictHostKeyChecking=no \
    "$HOST" "
cd '$APP_DIR' || exit 1
printf 'HEAD '
git rev-parse --short HEAD
printf 'EDGE_IP '
docker inspect -f '{{with index .NetworkSettings.Networks \"lighthouse_ai_video_net\"}}{{.IPAddress}}{{end}}' data_achieve_scrapy_edge
printf 'API_HEALTH '
docker inspect -f '{{.State.Health.Status}}' data_achieve_scrapy_api
printf 'VAULT_KEY_LEN '
docker exec data_achieve_scrapy_api python -c 'import os; print(len(os.environ.get(\"PLATFORM_CREDENTIAL_MASTER_KEY\",\"\")))'
printf 'TIKTOK_TOOL_COUNT '
docker exec data_achieve_scrapy_api python -c 'from data_intelligence_hub.services.tiktok_tools import TOOL_SPECS; print(len(TOOL_SPECS))'
" > "$REMOTE_OUTPUT" 2> "$REMOTE_ERROR"; then
    fail "remote command failed"
  fi

  REMOTE_HEAD="$(remote_value HEAD || true)"
  EDGE_IP="$(remote_value EDGE_IP || true)"
  API_HEALTH="$(remote_value API_HEALTH || true)"
  VAULT_KEY_LEN="$(remote_value VAULT_KEY_LEN || true)"
  TIKTOK_TOOL_COUNT="$(remote_value TIKTOK_TOOL_COUNT || true)"

  if [[ "$REMOTE_HEAD" =~ ^[0-9a-f]{7,}$ ]]; then
    pass "remote HEAD is a valid commit ID"
  else
    fail "remote HEAD is invalid"
  fi
  if [[ "$EDGE_IP" == "$EDGE_FIXED_IP" ]]; then
    pass "edge fixed IP $EDGE_FIXED_IP"
  else
    fail "edge fixed IP mismatch (expected $EDGE_FIXED_IP)"
  fi
  if [[ "$API_HEALTH" == "healthy" ]]; then
    pass "API container is healthy"
  else
    fail "API container is unhealthy"
  fi
  if [[ "$VAULT_KEY_LEN" == "44" ]]; then
    pass "vault key is a valid 44-char Fernet key"
  else
    fail "vault key missing or invalid (expected length 44)"
  fi
  if [[ "$TIKTOK_TOOL_COUNT" == "16" ]]; then
    pass "TikTok tools = 16"
  else
    fail "TikTok tool count mismatch (expected 16)"
  fi
fi

echo "== Result =="
if [[ "$FAIL" == "0" ]]; then
  echo "ALL CHECKS PASSED"
  exit 0
fi
echo "CHECKS FAILED"
exit 1
