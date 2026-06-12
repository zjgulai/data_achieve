from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    service: str
    environment: str
    status: str
    database: str
    scheduler_enabled: bool
