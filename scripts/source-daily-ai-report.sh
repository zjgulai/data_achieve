#!/usr/bin/env bash
# Source 项目每日 AI 日报（launchd 定时任务入口）
# 由 ~/Library/LaunchAgents/com.source.daily-ai-report.plist 每天 21:07 触发。
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

set -uo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:/usr/bin:/bin:$PATH"

PROJ=/Users/lute/Project/data_scrapy
LOG="$PROJ/tmp/daily-ai-report.log"
TODAY=$(date +%Y%m%d)
DOW=$(date +%u)
case "$DOW" in
  1) W=一 ;; 2) W=二 ;; 3) W=三 ;; 4) W=四 ;;
  5) W=五 ;; 6) W=六 ;; 7) W=日 ;;
  *) W=? ;;
esac
DATE_LABEL="$(date +%Y-%m-%d)（周${W}）"
WORK="$PROJ/tmp/daily-ai-report-$TODAY"
RAW="$WORK/raw.md"
JSON="$WORK/report.json"
MD="$PROJ/reports/Source-项目日报-$TODAY.md"
CONFIG="$HOME/.config/source-daily-report/feishu.json"
COLLECT_ONLY=0
[[ "${1:-}" == "--collect-only" ]] && COLLECT_ONLY=1

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
  echo "### health-$name HTTP=$code"
  head -c 400 "$body" 2>/dev/null
  echo
  echo
}

collect() {
  cd "$PROJ" || return 1
  echo "# 当日原始读数 · $DATE_LABEL"
  echo
  echo "## 仓库"
  echo "分支：$(git rev-parse --abbrev-ref HEAD)"
  echo "HEAD：$(git log -1 --pretty='%h %s')"
  echo "工作区：$(git status --porcelain | wc -l | tr -d ' ') 个改动"
  echo
  echo "## 今日提交"
  git log --since="$TODAY 00:00:00" --until="$TODAY 23:59:59" \
    --pretty=format:'%h %ad %s' --date=format:'%H:%M'
  echo
  echo
  local count first parent
  count=$(git log --since="$TODAY 00:00:00" --until="$TODAY 23:59:59" --pretty=%H | wc -l | tr -d ' ')
  first=$(git log --since="$TODAY 00:00:00" --until="$TODAY 23:59:59" --pretty=%H | tail -1)
  echo "提交数：$count"
  if [[ -n "$first" ]]; then
    parent=$(git rev-parse "$first^" 2>/dev/null || echo "$first")
    echo -n "代码量（$parent..HEAD）："
    git diff --shortstat "$parent" HEAD
  fi
  echo
  echo "## 迁移文件（仓库）"
  ls -1 apps/api/alembic/versions | tail -3
  echo
  echo "## 发布账本最后一条"
  tail -1 docs/ops/releases.jsonl
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
    gh run list --limit 40 --json name,conclusion,createdAt,headSha,displayTitle 2>&1 \
      | python3 -c 'import json,sys
try:
    rows=json.load(sys.stdin)
except Exception as exc:
    print("CI 未查：", exc); raise SystemExit(0)
for r in rows:
    if r.get("createdAt","").startswith(sys.argv[1]) and r.get("name")=="CI":
        print(r["createdAt"][:16], r.get("conclusion"), r.get("headSha","")[:7], r.get("displayTitle","")[:60])
' "$TODAY" 2>&1 | head -30
  else
    echo "CI 未查：gh 不在 PATH"
  fi
  echo
}

prompt_for_model() {
  cat <<EOF
读 $RAW（当日实跑读数），写 $JSON。只写 raw 里有的数字；raw 里 EXIT 非 0、HTTP 非 200、或明确标了未跑的，不准写成通过。

JSON 格式（严格）：
{"date":"$DATE_LABEL","progress":["1. ...","1.1 ..."],"verification":["1. ..."],"todo":["1. ..."]}

写作要求：
- 白话，像发给同事的 IM；动词开头；每条一行一事；板块内 1./1.1 编号。
- 量词给读数，不给形容词；没做就是没做。
- 技术痕迹只留提交号、命令、数字。
- 状态词固定：已完成 / 部分完成 / 未开始 / 进行中 / 已验证 / 未验证 / 失败 / 跳过 / 阻塞 / 未确认。
- 今日进展按提交归纳，带提交号；验证结果逐项列检查与读数；没做完的只写需要人拍板或知情的。
- 不写密钥、凭据、内网地址。
只读 $RAW，只写 $JSON。不要运行其他命令，不要写别的文件。
EOF
}

{
  echo "===== $(date '+%F %T') start collect-only=$COLLECT_ONLY ====="
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
