from __future__ import annotations

import asyncio
import hashlib
import json
import traceback
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from data_intelligence_hub.collectors import CollectorError, CollectorRawRecord, build_collector
from data_intelligence_hub.collectors.base import collector_log
from data_intelligence_hub.collectors.empty_result_policy import (
    EmptyResultPolicy,
    empty_result_error,
    resolve_empty_result_policy,
)
from data_intelligence_hub.collectors.guarded_http import collection_scope
from data_intelligence_hub.collectors.outbound_policy import (
    POLICY_VERSION,
    CollectionPolicyDenied,
    assert_collector_allowed,
    is_policy_failure,
)
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.raw_records import get_raw_record_by_hash
from data_intelligence_hub.repositories.sources import get_source
from data_intelligence_hub.services.exceptions import TaskAlreadyRunningError, TaskNotRunnableError
from data_intelligence_hub.services.normalization_service import normalize_raw_record
from data_intelligence_hub.services.run_status import (
    EMPTY,
    FAILED,
    PARTIAL_SUCCESS,
    run_status,
)
from data_intelligence_hub.services.signal_service import (
    detect_data_quality_anomaly,
    detect_empty_output_anomaly,
    detect_signals_for_snapshots,
)
from data_intelligence_hub.services.task_schedule_policy import update_retry_state_after_run

# The service budget must stay above the Apify collector's inner wait
# (APIFY_RUN_WAIT_TIMEOUT = 600s in collectors/apify_actor.py). If the service
# budget is shorter, asyncio.wait_for cancels collect() first. The caller then
# sees only `collection_timeout`, while the Apify run keeps going and billing.
# The 60s margin covers the start-run POST (APIFY_TIMEOUT = 30s) and the 5s
# poll interval, so the collector can return its own structured timeout.
DEFAULT_COLLECTION_TIMEOUT_SECONDS = 660.0
MAX_COLLECTION_TIMEOUT_SECONDS = 1800.0
MIN_COLLECTION_TIMEOUT_SECONDS = 0.1

# Endpoints whose scans routinely run past the default budget, measured on the two
# production hosts on 2026-10-13: aliens_eye_selfcheck 444s and the three
# spiderfoot scans >300s on the slower (domestic) host, aliens_eye_recurse 252s.
#
# 1200s is chosen from both ends: it is well above every measured duration, below
# the nginx quick-collect ceiling (1800s, so the API answers instead of the proxy
# cutting the connection), and below the collector subprocess budgets
# (OSINT_PROC_TIMEOUT=800 -> 1600s for advanced/selfcheck; SPIDERFOOT_TIMEOUT=1500)
# so a runaway scan still surfaces as the collector's own structured timeout.
# Callers can override per request with `run_timeout_seconds`.
SLOW_ENDPOINT_TIMEOUT_SECONDS: dict[str, float] = {
    # Needs the full window: 391s on the fast host, but the slower (domestic) host
    # was still scanning when 1200s expired on 2026-10-13. Still below the nginx
    # ceiling so the API answers, and above the 1600s subprocess budget so a
    # runaway scan surfaces as the collector's own timeout.
    "aliens_eye_advanced": 1700.0,
    "aliens_eye_selfcheck": 1200.0,
    "aliens_eye_recurse": 1200.0,
    "spiderfoot_email_osint": 1200.0,
    "spiderfoot_subdomain_enum": 1200.0,
    "spiderfoot_attack_surface": 1200.0,
}


async def execute_collection_task(
    session: AsyncSession,
    workspace: Workspace,
    task: CollectionTask,
    idempotency_key_hash: str | None = None,
    *,
    trigger: str = "manual",
) -> TaskRun:
    started_at = datetime.now(UTC)
    workspace_id = workspace.id
    task = await _lock_task_for_run_or_raise(session, workspace, task)
    previous_task_status = task.status
    timeout_seconds = _collection_timeout_seconds(task.config)
    logs = [
        collector_log("task_run_created", f"Collection requested by {trigger}."),
        *_task_run_idempotency_logs(idempotency_key_hash),
        collector_log("collector_execution_started", f"Starting collector {task.collector_type}."),
        collector_log(
            "collector_timeout_configured",
            f"Collector run timeout set to {timeout_seconds:g}s.",
        ),
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
        assert_collector_allowed(task.collector_type)
        collector = build_collector(task.collector_type, _collector_config(source, task))
        collector.validate_config()
        logs.append(collector_log("collector_config_valid", "Collector config validated."))
        try:
            with collection_scope(task.collector_type) as budget:
                try:
                    result = await asyncio.wait_for(collector.collect(), timeout=timeout_seconds)
                finally:
                    audit = collector_log(
                        "outbound_policy_checked", "Collection safety policy applied."
                    )
                    audit.update(
                        {
                            "policy_version": POLICY_VERSION,
                            "trigger": trigger,
                            "collector_type": task.collector_type,
                            "task_run_id": str(run_id),
                            "task_id": str(task_id),
                            "http_requests_sent": budget.requests_sent if budget else None,
                            "approved_hosts_used": sorted(budget.hosts_used) if budget else [],
                        }
                    )
                    logs.append(audit)
        except TimeoutError as exc:
            raise CollectorError(
                f"collection_timeout: collector exceeded {timeout_seconds:g}s"
            ) from exc
        logs.extend(result.logs)
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
        collected_records = len(result.raw_records)
        policy = resolve_empty_result_policy(
            collector_type=task.collector_type,
            config=collector.config,
            collector_class=type(collector),
            task_config=task.config,
        )
        status, result_errors, empty_log = _resolve_run_status(
            result_errors=result.errors,
            collected_records=collected_records,
            created_records=records_count,
            policy=policy,
            collector_type=task.collector_type,
            endpoint_type=_endpoint_type(collector.config),
        )
        for error in result.errors:
            logs.append(collector_log("collector_warning", error, level="warning"))
        if empty_log is not None:
            logs.append(empty_log)
        if status in (FAILED, PARTIAL_SUCCESS) and result_errors:
            error_message = "; ".join(result_errors[:3])
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
        failed_log = collector_log("collector_failed", error_message, level="error")
        failed_log["failure_reason"] = _collection_failure_reason(error_message)
        if isinstance(exc, CollectionPolicyDenied):
            failed_log.update(
                {
                    "policy_version": POLICY_VERSION,
                    "policy_reason": exc.code,
                    "trigger": trigger,
                    "task_run_id": str(run_id),
                    "collector_type": task.collector_type,
                    "http_requests_sent": next(
                        (
                            log.get("http_requests_sent")
                            for log in reversed(logs)
                            if log.get("step") == "outbound_policy_checked"
                        ),
                        0,
                    ),
                }
            )
        logs.append(failed_log)

    finished_at = datetime.now(UTC)
    run.status = status
    run.finished_at = finished_at
    run.records_count = records_count
    run.entities_count = entities_count
    run.error_message = error_message
    run.error_traceback = error_traceback
    task.last_run_at = finished_at
    if status == FAILED:
        task.failure_count += 1
    elif status != EMPTY:
        task.success_count += 1
    next_task_config = (
        task.config
        if is_policy_failure(error_message)
        else update_retry_state_after_run(task.config, status)
    )
    if next_task_config != task.config:
        task.config = next_task_config
        flag_modified(task, "config")
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
    empty_signal = await detect_empty_output_anomaly(session, workspace, task, run)
    if empty_signal is not None:
        logs.append(
            collector_log(
                "signals_detected",
                f"Detected empty output signal {empty_signal.id}.",
            )
        )
    run.logs = [dict(log) for log in logs]
    flag_modified(run, "logs")
    await session.commit()
    await session.refresh(run)
    return run


async def _lock_task_for_run_or_raise(
    session: AsyncSession,
    workspace: Workspace,
    task: CollectionTask,
) -> CollectionTask:
    result = await session.execute(
        select(CollectionTask)
        .where(CollectionTask.id == task.id, CollectionTask.workspace_id == workspace.id)
        .with_for_update()
    )
    locked_task = result.scalar_one_or_none()
    if locked_task is None:
        raise CollectorError("Task is missing")
    if locked_task.status == "running":
        raise TaskAlreadyRunningError
    if locked_task.status != "enabled":
        raise TaskNotRunnableError
    return locked_task


async def _get_task_source_or_raise(
    session: AsyncSession,
    workspace: Workspace,
    task: CollectionTask,
) -> Source:
    source = await get_source(session, workspace.id, task.source_id)
    if source is None:
        raise CollectorError("Task source is missing")
    if not source.enabled:
        raise CollectionPolicyDenied("采集来源已停用")
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


def _task_run_idempotency_logs(idempotency_key_hash: str | None) -> list[dict[str, Any]]:
    if idempotency_key_hash is None:
        return []
    log = collector_log(
        "idempotency_key_recorded",
        "Recorded manual task run idempotency key hash.",
    )
    log.update(
        {
            "scope": "task_manual_run",
            "idempotency_key_hash": idempotency_key_hash,
            "raw_key_stored": False,
        }
    )
    return [log]


def _collector_config(source: Source, task: CollectionTask) -> dict[str, Any]:
    config = dict(source.config)
    if task.config:
        config.update(task.config)
    return config


def _collection_timeout_seconds(config: dict[str, Any] | None) -> float:
    if not config:
        return DEFAULT_COLLECTION_TIMEOUT_SECONDS
    value = config.get("run_timeout_seconds")
    if not isinstance(value, int | float):
        # No explicit budget: fall back to the per-endpoint default when the
        # endpoint is known to be slow, else the global default.
        endpoint_type = str(config.get("endpoint_type") or "")
        return SLOW_ENDPOINT_TIMEOUT_SECONDS.get(endpoint_type, DEFAULT_COLLECTION_TIMEOUT_SECONDS)
    return max(
        MIN_COLLECTION_TIMEOUT_SECONDS,
        min(float(value), MAX_COLLECTION_TIMEOUT_SECONDS),
    )


def _run_status(
    result_errors: list[str],
    collected_records: int,
    created_records: int,
) -> str:
    return run_status(
        result_errors=result_errors,
        collected_records=collected_records,
        created_records=created_records,
    )


def _endpoint_type(config: dict[str, Any]) -> str | None:
    value = config.get("endpoint_type")
    return value if isinstance(value, str) else None


def _resolve_run_status(
    *,
    result_errors: list[str],
    collected_records: int,
    created_records: int,
    policy: EmptyResultPolicy,
    collector_type: str,
    endpoint_type: str | None,
) -> tuple[str, list[str], dict[str, Any] | None]:
    """Apply the zero-record policy and return status, errors and a log entry.

    The `empty` status means the collector returned zero raw records without
    errors. A strict policy turns that state into `failed` and appends one
    error. A permissive policy keeps `empty` and emits a warning log.
    """
    status = _run_status(
        result_errors=result_errors,
        collected_records=collected_records,
        created_records=created_records,
    )
    errors = list(result_errors)
    if status != EMPTY:
        return status, errors, None

    details = {
        "collector_type": collector_type,
        "endpoint_type": endpoint_type,
        "allow_empty": policy.allow_empty,
        "min_expected_records": policy.min_expected_records,
        "collected_records": collected_records,
        "enforced": not policy.allow_empty,
    }
    if policy.allow_empty:
        log = collector_log(
            "collector_empty_result",
            (
                "collector returned 0 records "
                f"(collector_type={collector_type}, endpoint_type={endpoint_type}, "
                "allow_empty=true)"
            ),
            level="warning",
        )
        log.update(details)
        return EMPTY, errors, log

    message = empty_result_error(
        collector_type=collector_type,
        endpoint_type=endpoint_type,
        expected_records=policy.effective_min_expected_records,
    )
    errors.append(message)
    log = collector_log("collector_empty_result", message, level="error")
    log.update(details)
    log["failure_reason"] = _collection_failure_reason(message)
    return FAILED, errors, log


def _collection_failure_reason(message: str) -> str:
    normalized = message.strip().lower()
    if normalized.startswith("collector_empty_result"):
        return "empty_result"
    if is_policy_failure(normalized):
        return "policy_denied"
    if normalized.startswith("http_timeout") or normalized.startswith("collection_timeout"):
        return "timeout"
    if normalized.startswith("http_rate_limited"):
        return "rate_limited"
    if (
        normalized.startswith("collector config field is required")
        or normalized.startswith("collector is not registered")
        or normalized.startswith("url must be")
        or normalized.startswith("fields must be")
        or normalized.startswith("unsupported")
        or normalized.endswith("_not_detected")
        or normalized.endswith("_invalid_content")
    ):
        return "validation_failed"
    return "collector_failed"
