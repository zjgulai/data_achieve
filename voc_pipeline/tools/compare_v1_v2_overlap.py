#!/usr/bin/env python3
"""Compare v1 and v2 on the records v2 actually covers.

The v2 part files are incomplete (248 of 330 text records) and contain 83
duplicate ids, so a full v2 build is not possible.  This script makes the only
valid comparison: the same canonical records coded by both artifacts under the
published high-confidence gate.  It also records which C13 decisive records are
missing from v2, because that bounds what can be said about the claim.

No gold set is read.  No report or claims artifact is written.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from voc import claims as claims_mod  # noqa: E402
from voc import llm_coder  # noqa: E402
from voc.canonical import CanonicalRecord  # noqa: E402

RUN_DIR = ROOT / "artifacts" / "run-20261029"
OUT = RUN_DIR / "llm-coding-v2" / "overlap-comparison.json"
B05_ID = "c-7658003601176119053"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def code_rows(records: dict[str, CanonicalRecord], rows: dict[str, dict]) -> list:
    return [
        llm_coder.code_record(records[cid], row, min_confidence="high")
        for cid, row in rows.items()
    ]


def coded_stats(coded: list) -> dict:
    aspects = [a for record in coded for a in record.annotations if a.axis == "aspect"]
    return {
        "records": len(coded),
        "experience_records": sum(1 for record in coded if record.in_cohort),
        "experience_full": sum(1 for record in coded if record.experience_scope == "full"),
        "experience_partial": sum(1 for record in coded if record.experience_scope == "partial"),
        "aspects": len(aspects),
        "aspect_records": sum(
            1 for record in coded if any(a.axis == "aspect" for a in record.annotations)
        ),
        "polarity": dict(Counter(a.polarity for a in aspects)),
        "qualified_positive_records": sorted(
            {
                record.canonical_id
                for record in coded
                for a in record.annotations
                if a.axis == "aspect" and a.polarity == "qualified_positive"
            }
        ),
    }


def main() -> int:
    records = {
        row["canonical_id"]: CanonicalRecord(**row)
        for row in read_jsonl(RUN_DIR / "canonical-records.jsonl")
    }
    v1_rows = {
        row["canonical_id"]: row
        for row in read_jsonl(RUN_DIR / "llm-coding" / "coded" / "ALL.jsonl")
    }
    v2_rows = {
        row["canonical_id"]: row
        for row in read_jsonl(RUN_DIR / "llm-coding-v2" / "coded" / "ALL.jsonl")
    }
    covered = set(v2_rows)
    missing = set(v1_rows) - covered
    v1_all = code_rows(records, v1_rows)
    v1_overlap = [record for record in v1_all if record.canonical_id in covered]
    v2_all = code_rows(records, v2_rows)

    def direction(coded: list) -> dict:
        stats = claims_mod.direction_stats(
            list(records.values()),
            coded,
            claims_mod.SUPPORT_CODES,
            "tiktok_shop_verified",
            scope="full",
        )
        keys = (
            "decisive_records",
            "same_direction_records",
            "opposite_direction_records",
            "mixed_records",
            "agreement_pct",
            "excluded_partial_records",
            "excluded_none_records",
            "scope",
        )
        return {key: stats[key] for key in keys}

    def decisive_ids(coded: list) -> set[str]:
        out: set[str] = set()
        for record in coded:
            source = records[record.canonical_id]
            if "tiktok_shop_verified" not in source.frames:
                continue
            if any(
                a.axis == "aspect"
                and a.code in claims_mod.SUPPORT_CODES
                and a.polarity in {"positive", "qualified_positive", "negative", "qualified_negative"}
                for a in record.annotations
            ):
                out.add(record.canonical_id)
        return out

    v1_decisive = decisive_ids(v1_all)
    v2_decisive = decisive_ids(v2_all)

    if B05_ID not in v2_rows:
        b05 = {"covered": False}
    else:
        b05_record = next(r for r in v2_all if r.canonical_id == B05_ID)
        b05 = {
            "covered": True,
            "raw_aspects": v2_rows[B05_ID].get("aspects") or [],
            "high_gate_aspects": [
                {"code": a.code, "polarity": a.polarity, "evidence_span": a.span_text}
                for a in b05_record.annotations
                if a.axis == "aspect"
            ],
            "expected": {"code": "SUP.PRESSURE_OFFLOAD", "polarity": "qualified_positive"},
        }

    v1_claims = json.loads((RUN_DIR / "claims.json").read_text(encoding="utf-8"))
    v1_grades = {claim["claim_id"]: claim["grade"] for claim in v1_claims}

    payload = {
        "schema_version": "voc_v1_v2_overlap_comparison_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "caveat": (
            "v2 covers 248 of 330 text records and has 83 duplicate ids; this is a "
            "same-record overlap comparison, not a full v2 run, and it cannot grade claims."
        ),
        "coverage": {
            "v1_records": len(v1_rows),
            "v2_records": len(v2_rows),
            "text_records_expected": sum(
                1 for row in records.values() if (row.title or "").strip() or (row.text or "").strip()
            ),
            "missing_from_v2": len(missing),
            "missing_by_source": dict(
                Counter(records[cid].source for cid in missing)
            ),
        },
        "high_gate_overlap": {
            "v1_on_overlap": coded_stats(v1_overlap),
            "v2_on_overlap": coded_stats(v2_all),
        },
        "c13": {
            "v1_official": direction(v1_all),
            "v1_on_v2_covered": direction(v1_overlap),
            "v2_on_covered": direction(v2_all),
            "v1_decisive_records": len(v1_decisive),
            "v1_decisive_missing_from_v2": sorted(v1_decisive & missing),
            "v2_decisive_records": len(v2_decisive),
            "v2_newly_decisive_vs_v1": sorted(v2_decisive - v1_decisive),
            "v2_no_longer_decisive_vs_v1": sorted(v1_decisive - v2_decisive),
        },
        "c04_c05_dependencies": {
            "c-1sn9hb1": "c-1sn9hb1" in covered,
            "c-1opsx7o": "c-1opsx7o" in covered,
            "c-1q2ir63": "c-1q2ir63" in covered,
        },
        "b05": b05,
        "claim_grades": {
            "v1": v1_claims and {claim["claim_id"]: claim["grade"] for claim in v1_claims},
            "v2": None,
            "v2_reason": "v2 artifact is incomplete (82 records missing) and internally conflicted (43 coding conflicts)",
        },
        "v1_grade_distribution": dict(Counter(v1_grades.values())),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
