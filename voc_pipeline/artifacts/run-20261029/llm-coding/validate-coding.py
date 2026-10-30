#!/usr/bin/env python3
"""Validate LLM coding output against the source batches.

LEGACY INPUT VALIDATOR.  It validates the frozen ``llm-coding`` artifact that
fed the A/A2 coder.  ``is_product_experience`` is a historical input field;
since E-merge it is audit-only and the published aspect gate is
``product_match in {exact_current_family, category_adjacent} and
experience_scope in {full, partial} and text non-empty``.  Do not use this
script's gate to recompute a published cohort.

Checks performed:
  * every output line is a JSON object with the required fields and enums;
  * every aspect code is in taxonomy.json;
  * every evidence_span is a verbatim substring of the record title or text,
    is at most 120 characters, and is not reused inside one record;
  * is_product_experience=false implies an empty aspects list (frozen input
    convention; the merged coder suppresses off-target aspects downstream);
  * at most 6 aspects per record;
  * every source canonical_id appears exactly once (strict mode).

It also writes per-batch statistics: aspect count, unknown-polarity ratio and
is_product_experience ratio, plus polarity/code/confidence distributions.

Usage:
  python3 validate-coding.py \
    --batches-dir <.../llm-coding/batches> \
    --outputs <.../llm-coding/outputs> \
    --report <.../llm-coding/batch-report.json> \
    [--allow-missing]

--allow-missing downgrades missing output files and missing records to
warnings, so the validator can be dry-run before any coding exists.
Exit code is 0 only when no errors remain.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent

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
JOURNEYS = {"purchase", "selection", "first_use", "repeat_use", "return", None}
OUTCOMES = {"relief", "no_relief", None}

REQUIRED_FIELDS = [
    "canonical_id",
    "is_product_experience",
    "experience_reason",
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


class BatchReport:
    def __init__(self, name: str) -> None:
        self.name = name
        self.output_file = None
        self.source_records = 0
        self.output_records = 0
        self.missing_records = 0
        self.extra_records = 0
        self.parse_errors = 0
        self.error_count = 0
        self.warning_count = 0
        self.n_aspects = 0
        self.unknown_polarity = 0
        self.is_product_experience_true = 0
        self.polarity_counts = Counter()
        self.confidence_counts = Counter()
        self.code_counts = Counter()
        self.evidence_span_failures = 0
        self.non_experience_with_aspects = 0
        self.records_with_zero_aspects = 0
        self.max_aspects_per_record = 0

    def as_dict(self) -> dict:
        aspects_per_record = (self.n_aspects / self.output_records) if self.output_records else 0.0
        unknown_ratio = (self.unknown_polarity / self.n_aspects) if self.n_aspects else 0.0
        exp_ratio = (self.is_product_experience_true / self.output_records) if self.output_records else 0.0
        return {
            "batch": self.name,
            "output_file": self.output_file,
            "source_records": self.source_records,
            "output_records": self.output_records,
            "missing_records": self.missing_records,
            "extra_records": self.extra_records,
            "parse_errors": self.parse_errors,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "n_aspects": self.n_aspects,
            "aspects_per_record": round(aspects_per_record, 4),
            "unknown_polarity": self.unknown_polarity,
            "unknown_ratio": round(unknown_ratio, 4),
            "is_product_experience_true": self.is_product_experience_true,
            "is_product_experience_ratio": round(exp_ratio, 4),
            "polarity_counts": dict(sorted(self.polarity_counts.items())),
            "confidence_counts": dict(sorted(self.confidence_counts.items())),
            "code_counts": dict(sorted(self.code_counts.items())),
            "evidence_span_failures": self.evidence_span_failures,
            "non_experience_with_aspects": self.non_experience_with_aspects,
            "records_with_zero_aspects": self.records_with_zero_aspects,
            "max_aspects_per_record": self.max_aspects_per_record,
        }


class Validator:
    def __init__(self, batches_dir: Path, outputs_dir: Path, allow_missing: bool, max_errors: int) -> None:
        self.batches_dir = batches_dir
        self.outputs_dir = outputs_dir
        self.allow_missing = allow_missing
        self.max_errors = max_errors
        self.errors: list[dict] = []
        self.warnings: list[dict] = []
        self.total_errors = 0
        self.total_warnings = 0
        self.report_by_name: dict[str, BatchReport] = {}

    def error(self, batch: str, line, cid, kind: str, detail: str) -> None:
        self.total_errors += 1
        report = self.report_by_name.get(batch)
        if report is not None:
            report.error_count += 1
        if len(self.errors) < self.max_errors:
            self.errors.append(
                {"batch": batch, "line": line, "canonical_id": cid, "kind": kind, "detail": detail}
            )

    def warning(self, batch: str, line, cid, kind: str, detail: str) -> None:
        self.total_warnings += 1
        report = self.report_by_name.get(batch)
        if report is not None:
            report.warning_count += 1
        if len(self.warnings) < self.max_errors:
            self.warnings.append(
                {"batch": batch, "line": line, "canonical_id": cid, "kind": kind, "detail": detail}
            )

    def run(self) -> dict:
        taxonomy_path = HERE / "taxonomy.json"
        if not taxonomy_path.exists():
            raise SystemExit("missing taxonomy.json next to validator: %s" % taxonomy_path)
        taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
        aspect_codes = {item["code"] for item in taxonomy["aspects"]}
        context_codes = {item["code"] for item in taxonomy["contexts"]}

        batch_files = sorted(self.batches_dir.glob("batch-*.jsonl"))
        if not batch_files:
            raise SystemExit("no batch-*.jsonl under %s" % self.batches_dir)

        reports: list[BatchReport] = []
        id_to_batch: dict[str, str] = {}
        source_orders: dict[str, list[str]] = {}

        if not self.outputs_dir.exists():
            if self.allow_missing:
                self.warning("-", None, None, "outputs_dir_missing", str(self.outputs_dir))
            else:
                self.error("-", None, None, "outputs_dir_missing", str(self.outputs_dir))

        for batch_path in batch_files:
            report = BatchReport(batch_path.stem)
            reports.append(report)
            self.report_by_name[report.name] = report

            source_rows = self._read_jsonl(batch_path, report, is_source=True)
            source_ids: list[str] = []
            source_by_id: dict[str, dict] = {}
            for line_no, rec in source_rows:
                cid = rec.get("canonical_id")
                if not isinstance(cid, str) or not cid:
                    self.error(report.name, line_no, cid, "source_invalid_id", "source row has no canonical_id")
                    continue
                if cid in id_to_batch:
                    self.error(report.name, line_no, cid, "source_duplicate_id",
                               "already seen in %s" % id_to_batch[cid])
                    continue
                id_to_batch[cid] = report.name
                source_ids.append(cid)
                source_by_id[cid] = rec
            source_orders[report.name] = source_ids
            report.source_records = len(source_ids)

            output_path = self.outputs_dir / batch_path.name
            report.output_file = str(output_path)
            if not output_path.exists():
                if self.allow_missing:
                    self.warning(report.name, None, None, "output_missing", str(output_path))
                else:
                    self.error(report.name, None, None, "output_missing", str(output_path))
                report.missing_records = len(source_ids)
                if not self.allow_missing:
                    extra = max(0, len(source_ids) - 1)
                    self.total_errors += extra
                    report.error_count += extra
                continue

            output_rows = self._read_jsonl(output_path, report, is_source=False)
            seen_ids: list[str] = []
            for line_no, obj in output_rows:
                self._validate_record(obj, line_no, report, source_by_id, aspect_codes, context_codes, seen_ids)

            report.output_records = len(seen_ids)
            missing = [cid for cid in source_ids if cid not in set(seen_ids)]
            extra = [cid for cid in seen_ids if cid not in source_by_id]
            report.missing_records = len(missing)
            report.extra_records = len(extra)
            for cid in missing:
                if self.allow_missing:
                    self.warning(report.name, None, cid, "missing_record", "no output line for this canonical_id")
                else:
                    self.error(report.name, None, cid, "missing_record", "no output line for this canonical_id")
            for cid in extra:
                self.error(report.name, None, cid, "extra_canonical_id", "not present in the source batch")

            if not missing and not extra and seen_ids != source_ids:
                self.warning(report.name, None, None, "order_mismatch",
                             "output canonical_id order differs from source order")

        if self.outputs_dir.exists():
            outputs_names = {p.name for p in self.outputs_dir.glob("batch-*.jsonl")}
            expected_names = {p.name for p in batch_files}
            for name in sorted(outputs_names - expected_names):
                self.warning("-", None, None, "unexpected_output_file", name)

        totals = self._totals(reports)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "batches_dir": str(self.batches_dir),
            "outputs_dir": str(self.outputs_dir),
            "strict": not self.allow_missing,
            "ok": self.total_errors == 0,
            "total_errors": self.total_errors,
            "total_warnings": self.total_warnings,
            "errors_truncated": self.total_errors > len(self.errors),
            "warnings_truncated": self.total_warnings > len(self.warnings),
            "totals": totals,
            "batches": [report.as_dict() for report in reports],
            "errors": self.errors,
            "warnings": self.warnings,
        }

    def _read_jsonl(self, path: Path, report: BatchReport, is_source: bool) -> list[tuple[int, dict]]:
        rows: list[tuple[int, dict]] = []
        try:
            handle = path.open("r", encoding="utf-8")
        except OSError as exc:
            self.error(report.name, None, None, "read_error", str(exc))
            return rows
        with handle:
            for line_no, raw in enumerate(handle, start=1):
                if not raw.strip():
                    continue
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError as exc:
                    report.parse_errors += 1
                    self.error(report.name, line_no, None, "json_parse",
                               "line %d: %s" % (line_no, exc))
                    continue
                if not isinstance(obj, dict):
                    report.parse_errors += 1
                    self.error(report.name, line_no, None, "record_not_object",
                               "line %d is %s, expected object" % (line_no, type(obj).__name__))
                    continue
                rows.append((line_no, obj))
                if not is_source:
                    report.output_records += 1
        return rows

    def _validate_record(self, obj, line_no, report, source_by_id, aspect_codes, context_codes, seen_ids) -> None:
        cid = obj.get("canonical_id")
        if not isinstance(cid, str) or not cid:
            self.error(report.name, line_no, cid, "invalid_canonical_id", "canonical_id must be a non-empty string")
            return
        if cid in seen_ids:
            self.error(report.name, line_no, cid, "duplicate_canonical_id", "canonical_id appears more than once")
        seen_ids.append(cid)

        extra_fields = sorted(set(obj) - set(REQUIRED_FIELDS))
        if extra_fields:
            self.warning(report.name, line_no, cid, "extra_field", "unexpected fields: %s" % extra_fields)
        missing_fields = [field for field in REQUIRED_FIELDS if field not in obj]
        for field in missing_fields:
            self.error(report.name, line_no, cid, "missing_field", field)
        if missing_fields:
            return

        if not isinstance(obj["is_product_experience"], bool):
            self.error(report.name, line_no, cid, "wrong_type", "is_product_experience must be boolean")
        is_experience = obj["is_product_experience"] is True
        if is_experience:
            report.is_product_experience_true += 1

        if not _is_enum(obj["experience_reason"], EXPERIENCE_REASONS):
            self.error(report.name, line_no, cid, "invalid_enum",
                       "experience_reason=%r" % (obj["experience_reason"],))
        elif is_experience and obj["experience_reason"] != "first_person_use":
            self.warning(report.name, line_no, cid, "reason_inconsistent",
                         "is_product_experience=true but reason=%r" % (obj["experience_reason"],))

        aspects = obj["aspects"]
        if not isinstance(aspects, list):
            self.error(report.name, line_no, cid, "wrong_type", "aspects must be a list")
            aspects = []
        if not is_experience and aspects:
            report.non_experience_with_aspects += 1
            self.error(report.name, line_no, cid, "non_experience_with_aspects",
                       "is_product_experience=false but %d aspect(s) present" % len(aspects))
        if len(aspects) > MAX_ASPECTS:
            self.error(report.name, line_no, cid, "too_many_aspects",
                       "%d aspects, max %d" % (len(aspects), MAX_ASPECTS))
        report.max_aspects_per_record = max(report.max_aspects_per_record, len(aspects))
        if not aspects:
            report.records_with_zero_aspects += 1

        source_rec = source_by_id.get(cid)
        title = ""
        text = ""
        if source_rec is not None:
            title = source_rec.get("title") or ""
            text = source_rec.get("text") or ""
            if not isinstance(title, str):
                title = ""
            if not isinstance(text, str):
                text = ""

        used_spans: set[str] = set()
        for index, aspect in enumerate(aspects):
            label = "aspects[%d]" % index
            if not isinstance(aspect, dict):
                self.error(report.name, line_no, cid, "wrong_type", label + " must be an object")
                continue
            extra_aspect = sorted(set(aspect) - set(REQUIRED_ASPECT_FIELDS))
            if extra_aspect:
                self.warning(report.name, line_no, cid, "aspect_extra_field",
                             "%s unexpected fields: %s" % (label, extra_aspect))
            missing_aspect = [field for field in REQUIRED_ASPECT_FIELDS if field not in aspect]
            for field in missing_aspect:
                self.error(report.name, line_no, cid, "missing_field", "%s.%s" % (label, field))
            if missing_aspect:
                continue

            code = aspect["code"]
            polarity = aspect["polarity"]
            span = aspect["evidence_span"]
            confidence = aspect["confidence"]

            if not isinstance(code, str) or code not in aspect_codes:
                self.error(report.name, line_no, cid, "invalid_code", "%s.code=%r" % (label, code))
            else:
                report.code_counts[code] += 1

            if not _is_enum(polarity, POLARITIES):
                self.error(report.name, line_no, cid, "invalid_enum",
                           "%s.polarity=%r" % (label, polarity))
            else:
                report.polarity_counts[polarity] += 1
                if polarity == "unknown":
                    report.unknown_polarity += 1

            if not _is_enum(confidence, CONFIDENCES):
                self.error(report.name, line_no, cid, "invalid_enum",
                           "%s.confidence=%r" % (label, confidence))
            else:
                report.confidence_counts[confidence] += 1

            report.n_aspects += 1

            if not isinstance(span, str) or not span.strip():
                report.evidence_span_failures += 1
                self.error(report.name, line_no, cid, "span_missing",
                           "%s.evidence_span is empty or not a string" % label)
                continue
            if len(span) > MAX_SPAN_CHARS:
                report.evidence_span_failures += 1
                self.error(report.name, line_no, cid, "span_too_long",
                           "%s.evidence_span has %d chars, max %d" % (label, len(span), MAX_SPAN_CHARS))
            if span in used_spans:
                self.error(report.name, line_no, cid, "span_duplicate",
                           "%s.evidence_span reused for another aspect" % label)
            used_spans.add(span)
            if source_rec is None:
                report.evidence_span_failures += 1
                self.error(report.name, line_no, cid, "span_not_checked",
                           "no source record for canonical_id")
                continue
            if span not in title and span not in text:
                report.evidence_span_failures += 1
                detail = "%s.evidence_span not found verbatim: %r" % (label, span[:80])
                if _normalized_match(span, title, text):
                    detail += " (matches only after whitespace/case normalization)"
                self.error(report.name, line_no, cid, "span_not_found", detail)

        contexts = obj["contexts"]
        if not isinstance(contexts, list):
            self.error(report.name, line_no, cid, "wrong_type", "contexts must be a list")
        else:
            for ctx in contexts:
                if not isinstance(ctx, str) or ctx not in context_codes:
                    self.error(report.name, line_no, cid, "invalid_code", "contexts entry %r" % (ctx,))

        if not _is_enum(obj["journey"], JOURNEYS):
            self.error(report.name, line_no, cid, "invalid_enum", "journey=%r" % (obj["journey"],))
        if not _is_enum(obj["outcome"], OUTCOMES):
            self.error(report.name, line_no, cid, "invalid_enum", "outcome=%r" % (obj["outcome"],))
        if not isinstance(obj["medical_self_report"], bool):
            self.error(report.name, line_no, cid, "wrong_type", "medical_self_report must be boolean")
        if not isinstance(obj["notes"], str):
            self.error(report.name, line_no, cid, "wrong_type", "notes must be a string")
        elif not obj["notes"].strip():
            self.warning(report.name, line_no, cid, "empty_notes", "notes is empty; use \"none\"")

    def _totals(self, reports: list[BatchReport]) -> dict:
        n_aspects = sum(r.n_aspects for r in reports)
        unknown = sum(r.unknown_polarity for r in reports)
        outputs = sum(r.output_records for r in reports)
        experiences = sum(r.is_product_experience_true for r in reports)
        return {
            "batches": len(reports),
            "records": sum(r.source_records for r in reports),
            "output_records": outputs,
            "missing_records": sum(r.missing_records for r in reports),
            "extra_records": sum(r.extra_records for r in reports),
            "parse_errors": sum(r.parse_errors for r in reports),
            "n_aspects": n_aspects,
            "aspects_per_record": round(n_aspects / outputs, 4) if outputs else 0.0,
            "unknown_polarity": unknown,
            "unknown_ratio": round(unknown / n_aspects, 4) if n_aspects else 0.0,
            "is_product_experience_true": experiences,
            "is_product_experience_ratio": round(experiences / outputs, 4) if outputs else 0.0,
            "evidence_span_failures": sum(r.evidence_span_failures for r in reports),
            "non_experience_with_aspects": sum(r.non_experience_with_aspects for r in reports),
            "records_with_zero_aspects": sum(r.records_with_zero_aspects for r in reports),
            "polarity_counts": _sum_counters(r.polarity_counts for r in reports),
            "confidence_counts": _sum_counters(r.confidence_counts for r in reports),
            "code_counts": _sum_counters(r.code_counts for r in reports),
        }


def _is_enum(value, allowed) -> bool:
    if value is None:
        return None in allowed
    return isinstance(value, str) and value in allowed


def _sum_counters(counters) -> dict:
    total: Counter = Counter()
    for counter in counters:
        total.update(counter)
    return dict(sorted(total.items()))


def _normalized_match(span: str, title: str, text: str) -> bool:
    needle = " ".join(span.split()).casefold()
    haystack = " ".join((title + "\n" + text).split()).casefold()
    return needle in haystack


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate VOC LLM coding batches")
    parser.add_argument("--batches-dir", default=str(HERE / "batches"))
    parser.add_argument("--outputs", default=str(HERE / "outputs"))
    parser.add_argument("--report", default=str(HERE / "batch-report.json"))
    parser.add_argument("--allow-missing", action="store_true",
                        help="downgrade missing output files/records to warnings (dry run)")
    parser.add_argument("--max-errors", type=int, default=200,
                        help="cap stored error/warning entries in the report (counts stay exact)")
    args = parser.parse_args()

    validator = Validator(
        batches_dir=Path(args.batches_dir).resolve(),
        outputs_dir=Path(args.outputs).resolve(),
        allow_missing=args.allow_missing,
        max_errors=max(1, args.max_errors),
    )
    report = validator.run()

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    totals = report["totals"]
    print("ok=%s errors=%d warnings=%d" % (report["ok"], report["total_errors"], report["total_warnings"]))
    print("records=%d/%d aspects=%d unknown_ratio=%.4f experience_ratio=%.4f span_failures=%d"
          % (totals["output_records"], totals["records"], totals["n_aspects"],
             totals["unknown_ratio"], totals["is_product_experience_ratio"],
             totals["evidence_span_failures"]))
    for batch in report["batches"]:
        print("%-9s src=%3d out=%3d aspects=%3d unknown=%.3f experience=%.3f errors=%d"
              % (batch["batch"], batch["source_records"], batch["output_records"],
                 batch["n_aspects"], batch["unknown_ratio"],
                 batch["is_product_experience_ratio"], batch["error_count"]))
    print("report", report_path)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
