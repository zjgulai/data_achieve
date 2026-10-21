#!/usr/bin/env bash
# 安装生产 A 健康巡检 cron。重复执行安全。
set -euo pipefail

MARKER="# SP-43 scrapy-health-check"
COMMAND="cd /opt/data-achieve-scrapy/app && docker exec data_achieve_scrapy_api python -m data_intelligence_hub.maintenance.prod_health_check >> /var/log/scrapy-health.log 2>&1"
CRON_LINE="*/10 * * * * ${COMMAND}"
LOG_FILE="/var/log/scrapy-health.log"

if ! command -v crontab >/dev/null 2>&1; then
  echo "未找到 crontab 命令，无法安装定时任务。" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "警告：未找到 docker 命令。cron 条目仍会写入，但运行时需要 docker。" >&2
fi

current="$(mktemp)"
trap 'rm -f "$current"' EXIT
# 当前用户没有 crontab 时，crontab -l 返回非零。这是正常情况。
crontab -l >"$current" 2>/dev/null || true

if grep -Fq "$COMMAND" "$current"; then
  echo "健康巡检 cron 已存在，未改动。"
  exit 0
fi

{
  printf '%s\n' "$MARKER"
  printf '%s\n' "$CRON_LINE"
} >>"$current"

crontab "$current"

if [[ ! -e "$LOG_FILE" ]]; then
  touch "$LOG_FILE" 2>/dev/null || \
    echo "提示：无法创建 ${LOG_FILE}。请确认 cron 用户对该路径有写权限。" >&2
fi

echo "已安装健康巡检 cron："
echo "  $CRON_LINE"
echo "日志：$LOG_FILE"
