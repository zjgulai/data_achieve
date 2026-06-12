from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class EntityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    entity_type: str
    external_id: str
    canonical_url: str | None
    name: str
    domain: str
    latest_snapshot_id: uuid.UUID | None
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime


class EntitySnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    raw_record_id: uuid.UUID
    snapshot_data: dict[str, Any]
    metrics: dict[str, Any]
    captured_at: datetime
    created_at: datetime
