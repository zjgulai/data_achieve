from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class RawRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    source_id: uuid.UUID | None
    task_run_id: uuid.UUID | None
    workflow_run_id: uuid.UUID | None = None
    workflow_step_run_id: uuid.UUID | None = None
    workflow_lineage_contract_version: str | None = None
    record_type: str
    source_url: str | None
    content: dict[str, Any] | list[Any]
    content_hash: str
    screenshot_url: str | None
    collected_at: datetime
    created_at: datetime
