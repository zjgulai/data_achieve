from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    service: str
    environment: str
    status: str
    database: str
    database_schema: str = Field(alias="schema")
    schema_revision: str | None
    schema_head: str | None
    scheduler_enabled: bool
