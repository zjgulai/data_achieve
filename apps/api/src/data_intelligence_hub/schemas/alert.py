from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from data_intelligence_hub.models.alert import AlertEvent, AlertRule

AlertChannel = Literal["email", "in_app", "both"]
AlertEventStatus = Literal["triggered", "sent", "acknowledged", "muted", "resolved"]


class AlertRuleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    project_id: uuid.UUID | None = None
    signal_type: str = Field(default="*", min_length=1, max_length=30)
    condition: dict[str, Any]
    channel: AlertChannel = "in_app"
    enabled: bool = True


class AlertRuleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    project_id: uuid.UUID | None = None
    signal_type: str | None = Field(default=None, min_length=1, max_length=30)
    condition: dict[str, Any] | None = None
    channel: AlertChannel | None = None
    enabled: bool | None = None


class AlertEventStatusUpdateRequest(BaseModel):
    status: AlertEventStatus


class AlertRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID | None
    name: str
    signal_type: str
    condition: dict[str, Any]
    channel: str
    enabled: bool
    created_at: datetime

    @classmethod
    def from_model(cls, rule: AlertRule) -> AlertRuleResponse:
        return cls.model_validate(rule)


class AlertEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rule_id: uuid.UUID
    signal_id: uuid.UUID
    status: str
    payload: dict[str, Any]
    triggered_at: datetime
    sent_at: datetime | None

    @classmethod
    def from_model(cls, event: AlertEvent) -> AlertEventResponse:
        return cls.model_validate(event)
