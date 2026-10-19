"""Backfill historical TikTok RawRecords into the canonical tables.

The live path projects records right after collection. This service replays
historical ``raw_records`` rows through the same ingestion function. It reuses
the original ``run_id`` and each record's ``collected_at`` so snapshot ids and
observation unique keys stay stable.

The service is deliberately conservative:

* only content and commerce endpoints are eligible by default;
* each record runs in its own savepoint, so one bad row does not abort a run;
* the default is a dry run.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.collectors.base import CollectorRawRecord
from data_intelligence_hub.collectors.tikhub_social import (
    TIKHUB_COMMERCE_ENDPOINT_MAP,
    TIKHUB_CONTENT_ENDPOINT_MAP,
    TIKHUB_ENDPOINT_MAP,
)
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.repositories.tiktok_content import BACKFILL_ONLY_IF_NEWER
from data_intelligence_hub.services.tiktok_content_ingestion import (
    IngestionContext,
    ingest_tiktok_content,
)

MAX_ERRORS = 100
PHASE0_RECORD_TYPES = {
    "tiktok_video",
    "tiktok_comment",
    "tiktok_user",
    "tiktok_hashtag",
    "tiktok_trend",
}
APIFY_TRANSCRIPT_ENDPOINT = "apify_tiktok_transcript_extractor"
APIFY_COMMERCE_ENDPOINTS = {
    "apify_tiktok_shop_scraper",
    "apify_tiktok_shop_product_detail",
    "apify_tiktok_shop_search_v2",
    "apify_tiktok_shop_search_scraper",
    "apify_tiktok_shop_creators",
}
RECORD_PRIORITY = {
    "tiktok_video": 0,
    "tiktok_user": 1,
    "tiktok_hashtag": 2,
    "tiktok_trend": 3,
    "tiktok_product": 4,
    "tiktok_shop_product": 4,
    "tiktok_creator_commerce": 5,
    "tiktok_product_review": 6,
    "tiktok_comment": 7,
}


@dataclass(frozen=True)
class BackfillFilters:
    workspace_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None
    endpoint_types: tuple[str, ...] = ()
    since: datetime | None = None
    until: datetime | None = None
    include_phase0_tikhub: bool = False
    limit: int | None = None


@dataclass
class BackfillReport:
    dry_run: bool = True
    scanned_runs: int = 0
    eligible_runs: int = 0
    scanned_records: int = 0
    eligible_records: int = 0
    projected_records: int = 0
    skipped_records: int = 0
    failed_records: int = 0
    table_counts: dict[str, int] = field(default_factory=dict)
    by_endpoint: dict[str, int] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)
    samples: list[dict[str, Any]] = field(default_factory=list)

    def add_result(self, result: Any) -> None:
        for key, value in result.as_dict().items():
            if key == "errors":
                continue
            if isinstance(value, int):
                self.table_counts[key] = self.table_counts.get(key, 0) + value

    def as_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "scanned_runs": self.scanned_runs,
            "eligible_runs": self.eligible_runs,
            "scanned_records": self.scanned_records,
            "eligible_records": self.eligible_records,
            "projected_records": self.projected_records,
            "skipped_records": self.skipped_records,
            "failed_records": self.failed_records,
            "table_counts": self.table_counts,
            "by_endpoint": self.by_endpoint,
            "errors": self.errors,
            "samples": self.samples,
        }


def _content_dict(raw: RawRecord) -> dict[str, Any] | None:
    return raw.content if isinstance(raw.content, dict) else None


def _resolve_scope(
    task: CollectionTask,
    raw: RawRecord,
    *,
    include_phase0_tikhub: bool,
) -> tuple[str, str, str] | None:
    """Return (provider, endpoint_type, schema_version) or None."""
    content = _content_dict(raw)
    if content is None:
        return None
    task_config = task.config or {}
    task_endpoint = str(task_config.get("endpoint_type") or "")
    record_type = content.get("record_type") or raw.record_type
    schema_version = str(content.get("schema_version") or "")

    if task.collector_type == "tikhub_social":
        endpoint = str(content.get("collector_type") or task_endpoint)
        if endpoint in TIKHUB_CONTENT_ENDPOINT_MAP:
            return "tikhub", endpoint, schema_version or "tikhub_tiktok_content.v1"
        if endpoint in TIKHUB_COMMERCE_ENDPOINT_MAP:
            return "tikhub", endpoint, schema_version or "tikhub_tiktok_commerce.v1"
        if (
            include_phase0_tikhub
            and endpoint in TIKHUB_ENDPOINT_MAP
            and record_type in PHASE0_RECORD_TYPES
            and schema_version.startswith("tikhub_tiktok_")
        ):
            return "tikhub", endpoint, schema_version
        return None

    if task.collector_type == "apify_actor":
        endpoint = task_endpoint or (
            APIFY_TRANSCRIPT_ENDPOINT
            if content.get("actor_id") == "clockworks/tiktok-transcript-extractor"
            else ""
        )
        if endpoint == APIFY_TRANSCRIPT_ENDPOINT:
            if (
                record_type == "tiktok_video"
                and schema_version == "apify_tiktok_video.v1"
                and isinstance(content.get("raw"), dict)
            ):
                return "apify", endpoint, schema_version
            return None
        if endpoint in APIFY_COMMERCE_ENDPOINTS:
            return "apify", endpoint, schema_version or "apify_tiktok_commerce.v1"
        return None

    return None


def _run_context(
    task: CollectionTask,
    run: TaskRun,
    raw: RawRecord,
    *,
    provider: str,
    endpoint_type: str,
    schema_version: str,
) -> IngestionContext:
    config = task.config or {}
    raw_period = config.get("period")
    try:
        period_days = int(raw_period) if raw_period is not None else 7
    except (TypeError, ValueError):
        period_days = 7
    captured_at = raw.collected_at or run.started_at or run.created_at
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=UTC)
    return IngestionContext(
        workspace_id=task.workspace_id,
        project_id=task.project_id,
        provider=provider,
        endpoint_type=endpoint_type,
        schema_version=schema_version,
        run_id=str(run.id),
        raw_ref=str(raw.id),
        captured_at=captured_at,
        country_code=str(
            config.get("country_code") or config.get("region") or "US"
        ),
        period_days=period_days,
        time_window=f"{period_days}d",
        language=str(config.get("language") or "unknown"),
    )


def _to_collector_record(raw: RawRecord) -> CollectorRawRecord | None:
    content = _content_dict(raw)
    if content is None:
        return None
    payload = dict(content)
    payload.setdefault("record_type", raw.record_type)
    return CollectorRawRecord(
        record_type=raw.record_type,
        source_url=raw.source_url,
        content=payload,
        screenshot_url=raw.screenshot_url,
        collected_at=raw.collected_at or datetime.now(UTC),
    )


async def _load_runs(
    session: AsyncSession,
    filters: BackfillFilters,
    *,
    batch_size: int,
) -> list[tuple[TaskRun, CollectionTask]]:
    query = (
        select(TaskRun, CollectionTask)
        .join(CollectionTask, CollectionTask.id == TaskRun.task_id)
        .where(CollectionTask.collector_type.in_(("tikhub_social", "apify_actor")))
        .order_by(TaskRun.created_at.asc(), TaskRun.id.asc())
    )
    if filters.workspace_id is not None:
        query = query.where(TaskRun.workspace_id == filters.workspace_id)
    if filters.project_id is not None:
        query = query.where(CollectionTask.project_id == filters.project_id)
    if filters.task_id is not None:
        query = query.where(TaskRun.task_id == filters.task_id)
    if filters.run_id is not None:
        query = query.where(TaskRun.id == filters.run_id)
    if filters.since is not None:
        query = query.where(TaskRun.created_at >= filters.since)
    if filters.until is not None:
        query = query.where(TaskRun.created_at <= filters.until)
    limit = filters.limit if filters.limit is not None else batch_size
    query = query.limit(limit)
    result = await session.execute(query)
    return list(result.all())


async def _load_records(
    session: AsyncSession,
    run: TaskRun,
    filters: BackfillFilters,
) -> list[RawRecord]:
    query = (
        select(RawRecord)
        .where(RawRecord.task_run_id == run.id)
        .order_by(RawRecord.collected_at.asc(), RawRecord.id.asc())
    )
    if filters.since is not None:
        query = query.where(RawRecord.collected_at >= filters.since)
    if filters.until is not None:
        query = query.where(RawRecord.collected_at <= filters.until)
    result = await session.execute(query)
    records = list(result.scalars().all())
    records.sort(
        key=lambda raw: RECORD_PRIORITY.get(raw.record_type, 99)
    )
    return records


async def backfill_tiktok_content(
    session: AsyncSession,
    *,
    filters: BackfillFilters | None = None,
    dry_run: bool = True,
    batch_size: int = 200,
    progress: Callable[[dict[str, Any]], Awaitable[None] | None] | None = None,
) -> BackfillReport:
    filters = filters or BackfillFilters()
    report = BackfillReport(dry_run=dry_run)
    runs = await _load_runs(session, filters, batch_size=batch_size)
    token = BACKFILL_ONLY_IF_NEWER.set(True)

    for run, task in runs:
        report.scanned_runs += 1
        records = await _load_records(session, run, filters)
        eligible_for_run = 0
        for raw in records:
            report.scanned_records += 1
            scope = _resolve_scope(
                task,
                raw,
                include_phase0_tikhub=filters.include_phase0_tikhub,
            )
            if scope is None:
                report.skipped_records += 1
                continue
            provider, endpoint_type, schema_version = scope
            if filters.endpoint_types and endpoint_type not in filters.endpoint_types:
                report.skipped_records += 1
                continue
            report.eligible_records += 1
            eligible_for_run += 1
            report.by_endpoint[endpoint_type] = (
                report.by_endpoint.get(endpoint_type, 0) + 1
            )
            if len(report.samples) < 20:
                report.samples.append(
                    {
                        "run_id": str(run.id),
                        "raw_record_id": str(raw.id),
                        "endpoint_type": endpoint_type,
                        "record_type": raw.record_type,
                        "collected_at": (
                            raw.collected_at.isoformat()
                            if raw.collected_at
                            else None
                        ),
                    }
                )
            if dry_run:
                continue
            record = _to_collector_record(raw)
            if record is None:
                report.skipped_records += 1
                continue
            context = _run_context(
                task,
                run,
                raw,
                provider=provider,
                endpoint_type=endpoint_type,
                schema_version=schema_version,
            )
            try:
                async with session.begin_nested():
                    result = await ingest_tiktok_content(session, [record], context)
                report.projected_records += 1
                report.add_result(result)
                if result.errors and len(report.errors) < MAX_ERRORS:
                    for error in result.errors:
                        report.errors.append(
                            {
                                "run_id": str(run.id),
                                "raw_record_id": str(raw.id),
                                "endpoint_type": endpoint_type,
                                "record_type": raw.record_type,
                                "error": error,
                            }
                        )
            except Exception as exc:
                report.failed_records += 1
                if len(report.errors) < MAX_ERRORS:
                    report.errors.append(
                        {
                            "run_id": str(run.id),
                            "raw_record_id": str(raw.id),
                            "endpoint_type": endpoint_type,
                            "record_type": raw.record_type,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
        if eligible_for_run:
            report.eligible_runs += 1
        if not dry_run:
            await session.commit()
        if progress is not None:
            maybe = progress(report.as_dict())
            if isinstance(maybe, Awaitable):
                await maybe
    BACKFILL_ONLY_IF_NEWER.reset(token)
    return report
