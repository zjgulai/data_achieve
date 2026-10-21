#!/usr/bin/env bash
# Run the Shusuo secret rotation on production A from the local repository.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KEY="${SCRAPY_PROD_KEY:-$ROOT_DIR/zhoujian_pachong.pem}"
HOST="${SCRAPY_PROD_HOST:-ubuntu@43.163.92.244}"

exec ssh -t -i "$KEY" "$HOST" \
  "cd /opt/data-achieve-scrapy/app && bash scripts/rotate-shusuo-secret.sh"
