#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT_DIR = Path(__file__).resolve().parents[1]
API_SRC_DIR = ROOT_DIR / "apps" / "api" / "src"
if str(API_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(API_SRC_DIR))

from data_intelligence_hub.collectors import CollectorError, build_collector  # noqa: E402

MAX_TEXT_EXCERPT_CHARS = 5000


@dataclass(frozen=True)
class SnapshotArgs:
    config_path: Path
    output_path: Path
    min_successful_records: int


def parse_args() -> SnapshotArgs:
    parser = argparse.ArgumentParser(
        description="Collect a current source-backed snapshot for curated training content."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT_DIR / "configs" / "training-content-sources.json",
        help="Path to the training source catalog.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT_DIR / "tmp" / "outputs" / "training-content-snapshot-20260615.json",
        help="Path to write the snapshot JSON.",
    )
    parser.add_argument(
        "--min-successful-records",
        type=int,
        default=40,
        help="Fail if fewer than this many raw records are collected successfully.",
    )
    parsed = parser.parse_args()
    return SnapshotArgs(
        config_path=parsed.config,
        output_path=parsed.output,
        min_successful_records=parsed.min_successful_records,
    )


def load_catalog(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        catalog = json.load(file)
    if not isinstance(catalog, dict):
        raise ValueError("training source catalog must be a JSON object")
    sources = catalog.get("sources")
    if not isinstance(sources, list) or len(sources) == 0:
        raise ValueError("training source catalog must contain non-empty sources")
    return catalog


async def collect_snapshot(catalog: dict[str, Any], config_path: Path) -> dict[str, Any]:
    now = datetime.now(UTC).replace(microsecond=0)
    records: list[dict[str, Any]] = []
    source_summaries: list[dict[str, Any]] = []
    async with httpx.AsyncClient(follow_redirects=False) as client:
        for source in catalog["sources"]:
            if not isinstance(source, dict):
                continue
            source_records = await collect_source(source, client, now)
            records.extend(source_records)
            source_summaries.append(
                {
                    "id": source.get("id"),
                    "title": source.get("title"),
                    "collector_type": source.get("collector_type"),
                    "category": source.get("category"),
                    "risk_level": source.get("risk_level"),
                    "record_statuses": [record["status"] for record in source_records],
                }
            )
    successful_records = [record for record in records if record["status"] == "ok"]
    failed_records = [record for record in records if record["status"] != "ok"]
    return {
        "snapshot_version": now.date().isoformat(),
        "dataset": catalog.get("dataset"),
        "generated_at": now.isoformat(),
        "config_path": str(config_path),
        "summary": {
            "source_count": len(catalog["sources"]),
            "record_count": len(records),
            "successful_record_count": len(successful_records),
            "failed_record_count": len(failed_records),
            "collector_counts": count_by(catalog["sources"], "collector_type"),
            "category_counts": count_by(catalog["sources"], "category"),
            "risk_counts": count_by(catalog["sources"], "risk_level"),
        },
        "content_contract": catalog.get("content_contract"),
        "projects": catalog.get("projects"),
        "sources": source_summaries,
        "records": records,
    }


async def collect_source(
    source: dict[str, Any],
    client: httpx.AsyncClient,
    collected_at: datetime,
) -> list[dict[str, Any]]:
    source_id = require_text(source, "id")
    collector_type = require_text(source, "collector_type")
    config = source.get("config")
    if not isinstance(config, dict):
        return [failed_record(source, collected_at, "config_invalid: config must be an object")]

    try:
        collector = build_collector(collector_type, config, http_client=client)
        result = await collector.collect()
    except (CollectorError, httpx.HTTPError, ValueError) as exc:
        return [failed_record(source, collected_at, f"{exc.__class__.__name__}: {exc}")]

    if len(result.raw_records) == 0:
        return [failed_record(source, collected_at, "collector_returned_no_records")]

    records: list[dict[str, Any]] = []
    for index, raw_record in enumerate(result.raw_records):
        record_time = raw_record.collected_at or collected_at
        records.append(
            {
                "source_id": source_id,
                "source_title": source.get("title"),
                "project_key": source.get("project_key"),
                "category": source.get("category"),
                "risk_level": source.get("risk_level"),
                "collector_type": collector_type,
                "record_index": index,
                "record_type": raw_record.record_type,
                "source_url": raw_record.source_url or source.get("source_url"),
                "collected_at": record_time.isoformat(),
                "status": "ok",
                "content": compact_content(raw_record.record_type, raw_record.content),
                "logs": result.logs,
                "errors": result.errors,
            }
        )
    return records


def failed_record(
    source: dict[str, Any],
    collected_at: datetime,
    error: str,
) -> dict[str, Any]:
    return {
        "source_id": source.get("id"),
        "source_title": source.get("title"),
        "project_key": source.get("project_key"),
        "category": source.get("category"),
        "risk_level": source.get("risk_level"),
        "collector_type": source.get("collector_type"),
        "record_index": 0,
        "record_type": source.get("collector_type"),
        "source_url": source.get("source_url"),
        "collected_at": collected_at.isoformat(),
        "status": "failed",
        "content": None,
        "logs": [],
        "errors": [error],
    }


def compact_content(record_type: str, content: Any) -> Any:
    if not isinstance(content, dict):
        return content
    if record_type == "generic_web":
        text = as_text(content.get("text_content"))
        return {
            "provider": content.get("provider"),
            "kind": content.get("kind"),
            "url": content.get("url"),
            "title": content.get("title"),
            "text_excerpt": text[:MAX_TEXT_EXCERPT_CHARS],
            "text_length": len(text),
            "extract_mode": content.get("extract_mode"),
        }
    if record_type == "github_repo":
        raw = content.get("raw") if isinstance(content.get("raw"), dict) else {}
        license_value = raw.get("license") if isinstance(raw, dict) else None
        return {
            "provider": content.get("provider"),
            "kind": content.get("kind"),
            "owner": content.get("owner"),
            "name": content.get("name"),
            "full_name": content.get("full_name"),
            "html_url": content.get("html_url"),
            "description": content.get("description"),
            "language": raw.get("language") if isinstance(raw, dict) else None,
            "topics": raw.get("topics") if isinstance(raw, dict) else None,
            "license": license_value.get("spdx_id") if isinstance(license_value, dict) else None,
            "archived": raw.get("archived") if isinstance(raw, dict) else None,
            "stargazers_count": content.get("stargazers_count"),
            "forks_count": content.get("forks_count"),
            "open_issues_count": content.get("open_issues_count"),
            "watchers_count": content.get("watchers_count"),
            "default_branch": content.get("default_branch"),
            "created_at": raw.get("created_at") if isinstance(raw, dict) else None,
            "pushed_at": content.get("pushed_at"),
            "updated_at": content.get("updated_at"),
        }
    if record_type == "github_topic":
        return {
            "provider": content.get("provider"),
            "kind": content.get("kind"),
            "topic": content.get("topic"),
            "total_count": content.get("total_count"),
            "repositories": content.get("repositories"),
        }
    return content


def as_text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def require_text(source: dict[str, Any], key: str) -> str:
    value = source.get(key)
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError(f"source field is required: {key}")
    return value.strip()


def count_by(items: list[Any], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        value = item.get(key)
        if not isinstance(value, str):
            continue
        counts[value] = counts.get(value, 0) + 1
    return counts


def write_snapshot(snapshot: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(snapshot, file, ensure_ascii=False, indent=2)
        file.write("\n")


async def main() -> int:
    args = parse_args()
    catalog = load_catalog(args.config_path)
    snapshot = await collect_snapshot(catalog, args.config_path)
    write_snapshot(snapshot, args.output_path)
    summary = snapshot["summary"]
    print(
        "snapshot_written="
        f"{args.output_path} "
        f"successful_record_count={summary['successful_record_count']} "
        f"failed_record_count={summary['failed_record_count']}"
    )
    if summary["successful_record_count"] < args.min_successful_records:
        print(
            "snapshot_threshold_failed="
            f"{summary['successful_record_count']}<{args.min_successful_records}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
