#!/usr/bin/env python3
"""Build deterministic coding batches from canonical-records.jsonl.

Rules:
  * only records with non-empty title+text enter coding scope;
  * records are sorted by canonical_id (plain Python str sort);
  * rank r (0-based) goes to batch (r % 8) + 1, so batches stay equal in size
    and mixed by source;
  * each batch file is written in canonical_id order.

Outputs (next to this script): batches/batch-01.jsonl .. batch-08.jsonl,
skipped-empty.jsonl and manifest.json.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN_DIR = HERE.parent
SOURCE = RUN_DIR / "canonical-records.jsonl"
BATCH_DIR = HERE / "batches"
SKIPPED = HERE / "skipped-empty.jsonl"
MANIFEST = HERE / "manifest.json"

NUM_BATCHES = 8
KEEP_FIELDS = ["canonical_id", "source", "title", "text", "product_match"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def combined_text(rec: dict) -> str:
    return ((rec.get("title") or "") + "\n" + (rec.get("text") or "")).strip()


def coding_record(rec: dict) -> dict:
    out = {field: rec.get(field) for field in KEEP_FIELDS}
    out["title"] = out.get("title") or ""
    out["text"] = out.get("text") or ""
    meta = rec.get("source_meta") or {}
    if meta.get("rating") is not None:
        out["rating"] = meta["rating"]
    if meta.get("verified_purchase") is not None:
        out["verified_purchase"] = meta["verified_purchase"]
    return out


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def dist(rows: list[dict], field: str) -> dict:
    return dict(sorted(Counter(row.get(field) for row in rows).items(), key=lambda kv: str(kv[0])))


def main() -> None:
    records = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]

    with_text = [rec for rec in records if combined_text(rec)]
    skipped = [rec for rec in records if not combined_text(rec)]
    title_only = [rec for rec in with_text if not (rec.get("text") or "").strip()]
    text_nonempty = [rec for rec in records if (rec.get("text") or "").strip()]

    ordered = sorted(with_text, key=lambda rec: rec["canonical_id"])
    buckets: list[list[dict]] = [[] for _ in range(NUM_BATCHES)]
    for rank, rec in enumerate(ordered):
        buckets[rank % NUM_BATCHES].append(coding_record(rec))

    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    batch_meta = []
    for index, bucket in enumerate(buckets, start=1):
        path = BATCH_DIR / ("batch-%02d.jsonl" % index)
        write_jsonl(path, bucket)
        batch_meta.append(
            {
                "batch": index,
                "file": "batches/" + path.name,
                "count": len(bucket),
                "source_counts": dist(bucket, "source"),
                "product_match_counts": dist(bucket, "product_match"),
                "sha256": sha256(path),
            }
        )

    skipped_rows = [
        {
            "canonical_id": rec["canonical_id"],
            "source": rec.get("source"),
            "product_match": rec.get("product_match"),
            "reason": "empty_text",
            "detail": "title and text are both empty (rating-only row)",
        }
        for rec in skipped
    ]
    write_jsonl(SKIPPED, skipped_rows)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_file": str(SOURCE.relative_to(HERE.parent)),
        "source_sha256": sha256(SOURCE),
        "source_bytes": SOURCE.stat().st_size,
        "taxonomy_file": "taxonomy.json",
        "total_records": len(records),
        "with_text": len(with_text),
        "with_text_definition": "records whose title+text is non-empty after strip; title alone counts",
        "text_field_nonempty": len(text_nonempty),
        "title_only": len(title_only),
        "both_empty": len(skipped),
        "skipped_empty_text": len(skipped),
        "encoded_scope": len(ordered),
        "num_batches": NUM_BATCHES,
        "batch_counts": {str(meta["batch"]): meta["count"] for meta in batch_meta},
        "split_method": (
            "Filter to records whose title+text is non-empty after strip. "
            "Sort those records by canonical_id ascending (Python str sort). "
            "Assign zero-based rank r to batch ((r % 8) + 1). "
            "Write each batch in canonical_id order. Re-running on the same "
            "source file reproduces byte-identical batch files."
        ),
        "fields_kept": KEEP_FIELDS + ["rating (only when source_meta has it)", "verified_purchase (only when source_meta has it)"],
        "rating_records": sum(1 for rec in with_text if (rec.get("source_meta") or {}).get("rating") is not None),
        "verified_purchase_records": sum(1 for rec in with_text if (rec.get("source_meta") or {}).get("verified_purchase") is not None),
        "source_counts_total": dist(records, "source"),
        "source_counts_with_text": dist(with_text, "source"),
        "product_match_counts_total": dist(records, "product_match"),
        "product_match_counts_with_text": dist(with_text, "product_match"),
        "skipped_file": SKIPPED.name,
        "skipped_sha256": sha256(SKIPPED),
        "skipped_reasons": dist(skipped_rows, "reason"),
        "batches": batch_meta,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("total", len(records), "with_text", len(with_text), "skipped", len(skipped))
    print("batch_counts", manifest["batch_counts"])
    print("source_counts_with_text", manifest["source_counts_with_text"])
    print("wrote", MANIFEST)


if __name__ == "__main__":
    main()
