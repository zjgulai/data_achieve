#!/usr/bin/env bash
# Rebuild the run artifacts, the report, the method spec, and run validators.
set -euo pipefail
cd "$(dirname "$0")"
RUN="${1:-run-20261029}"
python3 -m voc.cli spec --out spec
python3 -m voc.cli build --run "$RUN"
python3 tools/check_support_exclusivity.py \
  --canonical "artifacts/$RUN/canonical-records.jsonl" \
  --coded "artifacts/$RUN/llm-coding/coded/ALL.jsonl" \
  --json-out "artifacts/$RUN/llm-coding/support-exclusivity-check.json"
python3 -m voc.cli validate --run "$RUN"
python3 -m unittest discover -s tests
