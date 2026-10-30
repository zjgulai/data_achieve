#!/usr/bin/env python3
"""Build the blind 20-item calibration sample and the offline label page.

The sample is drawn from records that the LLM coder marked with at least one
``high``-confidence aspect.  Twelve TikTok Shop records and eight Reddit
records are selected.  The draw is reproducible from a fixed seed.

Outputs (all in this directory unless overridden):

  blind-sample.jsonl    the only file the annotator may see
  mapping.json          item_id -> canonical_id; do NOT show to the annotator
  sample-manifest.json  seed, population, counts and hashes
  label.html            generated from label.template.html

No LLM label is embedded in ``blind-sample.jsonl`` or ``label.html``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RUN_DIR = HERE.parent
DEFAULT_CODED = RUN_DIR / "llm-coding" / "coded" / "ALL.jsonl"
DEFAULT_RECORDS = RUN_DIR / "canonical-records.jsonl"
DEFAULT_TAXONOMY = RUN_DIR / "llm-coding" / "taxonomy.json"
DEFAULT_TEMPLATE = HERE / "label.template.html"
DEFAULT_SEED = 20261030

# The split follows the aspect density: TikTok Shop has many high-confidence
# aspects per record, Reddit has few, so Reddit needs a larger share of records
# to produce a usable number of aspect judgments.
PER_SOURCE = OrderedDict([("tiktok_shop", 12), ("reddit", 8)])
SOURCE_LABEL = {"tiktok_shop": "TikTok Shop", "reddit": "Reddit"}

# Chinese family headings for the picker.  Aspect labels themselves come
# verbatim from taxonomy.json; these are only the group headings.
FAMILY_ZH = {
    "SUP": "支撑",
    "FIT": "尺码与合身",
    "ADJ": "调节与结构",
    "STB": "稳定性",
    "COM": "舒适",
    "APP": "外观与衣下表现",
    "MAT": "面料与耐用",
    "VAL": "性价比",
    "CX": "退换与服务",
    "FUL": "到货状态",
    "GEN": "总体评价",
    "USE": "穿着方式",
    "ACT": "活动兼容",
    "SAF": "受力安全",
}

# Six choices shown to the annotator; qualified_* are a mirror pair.
POLARITIES = [
    {"value": "positive", "label": "正向"},
    {"value": "qualified_positive", "label": "有条件正向"},
    {"value": "negative", "label": "负向"},
    {"value": "qualified_negative", "label": "有条件负向"},
    {"value": "mixed", "label": "混合"},
    {"value": "unknown", "label": "不确定"},
]

ALLOWED_ITEM_FIELDS = {"item_id", "source", "title", "text", "rating"}
FORBIDDEN_ITEM_FIELDS = {
    "canonical_id",
    "aspects",
    "confidence",
    "evidence",
    "evidence_span",
    "is_product_experience",
    "experience_reason",
    "polarity",
    "notes",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_taxonomy_payload(taxonomy: dict[str, Any]) -> dict[str, Any]:
    family_labels = taxonomy.get("family_labels", {})
    families: list[dict[str, Any]] = []
    seen: dict[str, dict[str, Any]] = {}
    for aspect in taxonomy["aspects"]:
        family_key = aspect["family"]
        if family_key not in seen:
            english = family_labels.get(family_key, family_key)
            chinese = FAMILY_ZH.get(family_key)
            label = f"{chinese} / {english}" if chinese else english
            entry = {
                "key": family_key,
                "label": label,
                "aspects": [],
            }
            seen[family_key] = entry
            families.append(entry)
        seen[family_key]["aspects"].append(
            {
                "code": aspect["code"],
                "label": aspect["label"],
                "definition": aspect.get("definition", ""),
                "include": aspect.get("include", ""),
                "exclude": aspect.get("exclude", ""),
            }
        )
    return {"families": families, "polarities": POLARITIES}


def select_sample(
    coded_rows: list[dict[str, Any]],
    canonical_by_id: dict[str, dict[str, Any]],
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    """Return (blind_items, mapping_items, population_counts)."""
    populations: dict[str, list[dict[str, Any]]] = {src: [] for src in PER_SOURCE}
    for row in coded_rows:
        cid = row["canonical_id"]
        record = canonical_by_id.get(cid)
        if record is None:
            raise SystemExit(f"coded record {cid} has no canonical record")
        source = record["source"]
        if source not in PER_SOURCE:
            continue
        high = [a for a in row.get("aspects", []) if a.get("confidence") == "high"]
        if not high:
            continue
        populations[source].append(
            {
                "canonical_id": cid,
                "source": source,
                "high_aspect_count": len(high),
            }
        )

    population_counts = {src: len(populations[src]) for src in PER_SOURCE}
    for source, wanted in PER_SOURCE.items():
        if len(populations[source]) < wanted:
            raise SystemExit(
                f"not enough high-aspect records for {source}: "
                f"{len(populations[source])} < {wanted}"
            )

    chosen: list[dict[str, Any]] = []
    for source, wanted in PER_SOURCE.items():
        # Sort before sampling so the result does not depend on input order.
        pool = sorted(populations[source], key=lambda item: item["canonical_id"])
        rng = random.Random(f"{seed}:{source}")
        chosen.extend(rng.sample(pool, wanted))

    # Randomise presentation order, then assign opaque new ids.
    random.Random(f"{seed}:order").shuffle(chosen)
    width = max(2, len(str(len(chosen))))
    blind_items: list[dict[str, Any]] = []
    mapping_items: list[dict[str, Any]] = []
    for index, picked in enumerate(chosen, start=1):
        item_id = f"B{index:0{width}d}"
        record = canonical_by_id[picked["canonical_id"]]
        item: dict[str, Any] = {
            "item_id": item_id,
            "source": picked["source"],
            "title": (record.get("title") or "").strip(),
            "text": (record.get("text") or "").strip(),
        }
        rating = (record.get("source_meta") or {}).get("rating")
        if isinstance(rating, (int, float)) and not isinstance(rating, bool):
            item["rating"] = rating
        if not item["text"] and not item["title"]:
            raise SystemExit(f"selected record {picked['canonical_id']} has no text")
        if set(item) - ALLOWED_ITEM_FIELDS:
            raise SystemExit(f"unexpected blind fields: {set(item) - ALLOWED_ITEM_FIELDS}")
        if set(item) & FORBIDDEN_ITEM_FIELDS:
            raise SystemExit(f"forbidden blind fields: {set(item) & FORBIDDEN_ITEM_FIELDS}")
        blind_items.append(item)
        mapping_items.append(
            {
                "item_id": item_id,
                "canonical_id": picked["canonical_id"],
                "source": picked["source"],
            }
        )

    return blind_items, mapping_items, population_counts


def sample_id_for(seed: int, mapping_items: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for item in sorted(mapping_items, key=lambda row: row["item_id"]):
        digest.update(f"{item['item_id']}:{item['canonical_id']}\n".encode("utf-8"))
    return f"voc-cal-{seed}-{digest.hexdigest()[:8]}"


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def embed_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # Prevent a literal </script> inside source text from closing the script.
    raw = raw.replace("<", "\\u003c")
    raw = raw.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return raw


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coded", type=Path, default=DEFAULT_CODED)
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out-dir", type=Path, default=HERE)
    args = parser.parse_args()

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    coded_rows = load_jsonl(args.coded)
    canonical_by_id = {row["canonical_id"]: row for row in load_jsonl(args.records)}
    taxonomy = load_json(args.taxonomy)
    taxonomy_payload = build_taxonomy_payload(taxonomy)

    blind_items, mapping_items, population_counts = select_sample(
        coded_rows, canonical_by_id, args.seed
    )
    sample_id = sample_id_for(args.seed, mapping_items)

    blind_path = out_dir / "blind-sample.jsonl"
    mapping_path = out_dir / "mapping.json"
    manifest_path = out_dir / "sample-manifest.json"
    html_path = out_dir / "label.html"

    write_jsonl(blind_path, blind_items)
    write_json(
        mapping_path,
        {
            "schema": "voc-calibration-mapping-v1",
            "sample_id": sample_id,
            "seed": args.seed,
            "warning": "Do not show this file to the annotator; it links opaque item ids to corpus ids.",
            "items": mapping_items,
        },
    )

    payload = {
        "sample_id": sample_id,
        "seed": args.seed,
        "items": blind_items,
        "taxonomy": taxonomy_payload,
    }
    template = args.template.read_text(encoding="utf-8")
    placeholder = "__CALIBRATION_DATA__"
    if template.count(placeholder) != 1:
        raise SystemExit(f"template must contain exactly one {placeholder}")
    html = template.replace(placeholder, embed_payload(payload))
    html_path.write_text(html, encoding="utf-8", newline="\n")

    # Hard blindness assertions on the generated, visible artifact.
    if "canonical_id" in html:
        raise SystemExit("label.html leaks canonical_id")
    if re.search(r"\bc-[0-9a-z]{4,}\b", html):
        raise SystemExit("label.html looks like it contains a canonical id")
    if re.search(r"<script[^>]+src\s*=", html, re.IGNORECASE):
        raise SystemExit("label.html must not load external scripts")
    if re.search(r"@import|url\(\s*['\"]?https?://", html, re.IGNORECASE):
        raise SystemExit("label.html must not load external CSS or fonts")

    source_counts = {
        label: sum(1 for item in blind_items if item["source"] == source)
        for source, label in SOURCE_LABEL.items()
    }
    manifest = {
        "schema": "voc-calibration-sample-v1",
        "sample_id": sample_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "sampling": {
            "method": "uniform random within source among records with at least one high-confidence LLM aspect",
            "per_source_rng": "random.Random(f'{seed}:{source}') after sorting by canonical_id",
            "presentation_order_rng": "random.Random(f'{seed}:order')",
            "per_source": {src: n for src, n in PER_SOURCE.items()},
        },
        "population": {
            "high_aspect_records": population_counts,
            "total_high_aspect_records": sum(population_counts.values()),
        },
        "sample": {
            "total": len(blind_items),
            "by_source": {
                source: sum(1 for item in blind_items if item["source"] == source)
                for source in PER_SOURCE
            },
            "display_counts": source_counts,
        },
        "blind_contract": {
            "visible_fields": sorted(ALLOWED_ITEM_FIELDS),
            "forbidden_fields": sorted(FORBIDDEN_ITEM_FIELDS),
            "llm_labels_in_blind_sample": False,
            "llm_labels_in_label_html": False,
        },
        "reference_llm": {
            "file": str(args.coded),
            "confidence_gate": "high",
            "note": "Used only by compute-kappa.py; never embedded in the blind sample or label.html.",
        },
        "files": {
            "blind_sample": {
                "path": str(blind_path),
                "sha256": sha256_file(blind_path),
            },
            "mapping": {
                "path": str(mapping_path),
                "sha256": sha256_file(mapping_path),
            },
            "label_html": {
                "path": str(html_path),
                "sha256": sha256_file(html_path),
            },
        },
    }
    write_json(manifest_path, manifest)

    print(f"sample_id: {sample_id}")
    print(f"blind sample: {blind_path} ({len(blind_items)} items)")
    print(
        "source split: "
        + ", ".join(
            f"{SOURCE_LABEL[src]}={sum(1 for item in blind_items if item['source'] == src)}"
            for src in PER_SOURCE
        )
    )
    print(f"mapping: {mapping_path} (do not show to annotator)")
    print(f"manifest: {manifest_path}")
    print(f"label page: {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
