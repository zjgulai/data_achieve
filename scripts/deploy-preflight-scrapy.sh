#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-/opt/data-achieve-scrapy/.env.production}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/configs/deploy/scrapy/docker-compose.yml}"
BASE_URL="${BASE_URL:-https://scrapy.lute-tlz-dddd.top}"
CHECK_DOCKER=1

usage() {
  cat <<'EOF'
Usage: scripts/deploy-preflight-scrapy.sh [--env-file PATH] [--compose-file PATH] [--base-url URL] [--skip-docker]

Validates production deployment prerequisites without printing secrets.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    --compose-file)
      COMPOSE_FILE="$2"
      shift 2
      ;;
    --base-url)
      BASE_URL="$2"
      shift 2
      ;;
    --skip-docker)
      CHECK_DOCKER=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

BASE_URL="${BASE_URL%/}"

fail() {
  echo "preflight failed: $*" >&2
  exit 1
}

require_file() {
  local path="$1"
  [[ -f "$path" ]] || fail "missing file: $path"
}

require_command() {
  local command_name="$1"
  command -v "$command_name" >/dev/null 2>&1 || fail "missing command: $command_name"
}

require_env() {
  local name="$1"
  local value="${!name:-}"
  [[ -n "$value" ]] || fail "$name is required"
}

reject_weak_value() {
  local name="$1"
  local value="${!name:-}"
  case "$value" in
    change-me*|*local-only*|dev_password|change-me-in-local-env)
      fail "$name uses an unsafe placeholder value"
      ;;
  esac
}

require_file "$ENV_FILE"
require_file "$COMPOSE_FILE"

set -a
# shellcheck source=/dev/null
source "$ENV_FILE"
set +a

required_env=(
  SCRAPY_POSTGRES_DB
  SCRAPY_POSTGRES_USER
  SCRAPY_POSTGRES_PASSWORD
  SCRAPY_JWT_SECRET
  SCRAPY_AUTH_COOKIE_SECURE
)

for name in "${required_env[@]}"; do
  require_env "$name"
  reject_weak_value "$name"
done

[[ "${#SCRAPY_POSTGRES_PASSWORD}" -ge 20 ]] || fail "SCRAPY_POSTGRES_PASSWORD must be at least 20 characters"
[[ "${#SCRAPY_JWT_SECRET}" -ge 32 ]] || fail "SCRAPY_JWT_SECRET must be at least 32 characters"

if [[ "${SCRAPY_AUTH_COOKIE_SECURE}" != "true" ]]; then
  fail "SCRAPY_AUTH_COOKIE_SECURE must be true in production"
fi

if [[ "${SCRAPY_SMTP_HOST:-}" != "" || "${SCRAPY_SMTP_USER:-}" != "" || "${SCRAPY_SMTP_PASSWORD:-}" != "" ]]; then
  require_env SCRAPY_SMTP_HOST
  require_env SCRAPY_SMTP_USER
  require_env SCRAPY_SMTP_PASSWORD
  require_env SCRAPY_SMTP_FROM
fi

if [[ "$CHECK_DOCKER" == "1" ]]; then
  require_command docker
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config >/dev/null
  docker network inspect lighthouse_ai_video_net >/dev/null
fi

if command -v curl >/dev/null 2>&1; then
  curl -ksS --max-time 10 "$BASE_URL/api/health" >/dev/null || true
fi

echo "scrapy deploy preflight passed"
