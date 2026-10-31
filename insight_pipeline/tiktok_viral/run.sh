#!/usr/bin/env bash
# Rebuild the TikTok viral analysis artifacts and the report bundle.
set -euo pipefail
cd "$(dirname "$0")"

# Stable ordering for Counter ties in saturation_analysis.py.
export PYTHONHASHSEED=0

python3 -B final_analysis.py
python3 -B render_md.py
python3 -B build_replicability.py
python3 -B saturation_analysis.py
python3 -B tools/gen_json.py
python3 -B gen_charts.py
python3 -B verify.py

echo "pipeline OK"
