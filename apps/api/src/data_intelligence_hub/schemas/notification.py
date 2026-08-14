from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from data_intelligence_hub.models.notification import Notification
from data_intelligence_hub.services.notification_service import (
    EmailChannelStatus,
    EmailChannelTestResult,
    EmailProviderLiveGateResult,
    EmailProviderLiveSendReadiness,
    EmailProviderLiveSendResult,
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


class EmailChannelTestRequest(BaseModel):
    authorized: bool
    confirm_send: bool


class EmailChannelTestResponse(BaseModel):
    delivered: bool
    recipient_email: str
    status: EmailChannelStatusResponse
    reason: str | None
    tested_at: datetime
    provider_call_attempted: bool
    idempotency_replayed: bool = False
    idempotency_scope: str | None = None
    idempotency_key_hash: str | None = None

    @classmethod
    def from_result(cls, result: EmailChannelTestResult) -> EmailChannelTestResponse:
        return cls(
            delivered=result.delivered,
            recipient_email=result.recipient_email,
            status=EmailChannelStatusResponse.from_status(result.status),
            reason=result.reason,
            tested_at=result.tested_at,
            provider_call_attempted=result.provider_call_attempted,
            idempotency_replayed=result.idempotency_replayed,
            idempotency_scope=result.idempotency_scope,
            idempotency_key_hash=result.idempotency_key_hash,
        )


class EmailProviderLiveGateRequest(BaseModel):
    authorized: bool
    confirm_prepare: bool
    operation: Literal["email_channel_test", "report_send", "drift_alert_email"] = (
        "email_channel_test"
    )
    recipient_email: str | None = Field(default=None, max_length=255)
    max_provider_calls: int = Field(default=1, ge=1, le=5)
    expires_at: datetime | None = None
    note: str | None = Field(default=None, max_length=500)


class EmailProviderLiveGateResponse(BaseModel):
    id: uuid.UUID
    operation: str
    status: str
    recipient_email: str
    channel_status: EmailChannelStatusResponse
    blocked_reasons: list[str]
    provider_call_allowed: bool
    email_send_allowed: bool
    production_write_allowed: bool
    provider_call_attempted: bool
    max_provider_calls: int
    audit_fields: list[str]
    next_required_authorization: str
    prepared_at: datetime
    expires_at: datetime | None
    idempotency_replayed: bool = False
    idempotency_scope: str | None = None
    idempotency_key_hash: str | None = None

    @classmethod
    def from_result(
        cls,
        result: EmailProviderLiveGateResult,
    ) -> EmailProviderLiveGateResponse:
        return cls(
            id=result.id,
            operation=result.operation,
            status=result.status,
            recipient_email=result.recipient_email,
            channel_status=EmailChannelStatusResponse.from_status(result.channel_status),
            blocked_reasons=result.blocked_reasons,
            provider_call_allowed=result.provider_call_allowed,
            email_send_allowed=result.email_send_allowed,
            production_write_allowed=result.production_write_allowed,
            provider_call_attempted=result.provider_call_attempted,
            max_provider_calls=result.max_provider_calls,
            audit_fields=result.audit_fields,
            next_required_authorization=result.next_required_authorization,
            prepared_at=result.prepared_at,
            expires_at=result.expires_at,
            idempotency_replayed=result.idempotency_replayed,
            idempotency_scope=result.idempotency_scope,
            idempotency_key_hash=result.idempotency_key_hash,
        )


class EmailProviderLiveSendRequest(BaseModel):
    authorized: bool
    confirm_send: bool
    gate_run_id: uuid.UUID
    approval_id: str = Field(min_length=1, max_length=120)
    operation: Literal["email_channel_test", "report_send", "drift_alert_email"] = (
        "email_channel_test"
    )
    recipient_email: str | None = Field(default=None, max_length=255)


class EmailProviderLiveSendResponse(BaseModel):
    id: uuid.UUID
    gate_run_id: uuid.UUID
    approval_id: str
    operation: str
    status: str
    delivered: bool
    recipient_email: str
    channel_status: EmailChannelStatusResponse
    blocked_reasons: list[str]
    reason: str | None
    send_enabled: bool
    live_approval_required: bool
    recipient_allowlisted: bool
    provider_call_allowed: bool
    email_send_allowed: bool
    production_write_allowed: bool
    provider_call_attempted: bool
    audit_fields: list[str]
    next_required_authorization: str
    sent_at: datetime
    idempotency_replayed: bool = False
    idempotency_scope: str | None = None
    idempotency_key_hash: str | None = None

    @classmethod
    def from_result(
        cls,
        result: EmailProviderLiveSendResult,
    ) -> EmailProviderLiveSendResponse:
        return cls(
            id=result.id,
            gate_run_id=result.gate_run_id,
            approval_id=result.approval_id,
            operation=result.operation,
            status=result.status,
            delivered=result.delivered,
            recipient_email=result.recipient_email,
            channel_status=EmailChannelStatusResponse.from_status(result.channel_status),
            blocked_reasons=result.blocked_reasons,
            reason=result.reason,
            send_enabled=result.send_enabled,
            live_approval_required=result.live_approval_required,
            recipient_allowlisted=result.recipient_allowlisted,
            provider_call_allowed=result.provider_call_allowed,
            email_send_allowed=result.email_send_allowed,
            production_write_allowed=result.production_write_allowed,
            provider_call_attempted=result.provider_call_attempted,
            audit_fields=result.audit_fields,
            next_required_authorization=result.next_required_authorization,
            sent_at=result.sent_at,
            idempotency_replayed=result.idempotency_replayed,
            idempotency_scope=result.idempotency_scope,
            idempotency_key_hash=result.idempotency_key_hash,
        )


class EmailProviderLiveSendReadinessResponse(BaseModel):
    status: str
    channel_status: EmailChannelStatusResponse
    blocked_reasons: list[str]
    send_enabled: bool
    live_approval_required: bool
    recipient_allowlist_configured: bool
    recipient_allowlist_count: int
    provider_call_allowed: bool
    email_send_allowed: bool
    production_write_allowed: bool
    provider_call_attempted: bool
    required_authorization: str
    required_request_fields: list[str]
    checked_at: datetime

    @classmethod
    def from_readiness(
        cls,
        readiness: EmailProviderLiveSendReadiness,
    ) -> EmailProviderLiveSendReadinessResponse:
        return cls(
            status=readiness.status,
            channel_status=EmailChannelStatusResponse.from_status(
                readiness.channel_status
            ),
            blocked_reasons=readiness.blocked_reasons,
            send_enabled=readiness.send_enabled,
            live_approval_required=readiness.live_approval_required,
            recipient_allowlist_configured=readiness.recipient_allowlist_configured,
            recipient_allowlist_count=readiness.recipient_allowlist_count,
            provider_call_allowed=readiness.provider_call_allowed,
            email_send_allowed=readiness.email_send_allowed,
            production_write_allowed=readiness.production_write_allowed,
            provider_call_attempted=readiness.provider_call_attempted,
            required_authorization=readiness.required_authorization,
            required_request_fields=readiness.required_request_fields,
            checked_at=readiness.checked_at,
        )
