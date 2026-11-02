#!/usr/bin/env bash
# Deterministic test for scripts/check_daily_report_health.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$ROOT/scripts/check_daily_report_health.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
DATE=20260101
OUT="$TMP/reports/achievements-$DATE"
MD="$OUT/Source-项目成果总结-$DATE.md"
HTML="$OUT/Source-项目成果总结-$DATE.html"
LOG="$TMP/tmp/daily-report.log"

mkdir -p "$OUT" "$TMP/tmp"
printf 'report\n' >"$MD"
printf '<html></html>\n' >"$HTML"
printf 'RUN_STATUS=success md_bytes=7 html_bytes=14\n' >"$LOG"

git -C "$TMP" init -q
git -C "$TMP" config user.email test@example.com
git -C "$TMP" config user.name Test
git -C "$TMP" commit --allow-empty -q -m "docs(report): Source 项目成果总结 $DATE"

run() {
  DAILY_REPORT_PROJ="$TMP" bash "$SCRIPT" --date "$DATE"
}

echo "case 1: healthy report"
out="$(run)"
grep -q "RESULT  PASS" <<<"$out" || { echo "FAIL: expected PASS"; echo "$out"; exit 1; }

echo "case 2: missing html"
rm "$HTML"
set +e
out="$(run)"
code=$?
set -e
[[ "$code" == "1" ]] || { echo "FAIL: missing html should exit 1, got $code"; echo "$out"; exit 1; }
grep -q "html missing or empty" <<<"$out" || { echo "FAIL: expected html failure"; echo "$out"; exit 1; }

echo "case 3: known_gap"
printf 'missing\n' >"$OUT/MISSING.md"
out="$(run)"
grep -q "RESULT  KNOWN_GAP" <<<"$out" || { echo "FAIL: expected KNOWN_GAP"; echo "$out"; exit 1; }
rm "$OUT/MISSING.md"
printf '<html></html>\n' >"$HTML"

echo "case 4: missing RUN_STATUS"
printf 'no status here\n' >"$LOG"
set +e
out="$(run)"
code=$?
set -e
[[ "$code" == "1" ]] || { echo "FAIL: missing RUN_STATUS should exit 1, got $code"; echo "$out"; exit 1; }
printf 'RUN_STATUS=success\n' >"$LOG"

echo "case 5: duplicate report file"
mkdir -p "$TMP/reports/duplicate"
cp "$MD" "$TMP/reports/duplicate/Source-项目成果总结-$DATE.md"
set +e
out="$(run)"
code=$?
set -e
[[ "$code" == "1" ]] || { echo "FAIL: duplicate report should exit 1, got $code"; echo "$out"; exit 1; }
grep -q "report files for" <<<"$out" || { echo "FAIL: expected duplicate warning"; echo "$out"; exit 1; }

echo "daily report health test OK"