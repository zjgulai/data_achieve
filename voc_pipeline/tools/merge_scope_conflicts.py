#!/usr/bin/env python3
"""Merge the per-run scope audits into one comparison artifact.

Each build writes ``scope-audit.json`` into its own run directory (E-merge
schema v2).  The published v1 path is the one reviewers read, so this script
keeps the v1 payload at the top level and nests the v2 payload under
``comparison``.  No count is recomputed: the merge is a pure read of the two
build artifacts.

The old ``scope-conflicts.json`` schema is retired; it measured a
product_match/scope disagreement the merged model cannot express.

Run from the repository root:

    python3 tools/merge_scope_conflicts.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_V1 = ROOT / "artifacts" / "run-20261029" / "scope-audit.json"
DEFAULT_V2 = ROOT / "artifacts" / "run-20261029-v2" / "scope-audit.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v1", default=str(DEFAULT_V1))
    parser.add_argument("--v2", default=str(DEFAULT_V2))
    parser.add_argument("--out", default=str(DEFAULT_V1))
    args = parser.parse_args()

    v1 = json.loads(Path(args.v1).read_text(encoding="utf-8"))
    v2 = json.loads(Path(args.v2).read_text(encoding="utf-8"))
    combined = dict(v1)
    combined["comparison"] = {"llm-v2": v2}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(combined, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "out": str(out),
                "v1": {
                    "in_experience_cohort": v1.get("in_experience_cohort"),
                    "off_target_evaluations": len(v1.get("off_target_evaluations", [])),
                    "admit_candidates": len(v1.get("admit_candidates", [])),
                    "downgrades": len(v1.get("downgrades", [])),
                },
                "v2": {
                    "in_experience_cohort": v2.get("in_experience_cohort"),
                    "off_target_evaluations": len(v2.get("off_target_evaluations", [])),
                    "admit_candidates": len(v2.get("admit_candidates", [])),
                    "downgrades": len(v2.get("downgrades", [])),
                },
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
