#!/usr/bin/env bash
#
# DIH P0 发布脚本。
#
# 发布内容：apps/api 与 apps/scraper-console。没有数据库迁移。
# 不重建 web、db 与共享网关。重建 api/console 后必须重启 edge，
# 否则 edge 缓存旧容器 IP，公网 502。
#
# 用法：
#   scripts/deploy-p0.sh --host a            # 生产 A
#   scripts/deploy-p0.sh --host b            # 生产 B
#   scripts/deploy-p0.sh --host both         # 两台
#   scripts/deploy-p0.sh --host a --dry-run  # 只打印，不执行
#
# 退出码：0 成功。1 失败（含目标名非法）。2 参数错误。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

HOST=""
DRY_RUN=0
WAIT_SECONDS="${WAIT_SECONDS:-180}"

# 两台生产的固定信息。
A_KEY_FILE="zhoujian_pachong.pem"
A_SSH="ubuntu@43.163.92.244"
A_BRANCH="main"
A_URL="https://scrapy.luteos.com"

B_KEY_FILE="DDDD.pem"
B_SSH="ubuntu@101.34.52.232"
B_BRANCH="deploy/tiktok-cdo-codex"
B_URL="https://scrapy.lute-tlz-dddd.top"

REMOTE_APP="/opt/data-achieve-scrapy/app"
REMOTE_ENV="/opt/data-achieve-scrapy/.env.production"
COMPOSE_REL="configs/deploy/scrapy/docker-compose.yml"

usage() {
  cat <<'EOF'
用法：scripts/deploy-p0.sh --host <a|b|both> [--dry-run]

选项：
  --host <a|b|both>  选择生产目标。
  --dry-run          只打印将要执行的命令，不做任何改动。
  -h, --help         显示本帮助。

环境变量：
  WAIT_SECONDS       等待容器健康的秒数。默认 180。
  KEY_DIR            密钥所在目录。优先于其他候选位置。
EOF
}

die() {
  echo "失败：$*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      [[ $# -ge 2 ]] || { echo "--host 缺少取值" >&2; usage >&2; exit 2; }
      HOST="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数：$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

[[ -n "$HOST" ]] || { usage >&2; exit 2; }
case "$HOST" in
  a|b|both) ;;
  *) die "host 只能是 a、b 或 both" ;;
esac

# 打印并执行。dry-run 时只打印。
run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '  [dry-run] %s\n' "$*"
    return 0
  fi
  printf '  $ %s\n' "$*"
  "$@"
}

# 在远端执行一段脚本。走 stdin，避免引号转义。
# 远端脚本自带 set -euo pipefail。
run_remote() {
  local key="$1" target="$2" script="$3"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '  [dry-run] ssh %s <<< %s\n' "$target" "$(printf '%s' "$script" | head -1)…"
    return 0
  fi
  ssh -i "$key" -o StrictHostKeyChecking=no -o ConnectTimeout=20 "$target" 'bash -s' <<< "$script"
}

# 按候选顺序查找密钥。找不到返回非零。
find_key() {
  local name="$1" candidate
  local candidates=()
  [[ -n "${KEY_DIR:-}" ]] && candidates+=("$KEY_DIR/$name")
  candidates+=(
    "$ROOT_DIR/$name"
    "$ROOT_DIR/../data_scrapy/$name"
    "$ROOT_DIR/../$name"
    "$HOME/.ssh/$name"
    "$HOME/Downloads/$name"
  )
  for candidate in "${candidates[@]}"; do
    if [[ -f "$candidate" && -r "$candidate" ]]; then
      printf '%s' "$candidate"
      return 0
    fi
  done
  return 1
}

# 本地检查。只检查本次要发布的目标。
preflight_local() {
  echo "== 本地检查 =="

  cd "$ROOT_DIR"

  local dirty
  dirty="$(git status --porcelain | wc -l | tr -d ' ')"
  [[ "$dirty" == "0" ]] || die "工作区有 $dirty 个未提交改动。发布只从已推送的提交来。"

  LOCAL_HEAD="$(git rev-parse HEAD)"
  echo "  提交：$(git rev-parse --short HEAD)"

  # 只校验本次会用到的密钥。另一台的缺失不算错误。
  if [[ "$HOST" == "a" || "$HOST" == "both" ]]; then
    A_KEY="$(find_key "$A_KEY_FILE")" || die "找不到密钥 $A_KEY_FILE"
    echo "  A 密钥：$A_KEY"
  fi
  if [[ "$HOST" == "b" || "$HOST" == "both" ]]; then
    B_KEY="$(find_key "$B_KEY_FILE")" || die "找不到密钥 $B_KEY_FILE"
    echo "  B 密钥：$B_KEY"
  fi
}

# 远端分支必须已指向本地 HEAD。逐个分支校验。
check_remote_branches() {
  echo
  echo "== 远端同步检查 =="

  local branches=()
  [[ "$HOST" == "a" || "$HOST" == "both" ]] && branches+=("$A_BRANCH")
  [[ "$HOST" == "b" || "$HOST" == "both" ]] && branches+=("$B_BRANCH")

  local branch remote_head
  for branch in "${branches[@]}"; do
    remote_head="$(git ls-remote --heads origin "$branch" | cut -f1)"
    if [[ "$remote_head" != "$LOCAL_HEAD" ]]; then
      echo "  分支 $branch 当前为 ${remote_head:-<不存在>}，未指向本地 HEAD。" >&2
      echo "  先执行：" >&2
      echo "    git push origin $LOCAL_HEAD:$branch" >&2
      die "远端分支 $branch 未更新"
    fi
    echo "  $branch → ${LOCAL_HEAD:0:7}"
  done
}

# 发布前的卷检查。只读，不打印任何密钥值。
#
# 本脚本不含数据库迁移。若 /api/health 报 schema 不在 head，
# 说明本次发布与数据库状态不匹配，必须停下人工判断。
# 缺表时 api 容器会起不来，由后置健康检查兜住。
preflight_remote() {
  local key="$1" ssh_target="$2"
  echo "-- 发布前检查"
  run_remote "$key" "$ssh_target" "set -euo pipefail
cd $REMOTE_APP

# 生产工作区必须干净。有本地改动时 merge --ff-only 可能仍成功，
# 随后 build 会把未评审的改动打进镜像。
dirty=\$(git status --porcelain | wc -l | tr -d ' ')
[ \"\$dirty\" = \"0\" ] || { echo \"  生产工作区有 \$dirty 个改动，停止\" >&2; exit 1; }
echo \"  工作区干净：\$(git rev-parse --short HEAD)\"

envf=$REMOTE_ENV
compose=\"docker compose --env-file \$envf -f $REMOTE_APP/$COMPOSE_REL\"
\$compose config --quiet
echo '  编排有效'
docker inspect -f '  发布前 api={{.State.Health.Status}}' data_achieve_scrapy_api 2>/dev/null || echo '  发布前 api=未运行'
docker inspect -f '  发布前 console={{.State.Health.Status}}' data_achieve_scrapy_console 2>/dev/null || echo '  发布前 console=未运行'
"
}

# 等待两个容器健康。
#
# 三个终态：healthy 通过；unhealthy 失败；死活不出健康态则超时失败。
# missing 与 <no value> 都按未就绪处理，不当作通过。
wait_healthy() {
  local key="$1" ssh_target="$2"
  run_remote "$key" "$ssh_target" "set -euo pipefail
deadline=\$(( \$(date +%s) + $WAIT_SECONDS ))
while :; do
  api=\$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}nohealth{{end}}' data_achieve_scrapy_api 2>/dev/null || echo missing)
  con=\$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}nohealth{{end}}' data_achieve_scrapy_console 2>/dev/null || echo missing)
  echo \"  api=\$api console=\$con\"
  if [ \"\$api\" = healthy ] && [ \"\$con\" = healthy ]; then exit 0; fi
  if [ \"\$api\" = unhealthy ] || [ \"\$con\" = unhealthy ]; then
    echo '容器不健康。日志尾部：' >&2
    docker logs --tail 40 data_achieve_scrapy_api 2>&1 | tail -20 >&2 || true
    docker logs --tail 40 data_achieve_scrapy_console 2>&1 | tail -20 >&2 || true
    exit 1
  fi
  if [ \$(date +%s) -ge \$deadline ]; then
    echo '等待健康超时。' >&2
    docker logs --tail 40 data_achieve_scrapy_api 2>&1 | tail -20 >&2 || true
    exit 1
  fi
  sleep 5
done"
}

# 单台发布。任何一步失败都必须中止。
#
# 不用 `deploy_one ... || status=1`：那会让整个函数体的 errexit 失效，
# 后续步骤继续跑，失败被吞掉。
deploy_one() {
  local tag="$1" key="$2" ssh_target="$3" branch="$4" url="$5"

  echo
  echo "== 生产 ${tag}：$url =="

  preflight_remote "$key" "$ssh_target"

  # 第 1 步：拉取源码。
  # 生产 B 的 GitHub 拉取常报 GnuTLS recv error -110 / -54 与 too slow。
  # 必须重试，且不能把 fetch 接到管道——管道会吞掉退出码。
  echo "-- 1/5 拉取源码"
  local fetch_script
  fetch_script=$(cat <<REMOTE
set -euo pipefail
cd $REMOTE_APP

ok=0
for i in 1 2 3 4 5 6 7 8; do
  if git -c http.version=HTTP/1.1 -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=20 fetch origin $branch; then
    ok=1
    echo "  fetch 第 \$i 次成功"
    break
  fi
  echo "  fetch 第 \$i 次失败" >&2
  sleep 5
done
[ "\$ok" = "1" ] || { echo "fetch 连续失败，停止" >&2; exit 1; }

git merge --ff-only FETCH_HEAD
here=\$(git rev-parse HEAD)
echo "  远端提交：\$here"
REMOTE
)
  run_remote "$key" "$ssh_target" "$fetch_script"

  # 第 2 步：校验编排。所有 compose 命令都要显式传 --env-file。
  local compose
  compose="docker compose --env-file $REMOTE_ENV -f $REMOTE_APP/$COMPOSE_REL"

  echo "-- 2/5 校验编排"
  run_remote "$key" "$ssh_target" "set -euo pipefail
cd $REMOTE_APP
$compose config --quiet
echo '  编排有效'"

  # 第 3 步：构建 api 与 console。只构建这两个。
  echo "-- 3/5 构建镜像"
  run_remote "$key" "$ssh_target" "set -euo pipefail
cd $REMOTE_APP
$compose build api console"

  # 第 4 步：替换容器，然后重启 edge。
  # --no-deps 避免连带重启 db 等依赖。
  # 重启 edge 是必须的：edge 的 nginx 用静态 proxy_pass 主机名，
  # 只在启动时解析一次，容器换 IP 后会一直打旧地址。
  echo "-- 4/5 替换容器并重启 edge"
  run_remote "$key" "$ssh_target" "set -euo pipefail
cd $REMOTE_APP
$compose up -d --no-deps api console
$compose restart edge
sleep 3
docker inspect -f '  edge={{.State.Status}}' data_achieve_scrapy_edge"

  echo "-- 5/5 等待健康"
  wait_healthy "$key" "$ssh_target"
}

# 公网验收。任何一项不符即为失败。
verify_public() {
  local url="$1"
  local fail=0

  echo "-- 验收 $url"

  local path code
  for path in /api/tools /tools /docs /connect /tools/exa_search /settings/providers /settings/members; do
    code="$(curl -sL -o /dev/null -w '%{http_code}' --max-time 30 "$url$path")"
    printf '  %-24s %s\n' "$path" "$code"
    [[ "$code" == "200" ]] || fail=1
  done

  # 旧路径必须重定向，跟随之后仍为 200。
  code="$(curl -sL -o /dev/null -w '%{http_code}' --max-time 30 "$url/platforms")"
  printf '  %-24s %s\n' "/platforms" "$code"
  [[ "$code" == "200" ]] || fail=1

  # 前端烧录域名复核。
  # console 的 NEXT_PUBLIC_API_URL 在构建期烧进产物。
  # 若产物里出现另一台生产的域名，即为串台。
  local host_other baked
  case "$url" in
    *luteos.com*) host_other="scrapy.lute-tlz-dddd.top" ;;
    *lute-tlz-dddd.top*) host_other="scrapy.luteos.com" ;;
    *) host_other="" ;;
  esac
  if [[ -n "$host_other" ]]; then
    baked="$(curl -sL --max-time 30 "$url/platforms" \
      | grep -oE '/_next/static/chunks/[^" ]+\.js' | sort -u | head -12 \
      | while read -r chunk; do
          curl -s --max-time 15 "$url$chunk" | grep -oE 'https://scrapy\.[a-z0-9.-]+'
        done | sort -u)"
    if printf '%s\n' "$baked" | grep -qx "https://$host_other"; then
      echo "  产物烧录了另一台生产的域名 https://$host_other，串台" >&2
      fail=1
    fi
    printf '  %-24s %s\n' "烧录域名" "$(printf '%s' "$baked" | tr '\n' ' ')"
  fi

  # 策略字段必须已上线。发布前为 0。
  # 目录行数与策略字段数必须相等：每个端点行都应带该字段。
  local counts rows keyed blocked
  counts="$(curl -s --max-time 40 "$url/api/collectors/catalog" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print("PARSE_ERROR 0 0")
    raise SystemExit(0)
rows = [e for g in d.get("collectors", []) for e in g.get("endpoints", [])]
keyed = sum(1 for e in rows if "policy_block_reason" in e)
blocked = sum(1 for e in rows if e.get("policy_block_reason"))
print(len(rows), keyed, blocked)
' 2>/dev/null)" || counts=""

  if [[ -z "$counts" ]]; then
    echo "  目录接口不可用，无法校验策略字段" >&2
    fail=1
  else
    rows="$(echo "$counts" | cut -d' ' -f1)"
    keyed="$(echo "$counts" | cut -d' ' -f2)"
    blocked="$(echo "$counts" | cut -d' ' -f3)"
    printf '  目录行/有字段/被阻断    %s/%s/%s\n' "$rows" "$keyed" "$blocked"

    if [[ "$rows" == "PARSE_ERROR" || "$rows" == "0" ]]; then
      echo "  目录接口返回不可解析或空内容" >&2
      fail=1
    elif [[ "$rows" != "$keyed" ]]; then
      echo "  有 $(( rows - keyed )) 行缺少 policy_block_reason。新后端未生效。" >&2
      fail=1
    fi
  fi

  if [[ "$fail" == "1" ]]; then
    echo "验收失败" >&2
    return 1
  fi
  echo "  验收通过"
}

# ---------- 主流程 ----------

preflight_local
check_remote_branches

if [[ "$HOST" == "a" || "$HOST" == "both" ]]; then
  deploy_one A "$A_KEY" "$A_SSH" "$A_BRANCH" "$A_URL"
  verify_public "$A_URL"
fi

if [[ "$HOST" == "b" || "$HOST" == "both" ]]; then
  deploy_one B "$B_KEY" "$B_SSH" "$B_BRANCH" "$B_URL"
  verify_public "$B_URL"
fi

echo
echo "发布完成。"
