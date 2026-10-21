#!/usr/bin/env bash
# Rotate the Shusuo Feishu app secret on production A.
# The new secret is read from stdin and never printed or passed as an argument.
set -euo pipefail

ENVF="${SHUSUO_ENV_FILE:-/opt/data-achieve-scrapy/.env.production}"
APP_DIR="${SHUSUO_APP_DIR:-/opt/data-achieve-scrapy/app}"
COMPOSE_FILE="${SHUSUO_COMPOSE_FILE:-$APP_DIR/configs/deploy/scrapy/docker-compose.yml}"
PUBLIC_URL="${SHUSUO_PUBLIC_URL:-https://scrapy.luteos.com}"

if [[ ! -f "$ENVF" ]]; then
  echo "env file not found: $ENVF" >&2
  exit 1
fi
if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "compose file not found: $COMPOSE_FILE" >&2
  exit 1
fi

read -r -s -p "New Feishu app secret: " NEW_SECRET
echo
if [[ ${#NEW_SECRET} -lt 16 ]]; then
  echo "secret is too short" >&2
  exit 1
fi

stamp="$(date +%Y%m%dT%H%M%S)"
backup="${ENVF}.bak.${stamp}"
cp "$ENVF" "$backup"

NEW_SECRET="$NEW_SECRET" python3 - "$ENVF" <<'PY'
import os
import sys

path = sys.argv[1]
secret = os.environ["NEW_SECRET"]
lines = open(path, encoding="utf-8").read().splitlines()
out = []
found = False
for line in lines:
    if line.startswith("LARK_SHUSUO_APP_SECRET="):
        out.append("LARK_SHUSUO_APP_SECRET=" + secret)
        found = True
    else:
        out.append(line)
if not found:
    out.append("LARK_SHUSUO_APP_SECRET=" + secret)
open(path, "w", encoding="utf-8").write("\n".join(out) + "\n")
PY
unset NEW_SECRET

docker compose --env-file "$ENVF" -f "$COMPOSE_FILE" config --quiet
docker compose --env-file "$ENVF" -f "$COMPOSE_FILE" up -d api

ok=0
for _ in $(seq 1 60); do
  if curl -fsS "$PUBLIC_URL/api/agents/shusuo/health" >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 2
done
if [[ "$ok" != "1" ]]; then
  echo "API did not become healthy; restoring $backup" >&2
  cp "$backup" "$ENVF"
  docker compose --env-file "$ENVF" -f "$COMPOSE_FILE" up -d api
  exit 1
fi

if ! docker exec data_achieve_scrapy_api python - <<'PY'
import os
import httpx

app_id = os.environ.get("LARK_SHUSUO_APP_ID", "")
secret = os.environ.get("LARK_SHUSUO_APP_SECRET", "")
response = httpx.post(
    "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
    json={"app_id": app_id, "app_secret": secret},
    timeout=20,
)
payload = response.json()
raise SystemExit(0 if payload.get("code") == 0 else 1)
PY
then
  echo "new secret was rejected by Feishu; restoring $backup" >&2
  cp "$backup" "$ENVF"
  docker compose --env-file "$ENVF" -f "$COMPOSE_FILE" up -d api
  exit 1
fi

echo "Shusuo app secret rotated. Backup: $backup"
