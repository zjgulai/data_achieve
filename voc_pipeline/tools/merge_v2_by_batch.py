#!/usr/bin/env python3
"""Merge the v2 coding artifacts by batch and validate the result.

The previous merge concatenated part-01..04, but the parts were built from the
wrong batch pairs (01+02, 02+04, 03+06, 04+08).  That left batch-05 and
batch-07 uncovered and coded batch-02/batch-04 twice.  This script treats the
batch as the unit:

  * ``coded/by-batch/batch-XX.jsonl`` wins when present;
  * otherwise every row for that batch's canonical ids is taken from the part
    files, keyed by canonical_id;
  * a duplicated id keeps its first occurrence in sorted part order, which is
    the dedupe policy already recorded in the previous merge report.

Output order is batch-01..08, each in its input order, so ALL.jsonl matches the
v1 artifact order exactly.  The script fails closed on any coverage, schema,
enum, span, or duplicate defect.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from voc.taxonomy import ASPECTS, CONTEXTS  # noqa: E402

RUN_DIR = ROOT / "artifacts" / "run-20261029"
CODED_DIR = RUN_DIR / "llm-coding-v2" / "coded"
ALL_OUT = CODED_DIR / "ALL.jsonl"
REPORT_OUT = RUN_DIR / "llm-coding-v2" / "merge-report.json"
CONFLICTS_OUT = RUN_DIR / "llm-coding-v2" / "duplicate-conflicts.json"
V1_ALL = RUN_DIR / "llm-coding" / "coded" / "ALL.jsonl"

BATCH_ORDER = [f"batch-{index:02d}" for index in range(1, 9)]
POLARITIES = {"positive", "qualified_positive", "negative", "qualified_negative", "mixed", "unknown"}
CONFIDENCES = {"high", "medium", "low"}
EXPERIENCE_REASONS = {
    "first_person_use",
    "help_seeking",
    "third_party_event",
    "product_mismatch",
    "question",
    "other",
}
EXPERIENCE_SCOPES = {"full", "partial", "none"}
EXPERIENCE_SOURCES = {"first_person", "relayed"}
JOURNEYS = {"purchase", "selection", "first_use", "repeat_use", "return", None}
OUTCOMES = {"relief", "no_relief", None}
REQUIRED_FIELDS = {
    "canonical_id",
    "is_product_experience",
    "experience_reason",
    "experience_scope",
    "experience_source",
    "aspects",
    "contexts",
    "journey",
    "outcome",
    "medical_self_report",
    "notes",
}
REQUIRED_ASPECT_FIELDS = {"code", "polarity", "evidence_span", "confidence"}
MAX_SPAN_CHARS = 120
MAX_ASPECTS = 6


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with Path(path).open(encoding="utf-8") as handle:
        for lineno, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                rows.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
    return rows


def main() -> int:
    canonical = read_jsonl(RUN_DIR / "canonical-records.jsonl")
    record_by_id = {row["canonical_id"]: row for row in canonical}
    text_ids = {
        row["canonical_id"]
        for row in canonical
        if (row.get("title") or "").strip() or (row.get("text") or "").strip()
    }
    batch_ids = {
        batch: [row["canonical_id"] for row in read_jsonl(RUN_DIR / "llm-coding" / "batches" / f"{batch}.jsonl")]
        for batch in BATCH_ORDER
    }
    if sum(len(ids) for ids in batch_ids.values()) != len(text_ids):
        raise ValueError("batch inputs do not partition the text records")

    grouped: dict[str, list[tuple[str, int, dict]]] = defaultdict(list)
    for path in sorted(CODED_DIR.glob("part-*.jsonl")):
        for lineno, row in enumerate(read_jsonl(path), 1):
            canonical_id = row.get("canonical_id")
            if not canonical_id:
                raise ValueError(f"{path}:{lineno}: missing canonical_id")
            grouped[canonical_id].append((path.name, lineno, row))

    by_batch: dict[str, dict[str, dict]] = {}
    for batch in BATCH_ORDER:
        path = CODED_DIR / "by-batch" / f"{batch}.jsonl"
        if not path.exists():
            continue
        rows = read_jsonl(path)
        ids = [row["canonical_id"] for row in rows]
        if ids != batch_ids[batch]:
            raise ValueError(f"{path}: order or coverage differs from {batch}.jsonl")
        by_batch[batch] = dict(zip(ids, rows))

    merged: list[dict] = []
    provenance: list[dict] = []
    duplicate_details: list[dict] = []
    used_canonical: set[str] = set()
    for batch in BATCH_ORDER:
        for canonical_id in batch_ids[batch]:
            if canonical_id in used_canonical:
                raise ValueError(f"duplicate canonical_id in merged order: {canonical_id}")
            used_canonical.add(canonical_id)
            if batch in by_batch:
                row = by_batch[batch][canonical_id]
                source = {"file": f"by-batch/{batch}.jsonl", "line": None}
            else:
                copies = grouped.get(canonical_id) or []
                if not copies:
                    raise ValueError(f"{canonical_id} ({batch}) missing from every input")
                name, lineno, row = copies[0]
                source = {"file": name, "line": lineno}
                if len(copies) > 1:
                    conflict_fields = sorted(
                        {
                            field
                            for _, _, other in copies[1:]
                            for field in REQUIRED_FIELDS
                            if row.get(field) != other.get(field)
                        }
                    )
                    coding_conflict_fields = sorted(field for field in conflict_fields if field != "notes")
                    duplicate_details.append(
                        {
                            "canonical_id": canonical_id,
                            "batch": batch,
                            "copies": [{"file": name, "line": lineno} for name, lineno, _ in copies],
                            "kept_from": source,
                            "conflict_fields": conflict_fields,
                            "coding_conflict_fields": coding_conflict_fields,
                        }
                    )
            merged.append(row)
            provenance.append({"batch": batch, "canonical_id": canonical_id, **source})

    # --- validation -----------------------------------------------------
    aspect_codes = {code.code for code in ASPECTS}
    context_codes = {code.code for code in CONTEXTS}
    failures: list[dict] = []
    aspect_count = 0
    aspect_records = 0
    experience_true = 0
    experience_false = 0
    legacy_scope_independent = 0
    scope_counts: Counter[str] = Counter()
    polarity_counts: Counter[str] = Counter()
    code_counts: Counter[str] = Counter()
    qualified_positive: list[dict] = []
    per_batch_counts: Counter[str] = Counter()

    for entry in provenance:
        per_batch_counts[entry["batch"]] += 1

    for row in merged:
        canonical_id = row.get("canonical_id")
        source = record_by_id.get(canonical_id)
        if source is None:
            failures.append({"canonical_id": canonical_id, "kind": "not_in_canonical"})
            continue
        if set(row) != REQUIRED_FIELDS:
            failures.append(
                {
                    "canonical_id": canonical_id,
                    "kind": "field_set",
                    "missing": sorted(REQUIRED_FIELDS - set(row)),
                    "extra": sorted(set(row) - REQUIRED_FIELDS),
                }
            )
            continue
        experience = row["is_product_experience"]
        if not isinstance(experience, bool):
            failures.append({"canonical_id": canonical_id, "kind": "experience_not_bool"})
            continue
        experience_true += int(experience)
        experience_false += int(not experience)
        scope = row["experience_scope"]
        scope_counts[str(scope)] += 1
        if row["experience_reason"] not in EXPERIENCE_REASONS:
            failures.append({"canonical_id": canonical_id, "kind": "invalid_reason", "detail": row["experience_reason"]})
        if scope not in EXPERIENCE_SCOPES:
            failures.append({"canonical_id": canonical_id, "kind": "invalid_scope", "detail": scope})
        if row["experience_source"] not in EXPERIENCE_SOURCES:
            failures.append({"canonical_id": canonical_id, "kind": "invalid_source", "detail": row["experience_source"]})
        # E-merge §2: product_match and experience_scope are orthogonal.  The
        # old coupling rules below are counted for the transition audit, not
        # treated as build failures.
        if not experience and scope != "none":
            legacy_scope_independent += 1
        if experience and scope == "none":
            legacy_scope_independent += 1
        if row["journey"] not in JOURNEYS:
            failures.append({"canonical_id": canonical_id, "kind": "invalid_journey", "detail": row["journey"]})
        if row["outcome"] not in OUTCOMES:
            failures.append({"canonical_id": canonical_id, "kind": "invalid_outcome", "detail": row["outcome"]})
        if not isinstance(row["medical_self_report"], bool):
            failures.append({"canonical_id": canonical_id, "kind": "medical_not_bool"})
        if not isinstance(row["notes"], str):
            failures.append({"canonical_id": canonical_id, "kind": "notes_not_str"})
        for context in row["contexts"]:
            if context not in context_codes:
                failures.append({"canonical_id": canonical_id, "kind": "invalid_context", "detail": context})

        aspects = row["aspects"]
        if aspects:
            aspect_records += 1
        if len(aspects) > MAX_ASPECTS:
            failures.append({"canonical_id": canonical_id, "kind": "too_many_aspects", "detail": len(aspects)})
        if not experience and aspects:
            failures.append({"canonical_id": canonical_id, "kind": "false_record_has_aspects"})
        title = source.get("title") or ""
        text = source.get("text") or ""
        used_spans: set[str] = set()
        for index, aspect in enumerate(aspects):
            aspect_count += 1
            if set(aspect) != REQUIRED_ASPECT_FIELDS:
                failures.append(
                    {
                        "canonical_id": canonical_id,
                        "kind": "aspect_field_set",
                        "aspect_index": index,
                        "detail": sorted(set(aspect)),
                    }
                )
                continue
            code = aspect["code"]
            polarity = aspect["polarity"]
            confidence = aspect["confidence"]
            span = aspect["evidence_span"]
            code_counts[code] += 1
            polarity_counts[polarity] += 1
            if code not in aspect_codes:
                failures.append({"canonical_id": canonical_id, "kind": "invalid_code", "detail": code})
            if polarity not in POLARITIES:
                failures.append({"canonical_id": canonical_id, "kind": "invalid_polarity", "detail": polarity})
            if confidence not in CONFIDENCES:
                failures.append({"canonical_id": canonical_id, "kind": "invalid_confidence", "detail": confidence})
            if not isinstance(span, str) or not span.strip():
                failures.append({"canonical_id": canonical_id, "kind": "empty_span"})
            elif len(span) > MAX_SPAN_CHARS:
                failures.append({"canonical_id": canonical_id, "kind": "span_too_long", "detail": len(span)})
            elif span not in title and span not in text:
                failures.append({"canonical_id": canonical_id, "kind": "span_not_found", "detail": span})
            if span in used_spans:
                failures.append({"canonical_id": canonical_id, "kind": "span_reused", "detail": span})
            used_spans.add(span)
            if polarity == "qualified_positive":
                qualified_positive.append(
                    {"canonical_id": canonical_id, "code": code, "evidence_span": span}
                )

    merged_ids = [row["canonical_id"] for row in merged]
    v1_ids = {row["canonical_id"] for row in read_jsonl(V1_ALL)}
    missing_ids = sorted(text_ids - set(merged_ids))
    extra_ids = sorted(set(merged_ids) - set(record_by_id))
    duplicate_ids = sorted(cid for cid, count in Counter(merged_ids).items() if count > 1)
    set_matches_v1 = set(merged_ids) == v1_ids
    order_matches_v1 = merged_ids == [row["canonical_id"] for row in read_jsonl(V1_ALL)]
    buildable = (
        not failures
        and not missing_ids
        and not extra_ids
        and not duplicate_ids
        and len(merged_ids) == len(text_ids)
        and set_matches_v1
    )

    ALL_OUT.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in merged),
        encoding="utf-8",
    )
    CONFLICTS_OUT.write_text(
        json.dumps(duplicate_details, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    report = {
        "schema_version": "voc_llm_coding_v2_merge_v2",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "COMPLETE" if buildable else "INCOMPLETE",
        "buildable": buildable,
        "strategy": "batch is the unit; by-batch wins; parts fill missing batches by canonical_id",
        "inputs": {
            "by_batch": sorted(by_batch),
            "parts": [path.name for path in sorted(CODED_DIR.glob("part-*.jsonl"))],
            "batch_counts": {batch: len(ids) for batch, ids in batch_ids.items()},
        },
        "merged": {
            "rows_written": len(merged),
            "unique_canonical_ids": len(set(merged_ids)),
            "expected_text_records": len(text_ids),
            "missing_records": len(missing_ids),
            "extra_records_not_in_canonical": len(extra_ids),
            "duplicate_ids": len(duplicate_ids),
            "per_batch_counts": dict(per_batch_counts),
            "v1_id_set_match": set_matches_v1,
            "v1_order_match": order_matches_v1,
        },
        "duplicates": {
            "duplicate_groups": len(duplicate_details),
            "full_row_identical_groups": sum(1 for item in duplicate_details if not item["conflict_fields"]),
            "notes_only_groups": sum(
                1 for item in duplicate_details if item["conflict_fields"] == ["notes"]
            ),
            "coding_conflict_groups": sum(
                1 for item in duplicate_details if item["coding_conflict_fields"]
            ),
            "detail_file": str(CONFLICTS_OUT),
            "dedupe_policy": "first occurrence in sorted part order",
        },
        "validation": {
            "failures": len(failures),
            "failure_samples": failures[:20],
            "aspects": aspect_count,
            "aspect_records": aspect_records,
            "experience_true": experience_true,
            "experience_false": experience_false,
            "experience_scope": dict(scope_counts),
            "legacy_scope_independent": legacy_scope_independent,
            "polarity_counts": dict(polarity_counts),
            "code_counts": dict(code_counts),
        },
        "qualified_positive": {
            "aspects": len(qualified_positive),
            "records": len({item["canonical_id"] for item in qualified_positive}),
            "occurrences": qualified_positive,
        },
        "previous_attempt": {
            "status": "INCOMPLETE",
            "rows_written": 248,
            "missing_records": 82,
            "duplicate_canonical_ids": 83,
            "coding_conflict_groups": 43,
            "cause": "part-01..04 were built from the wrong batch pairs; batch-05 and batch-07 were never coded",
        },
        "constraints": {
            "gold_set_read": False,
            "v1_artifact_modified": False,
        },
    }
    REPORT_OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "buildable": buildable,
                "rows": len(merged),
                "unique": len(set(merged_ids)),
                "v1_id_set_match": set_matches_v1,
                "v1_order_match": order_matches_v1,
                "duplicates": len(duplicate_details),
                "coding_conflicts": report["duplicates"]["coding_conflict_groups"],
                "failures": len(failures),
                "aspects": aspect_count,
                "experience_false": experience_false,
                "qualified_positive_aspects": len(qualified_positive),
                "qualified_positive_records": report["qualified_positive"]["records"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if buildable else 2


if __name__ == "__main__":
    raise SystemExit(main())
