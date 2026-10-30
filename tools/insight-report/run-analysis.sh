#!/usr/bin/env bash
# One command for the analysis pipeline in this directory.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
RUN_DIR="${1:-$REPO/voc_pipeline/artifacts/run-20261029}"
OUT_DIR="${2:-$HERE/out/insight-report-run-20261029}"
cd "$REPO"
exec python3 "$HERE/build_report.py" --run-dir "$RUN_DIR" --out "$OUT_DIR"
