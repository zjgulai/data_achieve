from __future__ import annotations

import uuid
from datetime import datetime
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
    success_count: int
    failure_count: int
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime
    latest_run_status: str | None = None
    latest_run_error_message: str | None = None
    latest_run_records_count: int | None = None
    latest_run_entities_count: int | None = None
    latest_run_finished_at: datetime | None = None

    @classmethod
    def from_task(
        cls,
        task: CollectionTask,
        latest_run: TaskRun | None = None,
    ) -> CollectionTaskResponse:
        response = cls.model_validate(task)
        if latest_run is None:
            return response
        return response.model_copy(
            update={
                "latest_run_status": latest_run.status,
                "latest_run_error_message": latest_run.error_message,
                "latest_run_records_count": latest_run.records_count,
                "latest_run_entities_count": latest_run.entities_count,
                "latest_run_finished_at": latest_run.finished_at,
            }
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
