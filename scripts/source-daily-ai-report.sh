#!/usr/bin/env bash
# Main 每日 AI 日报（飞书 + 仓内 md，04:00）
# 由 ~/Library/LaunchAgents/com.source.main-daily-ai-report.plist 每天 04:00 触发。
# 04:00 跑的是前一天：报告日期取「昨天」，与文件名、飞书标题一致。
# 日志：/Users/lute/Project/data_scrapy/tmp/daily-ai-report.log
#
# 分工：
#   1. 本脚本跑确定性的收数命令（git/测试/探活/进程），写 raw.md。
#   2. headless claude 只读 raw.md、写 report.json，不跑命令。
#   3. 本脚本校验 JSON，跑 tools/lark_daily_report.py 双落点（md + 飞书），
#      检查 md 填充，最后提交 md。
#
# 用法：
#   bash scripts/source-daily-ai-report.sh            # 正常跑
#   bash scripts/source-daily-ai-report.sh --collect-only  # 只收数，不调模型、不写飞书
#   bash scripts/source-daily-ai-report.sh --report-date 20261105  # 指定报告日期（手动补跑）

set -uo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:/usr/bin:/bin:$PATH"

PROJ=/Users/lute/Project/data_scrapy
LOG="$PROJ/tmp/daily-ai-report.log"
COLLECT_ONLY=0
REPORT_DATE_OVERRIDE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --collect-only) COLLECT_ONLY=1; shift ;;
    --report-date) REPORT_DATE_OVERRIDE="${2:-}"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

RUN_DATE=$(date +%Y%m%d)
HOUR=$(date +%H)
if [[ -n "$REPORT_DATE_OVERRIDE" ]]; then
  TODAY="$REPORT_DATE_OVERRIDE"
elif (( 10#$HOUR < 6 )); then
  TODAY=$(date -v-1d +%Y%m%d)
else
  TODAY="$RUN_DATE"
fi
[[ "$TODAY" =~ ^[0-9]{8}$ ]] || { echo "--report-date 必须是 YYYYMMDD" >&2; exit 2; }
DOW=$(date -j -f "%Y%m%d" "$TODAY" "+%u")
case "$DOW" in
  1) W=一 ;; 2) W=二 ;; 3) W=三 ;; 4) W=四 ;;
  5) W=五 ;; 6) W=六 ;; 7) W=日 ;;
  *) W=? ;;
esac
DATE_LABEL="$(date -j -f "%Y%m%d" "$TODAY" "+%Y-%m-%d")（周${W}）"
READ_AT=$(date '+%F %T %Z')
WORK="$PROJ/tmp/daily-ai-report-$TODAY"
RAW="$WORK/raw.md"
JSON="$WORK/report.json"
MD="$PROJ/reports/Source-项目日报-$TODAY.md"
CONFIG="$HOME/.config/source-daily-report/feishu.json"

mkdir -p "$PROJ/tmp" "$WORK" "$PROJ/reports"

run_step() {
  local name=$1
  shift
  local out="$WORK/$name.log"
  "$@" > "$out" 2>&1
  local rc=$?
  echo "### $name EXIT=$rc"
  tail -6 "$out" | sed -E $'s/\x1b\\[[0-9;]*m//g'
  echo
}

probe() {
  local name=$1
  local url=$2
  local body="$WORK/health-$name.json"
  local code
  code=$(curl -sS -m 15 -o "$body" -w '%{http_code}' "$url" 2> "$WORK/health-$name.err")
  echo "### health-$name HTTP=$code as_of=${READ_AT}（运行时刻，不是报告日收盘）"
  head -c 400 "$body" 2>/dev/null
  echo
  echo
}

collect() {
  cd "$PROJ" || return 1
  echo "# 当日原始读数 · $DATE_LABEL"
  echo "读数时间：${READ_AT}（探活、进程、仓库 HEAD 都是这一刻的状态，不是报告日收盘值）"
  echo
  echo "## 仓库"
  echo "分支：$(git rev-parse --abbrev-ref HEAD)"
  echo "运行时刻 HEAD：$(git log -1 --pretty='%h %s')"
  echo "工作区：$(git status --porcelain | wc -l | tr -d ' ') 个改动"
  echo
  echo "## 今日提交"
  git log --since="$TODAY 00:00:00" --until="$TODAY 23:59:59" \
    --pretty=format:'%h %ad %s' --date=format:'%H:%M'
  echo
  echo
  local count first last parent
  count=$(git log --since="$TODAY 00:00:00" --until="$TODAY 23:59:59" --pretty=format:%H | grep -c .)
  first=$(git log --since="$TODAY 00:00:00" --until="$TODAY 23:59:59" --pretty=format:%H | tail -1)
  last=$(git log --since="$TODAY 00:00:00" --until="$TODAY 23:59:59" --pretty=format:%H | head -1)
  echo "提交数：${count}（原样抄这一行，不要自己数）"
  if [[ -n "$first" ]]; then
    parent=$(git rev-parse "$first^" 2>/dev/null || echo "$first")
    echo "报告日最后一条：$(git log -1 --pretty='%h %s' "$last")"
    echo -n "代码量（${parent}..${last}，原样抄这一行）："
    git diff --shortstat "$parent" "$last"
  fi
  echo
  echo "## 迁移文件（仓库）"
  ls -1 apps/api/alembic/versions | tail -3
  echo
  echo "## 发布账本最后一条（按报告日，UTC 转 Asia/Shanghai）"
  python3 - "$PROJ/docs/ops/releases.jsonl" "$TODAY" <<'PY'
import json
import sys
from datetime import datetime, timedelta, timezone

path, target = sys.argv[1], sys.argv[2]
cst = timezone(timedelta(hours=8))
last = None
for line in open(path, encoding="utf-8"):
    line = line.strip()
    if not line:
        continue
    obj = json.loads(line)
    ts = datetime.fromisoformat(obj["recorded_at"]).astimezone(cst)
    if ts.strftime("%Y%m%d") <= target:
        last = obj
print(json.dumps(last, ensure_ascii=False) if last else "无（报告日及以前没有发布记录）")
PY
  echo
  echo
  echo "## 本地测试"
  run_step api-unit bash -c "cd '$PROJ/apps/api' && uv run pytest tests/unit -q"
  run_step api-ruff bash -c "cd '$PROJ/apps/api' && uv run ruff check ."
  run_step console-unit bash -c "cd '$PROJ' && pnpm -C apps/scraper-console test"
  run_step web-unit bash -c "cd '$PROJ' && pnpm -C apps/web test"
  echo "## 生产探活"
  probe a https://scrapy.luteos.com/api/health
  probe b https://scrapy.lute-tlz-dddd.top/api/health
  echo "## 本机进程 / 容器"
  echo "### docker"
  docker ps --format '{{.Names}} {{.Status}}' 2>&1 | head -10
  echo
  echo "### ps"
  ps aux | grep -E "abi-ingest|uvicorn|celery" | grep -v grep | head -10
  echo
  echo "## CI（gh 可用时）"
  if command -v gh >/dev/null 2>&1; then
    gh run list --limit 200 --json name,conclusion,createdAt,headSha,displayTitle 2>&1 \
      | python3 -c 'import json,sys
from datetime import datetime,timedelta,timezone
try:
    rows=json.load(sys.stdin)
except Exception as exc:
    print("CI 未查：", exc); raise SystemExit(0)
cst=timezone(timedelta(hours=8))
for r in rows:
    ts=datetime.fromisoformat(r["createdAt"].replace("Z","+00:00")).astimezone(cst)
    if ts.strftime("%Y%m%d")==sys.argv[1] and r.get("name")=="CI":
        print(ts.strftime("%Y-%m-%d %H:%M CST"), r.get("conclusion"), r.get("headSha","")[:7], r.get("displayTitle","")[:60])
' "$TODAY" 2>&1 | head -30
  else
    echo "CI 未查：gh 不在 PATH"
  fi
  echo
}

prompt_for_model() {
  cat <<EOF
读 ${RAW}（当日实跑读数），写 ${JSON}。只写 raw 里有的数字；raw 里 EXIT 非 0、HTTP 非 200、或明确标了未跑的，不准写成通过。

口径约束：
- 「提交数」「代码量（…）」两行原样抄，不要自己数，也不要用运行时刻 HEAD 另算。
- 「今日进展」只写 raw「今日提交」列表里的提交；运行时刻 HEAD 不在列表里就不要写进今日进展。
- 探活、进程、仓库 HEAD 都是「读数时间」那一刻的状态，不是报告日收盘值；写进验证结果时必须注明读数时间。
- 发布账本只抄 raw 的「发布账本最后一条」，不要另行推断。

JSON 格式（严格）：
{"date":"$DATE_LABEL","progress":["1. ...","1.1 ..."],"verification":["1. ..."],"todo":["1. ..."]}

写作要求：
- 白话，像发给同事的 IM；动词开头；每条一行一事；板块内 1./1.1 编号。
- 量词给读数，不给形容词；没做就是没做。
- 技术痕迹只留提交号、命令、数字。
- 状态词固定：已完成 / 部分完成 / 未开始 / 进行中 / 已验证 / 未验证 / 失败 / 跳过 / 阻塞 / 未确认。
- 今日进展按提交归纳，带提交号；验证结果逐项列检查与读数；没做完的只写需要人拍板或知情的。
- 不写密钥、凭据、内网地址。
只读 ${RAW}，只写 ${JSON}。不要运行其他命令，不要写别的文件。
EOF
}

{
  echo "===== $(date '+%F %T') start run=$RUN_DATE report=$TODAY collect-only=$COLLECT_ONLY ====="
  collect > "$RAW" 2>&1
  echo "RAW $RAW $(stat -f%z "$RAW" 2>/dev/null || echo 0) bytes"

  if [[ "$COLLECT_ONLY" == "1" ]]; then
    echo "COLLECT_ONLY done"
    echo "===== $(date '+%F %T') end ====="
    exit 0
  fi

  STATUS=success
  PROMPT=$(prompt_for_model)
  claude -p "$PROMPT" --add-dir "$PROJ" --permission-mode acceptEdits 2>&1 \
    || { STATUS=model_failed; echo "MODEL_EXIT=$?"; }

  if [[ ! -s "$JSON" ]]; then
    STATUS=json_missing
  elif ! python3 "$PROJ/tools/lark_daily_report.py" --file "$JSON" --md "$MD" > "$WORK/dryrun.log" 2>&1; then
    STATUS=json_invalid
    tail -20 "$WORK/dryrun.log"
  else
    python3 "$PROJ/tools/lark_daily_report.py" --file "$JSON" --md "$MD" --apply > "$WORK/apply.log" 2>&1 \
      || STATUS=feishu_failed
    tail -5 "$WORK/apply.log"
  fi

  if [[ -s "$MD" ]]; then
    if ! python3 "$PROJ/tools/lark_daily_report.py" --md "$MD" --check-md >> "$WORK/apply.log" 2>&1; then
      python3 "$PROJ/tools/lark_daily_report.py" --md "$MD" --fix >> "$WORK/apply.log" 2>&1 \
        && python3 "$PROJ/tools/lark_daily_report.py" --md "$MD" --check-md >> "$WORK/apply.log" 2>&1 \
        || STATUS=md_broken
    fi
  else
    STATUS=md_missing
  fi

  if [[ "$STATUS" == "success" ]]; then
    if git -C "$PROJ" add -f "$MD"; then
      if git -C "$PROJ" diff --cached --quiet; then
        echo "GIT_COMMIT skipped: nothing staged"
      elif git -C "$PROJ" commit -m "docs(report): Source 项目日报 $TODAY"; then
        echo "GIT_COMMIT ok"
      else
        STATUS=commit_failed
      fi
    else
      STATUS=commit_failed
    fi
  fi

  echo "RUN_STATUS=$STATUS md_bytes=$(stat -f%z "$MD" 2>/dev/null || echo 0) json_bytes=$(stat -f%z "$JSON" 2>/dev/null || echo 0)"
  echo "===== $(date '+%F %T') end ====="
  echo
  [[ "$STATUS" == "success" ]] || exit 1
} >> "$LOG" 2>&1
