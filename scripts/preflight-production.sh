#!/usr/bin/env bash
# Read-only preflight for Production A (43.163.92.244).
# It never deploys, restarts, writes, or changes production state.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${SCRAPY_PROD_HOST:-ubuntu@43.163.92.244}"
KEY="${SCRAPY_PROD_KEY:-$ROOT_DIR/../data_scrapy/zhoujian_pachong.pem}"
APP_DIR="${SCRAPY_PROD_APP_DIR:-/opt/data-achieve-scrapy/app}"
ENV_FILE="${SCRAPY_PROD_ENV_FILE:-/opt/data-achieve-scrapy/.env.production}"
PUBLIC_URL="${SCRAPY_PUBLIC_URL:-https://scrapy.luteos.com}"
EXPECTED_EDGE_IP="${SCRAPY_EXPECTED_EDGE_IP:-172.20.0.16}"
EXPECTED_SCHEMA="${SCRAPY_EXPECTED_SCHEMA:-202610210055}"
EXPECTED_TOOLS="${SCRAPY_EXPECTED_TIKTOK_TOOLS:-16}"
FAIL=0

pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; FAIL=1; }
warn() { printf 'WARN  %s\n' "$1"; }

echo "== Local =="
cd "$ROOT_DIR" || exit 1
if [[ -z "$(git status --porcelain)" ]]; then
  pass "worktree clean"
else
  warn "worktree has uncommitted changes"
fi
git fetch origin main --quiet 2>/dev/null || warn "git fetch failed"
BEHIND="$(git rev-list --count HEAD..origin/main 2>/dev/null || echo unknown)"
if [[ "$BEHIND" == "0" ]]; then
  pass "local branch contains origin/main"
else
  fail "local branch is behind origin/main by $BEHIND commit(s)"
fi

echo "== Public =="
HEALTH="$(curl -sS -o /dev/null -w '%{http_code}' "$PUBLIC_URL/api/health" || echo 000)"
[[ "$HEALTH" == "200" ]] && pass "public health 200" || fail "public health $HEALTH"
AUTH="$(curl -sS -o /dev/null -w '%{http_code}' "$PUBLIC_URL/api/tiktok/tools" || echo 000)"
[[ "$AUTH" == "401" ]] && pass "TikTok tools require authentication" || fail "TikTok tools auth status $AUTH (expected 401)"

echo "== Remote =="
ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=10 "$HOST" "
cd '$APP_DIR' || exit 1
echo -n 'HEAD '
git rev-parse --short HEAD
echo -n 'STATUS '
if [ -z \"\$(git status --porcelain)\" ]; then echo clean; else echo dirty; fi
echo -n 'EDGE '
docker inspect data_achieve_scrapy_edge --format '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}'
echo -n 'API '
docker ps --filter name=data_achieve_scrapy_api --format '{{.Status}}'
echo -n 'VAULT_KEY_LEN '
docker exec data_achieve_scrapy_api python -c 'import os; print(len(os.environ.get(\"PLATFORM_CREDENTIAL_MASTER_KEY\",\"\")))'
echo -n 'TOOL_COUNT '
docker exec data_achieve_scrapy_api python -c 'from data_intelligence_hub.services.tiktok_tools import TOOL_SPECS; print(len(TOOL_SPECS))'
echo -n 'SCHEMA '
docker exec data_achieve_scrapy_api python -c 'import urllib.request; print(urllib.request.urlopen(\"http://127.0.0.1:8000/api/health\", timeout=3).read().decode())'
" > /tmp/scrapy_preflight_remote.txt 2>&1

grep -q '^HEAD ' /tmp/scrapy_preflight_remote.txt && pass "remote reachable" || fail "remote unreachable"
if grep -q "EDGE .*$EXPECTED_EDGE_IP" /tmp/scrapy_preflight_remote.txt; then
  pass "edge fixed IP $EXPECTED_EDGE_IP"
else
  fail "edge fixed IP missing $EXPECTED_EDGE_IP (see /tmp/scrapy_preflight_remote.txt)"
fi
if grep -q '^API Up .*healthy' /tmp/scrapy_preflight_remote.txt; then
  pass "API healthy"
else
  fail "API not healthy"
fi
if grep -q '^VAULT_KEY_LEN 44' /tmp/scrapy_preflight_remote.txt; then
  pass "vault key is a valid 44-char Fernet key"
else
  fail "vault key missing or invalid (expected 44 chars)"
fi
if grep -q "^TOOL_COUNT $EXPECTED_TOOLS$" /tmp/scrapy_preflight_remote.txt; then
  pass "TikTok tools = $EXPECTED_TOOLS"
else
  fail "TikTok tool count mismatch"
fi
if grep -q "\"schema_revision\":\"$EXPECTED_SCHEMA\"" /tmp/scrapy_preflight_remote.txt; then
  pass "schema revision $EXPECTED_SCHEMA"
else
  fail "schema revision mismatch (expected $EXPECTED_SCHEMA)"
fi

echo "== Result =="
if [[ "$FAIL" == "0" ]]; then
  echo "ALL CHECKS PASSED"
  exit 0
fi
echo "CHECKS FAILED"
exit 1
