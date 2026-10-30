#!/usr/bin/env bash
# One command: rebuild report-data.json + report.html + validation-result.json.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RUN_DIR="${1:-$ROOT/voc_pipeline/artifacts/run-20261029}"
OUT_DIR="${2:-$ROOT/tools/insight-report/out/insight-report-run-20261029}"
cd "$ROOT"
exec python3 tools/insight-report/build_report.py --run-dir "$RUN_DIR" --out "$OUT_DIR"
