from __future__ import annotations

import hashlib
import json
import traceback
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from data_intelligence_hub.collectors import CollectorError, CollectorRawRecord, build_collector
from data_intelligence_hub.collectors.base import collector_log
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.raw_records import get_raw_record_by_hash
from data_intelligence_hub.repositories.sources import get_source
from data_intelligence_hub.services.normalization_service import normalize_raw_record
from data_intelligence_hub.services.signal_service import (
    detect_data_quality_anomaly,
    detect_signals_for_snapshots,
)


async def execute_collection_task(
    session: AsyncSession,
    workspace: Workspace,
    task: CollectionTask,
) -> TaskRun:
    started_at = datetime.now(UTC)
    workspace_id = workspace.id
    previous_task_status = task.status
    logs = [
        collector_log("task_run_created", "Manual run requested."),
        collector_log("collector_execution_started", f"Starting collector {task.collector_type}."),
        collector_log("task_status_running", "Task status changed to running."),
    ]
    task.status = "running"
    run = TaskRun(
        task_id=task.id,
        workspace_id=workspace.id,
        status="running",
        started_at=started_at,
        finished_at=None,
        records_count=0,
        entities_count=0,
        error_message=None,
        error_traceback=None,
        logs=logs,
        created_at=started_at,
    )
    session.add(run)
    await session.flush()
    task_id = task.id
    run_id = run.id
    await session.commit()

    records_count = 0
    entities_count = 0
    error_message: str | None = None
    error_traceback: str | None = None

    try:
        source = await _get_task_source_or_raise(session, workspace, task)
        collector = build_collector(task.collector_type, _collector_config(source, task))
        collector.validate_config()
        logs.append(collector_log("collector_config_valid", "Collector config validated."))
        result = await collector.collect()
        logs.extend(result.logs)
        for error in result.errors:
            logs.append(collector_log("collector_warning", error, level="warning"))
        records_count, entities_count, signals_count = await _store_raw_records(
            session=session,
            workspace=workspace,
            source=source,
            task=task,
            run=run,
            raw_records=result.raw_records,
            logs=logs,
        )
        if signals_count > 0:
            logs.append(collector_log("signals_detected", f"Detected {signals_count} signals."))
        status = _run_status(result_errors=result.errors, created_records=records_count)
    except Exception as exc:
        await session.rollback()
        refreshed_workspace = await session.get(Workspace, workspace_id)
        refreshed_task = await session.get(CollectionTask, task_id)
        refreshed_run = await session.get(TaskRun, run_id)
        if refreshed_workspace is None or refreshed_task is None or refreshed_run is None:
            raise
        workspace = refreshed_workspace
        task = refreshed_task
        run = refreshed_run
        status = "failed"
        error_message = str(exc) or exc.__class__.__name__
        error_traceback = traceback.format_exc()
        logs.append(collector_log("collector_failed", error_message, level="error"))

    finished_at = datetime.now(UTC)
    run.status = status
    run.finished_at = finished_at
    run.records_count = records_count
    run.entities_count = entities_count
    run.error_message = error_message
    run.error_traceback = error_traceback
    task.last_run_at = finished_at
    if status == "failed":
        task.failure_count += 1
    else:
        task.success_count += 1
    task.status = previous_task_status
    logs.append(collector_log("task_status_restored", f"Task status restored to {task.status}."))
    await session.flush()
    quality_signal = await detect_data_quality_anomaly(session, workspace, task, run)
    if quality_signal is not None:
        logs.append(
            collector_log(
                "signals_detected",
                f"Detected data quality signal {quality_signal.id}.",
            )
        )
    run.logs = [dict(log) for log in logs]
    flag_modified(run, "logs")
    await session.commit()
    await session.refresh(run)
    return run


async def _get_task_source_or_raise(
    session: AsyncSession,
    workspace: Workspace,
    task: CollectionTask,
) -> Source:
    source = await get_source(session, workspace.id, task.source_id)
    if source is None:
        raise CollectorError("Task source is missing")
    return source


async def _store_raw_records(
    session: AsyncSession,
    workspace: Workspace,
    source: Source,
    task: CollectionTask,
    run: TaskRun,
    raw_records: list[CollectorRawRecord],
    logs: list[dict[str, object]],
) -> tuple[int, int, int]:
    created_count = 0
    entities_count = 0
    signals_count = 0
    for raw_record in raw_records:
        content_hash = raw_record_content_hash(raw_record)
        existing = await get_raw_record_by_hash(
            session,
            workspace.id,
            source.id,
            content_hash,
        )
        if existing is not None:
            logs.append(
                collector_log(
                    "raw_record_deduplicated",
                    f"Skipped duplicate raw record {content_hash}.",
                )
            )
            continue
        collected_at = raw_record.collected_at or datetime.now(UTC)
        stored_raw_record = RawRecord(
            workspace_id=workspace.id,
            project_id=task.project_id,
            source_id=source.id,
            task_run_id=run.id,
            record_type=raw_record.record_type,
            source_url=raw_record.source_url,
            content=raw_record.content,
            content_hash=content_hash,
            screenshot_url=raw_record.screenshot_url,
            collected_at=collected_at,
            created_at=datetime.now(UTC),
        )
        session.add(stored_raw_record)
        await session.flush()
        snapshots = await normalize_raw_record(session, workspace, stored_raw_record)
        entities_count += len(snapshots)
        signals = await detect_signals_for_snapshots(session, workspace, snapshots)
        signals_count += len(signals)
        created_count += 1
    logs.append(collector_log("raw_records_stored", f"Stored {created_count} new raw records."))
    logs.append(collector_log("entities_normalized", f"Created {entities_count} snapshots."))
    return created_count, entities_count, signals_count


def raw_record_content_hash(raw_record: CollectorRawRecord) -> str:
    payload = {
        "record_type": raw_record.record_type,
        "source_url": raw_record.source_url,
        "content": raw_record.content,
    }
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _collector_config(source: Source, task: CollectionTask) -> dict[str, Any]:
    config = dict(source.config)
    if task.config:
        config.update(task.config)
    return config


def _run_status(result_errors: list[str], created_records: int) -> str:
    if result_errors and created_records > 0:
        return "partial_success"
    if result_errors:
        return "failed"
    return "success"
