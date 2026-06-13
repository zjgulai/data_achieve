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

echo "Logging in: $SCRAPY_DEMO_EMAIL"
request POST "/api/auth/login" \
  -c "$COOKIE_JAR" \
  -H "Content-Type: application/json" \
  --data "{\"email\":\"$SCRAPY_DEMO_EMAIL\",\"password\":\"$SCRAPY_DEMO_PASSWORD\"}" \
  >/dev/null

echo "Checking email channel status"
request GET "/api/notifications/email-channel" -b "$COOKIE_JAR" | python3 -m json.tool

if [[ "${TEST_EMAIL_CHANNEL:-false}" == "true" ]]; then
  echo "Sending test email to authenticated user"
  request POST "/api/notifications/email-channel/test" -b "$COOKIE_JAR" | python3 -m json.tool
fi
