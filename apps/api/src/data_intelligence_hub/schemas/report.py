from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from data_intelligence_hub.models.report import Report

ReportType = Literal["daily"]


class ReportGenerateRequest(BaseModel):
    project_id: uuid.UUID | None = None
    report_type: ReportType = "daily"
    period_start: datetime | None = None
    period_end: datetime | None = None


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID | None
    report_type: str
    title: str
    content: str = Field(repr=False)
    status: str
    period_start: datetime
    period_end: datetime
    created_at: datetime

    @classmethod
    def from_model(cls, report: Report) -> ReportResponse:
        return cls.model_validate(report)
