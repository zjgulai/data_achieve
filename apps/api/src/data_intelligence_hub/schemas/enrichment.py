from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StartEnrichmentRequest(BaseModel):
    project_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    query_template: str = Field(min_length=1, max_length=2000)
    items: list[dict[str, Any]] = Field(min_length=1, max_length=100)
    output_schema: dict[str, Any]


class EnrichmentRowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    row_index: int
    input: dict[str, Any]
    status: str
    output: dict[str, Any] | None
    citations: list[Any] | None
    cost_usd: str | None
    error: str | None


class EnrichmentJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    status: str
    total: int
    processed: int
    failed: int
    created_at: datetime
    finished_at: datetime | None


class EnrichmentJobDetailResponse(EnrichmentJobResponse):
    rows: list[EnrichmentRowResponse]