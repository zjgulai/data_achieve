#!/usr/bin/env python3
"""Merge the v2 part files into ALL.jsonl and validate the result.

Checks:
  * line count against the canonical text-record set
  * duplicate canonical_id across parts
  * per-aspect evidence_span verbatim substring, <=120 chars, no reuse
  * code/enum/structural rules from CODING-CONTRACT.md
  * qualified_positive occurrences before and after deduplication

The v2 parts overlap and leave records uncovered.  This script still writes the
best available deduplicated ALL.jsonl (first occurrence wins) so the failure is
inspectable, but it records ``buildable: false`` and never pretends the artifact
covers the corpus.  ``voc.build --coder llm-v2`` then fails closed on the
missing records.
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

POLARITIES = {"positive", "qualified_positive", "negative", "qualified_negative", "mixed", "unknown"}
CONFIDENCES = {"high", "medium", "low"}
EXPERIENCE_SCOPES = {"full", "partial", "none"}
EXPERIENCE_SOURCES = {"first_person", "relayed"}
JOURNEYS = {"purchase", "selection", "first_use", "repeat_use", "return", None}
OUTCOMES = {"relief", "no_relief", None}
REQUIRED_FIELDS = [
    "canonical_id",
    # Legacy audit field.  E-merge §3.1 keeps it in old inputs so the adapter
    # can classify downgrades, admit candidates and off-target evaluations.
    # It is never a gate and the merged output is not rebuilt from it.
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
]
REQUIRED_ASPECT_FIELDS = ["code", "polarity", "evidence_span", "confidence"]
MAX_SPAN_CHARS = 120
MAX_ASPECTS = 6
CODING_FIELDS = [
    "is_product_experience",
    "experience_reason",
    "experience_scope",
    "experience_source",
    "aspects",
    "contexts",
    "journey",
    "outcome",
    "medical_self_report",
]


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
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
    source_by_id = {row["canonical_id"]: row for row in canonical}
    text_ids = {
        row["canonical_id"]
        for row in canonical
        if (row.get("title") or "").strip() or (row.get("text") or "").strip()
    }

    part_paths = sorted(CODED_DIR.glob("part-*.jsonl"))
    if not part_paths:
        raise FileNotFoundError(f"no part-*.jsonl in {CODED_DIR}")

    grouped: dict[str, list[tuple[str, int, dict]]] = defaultdict(list)
    first_order: list[str] = []
    per_part: list[dict] = []
    raw_rows = 0
    for path in part_paths:
        rows = read_jsonl(path)
        per_part.append({"file": path.name, "rows": len(rows)})
        raw_rows += len(rows)
        for lineno, row in enumerate(rows, 1):
            cid = row.get("canonical_id")
            if not cid:
                raise ValueError(f"{path}:{lineno}: missing canonical_id")
            if cid not in grouped:
                first_order.append(cid)
            grouped[cid].append((path.name, lineno, row))

    unique_ids = set(grouped)
    duplicate_ids = sorted(cid for cid, copies in grouped.items() if len(copies) > 1)
    missing_ids = sorted(text_ids - unique_ids)
    extra_ids = sorted(unique_ids - set(source_by_id))

    # First occurrence wins.  Record every field that disagrees so the choice
    # is visible instead of silent.
    duplicate_details: list[dict] = []
    coding_conflicts: list[dict] = []
    for cid in duplicate_ids:
        copies = grouped[cid]
        kept_file, kept_line, kept = copies[0]
        fields: set[str] = set()
        coding_fields: set[str] = set()
        for name, lineno, other in copies[1:]:
            for field in REQUIRED_FIELDS:
                if kept.get(field) != other.get(field):
                    fields.add(field)
                    if field in CODING_FIELDS:
                        coding_fields.add(field)
        detail = {
            "canonical_id": cid,
            "copies": [{"file": name, "line": lineno} for name, lineno, _ in copies],
            "kept_from": {"file": kept_file, "line": kept_line},
            "conflict_fields": sorted(fields),
            "coding_conflict_fields": sorted(coding_fields),
        }
        duplicate_details.append(detail)
        if coding_fields:
            coding_conflicts.append(
                {
                    **detail,
                    "rows": [
                        {"file": name, "line": lineno, "row": row}
                        for name, lineno, row in copies
                    ],
                }
            )

    # Structural and evidence validation on the deduplicated set.
    aspect_codes = {code.code for code in ASPECTS}
    context_codes = {code.code for code in CONTEXTS}
    failures: list[dict] = []
    aspect_count = 0
    aspect_records = 0
    polarity_counts: Counter[str] = Counter()
    code_counts: Counter[str] = Counter()
    qualified_positive: list[dict] = []
    experience_true = 0
    experience_false = 0
    legacy_false_with_aspects = 0
    scope_counts: Counter[str] = Counter()

    for cid in first_order:
        row = grouped[cid][0][2]
        source = source_by_id.get(cid)
        if source is None:
            failures.append({"canonical_id": cid, "kind": "not_in_canonical"})
            continue
        missing_fields = [field for field in REQUIRED_FIELDS if field not in row]
        if missing_fields:
            failures.append(
                {"canonical_id": cid, "kind": "missing_field", "detail": missing_fields}
            )
            continue
        if row.get("is_product_experience") is True:
            experience_true += 1
        else:
            experience_false += 1
        scope = row.get("experience_scope")
        if scope not in EXPERIENCE_SCOPES:
            failures.append({"canonical_id": cid, "kind": "invalid_scope", "detail": scope})
        else:
            scope_counts[str(scope)] += 1
        if row.get("experience_source") not in EXPERIENCE_SOURCES:
            failures.append(
                {
                    "canonical_id": cid,
                    "kind": "invalid_source",
                    "detail": row.get("experience_source"),
                }
            )
        if row.get("journey") not in JOURNEYS:
            failures.append({"canonical_id": cid, "kind": "invalid_journey", "detail": row.get("journey")})
        if row.get("outcome") not in OUTCOMES:
            failures.append({"canonical_id": cid, "kind": "invalid_outcome", "detail": row.get("outcome")})
        for context in row.get("contexts") or []:
            if context not in context_codes:
                failures.append({"canonical_id": cid, "kind": "invalid_context", "detail": context})

        aspects = row.get("aspects") or []
        if aspects:
            aspect_records += 1
        if len(aspects) > MAX_ASPECTS:
            failures.append({"canonical_id": cid, "kind": "too_many_aspects", "detail": len(aspects)})
        if row.get("is_product_experience") is False and aspects:
            # E-merge §2.3: an off-target evaluation may exist in the raw LLM
            # output; the adapter suppresses its aspects.  This is an audit
            # count, not a build failure.
            legacy_false_with_aspects += 1

        title = source.get("title") or ""
        text = source.get("text") or ""
        used_spans: set[str] = set()
        for index, aspect in enumerate(aspects):
            aspect_count += 1
            missing_aspect = [field for field in REQUIRED_ASPECT_FIELDS if field not in aspect]
            if missing_aspect:
                failures.append(
                    {
                        "canonical_id": cid,
                        "kind": "aspect_missing_field",
                        "aspect_index": index,
                        "detail": missing_aspect,
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
                failures.append({"canonical_id": cid, "kind": "invalid_code", "detail": code})
            if polarity not in POLARITIES:
                failures.append({"canonical_id": cid, "kind": "invalid_polarity", "detail": polarity})
            if confidence not in CONFIDENCES:
                failures.append({"canonical_id": cid, "kind": "invalid_confidence", "detail": confidence})
            if not isinstance(span, str) or not span.strip():
                failures.append({"canonical_id": cid, "kind": "empty_span"})
            elif len(span) > MAX_SPAN_CHARS:
                failures.append(
                    {"canonical_id": cid, "kind": "span_too_long", "detail": len(span)}
                )
            elif span not in title and span not in text:
                failures.append({"canonical_id": cid, "kind": "span_not_found", "detail": span})
            if span in used_spans:
                failures.append({"canonical_id": cid, "kind": "span_reused", "detail": span})
            used_spans.add(span)
            if polarity == "qualified_positive":
                qualified_positive.append(
                    {"canonical_id": cid, "code": code, "evidence_span": span}
                )

    merged = [grouped[cid][0][2] for cid in first_order]
    ALL_OUT.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in merged),
        encoding="utf-8",
    )
    CONFLICTS_OUT.write_text(
        json.dumps(coding_conflicts, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    raw_qp = sum(
        1
        for copies in grouped.values()
        for _, _, row in copies
        for aspect in row.get("aspects") or []
        if aspect.get("polarity") == "qualified_positive"
    )
    buildable = not missing_ids and not extra_ids and not duplicate_ids and not failures
    report = {
        "schema_version": "voc_llm_coding_v2_merge_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "COMPLETE" if buildable else "INCOMPLETE",
        "buildable": buildable,
        "inputs": {"parts": per_part, "part_rows": raw_rows},
        "merged": {
            "rows_written": len(merged),
            "unique_canonical_ids": len(unique_ids),
            "expected_text_records": len(text_ids),
            "missing_records": len(missing_ids),
            "extra_records_not_in_canonical": len(extra_ids),
        },
        "duplicates": {
            "duplicate_canonical_ids": len(duplicate_ids),
            "full_row_identical_groups": sum(
                1
                for cid in duplicate_ids
                if all(row == grouped[cid][0][2] for _, _, row in grouped[cid][1:])
            ),
            "notes_only_groups": len(duplicate_ids)
            - len(coding_conflicts)
            - sum(
                1
                for cid in duplicate_ids
                if all(row == grouped[cid][0][2] for _, _, row in grouped[cid][1:])
            ),
            "coding_conflict_groups": len(coding_conflicts),
            "detail_file": str(CONFLICTS_OUT),
            "groups": duplicate_details,
        },
        "validation": {
            "failures": len(failures),
            "failure_samples": failures[:20],
            "aspects": aspect_count,
            "aspect_records": aspect_records,
            "experience_true": experience_true,
            "experience_false": experience_false,
            "legacy_false_with_aspects": legacy_false_with_aspects,
            "experience_scope": dict(scope_counts),
            "polarity_counts": dict(polarity_counts),
            "code_counts": dict(code_counts),
        },
        "qualified_positive": {
            "raw_occurrences_with_duplicates": raw_qp,
            "deduplicated_records": len({item["canonical_id"] for item in qualified_positive}),
            "occurrences": qualified_positive,
        },
        "missing_by_source": dict(
            Counter(source_by_id[cid]["source"] for cid in missing_ids)
        ),
        "missing_ids": missing_ids,
        "extra_ids": extra_ids,
        "constraints": {
            "gold_set_read": False,
            "v1_artifact_modified": False,
            "dedupe_policy": "first occurrence in sorted part order",
        },
    }
    REPORT_OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": report["status"],
                "buildable": buildable,
                "part_rows": raw_rows,
                "unique": len(unique_ids),
                "expected": len(text_ids),
                "missing": len(missing_ids),
                "duplicates": len(duplicate_ids),
                "coding_conflicts": len(coding_conflicts),
                "failures": len(failures),
                "qualified_positive_raw": raw_qp,
                "qualified_positive_unique": report["qualified_positive"]["deduplicated_records"],
                "all_out": str(ALL_OUT),
                "report": str(REPORT_OUT),
            },
            ensure_ascii=False,
        )
    )
    return 0 if buildable else 2


if __name__ == "__main__":
    raise SystemExit(main())
