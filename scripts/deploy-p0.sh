#!/usr/bin/env bash
#
# DIH 发布脚本。
#
# 两种模式：
#   1. 发布模式（默认）：拉源码，构建并替换 api 与 console。
#   2. 批准模式（--grants-file）：只更新外访域名批准，不构建镜像。
#
# 发布模式的准入顺序：目标策略 → 本地检查 → 生产 A 只读 preflight →
# 远端同步检查 → 发布。任何一步失败都不进入下一步。
# 生产 B 的 preflight 尚未接入，因此 b 与 both 的代码发布一律拒绝；
# 批准模式不受此限制。
#
# 不重建 web、db 与共享网关。构建后用新镜像执行 alembic upgrade head；
# 迁移失败会中止发布，旧容器继续服务。重建 api/console 后必须重启 edge，
# 否则 edge 缓存旧容器 IP，公网 502。替换完容器还会尝试重载共享网关
# （scripts/reload-scrapy-gateway.sh）；重载失败只告警，不中止发布。
#
# 用法：
#   scripts/deploy-p0.sh --host a
#   scripts/deploy-p0.sh --host both
#   scripts/deploy-p0.sh --host a --dry-run
#   scripts/deploy-p0.sh --host both --grants-file /tmp/grants.json
#
# 退出码：0 成功。1 失败（含目标名非法）。2 参数错误。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

HOST=""
DRY_RUN=0
GRANTS_FILE=""
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
用法：scripts/deploy-p0.sh --host <a|b|both> [选项]

选项：
  --host <a|b|both>     选择生产目标。
                        a：支持代码发布。
                        b、both：B 门禁完成前拒绝代码发布。批准模式仍可使用。
  --grants-file <路径>  只更新外访域名批准。文件内容为 JSON 数组。
                        此模式不构建镜像，只替换 api 容器并重启 edge。
  --dry-run             只打印将要执行的命令，不做任何改动。
                        代码发布模式仍执行只读 preflight。
  -h, --help            显示本帮助。

环境变量：
  WAIT_SECONDS          等待容器健康的秒数。默认 180。
  KEY_DIR               密钥所在目录。优先于其他候选位置。

批准文件的格式见 docs/standards/http-grant-runbook.md。
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
    --grants-file)
      [[ $# -ge 2 ]] || { echo "--grants-file 缺少路径" >&2; usage >&2; exit 2; }
      GRANTS_FILE="$2"
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

# 在远端执行一段脚本。走 stdin，避免引号转义。
# 远端脚本自带 set -euo pipefail。
run_remote() {
  local key="$1" target="$2" script="$3"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '  [dry-run] ssh %s <<< %s\n' "$target" "$(printf '%s' "$script" | sed -n '2p')"
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

# ---------- 批准文件的本地校验 ----------

# 读取并校验批准文件。校验通过后设置 GRANTS_JSON。
#
# 这里只做结构检查。权威校验在远端用真实策略代码执行。
# 内容不以命令行参数传递，而是用 scp 上传后由远端脚本读文件，
# 因此不需要做 shell 字符白名单。
load_grants() {
  [[ -f "$GRANTS_FILE" ]] || die "找不到批准文件：$GRANTS_FILE"

  GRANTS_JSON="$(python3 - "$GRANTS_FILE" <<'PY'
import json, sys

path = sys.argv[1]
try:
    with open(path, encoding="utf-8") as f:
        grants = json.load(f)
except Exception as exc:
    sys.exit(f"不是合法 JSON：{exc}")

if not isinstance(grants, list) or not grants:
    sys.exit("顶层必须是至少含一项的数组")

ALLOWED = {
    "generic_web",
    "public_feed",
    "ecommerce_product_page",
    "ecommerce_product_discovery",
}

seen = set()
for i, g in enumerate(grants):
    if not isinstance(g, dict):
        sys.exit(f"第 {i + 1} 项不是对象")
    ct = g.get("collector_type")
    if ct not in ALLOWED:
        sys.exit(f"第 {i + 1} 项的 collector_type 不合法：{ct!r}")
    if ct in seen:
        sys.exit(f"collector_type 重复：{ct}。同一类型只能有一条配置。")
    seen.add(ct)

    hosts = g.get("hosts")
    if not isinstance(hosts, list) or not 1 <= len(hosts) <= 5:
        sys.exit(f"{ct} 的 hosts 必须是 1 到 5 个主机名")
    for h in hosts:
        if not isinstance(h, str) or not h or "/" in h or ":" in h:
            sys.exit(f"{ct} 的主机名不合法：{h!r}。只写主机名，不带协议、路径或端口。")

    md = g.get("max_domains", 5)
    if not isinstance(md, int) or isinstance(md, bool) or not 1 <= md <= 5:
        sys.exit(f"{ct} 的 max_domains 必须是 1 到 5")
    if len(hosts) > md:
        sys.exit(f"{ct} 的 max_domains 小于 hosts 数量")

    mr = g.get("max_requests", 50)
    if not isinstance(mr, int) or isinstance(mr, bool) or not 1 <= mr <= 50:
        sys.exit(f"{ct} 的 max_requests 必须是 1 到 50")

    ts = g.get("timeout_seconds", 60)
    if not isinstance(ts, (int, float)) or isinstance(ts, bool) or not 0 < ts <= 60:
        sys.exit(f"{ct} 的 timeout_seconds 必须大于 0 且不超过 60")

    exp = g.get("expires_at")
    if not isinstance(exp, str) or "T" not in exp:
        sys.exit(f"{ct} 的 expires_at 必须是带时区的 ISO 8601")

# 去掉空白，供日志显示。
print(json.dumps(grants, separators=(",", ":"), ensure_ascii=False))
PY
)" || die "批准文件不合法"

  echo "  批准文件结构有效"
  python3 - "$GRANTS_JSON" <<'PY'
import json, sys
for g in json.loads(sys.argv[1]):
    print(f"    {g['collector_type']}: {len(g['hosts'])} 个主机")
PY
}

# ---------- 目标策略 ----------

# 代码发布的目标准入。生产 B 的 preflight 尚未接入，因此拒绝 b 与 both。
# 必须在 preflight_local 与密钥查找之前调用：目标不支持时不应触碰本地状态。
# 批准模式不经过这里。
require_supported_deploy_target() {
  case "$HOST" in
    a) return 0 ;;
    b|both)
      die "生产 B 的 preflight 尚未接入。请使用 --host a，或先完成 B 门禁。"
      ;;
    *) die "host 只能是 a、b 或 both" ;;
  esac
}

# ---------- 本地检查 ----------

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

  if [[ -n "$GRANTS_FILE" ]]; then
    echo
    echo "== 批准文件 =="
    load_grants
  fi
}

# 生产 A 的只读 preflight。任何一项检查失败即中止，不进入发布。
# 检查逻辑在 scripts/preflight-production.sh，本函数只传目标信息。
# preflight 脚本自身以退出码表达结论，这里不再解析输出。
preflight_production_a() {
  echo
  echo "== 生产 A 只读 preflight =="
  SCRAPY_PROD_KEY="$A_KEY" \
  SCRAPY_PROD_HOST="$A_SSH" \
  SCRAPY_PUBLIC_URL="$A_URL" \
    bash "$ROOT_DIR/scripts/preflight-production.sh" \
    || die "生产 A preflight 未通过，停止发布"
  echo "preflight 总体 PASS"
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

# 发布前的只读检查。
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

# 等待指定容器健康。
#
# 三个终态：healthy 通过；unhealthy 失败；死活不出健康态则超时失败。
# missing 与 nohealth 都按未就绪处理，不当作通过。
wait_healthy() {
  local key="$1" ssh_target="$2" names="$3"
  run_remote "$key" "$ssh_target" "set -euo pipefail
deadline=\$(( \$(date +%s) + $WAIT_SECONDS ))
while :; do
  line=''
  bad=0
  for n in $names; do
    s=\$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}nohealth{{end}}' "data_achieve_scrapy_\$n" 2>/dev/null || echo missing)
    line=\"\$line \$n=\$s\"
    [ \"\$s\" = unhealthy ] && bad=1
  done
  echo \"  \$line\"
  [ \"\$bad\" = 1 ] && { echo '容器不健康。日志尾部：' >&2; docker logs --tail 40 data_achieve_scrapy_api 2>&1 | tail -20 >&2 || true; exit 1; }
  ok=1
  for n in $names; do
    s=\$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}nohealth{{end}}' \"data_achieve_scrapy_\$n\" 2>/dev/null || echo missing)
    [ \"\$s\" = healthy ] || ok=0
  done
  [ \"\$ok\" = 1 ] && exit 0
  if [ \$(date +%s) -ge \$deadline ]; then
    echo '等待健康超时。' >&2
    docker logs --tail 40 data_achieve_scrapy_api 2>&1 | tail -20 >&2 || true
    exit 1
  fi
  sleep 5
done"
}

# 取公网目录里被策略阻断的行数。失败时输出空串。
blocked_count() {
  local url="$1"
  curl -s --max-time 40 "$url/api/collectors/catalog" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    raise SystemExit(1)
rows = [e for g in d.get("collectors", []) for e in g.get("endpoints", [])]
print(sum(1 for e in rows if e.get("policy_block_reason")))
' 2>/dev/null
}

# ---------- 发布模式 ----------

deploy_one() {
  local tag="$1" key="$2" ssh_target="$3" branch="$4" url="$5"

  echo
  echo "== 生产 ${tag}：$url =="

  preflight_remote "$key" "$ssh_target"

  # 第 1 步：拉取源码。
  # 生产 B 的 GitHub 拉取常报 GnuTLS recv error -110 / -54 与 too slow。
  # 必须重试，且不能把 fetch 接到管道——管道会吞掉退出码。
  echo "-- 1/6 拉取源码"
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

  echo "-- 2/6 校验编排"
  run_remote "$key" "$ssh_target" "set -euo pipefail
cd $REMOTE_APP
$compose config --quiet
echo '  编排有效'"

  # 第 3 步：构建 api 与 console。只构建这两个。
  echo "-- 3/6 构建镜像"
  run_remote "$key" "$ssh_target" "set -euo pipefail
cd $REMOTE_APP
$compose build api console"

  # 第 4 步：应用数据库迁移。用新镜像跑 alembic，失败则中止发布，
  # 旧容器仍在运行。迁移只应向前，回滚需人工处理。
  echo "-- 4/7 应用数据库迁移"
  run_remote "$key" "$ssh_target" "set -euo pipefail
cd $REMOTE_APP
$compose run --rm --no-deps api alembic upgrade head"

  # 第 5 步：替换容器，然后重启 edge。
  # --no-deps 避免连带重启 db 等依赖。
  # 重启 edge 是必须的：edge 的 nginx 用静态 proxy_pass 主机名，
  # 只在启动时解析一次，容器换 IP 后会一直打旧地址。
  echo "-- 5/7 替换容器并重启 edge"
  run_remote "$key" "$ssh_target" "set -euo pipefail
cd $REMOTE_APP
$compose up -d --no-deps api console
$compose restart edge
sleep 3
docker inspect -f '  edge={{.State.Status}}' data_achieve_scrapy_edge"

  echo "-- 6/7 等待健康"
  wait_healthy "$key" "$ssh_target" "api console"

  echo "-- 7/7 重载共享网关"
  reload_gateway "$key" "$ssh_target"
}

# 尝试重载共享网关。失败只告警，不中止发布。
#
# 重载会用新 DNS 解析换掉网关里的静态上游地址。网关另有无关上游
# （ai_video_backend）解析不到时，重载会失败，但本项目的 edge 不受影响：
# 只要 edge 容器不重建，网关缓存的旧地址仍然有效。
# 因此这里不把失败当发布失败，由后续公网验收给出最终结论。
reload_gateway() {
  local key="$1" ssh_target="$2"

  # timeout 兜底：网关容器异常时 docker exec 可能长时间无响应。
  run_remote "$key" "$ssh_target" "set -uo pipefail
cd $REMOTE_APP
if timeout 90 bash scripts/reload-scrapy-gateway.sh --skip-public-smoke; then
  echo '  网关已重载'
else
  echo '  警告：网关重载失败。公网若 502，先查 scripts/reload-scrapy-gateway.sh --dry-run 的失败原因。' >&2
  echo '  网关可重载前，保持 edge 容器不被重建；网关会继续使用其当前地址。' >&2
fi"
}

# ---------- 批准模式 ----------

# 把一条批准写入远端 env 文件，用真实策略代码验证，再替换 api。
#
# 关键顺序：先备份，再写，再验证，验证失败立刻恢复。
# 验证不通过时容器还没重启，生产仍在用旧配置。
apply_grants_one() {
  local tag="$1" key="$2" ssh_target="$3" url="$4"

  echo
  echo "== 生产 ${tag}：$url =="

  local before
  before="$(blocked_count "$url")"
  if [[ -z "$before" ]]; then
    die "$tag 取不到当前被阻断行数，停止。发布会掩盖问题。"
  fi
  echo "  当前被阻断行：$before"

  echo "-- 1/4 写入并验证批准"

  # 批准内容用文件传输，不内联进 shell 命令。
  # 内联 JSON 会引入引号与元字符问题；实测括号表达式也无法可靠拦截。
  local local_grants remote_grants
  local_grants="$(mktemp)"
  printf '%s\n' "$GRANTS_JSON" > "$local_grants"
  remote_grants="/tmp/dih-grants-$$.json"

  if [[ "$DRY_RUN" == "1" ]]; then
    printf '  [dry-run] scp %s %s:%s\n' "$local_grants" "$ssh_target" "$remote_grants"
  else
    scp -q -i "$key" -o StrictHostKeyChecking=no -o ConnectTimeout=20 \
      "$local_grants" "$ssh_target:$remote_grants" \
      || { rm -f "$local_grants"; die "上传批准文件失败"; }
  fi
  rm -f "$local_grants"

  local script
  script=$(cat <<REMOTE
set -euo pipefail
cd $REMOTE_APP

envf=$REMOTE_ENV
composefile=$REMOTE_APP/$COMPOSE_REL
compose="docker compose --env-file \$envf -f \$composefile"

# 编排必须已声明该变量。否则只改 env 文件不会进容器。
grep -q 'COLLECTION_HTTP_GRANTS' "\$composefile" \
  || { echo '  编排未声明 COLLECTION_HTTP_GRANTS。先跑一次发布模式。' >&2; exit 1; }

# 批准值必须在一行内。compose 的 .env 解析不支持多行值。
grants_line=\$(tr -d '\n\r' < $remote_grants)
[ -n "\$grants_line" ] || { echo '  批准文件为空' >&2; exit 1; }

# 备份。保留权限与属主。
backup="\$envf.bak.\$(date +%Y%m%dT%H%M%S)"
cp -p "\$envf" "\$backup"
echo "  已备份：\$backup"

owner=\$(stat -c '%u:%g' "\$envf")
mode=\$(stat -c '%a' "\$envf")

# 原子替换。先删旧行，再追加新行，最后整体换入。
tmp="\$envf.new.\$\$"
grep -v '^COLLECTION_HTTP_GRANTS=' "\$envf" > "\$tmp" || true
printf 'COLLECTION_HTTP_GRANTS=%s\n' "\$grants_line" >> "\$tmp"
chown "\$owner" "\$tmp"
chmod "\$mode" "\$tmp"
mv "\$tmp" "\$envf"
echo '  已写入 env 文件'

# 用镜像里的真实策略代码验证。
# 失败就恢复备份，此时容器还没动，生产不受影响。
if ! \$compose run --rm --no-deps -T api python -c '
from data_intelligence_hub.collectors.outbound_policy import http_grant
import json, os
grants = json.loads(os.environ["COLLECTION_HTTP_GRANTS"])
if not isinstance(grants, list):
    raise SystemExit("not a list")
seen = set()
for g in grants:
    ct = g["collector_type"]
    if ct in seen:
        raise SystemExit("duplicate collector_type: " + ct)
    seen.add(ct)
    http_grant(ct)
print("  策略校验通过：" + str(len(grants)) + " 条")
'; then
  echo '  策略校验失败，恢复备份。' >&2
  cp -p "\$backup" "\$envf"
  exit 1
fi

rm -f $remote_grants
echo "\$backup"
REMOTE
)
  run_remote "$key" "$ssh_target" "$script"

  echo "-- 2/4 替换 api 并重启 edge"
  run_remote "$key" "$ssh_target" "set -euo pipefail
cd $REMOTE_APP
compose=\"docker compose --env-file $REMOTE_ENV -f $REMOTE_APP/$COMPOSE_REL\"
\$compose up -d --no-deps api
\$compose restart edge
sleep 3
docker inspect -f '  edge={{.State.Status}}' data_achieve_scrapy_edge"

  echo "-- 3/4 等待 api 健康"
  wait_healthy "$key" "$ssh_target" "api"

  echo "-- 4/4 验收"
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "  [dry-run] 上线后重新取被阻断行数，仅上升时回滚。"
    return 0
  fi

  local after
  after="$(blocked_count "$url")"
  if [[ -z "$after" ]]; then
    die "$tag 取不到新的被阻断行数。请人工核对 $url"
  fi
  echo "  被阻断行：$before → $after"

  if (( after > before )); then
    echo "  被阻断行上升，说明配置让某类采集整体被拒。" >&2
    echo "  回滚中：恢复备份并重建 api。" >&2
    rollback_grants "$key" "$ssh_target"
    die "$tag 批准失败，已回滚"
  fi

  if (( after == before )); then
    echo "  警告：被阻断行数未变化。确认这批主机对应的端点是否已解除。" >&2
  else
    echo "  解除 $(( before - after )) 行"
  fi
}

# 恢复最近一份 env 备份并重建 api。
rollback_grants() {
  local key="$1" ssh_target="$2"
  run_remote "$key" "$ssh_target" "set -euo pipefail
cd $REMOTE_APP
envf=$REMOTE_ENV
last=\$(ls -1t \"\$envf\".bak.* 2>/dev/null | head -1 || true)
[ -n \"\$last\" ] || { echo '  找不到备份，无法自动回滚。' >&2; exit 1; }
cp -p \"\$last\" \"\$envf\"
echo \"  已恢复：\$last\"
compose=\"docker compose --env-file \$envf -f $REMOTE_APP/$COMPOSE_REL\"
\$compose up -d --no-deps api
\$compose restart edge
" || echo "  自动回滚失败，请人工处理。" >&2
}

# ---------- 公网验收 ----------

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
    baked="$(
      chunks="$(curl -sL --max-time 30 "$url/platforms" \
        | grep -oE '/_next/static/chunks/[^" ]+\.js' | sort -u | sed -n '1,12p' \
        || true)"
      while read -r chunk; do
        [[ -n "$chunk" ]] || continue
        curl -s --max-time 15 "$url$chunk" \
          | grep -oE 'https://scrapy\.[a-z0-9.-]+' \
          || true
      done <<< "$chunks"
    )"
    baked="$(printf '%s\n' "$baked" | sed '/^$/d' | sort -u)"
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

# 批准模式先判断：它不动代码，因此不经过目标策略与生产 preflight。
if [[ -n "$GRANTS_FILE" ]]; then
  preflight_local
  if [[ "$HOST" == "a" || "$HOST" == "both" ]]; then
    apply_grants_one A "$A_KEY" "$A_SSH" "$A_URL"
  fi
  if [[ "$HOST" == "b" || "$HOST" == "both" ]]; then
    apply_grants_one B "$B_KEY" "$B_SSH" "$B_URL"
  fi
  echo
  echo "批准完成。"
  exit 0
fi

# 代码发布：目标策略在本地检查与密钥查找之前，失败时不触碰任何本地状态。
require_supported_deploy_target

preflight_local
preflight_production_a
check_remote_branches

if [[ "$HOST" == "a" ]]; then
  deploy_one A "$A_KEY" "$A_SSH" "$A_BRANCH" "$A_URL"
  # dry-run 只打印命令，没有真实发布产物，公网验收没有意义。
  if [[ "$DRY_RUN" != "1" ]]; then
    verify_public "$A_URL"
  fi
fi

echo
echo "发布完成。"
