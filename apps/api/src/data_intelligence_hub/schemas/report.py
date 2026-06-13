from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from data_intelligence_hub.models.report import Report, ReportAuditEvent, ReportSubscription
from data_intelligence_hub.schemas.intelligence import EvidenceResponse, IntelligenceResponse

ReportType = Literal["daily"]
ReportAuditEventType = Literal["generated", "sent", "share_link_copied", "share_sheet_opened"]
ReportDeliveryChannel = Literal["in_app", "email"]


def default_report_delivery_channels() -> list[ReportDeliveryChannel]:
    return ["in_app"]


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


class ReportSubscriptionUpsertRequest(BaseModel):
    project_id: uuid.UUID | None = None
    report_type: ReportType = "daily"
    schedule_time: str = "09:00"
    timezone: str = "Asia/Shanghai"
    channels: list[ReportDeliveryChannel] = Field(default_factory=default_report_delivery_channels)
    enabled: bool = True

    @field_validator("schedule_time")
    @classmethod
    def validate_schedule_time(cls, value: str) -> str:
        parts = value.split(":")
        if len(parts) != 2 or not all(part.isdigit() for part in parts):
            msg = "schedule_time must use HH:MM"
            raise ValueError(msg)
        hour = int(parts[0])
        minute = int(parts[1])
        if hour > 23 or minute > 59:
            msg = "schedule_time must use a valid 24-hour time"
            raise ValueError(msg)
        return f"{hour:02d}:{minute:02d}"

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            msg = "timezone must be an IANA timezone"
            raise ValueError(msg) from exc
        return value

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, value: list[ReportDeliveryChannel]) -> list[ReportDeliveryChannel]:
        channels = list(dict.fromkeys(value))
        if not channels:
            msg = "at least one delivery channel is required"
            raise ValueError(msg)
        return channels


class ReportSubscriptionResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    project_id: uuid.UUID | None
    report_type: str
    schedule_time: str
    timezone: str
    channels: list[str]
    enabled: bool
    next_run_at: datetime | None
    last_sent_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, subscription: ReportSubscription) -> ReportSubscriptionResponse:
        return cls(
            id=subscription.id,
            workspace_id=subscription.workspace_id,
            user_id=subscription.user_id,
            project_id=subscription.project_id,
            report_type=subscription.report_type,
            schedule_time=subscription.schedule_time,
            timezone=subscription.timezone,
            channels=list(subscription.channels),
            enabled=subscription.enabled,
            next_run_at=subscription.next_run_at,
            last_sent_at=subscription.last_sent_at,
            created_at=subscription.created_at,
            updated_at=subscription.updated_at,
        )
