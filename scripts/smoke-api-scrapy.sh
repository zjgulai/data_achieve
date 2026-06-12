#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://scrapy.lute-tlz-dddd.top}"
BASE_URL="${BASE_URL%/}"
SCRAPY_DEMO_EMAIL="${SCRAPY_DEMO_EMAIL:-owner@example.com}"

if [[ -z "${SCRAPY_DEMO_PASSWORD:-}" ]]; then
  echo "SCRAPY_DEMO_PASSWORD is required" >&2
  exit 2
fi

COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT

request() {
  local method="$1"
  local path="$2"
  shift 2
  curl --fail-with-body -sS -X "$method" "$BASE_URL$path" "$@"
}

authed_get() {
  local path="$1"
  request GET "$path" -b "$COOKIE_JAR"
}

assert_non_empty_array() {
  local label="$1"
  python3 -c '
import json
import sys

label = sys.argv[1]
payload = json.load(sys.stdin)
if not isinstance(payload, list) or len(payload) == 0:
    raise SystemExit(f"{label} expected a non-empty JSON array")
' "$label"
}

echo "Checking health: $BASE_URL/api/health"
request GET "/api/health" >/dev/null

echo "Logging in: $SCRAPY_DEMO_EMAIL"
request POST "/api/auth/login" \
  -c "$COOKIE_JAR" \
  -H "Content-Type: application/json" \
  --data "{\"email\":\"$SCRAPY_DEMO_EMAIL\",\"password\":\"$SCRAPY_DEMO_PASSWORD\"}" \
  >/dev/null

echo "Checking authenticated session"
authed_get "/api/auth/me" >/dev/null

echo "Checking dashboard overview"
authed_get "/api/dashboard/overview" >/dev/null

echo "Checking task data"
authed_get "/api/tasks" | assert_non_empty_array "/api/tasks"

echo "Checking report data"
authed_get "/api/reports" | assert_non_empty_array "/api/reports"

echo "Checking alert event data"
authed_get "/api/alert-events" | assert_non_empty_array "/api/alert-events"

echo "Checking notification data"
authed_get "/api/notifications" | assert_non_empty_array "/api/notifications"

echo "API smoke passed: $BASE_URL"
