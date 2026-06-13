from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from data_intelligence_hub.models.report import Report, ReportAuditEvent
from data_intelligence_hub.schemas.intelligence import EvidenceResponse, IntelligenceResponse

ReportType = Literal["daily"]
ReportAuditEventType = Literal["generated", "sent", "share_link_copied", "share_sheet_opened"]


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


class ReportAuditEventCreateRequest(BaseModel):
    event_type: Literal["share_link_copied", "share_sheet_opened"]
    metadata: dict[str, str] = Field(default_factory=dict)


class ReportAuditEventResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    report_id: uuid.UUID
    actor_id: uuid.UUID | None
    event_type: str
    from_status: str | None
    to_status: str | None
    metadata: dict[str, str]
    created_at: datetime

    @classmethod
    def from_model(cls, event: ReportAuditEvent) -> ReportAuditEventResponse:
        metadata: dict[str, str] = {}
        if event.metadata_json:
            parsed = json.loads(event.metadata_json)
            metadata = {str(key): str(value) for key, value in parsed.items()}
        return cls(
            id=event.id,
            workspace_id=event.workspace_id,
            report_id=event.report_id,
            actor_id=event.actor_id,
            event_type=event.event_type,
            from_status=event.from_status,
            to_status=event.to_status,
            metadata=metadata,
            created_at=event.created_at,
        )
