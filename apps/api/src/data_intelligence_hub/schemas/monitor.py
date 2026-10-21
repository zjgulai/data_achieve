from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CreateMonitorRequest(BaseModel):
    project_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    endpoint_type: str = Field(min_length=1, max_length=100)
    params: dict[str, Any] = Field(default_factory=dict)
    interval_hours: Literal[1, 6, 24] = 24


class MonitorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    endpoint_type: str
    params: dict[str, Any]
    interval_hours: int
    status: str
    task_id: uuid.UUID | None
    last_checked_at: datetime | None
    last_new_count: int | None
    created_at: datetime