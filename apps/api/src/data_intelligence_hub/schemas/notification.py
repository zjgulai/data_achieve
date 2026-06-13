from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from data_intelligence_hub.models.notification import Notification
from data_intelligence_hub.services.notification_service import (
    EmailChannelStatus,
    EmailChannelTestResult,
)


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    body: str
    notification_type: str
    reference_type: str
    reference_id: uuid.UUID
    is_read: bool
    created_at: datetime

    @classmethod
    def from_model(cls, notification: Notification) -> NotificationResponse:
        return cls.model_validate(notification)


class NotificationReadAllResponse(BaseModel):
    updated_count: int


class NotificationReadBulkRequest(BaseModel):
    notification_ids: list[uuid.UUID] = Field(min_length=1)


class EmailChannelStatusResponse(BaseModel):
    status: str
    configured: bool
    missing_settings: list[str]
    host_configured: bool
    port: int
    sender_configured: bool
    auth_configured: bool
    tls_mode: str
    reason: str | None

    @classmethod
    def from_status(cls, status: EmailChannelStatus) -> EmailChannelStatusResponse:
        return cls(
            status=status.status,
            configured=status.configured,
            missing_settings=status.missing_settings,
            host_configured=status.host_configured,
            port=status.port,
            sender_configured=status.sender_configured,
            auth_configured=status.auth_configured,
            tls_mode=status.tls_mode,
            reason=status.reason,
        )


class EmailChannelTestResponse(BaseModel):
    delivered: bool
    recipient_email: str
    status: EmailChannelStatusResponse
    reason: str | None
    tested_at: datetime

    @classmethod
    def from_result(cls, result: EmailChannelTestResult) -> EmailChannelTestResponse:
        return cls(
            delivered=result.delivered,
            recipient_email=result.recipient_email,
            status=EmailChannelStatusResponse.from_status(result.status),
            reason=result.reason,
            tested_at=result.tested_at,
        )
