#!/usr/bin/env bash
# Rotate the Shusuo Feishu app secret on production A.
# The new secret is read from a hidden prompt and verified before the env file
# is touched. After Feishu resets the secret, the old value is invalid: this
# script never rolls back to it.
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

APP_ID="$(grep '^LARK_SHUSUO_APP_ID=' "$ENVF" | head -1 | cut -d= -f2-)"
if [[ -z "$APP_ID" ]]; then
  echo "LARK_SHUSUO_APP_ID is missing from $ENVF" >&2
  exit 1
fi

read -r -s -p "New Feishu app secret: " NEW_SECRET
echo
if [[ ${#NEW_SECRET} -lt 16 ]]; then
  echo "secret is too short" >&2
  exit 1
fi

# Verify with Feishu before writing. The secret is passed in the environment
# of one short-lived process; it never appears in argv or shell history.
if ! NEW_SECRET="$NEW_SECRET" APP_ID="$APP_ID" python3 - <<'PY'
import json
import os
import urllib.request

secret = os.environ["NEW_SECRET"]
request = urllib.request.Request(
    "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
    data=json.dumps(
        {"app_id": os.environ["APP_ID"], "app_secret": secret}
    ).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
except Exception as exc:
    print(f"token check failed: {type(exc).__name__}")
    raise SystemExit(1)
print("token check code:", payload.get("code"))
raise SystemExit(0 if payload.get("code") == 0 else 1)
PY
then
  echo "Feishu rejected the new secret; env file was not changed." >&2
  exit 1
fi

# Atomic replace. Preserve mode and owner of the existing env file.
NEW_SECRET="$NEW_SECRET" python3 - "$ENVF" <<'PY'
import os
import sys
import tempfile

path = sys.argv[1]
secret = os.environ["NEW_SECRET"]
stat = os.stat(path)
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
directory = os.path.dirname(path)
fd, tmp = tempfile.mkstemp(dir=directory, prefix=".env.production.")
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write("\n".join(out) + "\n")
    os.chmod(tmp, stat.st_mode & 0o777)
    os.chown(tmp, stat.st_uid, stat.st_gid)
    os.replace(tmp, path)
except Exception:
    if os.path.exists(tmp):
        os.unlink(tmp)
    raise
PY
unset NEW_SECRET

fail_forward() {
  echo "env file now holds the new secret. The old secret is invalid after a Feishu reset." >&2
  echo "Do not roll back. Fix the reported failure, then re-run verification:" >&2
  echo "  curl -sS $PUBLIC_URL/api/agents/shusuo/health" >&2
  exit 1
}

docker compose --env-file "$ENVF" -f "$COMPOSE_FILE" config --quiet || fail_forward
docker compose --env-file "$ENVF" -f "$COMPOSE_FILE" up -d --no-deps --force-recreate api || fail_forward
docker compose --env-file "$ENVF" -f "$COMPOSE_FILE" restart edge || fail_forward

ready=0
for _ in $(seq 1 60); do
  if curl -fsS "$PUBLIC_URL/api/agents/shusuo/health" 2>/dev/null \
    | python3 -c 'import json,sys; raise SystemExit(0 if json.load(sys.stdin).get("ready") is True else 1)' 2>/dev/null
  then
    ready=1
    break
  fi
  sleep 2
done
if [[ "$ready" != "1" ]]; then
  echo "Shusuo health did not report ready=true." >&2
  fail_forward
fi

if ! docker exec data_achieve_scrapy_api python - <<'PY'
import os
import httpx

response = httpx.post(
    "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
    json={
        "app_id": os.environ.get("LARK_SHUSUO_APP_ID", ""),
        "app_secret": os.environ.get("LARK_SHUSUO_APP_SECRET", ""),
    },
    timeout=20,
)
payload = response.json()
print("container token check code:", payload.get("code"))
raise SystemExit(0 if payload.get("code") == 0 else 1)
PY
then
  fail_forward
fi

echo "Shusuo app secret rotated and verified."
