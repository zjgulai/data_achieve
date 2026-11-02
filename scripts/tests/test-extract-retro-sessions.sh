#!/usr/bin/env bash
# Deterministic test for scripts/extract_retro_sessions.py.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$ROOT/scripts/extract_retro_sessions.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/transcripts"
cat >"$TMP/transcripts/abcd1234-0000-0000-0000-000000000000.jsonl" <<'JSONL'
{"type":"user","timestamp":"2026-10-31T10:00:00Z","message":{"content":"目标：复盘本周。token=apify_api_abcdefghijklmnopqrstuvwxyz"}}
{"type":"user","timestamp":"2026-10-31T10:01:00Z","message":{"content":[{"type":"tool_result","content":"should be skipped"}]}}
{"type":"user","timestamp":"2026-10-31T10:02:00Z","message":{"content":[{"type":"text","text":"继续，先提交"}]}}
{"type":"assistant","timestamp":"2026-10-31T10:03:00Z","message":{"content":"not a user turn"}}
JSONL

python3 "$SCRIPT" \
  --since 2026-10-01 \
  --transcripts "$TMP/transcripts" \
  --out "$TMP/out" >/dev/null

[[ -f "$TMP/out/INDEX.md" ]] || { echo "FAIL: INDEX.md missing"; exit 1; }
SESSION="$TMP/out/session-abcd1234.md"
[[ -f "$SESSION" ]] || { echo "FAIL: session file missing"; exit 1; }

grep -q "<redacted>" "$SESSION" || {
  echo "FAIL: token was not redacted"
  cat "$SESSION"
  exit 1
}
grep -q "token=" "$SESSION" || {
  echo "FAIL: redaction removed the key name as well"
  cat "$SESSION"
  exit 1
}
if grep -q "apify_api_abcdefghijklmnopqrstuvwxyz" "$SESSION"; then
  echo "FAIL: raw token leaked"
  exit 1
fi
if grep -q "should be skipped" "$SESSION"; then
  echo "FAIL: tool_result leaked into user turns"
  exit 1
fi
grep -q "继续，先提交" "$SESSION" || { echo "FAIL: real user turn missing"; exit 1; }

# The editor layer can transiently pad st_size by one page. Assert it did not.
python3 - "$SESSION" <<'PY'
import os
import sys
path = sys.argv[1]
size = os.stat(path).st_size
data = open(path, "rb").read()
if size != len(data) or b"\x00" in data:
    raise SystemExit(f"FAIL: file integrity size={size} read={len(data)}")
PY

echo "extract retro sessions test OK"