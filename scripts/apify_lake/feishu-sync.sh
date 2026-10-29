#!/usr/bin/env bash
# ABI 存量同步：把数据库真实行数刷进飞书「ABI数据资产汇总表 → 存量汇总」。
#
# 为什么用独立 launchd 任务而不是塞进 abi-ingest：
# 这个任务的职责是「报告数据库现在有多少数据」。即使某天摄取失败，
# 它也应当反映真实状态。挂在摄取循环里会被上游失败连累。
#
# 环境：launchd 不读交互式 shell 的 profile，配置全部从 600 权限的 env 文件读。
set -uo pipefail

ENV_FILE="${HOME}/.config/apify-lake/feishu-sync.env"
REPO="/Users/lute/Project/data_scrapy"
PYTHON="${REPO}/apps/api/.venv/bin/python"
SCRIPT="${REPO}/scripts/apify_lake/sync_feishu_counts.py"
LOG_DIR="${HOME}/Library/Logs"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { printf '%s %s\n' "$(ts)" "$*"; }

if [[ ! -f "$ENV_FILE" ]]; then
  log "[FATAL] 缺少配置文件 $ENV_FILE"
  exit 78
fi

# shellcheck disable=SC1090
set -a
source "$ENV_FILE"
set +a

for var in ABI_DSN ABI_BASE_TOKEN ABI_SUMMARY_TABLE_ID; do
  if [[ -z "${!var:-}" ]]; then
    log "[FATAL] $var 未设置（检查 $ENV_FILE）"
    exit 78
  fi
done

if [[ ! -x "$PYTHON" ]]; then
  log "[FATAL] 解释器不存在: $PYTHON"
  exit 78
fi

# launchd 的 PATH 很短；lark-cli 装在 /opt/homebrew/bin
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

log "开始同步存量"

# 先 dry-run 判断有无差异。无差异就跳过写入，避免每分钟都打飞书接口。
dry_out="$("$PYTHON" "$SCRIPT" \
  --dsn "$ABI_DSN" \
  --base-token "$ABI_BASE_TOKEN" \
  --table-id "$ABI_SUMMARY_TABLE_ID" \
  --dry-run 2>&1)"
dry_rc=$?

if [[ $dry_rc -ne 0 ]]; then
  log "[ERROR] dry-run 失败 rc=$dry_rc"
  printf '%s\n' "$dry_out" | tail -20
  exit 1
fi

pending="$(printf '%s\n' "$dry_out" | sed -n 's/^待更新 \([0-9]\+\) 条.*/\1/p' | head -1)"
pending="${pending:-0}"

if [[ "$pending" == "0" ]]; then
  log "无变化，跳过写入"
  exit 0
fi

log "检测到 $pending 条变化，开始写入"
exec_out="$("$PYTHON" "$SCRIPT" \
  --dsn "$ABI_DSN" \
  --base-token "$ABI_BASE_TOKEN" \
  --table-id "$ABI_SUMMARY_TABLE_ID" \
  --execute 2>&1)"
exec_rc=$?

printf '%s\n' "$exec_out" | tail -30

if [[ $exec_rc -ne 0 ]]; then
  log "[ERROR] 写入失败 rc=$exec_rc"
  exit 1
fi

log "同步完成"
