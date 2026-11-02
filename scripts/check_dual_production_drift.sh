#!/usr/bin/env bash
#
# Read-only drift check for the two Source production sites.
#
# Why this exists: production A and B are supposed to differ only in the CDO
# Agent. In practice B stayed on schema 202610220056 while A moved to
# 202610310068. Nothing in the release flow surfaced that gap, because
# deploy-p0.sh only records host A and preflight-production.sh only checks A.
#
# The check reads configs/deploy/scrapy/production-scope.json. A host with role
# frozen_nonprod or decommissioned is skipped and reported as SKIP. A host with
# role active is checked. This replaces free-text waivers with a machine-read
# scope file.
#
# This script never writes, deploys, or restarts anything.
#
# Usage:
#   bash scripts/check_dual_production_drift.sh
#   bash scripts/check_dual_production_drift.sh --strict
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
A_URL="${SCRAPY_PROD_A_URL:-https://scrapy.luteos.com}"
B_URL="${SCRAPY_PROD_B_URL:-https://scrapy.lute-tlz-dddd.top}"
SCOPE_FILE="${SCRAPY_PRODUCTION_SCOPE:-$ROOT/configs/deploy/scrapy/production-scope.json}"
LEDGER="$ROOT/docs/ops/releases.jsonl"
STRICT=0
[[ "${1:-}" == "--strict" ]] && STRICT=1

fail=0

scope_role() {
  local host="$1"
  python3 - "$SCOPE_FILE" "$host" <<'PY'
import json
import sys

path, host = sys.argv[1], sys.argv[2]
try:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
except (OSError, json.JSONDecodeError):
    print("active")
    raise SystemExit(0)
print(data.get("hosts", {}).get(host, {}).get("role", "active"))
PY
}

fetch_health() {
  local url="$1"
  curl --connect-timeout 5 --max-time 15 -fsS "$url/api/health" 2>/dev/null || true
}

parse_health() {
  python3 -c 'import json,sys
try:
    data = json.load(sys.stdin)
except Exception:
    print("unreachable\t\t\t\t")
    raise SystemExit(0)
print("\t".join(str(data.get(key, "")) for key in ("status", "database", "schema", "schema_revision", "schema_head")))' <<<"$1"
}

A_ROLE="$(scope_role a)"
B_ROLE="$(scope_role b)"

echo "scope file: $SCOPE_FILE"
echo "roles: A=$A_ROLE B=$B_ROLE"
echo
printf '%-6s %-14s %-12s %-10s %-8s %-16s\n' HOST ROLE STATUS DATABASE SCHEMA REVISION

A_FIELDS="$(parse_health "$(fetch_health "$A_URL")")"
B_FIELDS="$(parse_health "$(fetch_health "$B_URL")")"
IFS=$'\t' read -r A_STATUS A_DB A_SCHEMA A_REV A_HEAD <<<"$A_FIELDS"
IFS=$'\t' read -r B_STATUS B_DB B_SCHEMA B_REV B_HEAD <<<"$B_FIELDS"

print_row() {
  local host="$1" role="$2" status="$3" db="$4" schema="$5" rev="$6"
  if [[ "$role" != "active" ]]; then
    printf '%-6s %-14s %-12s %-10s %-8s %-16s\n' "$host" "$role" SKIP - - -
  else
    printf '%-6s %-14s %-12s %-10s %-8s %-16s\n' "$host" "$role" "${status:-unreachable}" "$db" "$schema" "$rev"
  fi
}

print_row A "$A_ROLE" "$A_STATUS" "$A_DB" "$A_SCHEMA" "$A_REV"
print_row B "$B_ROLE" "$B_STATUS" "$B_DB" "$B_SCHEMA" "$B_REV"

for host in A B; do
  eval "role=\${${host}_ROLE}"
  [[ "$role" == "active" ]] || continue
  eval "status=\${${host}_STATUS:-}"
  eval "db=\${${host}_DB:-}"
  eval "schema=\${${host}_SCHEMA:-}"
  eval "rev=\${${host}_REV:-}"
  eval "head=\${${host}_HEAD:-}"
  if [[ "$status" != "ok" || "$db" != "connected" || "$schema" != "current" ]]; then
    printf 'FAIL  host %s is not healthy (status=%s database=%s schema=%s)\n' \
      "$host" "${status:-unreachable}" "${db:-}" "${schema:-}"
    fail=1
  elif [[ "$rev" != "$head" ]]; then
    printf 'FAIL  host %s schema revision %s does not match head %s\n' "$host" "$rev" "$head"
    fail=1
  fi
done

if [[ "$A_ROLE" == "active" && "$B_ROLE" == "active" && -n "${A_REV:-}" && -n "${B_REV:-}" && "$A_REV" != "$B_REV" ]]; then
  printf 'WARN  schema drift: A=%s B=%s\n' "$A_REV" "$B_REV"
  [[ "$STRICT" == "1" ]] && fail=1
elif [[ "$A_ROLE" == "active" && "$B_ROLE" == "active" ]]; then
  printf 'PASS  schema revisions match\n'
else
  printf 'SKIP  schema comparison (a host is not active)\n'
fi

if [[ -f "$LEDGER" ]]; then
  echo
  echo "Last recorded release per host:"
  python3 - "$LEDGER" <<'PY'
import json
import sys
from collections import OrderedDict

last = OrderedDict()
with open(sys.argv[1], encoding="utf-8") as handle:
    for line in handle:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        host = row.get("host")
        if host:
            last[host] = row
for host in ("a", "b"):
    row = last.get(host)
    if not row:
        print(f"  {host}: no ledger record")
        continue
    print(
        "  {host}: {commit} {date} {subject}".format(
            host=host,
            commit=row.get("short_commit", "?"),
            date=(row.get("recorded_at") or "")[:19],
            subject=row.get("subject", ""),
        )
    )
PY
fi

echo
if [[ "$fail" == "0" ]]; then
  echo "RESULT  PASS (drift may still be intentional; see WARN/SKIP lines)"
  exit 0
fi
echo "RESULT  FAIL"
exit 1