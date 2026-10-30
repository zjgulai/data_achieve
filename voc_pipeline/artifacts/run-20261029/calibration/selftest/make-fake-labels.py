#!/usr/bin/env python3
"""Create a deliberately-wrong "human" file for self-testing only.

This is NOT a real annotation.  It starts from the LLM high-confidence labels
and removes every third aspect (33.3% presence disagreement), then flips the
polarity of every fourth kept aspect.  The resulting file exercises the
presence kappa, the polarity table and the top-5 disagreement section.

Usage:
    python3 selftest/make-fake-labels.py
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CALIBRATION = HERE.parent
SAMPLE = CALIBRATION / "blind-sample.jsonl"
MAPPING = CALIBRATION / "mapping.json"
CODED = CALIBRATION.parent / "llm-coding" / "coded" / "ALL.jsonl"
OUT = HERE / "fake-human-labels.json"

FLIP = {
    "positive": "negative",
    "negative": "positive",
    "qualified_negative": "positive",
    "mixed": "positive",
    "unknown": "negative",
}


def load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def main() -> int:
    sample = load_jsonl(SAMPLE)
    mapping = {row["item_id"]: row for row in json.loads(MAPPING.read_text(encoding="utf-8"))["items"]}
    coded = {row["canonical_id"]: row for row in load_jsonl(CODED)}

    items = []
    total_aspects = 0
    kept_aspects = 0
    dropped_aspects = 0
    flipped_polarities = 0
    aspect_counter = 0
    kept_counter = 0

    for item in sample:
        canonical_id = mapping[item["item_id"]]["canonical_id"]
        row = coded[canonical_id]
        high = [a for a in row["aspects"] if a.get("confidence") == "high"]
        total_aspects += len(high)
        human_aspects = []
        for aspect in high:
            aspect_counter += 1
            if aspect_counter % 3 == 0:
                dropped_aspects += 1
                continue
            kept_aspects += 1
            kept_counter += 1
            polarity = aspect["polarity"]
            if kept_counter % 4 == 0:
                polarity = FLIP.get(polarity, polarity)
                flipped_polarities += 1
            human_aspects.append(
                {
                    "code": aspect["code"],
                    "polarity": polarity,
                    "evidence": aspect.get("evidence_span", ""),
                }
            )
        items.append(
            {
                "item_id": item["item_id"],
                "is_product_experience": bool(row.get("is_product_experience")),
                "experience_reason": None,
                "aspects": human_aspects,
            }
        )

    payload = {
        "schema": "voc-human-labels-v1",
        "sample_id": json.loads(MAPPING.read_text(encoding="utf-8"))["sample_id"],
        "exported_at": "2026-10-30T00:00:00+00:00",
        "annotator": "FAKE-SELFTEST (not a real annotator)",
        "note": "Self-test fixture. Do not use as real human annotations.",
        "items": items,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    print(f"wrote {OUT}")
    print(f"LLM high aspects: {total_aspects}")
    print(f"kept: {kept_aspects}; dropped (presence disagreement): {dropped_aspects} "
          f"({100.0 * dropped_aspects / total_aspects:.1f}%)")
    print(f"polarity flips among kept: {flipped_polarities}")
    print(f"presence disagreement fraction (dropped / union): "
          f"{100.0 * dropped_aspects / total_aspects:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
