from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.services.task_schedule_policy import (
    freshness_target_hours,
    max_retry_attempts,
    next_run_at,
    retry_after_at,
    retry_attempts_used,
    retry_budget_exhausted,
    retry_delay_minutes,
    task_schedule_policy,
)


class CollectionTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    source_id: uuid.UUID
    collector_type: str
    name: str
    schedule_cron: str | None
    status: str
    config: dict[str, Any] | None
    project_name: str | None = None
    project_domain: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    schedule_policy: str = "manual_refresh_only"
    freshness_target_hours: int = 24
    freshness_status: str = "unknown"
    stale_hours: float | None = None
    next_run_at: datetime | None = None
    retry_after_at: datetime | None = None
    retry_delay_minutes: int = 15
    max_retry_attempts: int = 3
    retry_attempts_used: int = 0
    retry_budget_exhausted: bool = False
    success_count: int
    failure_count: int
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime
    latest_run_status: str | None = None
    latest_run_error_message: str | None = None
    latest_run_records_count: int | None = None
    latest_run_entities_count: int | None = None
    latest_run_started_at: datetime | None = None
    latest_run_finished_at: datetime | None = None
    latest_run_created_at: datetime | None = None

    @classmethod
    def from_task(
        cls,
        task: CollectionTask,
        latest_run: TaskRun | None = None,
        project_name: str | None = None,
        project_domain: str | None = None,
        source_name: str | None = None,
        source_url: str | None = None,
        now: datetime | None = None,
    ) -> CollectionTaskResponse:
        response = cls.model_validate(task)
        current_time = now or datetime.now(UTC)
        target_hours = freshness_target_hours(task.config)
        freshness_status, stale_hours = _freshness_state(
            task=task,
            latest_run=latest_run,
            freshness_target_hours=target_hours,
            now=current_time,
        )
        updates: dict[str, Any] = {
            "project_name": project_name,
            "project_domain": project_domain,
            "source_name": source_name,
            "source_url": source_url,
            "schedule_policy": task_schedule_policy(task.config),
            "freshness_target_hours": target_hours,
            "freshness_status": freshness_status,
            "stale_hours": stale_hours,
            "next_run_at": next_run_at(task, latest_run, current_time),
            "retry_after_at": retry_after_at(task, latest_run),
            "retry_delay_minutes": retry_delay_minutes(task.config),
            "max_retry_attempts": max_retry_attempts(task.config),
            "retry_attempts_used": retry_attempts_used(task.config),
            "retry_budget_exhausted": retry_budget_exhausted(task, latest_run),
        }
        if latest_run is None:
            return response.model_copy(update=updates)
        updates.update(
            {
                "latest_run_status": latest_run.status,
                "latest_run_error_message": latest_run.error_message,
                "latest_run_records_count": latest_run.records_count,
                "latest_run_entities_count": latest_run.entities_count,
                "latest_run_started_at": latest_run.started_at,
                "latest_run_finished_at": latest_run.finished_at,
                "latest_run_created_at": latest_run.created_at,
            }
        )
        return response.model_copy(
            update=updates
        )


class TaskRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    workspace_id: uuid.UUID
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    records_count: int
    entities_count: int
    error_message: str | None
    error_traceback: str | None
    logs: list[dict[str, Any]]
    created_at: datetime
    idempotency_replayed: bool = False
    idempotency_scope: str | None = None
    idempotency_key_hash: str | None = None

    @classmethod
    def from_run(
        cls,
        run: TaskRun,
        *,
        idempotency_replayed: bool = False,
        idempotency_key_hash: str | None = None,
    ) -> TaskRunResponse:
        response = cls.model_validate(run)
        detected_key_hash = idempotency_key_hash or _task_run_idempotency_key_hash(run.logs)
        return response.model_copy(
            update={
                "idempotency_replayed": idempotency_replayed,
                "idempotency_scope": "task_manual_run" if detected_key_hash else None,
                "idempotency_key_hash": detected_key_hash,
            }
        )


def _task_run_idempotency_key_hash(logs: list[dict[str, Any]]) -> str | None:
    for log in logs:
        if log.get("step") != "idempotency_key_recorded":
            continue
        if log.get("scope") != "task_manual_run":
            continue
        idempotency_key_hash = log.get("idempotency_key_hash")
        if isinstance(idempotency_key_hash, str) and idempotency_key_hash:
            return idempotency_key_hash
    return None


def _freshness_state(
    *,
    task: CollectionTask,
    latest_run: TaskRun | None,
    freshness_target_hours: int,
    now: datetime,
) -> tuple[str, float | None]:
    if task.status == "running":
        return "running", None
    if task.status in {"paused", "disabled"}:
        return task.status, None
    if latest_run is not None and latest_run.status == "failed":
        if retry_budget_exhausted(task, latest_run):
            return "retry_exhausted", None
        return "failed", None
    if task.last_run_at is None:
        return "never_run", None

    age_hours = (_ensure_aware(now) - _ensure_aware(task.last_run_at)).total_seconds() / 3600
    stale_hours = round(max(age_hours - freshness_target_hours, 0.0), 2)
    if age_hours > freshness_target_hours:
        return "stale", stale_hours
    return "fresh", stale_hours


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
