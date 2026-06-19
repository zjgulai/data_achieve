#!/usr/bin/env bash
set -euo pipefail

GATEWAY_CONTAINER="${GATEWAY_CONTAINER:-ai_video_nginx}"
EDGE_CONTAINER="${EDGE_CONTAINER:-data_achieve_scrapy_edge}"
EDGE_ALIAS="${EDGE_ALIAS:-data_achieve_scrapy_proxy}"
EDGE_PORT="${EDGE_PORT:-8080}"
BASE_URL="${BASE_URL:-https://scrapy.lute-tlz-dddd.top}"
DRY_RUN=0
PUBLIC_SMOKE=1

usage() {
  cat <<'EOF'
Usage: scripts/reload-scrapy-gateway.sh [--dry-run] [--skip-public-smoke]
                                      [--gateway-container NAME]
                                      [--edge-container NAME]
                                      [--edge-alias NAME]
                                      [--edge-port PORT]
                                      [--base-url URL]

Reloads the shared outer gateway after data_achieve_scrapy_edge is recreated.
This prevents the gateway Nginx from keeping a stale Docker DNS resolution for
data_achieve_scrapy_proxy and serving transient 502 responses.

--dry-run performs read-only Docker/DNS/health probes but skips nginx reload.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --skip-public-smoke)
      PUBLIC_SMOKE=0
      shift
      ;;
    --gateway-container)
      GATEWAY_CONTAINER="$2"
      shift 2
      ;;
    --edge-container)
      EDGE_CONTAINER="$2"
      shift 2
      ;;
    --edge-alias)
      EDGE_ALIAS="$2"
      shift 2
      ;;
    --edge-port)
      EDGE_PORT="$2"
      shift 2
      ;;
    --base-url)
      BASE_URL="$2"
      shift 2
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
  echo "gateway reload failed: $*" >&2
  exit 1
}

require_command() {
  local command_name="$1"
  command -v "$command_name" >/dev/null 2>&1 || fail "missing command: $command_name"
}

container_running() {
  local name="$1"
  [[ "$(docker inspect --format '{{.State.Running}}' "$name" 2>/dev/null || true)" == "true" ]]
}

container_health() {
  local name="$1"
  docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "$name" 2>/dev/null
}

resolve_edge_alias() {
  docker exec "$GATEWAY_CONTAINER" getent hosts "$EDGE_ALIAS" | awk 'NR == 1 {print $1}'
}

require_command docker
require_command awk

container_running "$GATEWAY_CONTAINER" || fail "$GATEWAY_CONTAINER is not running"
container_running "$EDGE_CONTAINER" || fail "$EDGE_CONTAINER is not running"

edge_health="$(container_health "$EDGE_CONTAINER")"
if [[ "$edge_health" != "healthy" && "$edge_health" != "no-healthcheck" ]]; then
  fail "$EDGE_CONTAINER health is $edge_health"
fi

alias_ip="$(resolve_edge_alias)"
[[ -n "$alias_ip" ]] || fail "$EDGE_ALIAS could not be resolved inside $GATEWAY_CONTAINER"

docker exec "$GATEWAY_CONTAINER" nginx -t >/dev/null

if [[ "$DRY_RUN" == "1" ]]; then
  echo "dry-run: would reload $GATEWAY_CONTAINER"
else
  docker exec "$GATEWAY_CONTAINER" nginx -s reload >/dev/null
  echo "reloaded $GATEWAY_CONTAINER"
fi

docker exec "$GATEWAY_CONTAINER" \
  wget -qO- "http://${EDGE_ALIAS}:${EDGE_PORT}/api/health" >/dev/null || \
  fail "gateway cannot reach ${EDGE_ALIAS}:${EDGE_PORT}/api/health"

if [[ "$PUBLIC_SMOKE" == "1" ]]; then
  require_command curl
  curl -ksS --fail --max-time 10 "$BASE_URL/api/health" >/dev/null || \
    fail "public health smoke failed: $BASE_URL/api/health"
fi

echo "scrapy gateway check passed: alias=${EDGE_ALIAS} ip=${alias_ip} edge_health=${edge_health}"
