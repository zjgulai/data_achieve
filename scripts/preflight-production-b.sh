#!/usr/bin/env bash
#
# Read-only preflight for Production B (scrapy.lute-tlz-dddd.top).
#
# Why this exists: deploy-p0.sh refuses --host b because B had no preflight.
# B is currently a strict ancestor of main (217/0 on 2026-11-02), so the next
# upgrade is a fast-forward after backup, not a merge. This script proves the
# target is safe before that fast-forward.
#
# It never deploys, restarts, writes, or changes production state.
#
# Usage:
#   SCRAPY_PROD_B_KEY=DDDD.pem bash scripts/preflight-production-b.sh
#   bash scripts/preflight-production-b.sh --target <commit>
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${SCRAPY_PROD_B_HOST:-ubuntu@101.34.52.232}"
KEY="${SCRAPY_PROD_B_KEY:-$ROOT_DIR/DDDD.pem}"
APP_DIR="${SCRAPY_PROD_B_APP_DIR:-/opt/data-achieve-scrapy/app}"
PUBLIC_URL="${SCRAPY_PROD_B_URL:-https://scrapy.lute-tlz-dddd.top}"
EDGE_FIXED_IP="${SCRAPY_PROD_B_EDGE_IP:-172.20.0.30}"
TARGET=""
FAIL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="${2:-}"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; FAIL=1; }
warn() { printf 'WARN  %s\n' "$1"; }

remote() {
  ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new \
    "$HOST" "$@"
}

health_is_current() {
  python3 -c 'import json, sys
data = json.load(sys.stdin)
revision = data.get("schema_revision")
head = data.get("schema_head")
ok = (
    data.get("status") == "ok"
    and data.get("database") == "connected"
    and data.get("schema") == "current"
    and isinstance(revision, str) and revision
    and revision == head
)
raise SystemExit(0 if ok else 1)'
}

echo "== Local =="
cd "$ROOT_DIR"
if [[ -z "$(git status --porcelain)" ]]; then
  pass "worktree clean"
else
  warn "worktree has uncommitted changes"
fi
if [[ -f "$KEY" ]]; then
  pass "ssh key present: $KEY"
else
  fail "ssh key not found: $KEY"
fi

echo "== Public =="
PUBLIC_HEALTH="$(curl --connect-timeout 5 --max-time 15 -fsS "$PUBLIC_URL/api/health" 2>/dev/null || true)"
if [[ -n "$PUBLIC_HEALTH" ]] && printf '%s' "$PUBLIC_HEALTH" | health_is_current 2>/dev/null; then
  pass "public health and schema are current"
  printf '%s' "$PUBLIC_HEALTH" | python3 -c 'import json,sys; d=json.load(sys.stdin); print("      schema=", d.get("schema_revision"))'
else
  fail "public health or schema is unhealthy"
fi
AUTH="$(curl --connect-timeout 5 --max-time 15 -fsS -o /dev/null -w '%{http_code}' "$PUBLIC_URL/api/tiktok/tools" 2>/dev/null || true)"
[[ "$AUTH" == "401" ]] && pass "TikTok tools require authentication" || fail "TikTok tools auth status ${AUTH:-unreachable} (expected 401)"

echo "== Remote (read-only) =="
if ! remote "true" >/dev/null 2>&1; then
  fail "ssh to $HOST failed; cannot verify remote state"
else
  pass "ssh reachable"

  REMOTE_HEAD="$(remote "cd $APP_DIR && git rev-parse HEAD" 2>/dev/null || true)"
  REMOTE_BRANCH="$(remote "cd $APP_DIR && git rev-parse --abbrev-ref HEAD" 2>/dev/null || true)"
  printf '      head=%s branch=%s\n' "${REMOTE_HEAD:-unknown}" "${REMOTE_BRANCH:-unknown}"
  [[ "$REMOTE_BRANCH" == "deploy/tiktok-cdo-codex" ]] && pass "branch is deploy/tiktok-cdo-codex" || fail "unexpected branch: ${REMOTE_BRANCH:-unknown}"

  if [[ -n "$TARGET" ]]; then
    [[ "$REMOTE_HEAD" == "$TARGET" ]] && pass "remote HEAD equals target $TARGET" || fail "remote HEAD $REMOTE_HEAD does not equal target $TARGET"
  fi

  EDGE_IP="$(remote "docker inspect -f '{{with index .NetworkSettings.Networks \"lighthouse_ai_video_net\"}}{{.IPAddress}}{{end}}' data_achieve_scrapy_edge" 2>/dev/null || true)"
  [[ "$EDGE_IP" == "$EDGE_FIXED_IP" ]] && pass "edge fixed IP is $EDGE_FIXED_IP" || fail "edge IP is ${EDGE_IP:-unknown}; expected $EDGE_FIXED_IP"

  CONTAINERS="$(remote "docker inspect -f '{{.Name}}={{.State.Status}}' data_achieve_scrapy_api data_achieve_scrapy_console data_achieve_scrapy_web data_achieve_scrapy_edge 2>/dev/null" || true)"
  printf '%s\n' "$CONTAINERS" | sed 's/^/      /'
  for name in data_achieve_scrapy_api data_achieve_scrapy_console data_achieve_scrapy_web data_achieve_scrapy_edge; do
    printf '%s\n' "$CONTAINERS" | grep -q "$name=running" || fail "$name is not running"
  done

  BACKUPS="$(remote "ls -1t /opt/backups 2>/dev/null | head -5" || true)"
  if [[ -n "$BACKUPS" ]]; then
    pass "recent backups present"
    printf '%s\n' "$BACKUPS" | sed 's/^/      /'
  else
    fail "no backups under /opt/backups"
  fi

  FREE_GB="$(remote "df -BG --output=avail /opt | tail -1 | tr -dc '0-9'" 2>/dev/null || true)"
  if [[ -n "$FREE_GB" && "$FREE_GB" -ge 5 ]]; then
    pass "free disk on /opt: ${FREE_GB}G"
  else
    warn "free disk on /opt: ${FREE_GB:-unknown}G (want >= 5G)"
  fi
fi

echo
if [[ "$FAIL" == "0" ]]; then
  echo "RESULT  PASS"
  exit 0
fi
echo "RESULT  FAIL"
exit 1