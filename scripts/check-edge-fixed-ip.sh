#!/usr/bin/env bash
#
# Read-only check for the Production A edge fixed IP.
#
# It runs one `docker inspect` over SSH. It never deploys, restarts, writes,
# or changes production state.
#
# Exit codes:
#   0  The edge container has the expected fixed IP on the expected network.
#   1  The check failed: SSH error, missing container, or wrong IP.
#   2  Invalid argument.
#
# Environment overrides:
#   SCRAPY_PROD_HOST             SSH target. Default: ubuntu@43.163.92.244
#   SCRAPY_PROD_KEY              SSH private key path.
#   SCRAPY_EDGE_CONTAINER        Edge container name.
#   SCRAPY_EDGE_NETWORK          External network name.
#   SCRAPY_EXPECTED_EDGE_IP      Expected fixed IP.

set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

HOST="${SCRAPY_PROD_HOST:-ubuntu@43.163.92.244}"
KEY="${SCRAPY_PROD_KEY:-$ROOT_DIR/../data_scrapy/zhoujian_pachong.pem}"
CONTAINER="${SCRAPY_EDGE_CONTAINER:-data_achieve_scrapy_edge}"
NETWORK="${SCRAPY_EDGE_NETWORK:-lighthouse_ai_video_net}"
EXPECTED_IP="${SCRAPY_EXPECTED_EDGE_IP:-172.20.0.16}"

usage() {
  cat <<'EOF'
Usage: scripts/check-edge-fixed-ip.sh

Read-only check for the Production A edge fixed IP.

Environment overrides:
  SCRAPY_PROD_HOST          SSH target (default: ubuntu@43.163.92.244)
  SCRAPY_PROD_KEY           SSH private key path
  SCRAPY_EDGE_CONTAINER     Edge container name (default: data_achieve_scrapy_edge)
  SCRAPY_EDGE_NETWORK       Network name (default: lighthouse_ai_video_net)
  SCRAPY_EXPECTED_EDGE_IP   Expected IP (default: 172.20.0.16)

Exit codes: 0 pass, 1 fail, 2 usage error.
EOF
}

case "${1:-}" in
  -h|--help)
    usage
    exit 0
    ;;
  "")
    ;;
  *)
    echo "Unknown argument: $1" >&2
    usage >&2
    exit 2
    ;;
esac

fail() {
  echo "FAIL  $*" >&2
  exit 1
}

[[ "$CONTAINER" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]] \
  || fail "invalid container name: $CONTAINER"
[[ "$NETWORK" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]] \
  || fail "invalid network name: $NETWORK"
[[ -n "$EXPECTED_IP" ]] || fail "expected IP is empty"
[[ -r "$KEY" ]] || fail "SSH key is not readable: $KEY"
command -v ssh >/dev/null 2>&1 || fail "ssh is required"

remote_command="docker inspect --format '{{range \$name, \$net := .NetworkSettings.Networks}}{{\$name}}={{\$net.IPAddress}} {{end}}' $CONTAINER"

observed="$(ssh -i "$KEY" \
  -o BatchMode=yes \
  -o StrictHostKeyChecking=no \
  -o ConnectTimeout=10 \
  "$HOST" "$remote_command" 2>&1)"
status=$?

if [[ "$status" -ne 0 ]]; then
  fail "cannot inspect $CONTAINER on $HOST: $observed"
fi

observed="$(printf '%s' "$observed" | tr -d '\r')"

echo "Host:      $HOST"
echo "Container: $CONTAINER"
echo "Networks:  $observed"

if printf '%s\n' "$observed" | tr -s ' \r\n' '\n' | grep -Fxq "${NETWORK}=${EXPECTED_IP}"; then
  echo "PASS  $CONTAINER has $EXPECTED_IP on $NETWORK"
  exit 0
fi

fail "$CONTAINER does not have $EXPECTED_IP on $NETWORK"
