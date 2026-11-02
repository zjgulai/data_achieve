#!/usr/bin/env bash
#
# Health check for the daily Source report.
#
# Why this exists: on 2026-11-01 the launchd job created an empty directory and
# wrote nothing to the log. Nobody noticed until the next day. The report script
# now writes RUN_STATUS and commits its own output; this check verifies both.
#
# It is safe to run at any time. It never generates or edits a report.
#
# Usage:
#   bash scripts/check_daily_report_health.sh
#   bash scripts/check_daily_report_health.sh --date 20261101
#   DAILY_REPORT_PROJ=/tmp/fixture bash scripts/check_daily_report_health.sh --date 20260101
#
# Exit codes: 0 healthy or known_gap, 1 unhealthy, 2 usage error.
#
set -uo pipefail

PROJ="${DAILY_REPORT_PROJ:-/Users/lute/Project/data_scrapy}"
DATE="$(date +%Y%m%d)"
FAIL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --date) DATE="${2:-}"; shift 2 ;;
    --proj) PROJ="${2:-}"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

[[ "$DATE" =~ ^[0-9]{8}$ ]] || { echo "--date must be YYYYMMDD" >&2; exit 2; }

OUTDIR="$PROJ/reports/achievements-$DATE"
MD="$OUTDIR/Source-项目成果总结-$DATE.md"
HTML="$OUTDIR/Source-项目成果总结-$DATE.html"
MISSING="$OUTDIR/MISSING.md"
LOG="$PROJ/tmp/daily-report.log"

pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; FAIL=1; }
warn() { printf 'WARN  %s\n' "$1"; }

echo "date=$DATE proj=$PROJ"

if [[ -f "$MISSING" ]]; then
  pass "known_gap: $MISSING exists"
  echo "RESULT  KNOWN_GAP"
  exit 0
fi

if [[ -s "$MD" ]]; then
  pass "markdown exists and is non-empty"
else
  fail "markdown missing or empty: $MD"
fi

if [[ -s "$HTML" ]]; then
  pass "html exists and is non-empty"
else
  fail "html missing or empty: $HTML"
fi

if [[ -f "$LOG" ]]; then
  STATUS_LINE="$(grep '^RUN_STATUS=' "$LOG" | tail -1 || true)"
  if [[ "$STATUS_LINE" == "RUN_STATUS=success"* ]]; then
    pass "last RUN_STATUS is success"
  else
    fail "last RUN_STATUS is not success: ${STATUS_LINE:-missing}"
  fi
else
  fail "log missing: $LOG"
fi

SUBJECT="$(git -C "$PROJ" log -1 --format=%s 2>/dev/null || true)"
if [[ "$SUBJECT" == "docs(report): Source 项目成果总结 $DATE"* ]]; then
  pass "latest commit is the report commit"
else
  fail "latest commit does not match the report: ${SUBJECT:-no commit}"
fi

DUPES="$(find "$PROJ/reports" -name "Source-项目成果总结-$DATE.md" 2>/dev/null | wc -l | tr -d ' ')"
if [[ "$DUPES" -le 1 ]]; then
  pass "single report file for $DATE"
else
  fail "$DUPES report files for $DATE; keep one canonical copy"
fi

echo
if [[ "$FAIL" == "0" ]]; then
  echo "RESULT  PASS"
  exit 0
fi
echo "RESULT  FAIL"
exit 1