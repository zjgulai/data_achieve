from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SourceType = Literal[
    "github_repo",
    "github_topic",
    "generic_web",
    "manual_json",
    "ecommerce_product_discovery",
    "ecommerce_product_page",
]


class SourceCreateRequest(BaseModel):
    project_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    type: SourceType
    url: str | None = Field(default=None, max_length=5000)
    config: dict[str, Any]
    schedule_cron: str | None = Field(default=None, max_length=50)


class SourceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    url: str | None = Field(default=None, max_length=5000)
    config: dict[str, Any] | None = None
    schedule_cron: str | None = Field(default=None, max_length=50)


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    type: str
    url: str | None
    config: dict[str, Any]
    schedule_cron: str | None
    enabled: bool
    created_at: datetime
    updated_at: datetime


class SourceTestResponse(BaseModel):
    status: Literal["config_valid"]
    collector_type: str
    message: str
