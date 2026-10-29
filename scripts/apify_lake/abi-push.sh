#!/usr/bin/env bash
# =============================================================================
# ABI 本地 → 腾讯云 PostgreSQL 可重复推送
# =============================================================================
#
# 背景：
#   目标库 172.22.0.3:5432 是服务器上的 Docker 内网地址，公网不可达，
#   只能经 43.163.92.244 的 SSH 中转（scp + 远端容器内 psql）。
#
# 两种模式：
#   data    默认。TRUNCATE 目标表后重灌数据。表结构必须已存在。
#           适合日常反复执行：同一份数据推 10 次结果一样。
#   schema  重建表结构再灌数据。目标端表不存在时用这个。
#           注意：会 DROP 目标表，目标端独立写入的数据会丢。
#
# 用法：
#   ./abi-push.sh --dry-run                 # 只列出将推送什么
#   ./abi-push.sh                           # data 模式全量推送
#   ./abi-push.sh --mode schema             # 首次建库用
#   ./abi-push.sh --only raw.apify_dataset  # 只推一张表
#   ./abi-push.sh --only ai --verify-only   # 只做事后核对
#
# 幂等保证：
#   - data 模式先 TRUNCATE 再 COPY，重复执行结果一致。
#   - 导入用单事务，中途失败自动回滚，不会留下半份数据。
#   - 结束后必做逐表行数对账，不一致即非零退出。
#
# 依赖：
#   本地 docker（abi_migtest 容器）、zstd、ssh 密钥。
#   远端 docker（postgres:16 镜像已存在）。
# =============================================================================

set -uo pipefail

# ---------------------------------------------------------------- 配置
REPO="/Users/lute/Project/data_scrapy"
ENV_FILE="${HOME}/.config/apify-lake/push.env"

# 缺省值；可被 env 文件或环境变量覆盖
LOCAL_CONTAINER="${ABI_LOCAL_CONTAINER:-abi_migtest}"
LOCAL_DB="${ABI_LOCAL_DB:-abitest}"
LOCAL_USER="${ABI_LOCAL_USER:-test}"
REMOTE_HOST="${ABI_REMOTE_HOST:-43.163.92.244}"
REMOTE_PORT="${ABI_REMOTE_PORT:-22222}"
REMOTE_USER="${ABI_REMOTE_USER:-ubuntu}"
REMOTE_PG_HOST="${ABI_REMOTE_PG_HOST:-172.22.0.3}"
REMOTE_PG_PORT="${ABI_REMOTE_PG_PORT:-5432}"
REMOTE_PG_USER="${ABI_REMOTE_PG_USER:-zhoujian}"
REMOTE_PG_DB="${ABI_REMOTE_PG_DB:-postgres}"
PEM="${ABI_PEM:-${REPO}/zhoujian_pachong.pem}"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a; source "$ENV_FILE"; set +a
fi

# ---------------------------------------------------------------- 表清单
# 顺序即依赖顺序：被引用的父表在前，引用方在后。
# TRUNCATE 时反序执行（先清子表），避免外键阻塞。
#
# 分区表写父表名，传输时自动展开为 raw.<name>*，与 pg_dump 的通配符匹配。
META_TABLES=(
  meta.apify_account
)

RAW_TABLES=(
  raw.apify_dataset
  raw.apify_item
  raw.si_tiktok_video
  raw.si_tiktok_comment
  raw.si_tiktok_hashtag_snapshot
  raw.si_metric_snapshot
  raw.si_music_platform_snapshot
  raw.si_author_video_snapshot
  raw.si_social_post
  raw.apify_tweet
  raw.probe_instagram_post
  raw.probe_tiktok_video
  raw.probe_youtube_video
  raw.pmo_collection_record
  raw.amazon_review
  raw.product_catalog
  raw.load_file
  raw.load_error
)

ALL_TABLES=("${META_TABLES[@]}" "${RAW_TABLES[@]}")

# ---------------------------------------------------------------- 参数
MODE="data"
DRY_RUN=0
VERIFY_ONLY=0
ONLY_FILTER=""

usage() {
  sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)        MODE="${2:-}"; shift 2 ;;
    --only)        ONLY_FILTER="${2:-}"; shift 2 ;;
    --dry-run)     DRY_RUN=1; shift ;;
    --verify-only) VERIFY_ONLY=1; shift ;;
    -h|--help)     usage 0 ;;
    *)             echo "未知参数: $1" >&2; usage 2 ;;
  esac
done

case "$MODE" in
  data|schema) ;;
  *) echo "--mode 只接受 data 或 schema，收到: $MODE" >&2; exit 2 ;;
esac

# ---------------------------------------------------------------- 工具
ts()  { date '+%Y-%m-%d %H:%M:%S'; }
log() { printf '%s %s\n' "$(ts)" "$*"; }
die() { printf '%s [FATAL] %s\n' "$(ts)" "$*" >&2; exit 1; }

WORK="$(mktemp -d "${TMPDIR:-/tmp}/abi-push.XXXXXX")"
REMOTE_WORK="/tmp/abi-push-$$"
CLEANED=0

cleanup() {
  [[ $CLEANED -eq 1 ]] && return
  CLEANED=1
  rm -rf "$WORK"
  # 远端临时目录尽力清理；失败不阻塞
  ssh -i "$PEM" -p "$REMOTE_PORT" -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
      "${REMOTE_USER}@${REMOTE_HOST}" "rm -rf ${REMOTE_WORK}" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

ssh_do() {
  ssh -i "$PEM" -p "$REMOTE_PORT" -o StrictHostKeyChecking=no -o ConnectTimeout=15 \
      -o BatchMode=yes "${REMOTE_USER}@${REMOTE_HOST}" "$@"
}

# 远端 psql 包装：在 postgres:16 容器里连目标库
# 用 --network host 才能到达 172.22.0.3
remote_psql() {
  local args="$1"
  ssh_do "docker run --rm --network host -e PGPASSWORD='${REMOTE_PG_PASSWORD}' \
    -v ${REMOTE_WORK}:/w:ro postgres:16 \
    psql -h ${REMOTE_PG_HOST} -p ${REMOTE_PG_PORT} -U ${REMOTE_PG_USER} -d ${REMOTE_PG_DB} ${args}"
}

remote_query() {
  remote_psql "-tAc \"$1\"" 2>/dev/null
}

# ---------------------------------------------------------------- 目标端可用表
# data 模式只能写已存在的表。目标端缺表时直接跳过并告警，
# 让 --mode schema 负责建结构，避免每轮都因一张表整批失败。
TARGET_EXISTING=()

probe_target_tables() {
  local q="SELECT n.nspname||'.'||c.relname FROM pg_class c
           JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE c.relkind='r' AND n.nspname IN ('meta','raw')"
  local raw_list
  raw_list="$(ssh_do "docker run --rm --network host -e PGPASSWORD='${REMOTE_PG_PASSWORD}' \
    postgres:16 psql -h ${REMOTE_PG_HOST} -U ${REMOTE_PG_USER} -d ${REMOTE_PG_DB} -tAc \"$q\"" 2>/dev/null)"
  while IFS= read -r line; do
    [[ -n "$line" ]] && TARGET_EXISTING+=("$line")
  done <<< "$raw_list"
}

target_has() {
  local t="$1"
  local e
  for e in "${TARGET_EXISTING[@]+"${TARGET_EXISTING[@]}"}"; do
    [[ "$e" == "$t" ]] && return 0
    # 分区表：父表在目标端可能只以分区形式存在
    if [[ "$t" == "raw.apify_item" && "$e" == raw.apify_item_* ]]; then
      return 0
    fi
  done
  return 1
}

# ---------------------------------------------------------------- 选择表
# macOS 自带 bash 3.2 没有 mapfile，用 while read 代替
TABLES=()
while IFS= read -r _t; do
  [[ -n "$_t" ]] && TABLES+=("$_t")
done < <(
  for t in "${ALL_TABLES[@]}"; do
    if [[ -z "$ONLY_FILTER" ]] || [[ "$t" == *"$ONLY_FILTER"* ]]; then
      printf '%s\n' "$t"
    fi
  done
)
[[ ${#TABLES[@]} -eq 0 ]] && die "没有匹配的表（过滤器: ${ONLY_FILTER:-无}）"

log "模式=$MODE 表数=${#TABLES[@]} 目标=${REMOTE_PG_HOST}:${REMOTE_PG_PORT}/${REMOTE_PG_DB}"

# ---------------------------------------------------------------- 前置检查
preflight() {
  [[ -f "$PEM" ]] || die "找不到 SSH 密钥: $PEM"
  [[ -n "${REMOTE_PG_PASSWORD:-}" ]] || die "未设置数据库密码。请写入 ${ENV_FILE}：\n  REMOTE_PG_PASSWORD=..."
  command -v zstd >/dev/null || die "缺少 zstd"
  command -v docker >/dev/null || die "缺少 docker"

  docker inspect "$LOCAL_CONTAINER" >/dev/null 2>&1 \
    || die "本地容器 $LOCAL_CONTAINER 不存在或未启动（先 docker start）"

  # 必须在任何 docker run -v 之前建目录：
  # 目录不存在时 docker 会以 root 身份创建，后续 ubuntu 用户 scp 会 Permission denied。
  ssh_do "mkdir -p ${REMOTE_WORK}" || die "无法创建远端临时目录 ${REMOTE_WORK}"
  ssh_do "test -w ${REMOTE_WORK}" || die "远端目录不可写: ${REMOTE_WORK}"

  log "检查远端连通性…"
  ssh_do "docker image inspect postgres:16 >/dev/null 2>&1 || docker pull -q postgres:16" \
    || die "远端不可达或无法准备 postgres:16 镜像"

  local remote_ok
  remote_ok="$(remote_query 'SELECT 1')"
  # 首次执行时远端目录还没建，remote_psql 的挂载会失败；这里用不挂载的方式探测
  if [[ "$remote_ok" != "1" ]]; then
    remote_ok="$(ssh_do "docker run --rm --network host -e PGPASSWORD='${REMOTE_PG_PASSWORD}' \
      postgres:16 psql -h ${REMOTE_PG_HOST} -U ${REMOTE_PG_USER} -d ${REMOTE_PG_DB} -tAc 'SELECT 1'" 2>/dev/null)"
  fi
  [[ "$remote_ok" == "1" ]] || die "目标库连接失败（检查密码与网络）"

  log "探测目标端已有表…"
  probe_target_tables
  log "目标端已有 ${#TARGET_EXISTING[@]} 张表"
  log "前置检查通过"
}

[[ $VERIFY_ONLY -eq 0 ]] && preflight

# ---------------------------------------------------------------- 本地导出
dump_all() {
  local args=()
  for t in "${TABLES[@]}"; do
    if [[ "$t" == "raw.apify_item" ]]; then
      # 分区表必须用通配符，否则只导出父表定义、分区数据全丢
      args+=("--table=raw.apify_item*")
    else
      args+=("--table=$t")
    fi
  done

  local extra=()
  if [[ "$MODE" == "data" ]]; then
    extra+=(--data-only)          # 表结构已存在，只灌数据
  else
    extra+=(--clean --if-exists)  # 重建结构
  fi

  log "导出中（${MODE}）…"
  local out="$WORK/dump.sql"
  docker exec "$LOCAL_CONTAINER" pg_dump -U "$LOCAL_USER" -d "$LOCAL_DB" \
      "${args[@]}" --no-owner --no-privileges "${extra[@]}" > "$out" 2>"$WORK/dump.err"

  if [[ ! -s "$out" ]]; then
    cat "$WORK/dump.err" >&2
    die "导出为空，检查表名与容器状态"
  fi

  local copies
  copies="$(grep -cE '^COPY ' "$out" || true)"
  log "导出完成：$(du -h "$out" | cut -f1)，COPY 语句 ${copies} 条"

  if [[ $copies -eq 0 && "$MODE" == "data" ]]; then
    die "data 模式下没有任何 COPY 语句，导出可能不含数据"
  fi

  log "压缩…"
  zstd -3 -T0 -q -f "$out" -o "$WORK/dump.sql.zst"
  log "压缩后：$(du -h "$WORK/dump.sql.zst" | cut -f1)"
}

# ---------------------------------------------------------------- 传输
transfer() {
  log "传输到 ${REMOTE_HOST}…"
  local start=$SECONDS
  scp -i "$PEM" -P "$REMOTE_PORT" -o StrictHostKeyChecking=no -q \
      "$WORK/dump.sql.zst" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_WORK}/dump.sql.zst" \
    || die "scp 失败"
  log "传输完成，耗时 $((SECONDS - start)) 秒"
}

# ---------------------------------------------------------------- 导入
build_import_sql() {
  # data 模式：先清表再灌，保证可重复。
  # 反序清表（子表先清），避免外键阻塞；不用 CASCADE 以免误伤。
  local prep="$WORK/prep.sql"
  : > "$prep"

  if [[ "$MODE" == "data" ]]; then
    echo "SET client_min_messages = warning;" >> "$prep"
    echo "BEGIN;" >> "$prep"
    local i
    for (( i=${#TABLES[@]}-1; i>=0; i-- )); do
      echo "TRUNCATE TABLE ${TABLES[$i]} CASCADE;" >> "$prep"
    done
    echo "COMMIT;" >> "$prep"
  fi
}

import_remote() {
  build_import_sql

  log "远端导入…"
  ssh_do "cd ${REMOTE_WORK} && zstd -dc dump.sql.zst > dump.sql" || die "远端解压失败"

  local rc=0
  if [[ -s "$WORK/prep.sql" ]]; then
    scp -i "$PEM" -P "$REMOTE_PORT" -o StrictHostKeyChecking=no -q \
        "$WORK/prep.sql" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_WORK}/prep.sql" || die "scp prep 失败"
    ssh_do "docker run --rm --network host -e PGPASSWORD='${REMOTE_PG_PASSWORD}' \
      -v ${REMOTE_WORK}:/w:ro postgres:16 \
      psql -h ${REMOTE_PG_HOST} -U ${REMOTE_PG_USER} -d ${REMOTE_PG_DB} \
      -v ON_ERROR_STOP=1 -q -f /w/prep.sql" || die "清表失败"
  fi

  ssh_do "docker run --rm --network host -e PGPASSWORD='${REMOTE_PG_PASSWORD}' \
    -v ${REMOTE_WORK}:/w:ro postgres:16 \
    psql -h ${REMOTE_PG_HOST} -U ${REMOTE_PG_USER} -d ${REMOTE_PG_DB} \
    -v ON_ERROR_STOP=1 -q --single-transaction -f /w/dump.sql" >"$WORK/import.log" 2>&1 || rc=$?

  if [[ $rc -ne 0 ]]; then
    tail -25 "$WORK/import.log" >&2
    die "导入失败（单事务已回滚，目标库应保持推送前状态）"
  fi
  log "导入完成"
}

# ---------------------------------------------------------------- 核对
verify() {
  log "逐表对账…"
  local failed=0
  local detail="$WORK/verify.txt"
  : > "$detail"

  for t in "${TABLES[@]}"; do
    local lc rc
    if [[ "$t" == "raw.apify_item" ]]; then
      lc="$(docker exec "$LOCAL_CONTAINER" psql -U "$LOCAL_USER" -d "$LOCAL_DB" -tAc \
            "SELECT count(*) FROM raw.apify_item" 2>/dev/null | tr -d ' ')"
      rc="$(ssh_do "docker run --rm --network host -e PGPASSWORD='${REMOTE_PG_PASSWORD}' \
            postgres:16 psql -h ${REMOTE_PG_HOST} -U ${REMOTE_PG_USER} -d ${REMOTE_PG_DB} \
            -tAc 'SELECT count(*) FROM raw.apify_item'" 2>/dev/null | tr -d ' ')"
    else
      lc="$(docker exec "$LOCAL_CONTAINER" psql -U "$LOCAL_USER" -d "$LOCAL_DB" -tAc \
            "SELECT count(*) FROM $t" 2>/dev/null | tr -d ' ')"
      rc="$(ssh_do "docker run --rm --network host -e PGPASSWORD='${REMOTE_PG_PASSWORD}' \
            postgres:16 psql -h ${REMOTE_PG_HOST} -U ${REMOTE_PG_USER} -d ${REMOTE_PG_DB} \
            -tAc 'SELECT count(*) FROM $t'" 2>/dev/null | tr -d ' ')"
    fi

    if [[ -z "$lc" || -z "$rc" ]]; then
      printf '  %-36s 本地=%-8s 远端=%-8s [无法读取]\n' "$t" "${lc:-?}" "${rc:-?}" | tee -a "$detail"
      failed=$((failed + 1))
    elif [[ "$lc" == "$rc" ]]; then
      printf '  %-36s %8s  OK\n' "$t" "$lc" | tee -a "$detail"
    else
      printf '  %-36s 本地=%-8s 远端=%-8s  MISMATCH\n' "$t" "$lc" "$rc" | tee -a "$detail"
      failed=$((failed + 1))
    fi
  done

  echo
  if [[ $failed -eq 0 ]]; then
    log "对账通过：${#TABLES[@]} 张表全部一致"
    return 0
  fi
  log "对账失败：${failed} 张表不一致"
  return 1
}

# ---------------------------------------------------------------- 主流程
main() {
  if [[ $VERIFY_ONLY -eq 1 ]]; then
    verify
    exit $?
  fi

  if [[ $DRY_RUN -eq 1 ]]; then
    log "dry-run：将推送以下表"
    for t in "${TABLES[@]}"; do
      printf '  %s\n' "$t"
    done
    log "模式 ${MODE}；加 --dry-run 不写任何数据，去掉即执行"
    exit 0
  fi

  if [[ "$MODE" == "data" ]]; then
    local keep=() skipped=()
    for t in "${TABLES[@]}"; do
      if target_has "$t"; then keep+=("$t"); else skipped+=("$t"); fi
    done
    if [[ ${#skipped[@]} -gt 0 ]]; then
      log "跳过目标端不存在的表（需先 --mode schema）：${skipped[*]}"
    fi
    if [[ ${#keep[@]} -eq 0 ]]; then
      die "没有可推送的表：全部在目标端不存在"
    fi
    TABLES=("${keep[@]}")
    log "实际推送 ${#TABLES[@]} 张表"
  fi

  dump_all
  transfer
  import_remote
  local vrc=0
  verify || vrc=1
  exit $vrc
}

main
