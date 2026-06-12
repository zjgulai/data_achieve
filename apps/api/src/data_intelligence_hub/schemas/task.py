from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


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
