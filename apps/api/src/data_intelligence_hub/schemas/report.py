from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from data_intelligence_hub.models.report import Report
from data_intelligence_hub.schemas.intelligence import EvidenceResponse, IntelligenceResponse

ReportType = Literal["daily"]


class ReportGenerateRequest(BaseModel):
    project_id: uuid.UUID | None = None
    report_type: ReportType = "daily"
    period_start: datetime | None = None
    period_end: datetime | None = None

    @model_validator(mode="after")
    def validate_period(self) -> ReportGenerateRequest:
        if (
            self.period_start is not None
            and self.period_end is not None
            and self.period_end <= self.period_start
        ):
            msg = "period_end must be later than period_start"
            raise ValueError(msg)
        return self


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


class ReportEvidenceReferenceResponse(BaseModel):
    intelligence: IntelligenceResponse
    evidences: list[EvidenceResponse]
