#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify curated training content quality gates.")
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT_DIR / "configs" / "training-content-sources.json",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=ROOT_DIR / "tmp" / "outputs" / "training-content-snapshot-20260615.json",
    )
    parser.add_argument(
        "--curation",
        type=Path,
        default=ROOT_DIR / "tmp" / "outputs" / "training-content-curation-20260615.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_json(args.config)
    snapshot = load_json(args.snapshot)
    curation = load_json(args.curation)
    errors = [
        *verify_counts(config, snapshot, curation),
        *verify_intelligence(curation),
        *verify_visible_copy(config, curation),
    ]
    result = {
        "source_count": snapshot["summary"]["source_count"],
        "raw_record_count": curation["summary"]["raw_record_count"],
        "entity_count": curation["summary"]["entity_count"],
        "signal_count": curation["summary"]["signal_count"],
        "intelligence_item_count": curation["summary"]["intelligence_item_count"],
        "report_count": curation["summary"]["report_count"],
        "alert_count": curation["summary"]["alert_count"],
        "notification_count": curation["summary"]["notification_count"],
        "error_count": len(errors),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if errors else 0


def verify_counts(
    config: dict[str, Any],
    snapshot: dict[str, Any],
    curation: dict[str, Any],
) -> list[str]:
    rules = config["content_contract"]["quality_rules"]
    checks = {
        "sources": (snapshot["summary"]["source_count"], rules["min_sources"]),
        "raw_records": (curation["summary"]["raw_record_count"], rules["min_raw_records"]),
        "entities": (curation["summary"]["entity_count"], rules["min_entities"]),
        "signals": (curation["summary"]["signal_count"], rules["min_signals"]),
        "intelligence_items": (
            curation["summary"]["intelligence_item_count"],
            rules["min_intelligence_items"],
        ),
        "reports": (curation["summary"]["report_count"], rules["min_reports"]),
    }
    return [
        f"{name}: {actual} < {minimum}"
        for name, (actual, minimum) in checks.items()
        if actual < minimum
    ]


def verify_intelligence(curation: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for item in curation["intelligence_items"]:
        if not item.get("evidence_urls"):
            errors.append(f"{item.get('id')}: missing evidence_urls")
        if not item.get("recommended_action"):
            errors.append(f"{item.get('id')}: missing recommended_action")
        if not item.get("last_checked_at"):
            errors.append(f"{item.get('id')}: missing last_checked_at")
    return errors


def verify_visible_copy(config: dict[str, Any], curation: dict[str, Any]) -> list[str]:
    forbidden_terms = [
        str(term).lower()
        for term in config["content_contract"]["quality_rules"]["forbidden_visible_terms"]
    ]
    visible_texts: list[tuple[str, str]] = []
    for project in config["projects"]:
        visible_texts.extend(
            [
                (f"project:{project['key']}:name", str(project["name"])),
                (f"project:{project['key']}:description", str(project["description"])),
            ]
        )
    for source in config["sources"]:
        visible_texts.extend(
            [
                (f"source:{source['id']}:title", str(source["title"])),
                (f"source:{source['id']}:training_use", str(source["training_use"])),
            ]
        )
    for item in curation["intelligence_items"]:
        for field in ("title", "claim", "impact", "recommended_action", "training_talk_track"):
            visible_texts.append((f"intelligence:{item['id']}:{field}", str(item[field])))
    report = curation["report"]
    visible_texts.append(("report:title", str(report["title"])))
    visible_texts.append(("report:summary", str(report["summary"])))
    for alert in curation["alerts"]:
        visible_texts.append((f"alert:{alert['id']}:title", str(alert["title"])))
        visible_texts.append(
            (f"alert:{alert['id']}:recommended_action", str(alert["recommended_action"]))
        )
    for notification in curation["notifications"]:
        visible_texts.append(
            (f"notification:{notification['id']}:title", str(notification["title"]))
        )
        visible_texts.append(
            (f"notification:{notification['id']}:message", str(notification["message"]))
        )

    errors: list[str] = []
    for label, text in visible_texts:
        lowered = text.lower()
        for term in forbidden_terms:
            if term in lowered:
                errors.append(f"{label}: contains forbidden term {term}")
    return errors


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
