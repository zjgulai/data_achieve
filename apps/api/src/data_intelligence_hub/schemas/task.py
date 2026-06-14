from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from data_intelligence_hub.models.task import CollectionTask, TaskRun


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
    freshness_target_hours: int = 24
    freshness_status: str = "unknown"
    stale_hours: float | None = None
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
        freshness_target_hours = _freshness_target_hours(task.config)
        freshness_status, stale_hours = _freshness_state(
            task=task,
            latest_run=latest_run,
            freshness_target_hours=freshness_target_hours,
            now=now or datetime.now(UTC),
        )
        updates: dict[str, Any] = {
            "project_name": project_name,
            "project_domain": project_domain,
            "source_name": source_name,
            "source_url": source_url,
            "freshness_target_hours": freshness_target_hours,
            "freshness_status": freshness_status,
            "stale_hours": stale_hours,
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


def _freshness_target_hours(config: dict[str, Any] | None) -> int:
    if config is None:
        return 24
    value = config.get("freshness_target_hours")
    if isinstance(value, int | float) and value > 0:
        return int(value)
    return 24


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
