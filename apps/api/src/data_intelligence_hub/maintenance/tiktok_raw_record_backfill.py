"""Backfill historical TikTok RawRecords into the canonical tables.

Default is a dry run. Pass --execute to write.

Examples:
    python -m data_intelligence_hub.maintenance.tiktok_raw_record_backfill
    python -m data_intelligence_hub.maintenance.tiktok_raw_record_backfill \
        --execute --project-id 7fd6ed55-7b0c-5482-92f3-d03130168b70
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import datetime
from typing import Any

from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.services.tiktok_content_backfill import (
    BackfillFilters,
    backfill_tiktok_content,
)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("datetime must include a timezone")
    return parsed


def _progress(report: dict[str, Any]) -> None:
    print(
        json.dumps(
            {
                "scanned_runs": report["scanned_runs"],
                "eligible_records": report["eligible_records"],
                "projected_records": report["projected_records"],
                "failed_records": report["failed_records"],
            },
            ensure_ascii=False,
        ),
        file=sys.stderr,
        flush=True,
    )


async def _run(args: argparse.Namespace) -> int:
    filters = BackfillFilters(
        workspace_id=args.workspace_id,
        project_id=args.project_id,
        task_id=args.task_id,
        run_id=args.run_id,
        endpoint_types=tuple(args.endpoint_type or ()),
        since=args.since,
        until=args.until,
        include_phase0_tikhub=args.include_phase0_tikhub,
        limit=args.limit,
    )
    async with async_session_factory() as session:
        report = await backfill_tiktok_content(
            session,
            filters=filters,
            dry_run=not args.execute,
            batch_size=args.batch_size,
            progress=_progress,
        )
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    if args.fail_on_error and report.failed_records:
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="回填历史 TikTok RawRecord 到内容与电商规范表。默认只报告，不写库。",
    )
    parser.add_argument("--execute", action="store_true", help="写库执行。")
    parser.add_argument("--workspace-id", type=uuid.UUID)
    parser.add_argument("--project-id", type=uuid.UUID)
    parser.add_argument("--task-id", type=uuid.UUID)
    parser.add_argument("--run-id", type=uuid.UUID)
    parser.add_argument(
        "--endpoint-type",
        action="append",
        help="只回填指定端点，可重复。",
    )
    parser.add_argument("--since", type=_parse_datetime)
    parser.add_argument("--until", type=_parse_datetime)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--include-phase0-tikhub",
        action="store_true",
        help="额外纳入 Phase 0 的旧 TikHub 内容端点。",
    )
    parser.add_argument("--fail-on-error", action="store_true")
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be >= 1")
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
