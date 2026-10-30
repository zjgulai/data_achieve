#!/usr/bin/env python3
"""Merge the 8 LLM-coded batches into ALL.jsonl and re-validate every aspect.

LEGACY INPUT TOOL.  It rebuilds the frozen ``llm-coding`` artifact.
``is_product_experience`` is kept as an input audit field; since E-merge it is
not a published gate.  See ``decisions/E-merge-experience-fields.md`` §2.4.

Checks:
  * merged line count vs manifest encoded_scope (records with text)
  * duplicate canonical_id across the whole merge
  * missing canonical_id vs the union of source batch ids
  * per-aspect evidence_span verbatim substring match against the source
    record's title/text, <=120 chars, no reuse inside one record
  * code/enum/structural rules from CODING-CONTRACT.md

Writes merge-report.json next to this script.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BATCHES = HERE / "batches"
CODED = HERE / "coded"
ALL_OUT = CODED / "ALL.jsonl"
REPORT = HERE / "merge-report.json"

POLARITIES = {"positive", "qualified_positive", "negative", "qualified_negative", "mixed", "unknown"}
CONFIDENCES = {"high", "medium", "low"}
EXPERIENCE_REASONS = {
    "first_person_use", "help_seeking", "third_party_event",
    "product_mismatch", "question", "other",
}
JOURNEYS = {"purchase", "selection", "first_use", "repeat_use", "return", None}
OUTCOMES = {"relief", "no_relief", None}
REQUIRED_FIELDS = [
    "canonical_id", "is_product_experience", "experience_reason", "aspects",
    "contexts", "journey", "outcome", "medical_self_report", "notes",
]
REQUIRED_ASPECT_FIELDS = ["code", "polarity", "evidence_span", "confidence"]
MAX_SPAN_CHARS = 120
MAX_ASPECTS = 6


def read_jsonl(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, start=1):
            if not raw.strip():
                continue
            rows.append((line_no, json.loads(raw)))
    return rows


def main() -> int:
    manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    taxonomy = json.loads((HERE / "taxonomy.json").read_text(encoding="utf-8"))
    aspect_codes = {a["code"] for a in taxonomy["aspects"]}
    context_codes = {c["code"] for c in taxonomy["contexts"]}

    batch_files = sorted(BATCHES.glob("batch-*.jsonl"))
    coded_files = sorted(CODED.glob("batch-*.jsonl"))

    # ---------- source side ----------
    source_by_id: dict[str, dict] = {}
    source_batch: dict[str, str] = {}
    source_order: list[str] = []
    duplicate_source_ids: list[dict] = []
    per_batch_counts: dict[str, int] = {}
    for path in batch_files:
        rows = read_jsonl(path)
        per_batch_counts[path.stem] = len(rows)
        for line_no, rec in rows:
            cid = rec.get("canonical_id")
            if cid in source_by_id:
                duplicate_source_ids.append(
                    {"canonical_id": cid, "already_in": source_batch[cid], "again_in": path.stem}
                )
                continue
            source_by_id[cid] = rec
            source_batch[cid] = path.stem
            source_order.append(cid)

    # ---------- coded side ----------
    merged: list[dict] = []
    per_file: list[dict] = []
    duplicate_ids: list[dict] = []
    parse_errors: list[dict] = []
    order_mismatches: list[dict] = []
    seen: dict[str, str] = {}

    for path in coded_files:
        count = 0
        ids_in_file: list[str] = []
        try:
            rows = read_jsonl(path)
        except json.JSONDecodeError as exc:
            parse_errors.append({"file": path.name, "error": str(exc)})
            continue
        for line_no, obj in rows:
            count += 1
            cid = obj.get("canonical_id")
            ids_in_file.append(cid)
            if cid in seen:
                duplicate_ids.append(
                    {"canonical_id": cid, "first_file": seen[cid], "again_file": path.name, "line": line_no}
                )
            else:
                seen[cid] = path.name
            merged.append(obj)
        src_path = BATCHES / path.name
        if src_path.exists():
            src_ids = [r["canonical_id"] for _, r in read_jsonl(src_path)]
            if ids_in_file != src_ids:
                order_mismatches.append(
                    {
                        "file": path.name,
                        "same_set": set(ids_in_file) == set(src_ids),
                        "first_diff_index": next(
                            (i for i, (a, b) in enumerate(zip(ids_in_file, src_ids)) if a != b),
                            None,
                        ),
                        "out_len": len(ids_in_file),
                        "src_len": len(src_ids),
                    }
                )
        per_file.append({"file": path.name, "records": count})

    # stable merge output in batch order
    ALL_OUT.write_text(
        "".join(json.dumps(obj, ensure_ascii=False) + "\n" for obj in merged),
        encoding="utf-8",
    )

    # ---------- per-record checks ----------
    span_failures: list[dict] = []
    structural_errors: list[dict] = []
    invalid_codes: list[dict] = []
    invalid_enums: list[dict] = []
    non_experience_with_aspects: list[str] = []
    too_many_aspects: list[dict] = []
    span_duplicates: list[dict] = []

    n_aspects = 0
    aspect_records = 0
    aspect_count_dist = Counter()
    polarity_counts = Counter()
    confidence_counts = Counter()
    code_counts = Counter()
    unknown_aspects_by_record: list[dict] = []
    experience_true = 0

    for obj in merged:
        cid = obj.get("canonical_id")
        missing_fields = [f for f in REQUIRED_FIELDS if f not in obj]
        if missing_fields:
            structural_errors.append({"canonical_id": cid, "kind": "missing_field", "detail": missing_fields})
            continue
        if obj.get("is_product_experience") is True:
            experience_true += 1
        if obj.get("experience_reason") not in EXPERIENCE_REASONS:
            invalid_enums.append({"canonical_id": cid, "field": "experience_reason",
                                  "value": obj.get("experience_reason")})
        if obj.get("journey") not in JOURNEYS:
            invalid_enums.append({"canonical_id": cid, "field": "journey", "value": obj.get("journey")})
        if obj.get("outcome") not in OUTCOMES:
            invalid_enums.append({"canonical_id": cid, "field": "outcome", "value": obj.get("outcome")})
        for ctx in obj.get("contexts") or []:
            if ctx not in context_codes:
                invalid_codes.append({"canonical_id": cid, "kind": "context", "code": ctx})

        aspects = obj.get("aspects") or []
        aspect_count_dist[len(aspects)] += 1
        if aspects:
            aspect_records += 1
        if len(aspects) > MAX_ASPECTS:
            too_many_aspects.append({"canonical_id": cid, "n": len(aspects)})
        if obj.get("is_product_experience") is False and aspects:
            non_experience_with_aspects.append(cid)

        src = source_by_id.get(cid)
        title = (src.get("title") or "") if src else ""
        text = (src.get("text") or "") if src else ""
        used_spans: set[str] = set()
        for idx, aspect in enumerate(aspects):
            n_aspects += 1
            missing_aspect = [f for f in REQUIRED_ASPECT_FIELDS if f not in aspect]
            if missing_aspect:
                structural_errors.append({"canonical_id": cid, "kind": "aspect_missing_field",
                                          "aspect_index": idx, "detail": missing_aspect})
                continue
            code = aspect["code"]
            polarity = aspect["polarity"]
            confidence = aspect["confidence"]
            span = aspect["evidence_span"]
            if code not in aspect_codes:
                invalid_codes.append({"canonical_id": cid, "kind": "aspect", "code": code})
            else:
                code_counts[code] += 1
            if polarity not in POLARITIES:
                invalid_enums.append({"canonical_id": cid, "field": "aspect.polarity", "value": polarity})
            else:
                polarity_counts[polarity] += 1
                if polarity == "unknown":
                    unknown_aspects_by_record.append({"canonical_id": cid, "code": code, "span": span})
            if confidence not in CONFIDENCES:
                invalid_enums.append({"canonical_id": cid, "field": "aspect.confidence", "value": confidence})
            else:
                confidence_counts[confidence] += 1

            reason = None
            if not isinstance(span, str) or not span.strip():
                reason = "empty_span"
            elif len(span) > MAX_SPAN_CHARS:
                reason = "span_too_long"
            elif src is None:
                reason = "no_source_record"
            elif span not in title and span not in text:
                reason = "span_not_found"
            if span in used_spans:
                span_duplicates.append({"canonical_id": cid, "span": span})
            used_spans.add(span)
            if reason:
                span_failures.append(
                    {
                        "canonical_id": cid,
                        "source": src.get("source") if src else None,
                        "aspect_index": idx,
                        "code": code,
                        "polarity": polarity,
                        "reason": reason,
                        "span": span[:160] if isinstance(span, str) else span,
                        "span_len": len(span) if isinstance(span, str) else None,
                    }
                )

    merged_ids = [obj.get("canonical_id") for obj in merged]
    missing_ids = [cid for cid in source_order if cid not in set(merged_ids)]
    extra_ids = [cid for cid in merged_ids if cid not in source_by_id]
    gold_pool_missing = []

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "batches_dir": str(BATCHES),
            "coded_dir": str(CODED),
            "coded_files": [f["file"] for f in per_file],
            "manifest_total_records": manifest.get("total_records"),
            "manifest_encoded_scope": manifest.get("encoded_scope"),
            "manifest_with_text": manifest.get("with_text"),
            "manifest_both_empty": manifest.get("both_empty"),
            "manifest_skipped_empty_text": manifest.get("skipped_empty_text"),
            "manifest_batch_counts": manifest.get("batch_counts"),
        },
        "merge": {
            "output": str(ALL_OUT),
            "merged_records": len(merged),
            "merged_nonempty_lines": len(merged),
            "per_file": per_file,
            "matches_encoded_scope": len(merged) == manifest.get("encoded_scope"),
            "delta_vs_encoded_scope": len(merged) - (manifest.get("encoded_scope") or 0),
            "matches_total_records": len(merged) == manifest.get("total_records"),
            "source_records_union": len(source_order),
            "batch_source_counts": per_batch_counts,
        },
        "integrity": {
            "duplicate_canonical_ids": duplicate_ids,
            "duplicate_canonical_id_count": len(duplicate_ids),
            "duplicate_source_ids": duplicate_source_ids,
            "missing_canonical_ids": missing_ids,
            "missing_count": len(missing_ids),
            "extra_canonical_ids": extra_ids,
            "extra_count": len(extra_ids),
            "order_mismatches": order_mismatches,
            "parse_errors": parse_errors,
        },
        "evidence_span_validation": {
            "rule": "exact substring of source title or text, <=120 chars, no reuse in record",
            "aspects_checked": n_aspects,
            "failures": len(span_failures),
            "failure_rate_pct": round(100.0 * len(span_failures) / n_aspects, 2) if n_aspects else 0.0,
            "failure_detail": span_failures,
            "duplicate_span_in_record": span_duplicates,
        },
        "structural": {
            "records": len(merged),
            "is_product_experience_true": experience_true,
            "records_with_aspects": aspect_records,
            "records_with_zero_aspects": len(merged) - aspect_records,
            "aspect_count_distribution": dict(sorted(aspect_count_dist.items())),
            "n_aspects": n_aspects,
            "non_experience_with_aspects": non_experience_with_aspects,
            "too_many_aspects": too_many_aspects,
            "structural_errors": structural_errors,
            "invalid_codes": invalid_codes,
            "invalid_enums": invalid_enums,
        },
        "distributions": {
            "polarity": dict(sorted(polarity_counts.items())),
            "confidence": dict(sorted(confidence_counts.items())),
            "codes": dict(sorted(code_counts.items())),
        },
        "unknown_aspects": unknown_aspects_by_record,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({k: report[k] for k in ("merge", "integrity", "evidence_span_validation")},
                     ensure_ascii=False, indent=2)[:3500])
    print("\nstructural:", json.dumps(report["structural"], ensure_ascii=False)[:1500])
    print("distributions:", json.dumps(report["distributions"], ensure_ascii=False))
    print("report ->", REPORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
