from __future__ import annotations

import asyncio
import hashlib
import json
import smtplib
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.core.config import Settings, get_settings
from data_intelligence_hub.models.notification import (
    EmailChannelTestRun,
    EmailProviderLiveGateRun,
    EmailProviderLiveSendRun,
    Notification,
)
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.notifications import (
    create_email_channel_test_run,
    create_email_provider_live_gate_run,
    create_email_provider_live_send_run,
    create_notification,
    get_email_channel_test_run_by_idempotency_key_hash,
    get_email_provider_live_gate_run,
    get_email_provider_live_gate_run_by_idempotency_key_hash,
    get_email_provider_live_send_run_by_idempotency_key_hash,
    get_notification,
    list_notifications,
    list_notifications_by_ids,
)
from data_intelligence_hub.services.exceptions import (
    EmailChannelTestAuthorizationError,
    EmailChannelTestConfirmationRequiredError,
    EmailProviderLiveGateAuthorizationError,
    EmailProviderLiveGateConfirmationRequiredError,
    EmailProviderLiveGateRunNotFoundError,
    EmailProviderLiveSendAuthorizationError,
    EmailProviderLiveSendConfirmationRequiredError,
    EmailProviderLiveSendIdempotencyRequiredError,
    NotificationNotFoundError,
)

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class EmailDeliveryResult:
    delivered: bool
    reason: str | None = None


EmailSender = Callable[[str, str, str], Awaitable[EmailDeliveryResult]]


@dataclass(frozen=True)
class EmailChannelStatus:
    status: str
    configured: bool
    missing_settings: list[str]
    host_configured: bool
    port: int
    sender_configured: bool
    auth_configured: bool
    tls_mode: str
    reason: str | None = None


@dataclass(frozen=True)
class EmailChannelTestResult:
    delivered: bool
    recipient_email: str
    status: EmailChannelStatus
    reason: str | None
    tested_at: datetime
    provider_call_attempted: bool
    idempotency_replayed: bool = False
    idempotency_scope: str | None = None
    idempotency_key_hash: str | None = None


@dataclass(frozen=True)
class EmailProviderLiveGateResult:
    id: uuid.UUID
    operation: str
    status: str
    recipient_email: str
    channel_status: EmailChannelStatus
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


@dataclass(frozen=True)
class EmailProviderLiveSendResult:
    id: uuid.UUID
    gate_run_id: uuid.UUID
    approval_id: str
    operation: str
    status: str
    delivered: bool
    recipient_email: str
    channel_status: EmailChannelStatus
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


@dataclass(frozen=True)
class EmailProviderLiveSendReadiness:
    status: str
    channel_status: EmailChannelStatus
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


EMAIL_CHANNEL_TEST_IDEMPOTENCY_SCOPE = "email_channel_test"
EMAIL_PROVIDER_LIVE_GATE_IDEMPOTENCY_SCOPE = "email_provider_live_gate"
EMAIL_PROVIDER_LIVE_SEND_IDEMPOTENCY_SCOPE = "email_provider_live_send"


async def create_in_app_notification(
    session: AsyncSession,
    user_id: uuid.UUID,
    title: str,
    body: str,
    notification_type: str,
    reference_type: str,
    reference_id: uuid.UUID,
) -> Notification:
    return await create_notification(
        session,
        Notification(
            user_id=user_id,
            title=title,
            body=body,
            notification_type=notification_type,
            reference_type=reference_type,
            reference_id=reference_id,
            is_read=False,
        ),
    )


async def get_user_notifications(
    session: AsyncSession,
    user: User,
    is_read: bool | None,
) -> list[Notification]:
    return await list_notifications(session, user.id, is_read=is_read)


async def mark_notification_read(
    session: AsyncSession,
    user: User,
    notification_id: uuid.UUID,
) -> Notification:
    notification = await get_notification(session, user.id, notification_id)
    if notification is None:
        raise NotificationNotFoundError
    notification.is_read = True
    await session.commit()
    await session.refresh(notification)
    return notification


async def mark_all_notifications_read(session: AsyncSession, user: User) -> int:
    notifications = await list_notifications(session, user.id, is_read=False)
    for notification in notifications:
        notification.is_read = True
    await session.commit()
    return len(notifications)


async def mark_notifications_read(
    session: AsyncSession,
    user: User,
    notification_ids: list[uuid.UUID],
) -> int:
    notifications = await list_notifications_by_ids(
        session=session,
        user_id=user.id,
        notification_ids=list(dict.fromkeys(notification_ids)),
    )
    updated_count = 0
    for notification in notifications:
        if notification.is_read:
            continue
        notification.is_read = True
        updated_count += 1
    await session.commit()
    return updated_count


def get_email_channel_status() -> EmailChannelStatus:
    settings = get_settings()
    return _build_email_channel_status(settings)


def get_email_provider_live_send_readiness() -> EmailProviderLiveSendReadiness:
    settings = get_settings()
    channel_status = _build_email_channel_status(settings)
    allowlist_count = len(
        {
            item.strip().lower()
            for item in settings.email_live_recipient_allowlist
            if item.strip()
        }
    )
    blocked_reasons = _email_provider_live_send_readiness_blockers(
        settings=settings,
        channel_status=channel_status,
        allowlist_count=allowlist_count,
    )
    readiness_status = "blocked" if blocked_reasons else "ready_pending_l4_authorization"
    return EmailProviderLiveSendReadiness(
        status=readiness_status,
        channel_status=channel_status,
        blocked_reasons=blocked_reasons,
        send_enabled=settings.email_live_send_enabled,
        live_approval_required=settings.email_live_approval_required,
        recipient_allowlist_configured=allowlist_count > 0,
        recipient_allowlist_count=allowlist_count,
        provider_call_allowed=False,
        email_send_allowed=False,
        production_write_allowed=False,
        provider_call_attempted=False,
        required_authorization="L4_authorized_live_email_send",
        required_request_fields=[
            "authorized",
            "confirm_send",
            "gate_run_id",
            "approval_id",
            "operation",
            "Idempotency-Key",
        ],
        checked_at=datetime.now(UTC),
    )


async def test_email_channel(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    *,
    authorized: bool,
    confirm_send: bool,
    idempotency_key: str | None = None,
) -> EmailChannelTestResult:
    if not authorized:
        raise EmailChannelTestAuthorizationError
    if not confirm_send:
        raise EmailChannelTestConfirmationRequiredError

    status = get_email_channel_status()
    idempotency_key_hash = _email_channel_test_idempotency_key_hash(
        workspace_id=workspace.id,
        user_id=user.id,
        recipient_email=user.email,
        idempotency_key=idempotency_key,
    )
    if idempotency_key_hash is not None:
        existing_run = await get_email_channel_test_run_by_idempotency_key_hash(
            session=session,
            workspace_id=workspace.id,
            user_id=user.id,
            idempotency_scope=EMAIL_CHANNEL_TEST_IDEMPOTENCY_SCOPE,
            idempotency_key_hash=idempotency_key_hash,
        )
        if existing_run is not None:
            return _email_channel_test_result_from_run(
                existing_run,
                idempotency_replayed=True,
            )

    provider_call_attempted = status.configured
    if status.configured:
        result = await send_email_notification(
            recipient_email=user.email,
            subject="Data Achieve 邮件通道测试",
            body=(
                "这是一封 Data Achieve 邮件通道测试邮件。"
                "如果你收到它，说明当前 SMTP 配置可以完成基础投递。"
            ),
        )
    else:
        result = EmailDeliveryResult(delivered=False, reason=status.reason)
    tested_at = datetime.now(UTC)
    test_run = await create_email_channel_test_run(
        session,
        EmailChannelTestRun(
            workspace_id=workspace.id,
            user_id=user.id,
            recipient_email=user.email,
            delivered=result.delivered,
            reason=result.reason,
            status_snapshot=_email_channel_status_snapshot(status),
            provider_call_attempted=provider_call_attempted,
            idempotency_scope=(
                EMAIL_CHANNEL_TEST_IDEMPOTENCY_SCOPE
                if idempotency_key_hash is not None
                else None
            ),
            idempotency_key_hash=idempotency_key_hash,
            created_at=tested_at,
        ),
    )
    await session.commit()
    await session.refresh(test_run)
    return EmailChannelTestResult(
        delivered=result.delivered,
        recipient_email=user.email,
        status=status,
        reason=result.reason,
        tested_at=test_run.created_at,
        provider_call_attempted=provider_call_attempted,
        idempotency_replayed=False,
        idempotency_scope=(
            EMAIL_CHANNEL_TEST_IDEMPOTENCY_SCOPE
            if idempotency_key_hash is not None
            else None
        ),
        idempotency_key_hash=idempotency_key_hash,
    )


async def prepare_email_provider_live_gate(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    *,
    authorized: bool,
    confirm_prepare: bool,
    operation: str,
    recipient_email: str | None,
    max_provider_calls: int,
    expires_at: datetime | None = None,
    note: str | None = None,
    idempotency_key: str | None = None,
) -> EmailProviderLiveGateResult:
    if not authorized:
        raise EmailProviderLiveGateAuthorizationError
    if not confirm_prepare:
        raise EmailProviderLiveGateConfirmationRequiredError

    normalized_recipient = (recipient_email or user.email).strip()
    status = get_email_channel_status()
    idempotency_key_hash = _email_provider_live_gate_idempotency_key_hash(
        workspace_id=workspace.id,
        user_id=user.id,
        operation=operation,
        recipient_email=normalized_recipient,
        max_provider_calls=max_provider_calls,
        expires_at=expires_at,
        idempotency_key=idempotency_key,
    )
    if idempotency_key_hash is not None:
        existing_run = await get_email_provider_live_gate_run_by_idempotency_key_hash(
            session=session,
            workspace_id=workspace.id,
            user_id=user.id,
            idempotency_scope=EMAIL_PROVIDER_LIVE_GATE_IDEMPOTENCY_SCOPE,
            idempotency_key_hash=idempotency_key_hash,
        )
        if existing_run is not None:
            return _email_provider_live_gate_result_from_run(
                existing_run,
                idempotency_replayed=True,
            )

    decision_snapshot = _email_provider_live_gate_decision_snapshot(status)
    prepared_at = datetime.now(UTC)
    gate_run = await create_email_provider_live_gate_run(
        session,
        EmailProviderLiveGateRun(
            workspace_id=workspace.id,
            user_id=user.id,
            operation=operation,
            recipient_email=normalized_recipient,
            status=str(decision_snapshot["status"]),
            max_provider_calls=max_provider_calls,
            expires_at=expires_at,
            status_snapshot=_email_channel_status_snapshot(status),
            request_snapshot={
                "operation": operation,
                "recipient_email": normalized_recipient,
                "max_provider_calls": max_provider_calls,
                "expires_at": expires_at.isoformat() if expires_at is not None else None,
                "authorized": True,
                "confirm_prepare": True,
                "note_present": bool(note),
                "raw_idempotency_key_stored": False,
            },
            decision_snapshot=decision_snapshot,
            provider_call_allowed=False,
            email_send_allowed=False,
            production_write_allowed=False,
            provider_call_attempted=False,
            idempotency_scope=(
                EMAIL_PROVIDER_LIVE_GATE_IDEMPOTENCY_SCOPE
                if idempotency_key_hash is not None
                else None
            ),
            idempotency_key_hash=idempotency_key_hash,
            created_at=prepared_at,
        ),
    )
    await session.commit()
    await session.refresh(gate_run)
    return _email_provider_live_gate_result_from_run(
        gate_run,
        idempotency_replayed=False,
    )


async def execute_email_provider_live_send_gate(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    *,
    authorized: bool,
    confirm_send: bool,
    gate_run_id: uuid.UUID,
    approval_id: str,
    operation: str,
    recipient_email: str | None,
    idempotency_key: str | None,
    settings: Settings | None = None,
    email_sender: EmailSender | None = None,
) -> EmailProviderLiveSendResult:
    if not authorized:
        raise EmailProviderLiveSendAuthorizationError
    if not confirm_send:
        raise EmailProviderLiveSendConfirmationRequiredError

    normalized_key = (idempotency_key or "").strip()
    if not normalized_key:
        raise EmailProviderLiveSendIdempotencyRequiredError

    gate_run = await get_email_provider_live_gate_run(
        session=session,
        workspace_id=workspace.id,
        user_id=user.id,
        gate_run_id=gate_run_id,
    )
    if gate_run is None:
        raise EmailProviderLiveGateRunNotFoundError

    normalized_recipient = (recipient_email or gate_run.recipient_email).strip()
    normalized_approval = approval_id.strip()
    idempotency_key_hash = _email_provider_live_send_idempotency_key_hash(
        workspace_id=workspace.id,
        user_id=user.id,
        gate_run_id=gate_run.id,
        approval_id=normalized_approval,
        operation=operation,
        recipient_email=normalized_recipient,
        idempotency_key=normalized_key,
    )
    existing_run = await get_email_provider_live_send_run_by_idempotency_key_hash(
        session=session,
        workspace_id=workspace.id,
        user_id=user.id,
        idempotency_scope=EMAIL_PROVIDER_LIVE_SEND_IDEMPOTENCY_SCOPE,
        idempotency_key_hash=idempotency_key_hash,
    )
    if existing_run is not None:
        return _email_provider_live_send_result_from_run(
            existing_run,
            idempotency_replayed=True,
        )

    active_settings = settings or get_settings()
    channel_status = _build_email_channel_status(active_settings)
    recipient_allowlisted = _email_recipient_allowlisted(
        normalized_recipient,
        active_settings.email_live_recipient_allowlist,
    )
    blocked_reasons = _email_provider_live_send_blocked_reasons(
        settings=active_settings,
        channel_status=channel_status,
        gate_run=gate_run,
        operation=operation,
        recipient_email=normalized_recipient,
        approval_id=normalized_approval,
        recipient_allowlisted=recipient_allowlisted,
    )
    provider_call_allowed = not blocked_reasons
    email_send_allowed = not blocked_reasons
    provider_call_attempted = False
    delivery_result = EmailDeliveryResult(
        delivered=False,
        reason=blocked_reasons[0] if blocked_reasons else None,
    )
    if provider_call_allowed:
        provider_call_attempted = True
        sender = email_sender or send_email_notification
        delivery_result = await sender(
            normalized_recipient,
            "Data Achieve live email send gate",
            (
                "This message was sent by an explicitly authorized Data Achieve "
                "live-send gate run."
            ),
        )
    send_status = _email_provider_live_send_status(
        blocked_reasons=blocked_reasons,
        delivery_result=delivery_result,
    )
    sent_at = datetime.now(UTC)
    decision_snapshot = _email_provider_live_send_decision_snapshot(
        status=send_status,
        blocked_reasons=blocked_reasons,
        delivery_result=delivery_result,
        send_enabled=active_settings.email_live_send_enabled,
        live_approval_required=active_settings.email_live_approval_required,
        recipient_allowlisted=recipient_allowlisted,
        provider_call_allowed=provider_call_allowed,
        email_send_allowed=email_send_allowed,
        provider_call_attempted=provider_call_attempted,
    )
    send_run = await create_email_provider_live_send_run(
        session,
        EmailProviderLiveSendRun(
            workspace_id=workspace.id,
            user_id=user.id,
            gate_run_id=gate_run.id,
            approval_id=normalized_approval,
            operation=operation,
            recipient_email=normalized_recipient,
            status=send_status,
            delivered=delivery_result.delivered,
            reason=delivery_result.reason,
            status_snapshot=_email_channel_status_snapshot(channel_status),
            request_snapshot={
                "gate_run_id": str(gate_run.id),
                "approval_id": normalized_approval,
                "operation": operation,
                "recipient_email": normalized_recipient,
                "authorized": True,
                "confirm_send": True,
                "raw_idempotency_key_stored": False,
            },
            decision_snapshot=decision_snapshot,
            provider_call_allowed=provider_call_allowed,
            email_send_allowed=email_send_allowed,
            production_write_allowed=False,
            provider_call_attempted=provider_call_attempted,
            send_enabled=active_settings.email_live_send_enabled,
            live_approval_required=active_settings.email_live_approval_required,
            recipient_allowlisted=recipient_allowlisted,
            idempotency_scope=EMAIL_PROVIDER_LIVE_SEND_IDEMPOTENCY_SCOPE,
            idempotency_key_hash=idempotency_key_hash,
            created_at=sent_at,
        ),
    )
    await session.commit()
    await session.refresh(send_run)
    return _email_provider_live_send_result_from_run(
        send_run,
        idempotency_replayed=False,
    )


async def send_email_notification(
    recipient_email: str,
    subject: str,
    body: str,
) -> EmailDeliveryResult:
    settings = get_settings()
    channel_status = _build_email_channel_status(settings)
    if not channel_status.configured:
        return EmailDeliveryResult(delivered=False, reason=channel_status.reason)
    smtp_host = settings.smtp_host
    sender = settings.smtp_from or settings.smtp_user
    if smtp_host is None or sender is None:
        return EmailDeliveryResult(delivered=False, reason="smtp_not_configured")

    try:
        await asyncio.to_thread(
            _send_email_sync,
            settings,
            smtp_host,
            sender,
            recipient_email,
            subject,
            body,
        )
    except Exception as exc:
        logger.exception("email_delivery_failed", recipient_email=recipient_email)
        return EmailDeliveryResult(delivered=False, reason=exc.__class__.__name__)
    return EmailDeliveryResult(delivered=True)


def _send_email_sync(
    settings: Settings,
    smtp_host: str,
    sender: str,
    recipient_email: str,
    subject: str,
    body: str,
) -> None:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient_email
    message["Subject"] = subject
    message.set_content(body)

    if settings.smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, settings.smtp_port, timeout=10) as smtp:
            _login_if_configured(smtp, settings)
            smtp.send_message(message)
        return

    with smtplib.SMTP(smtp_host, settings.smtp_port, timeout=10) as smtp:
        smtp.starttls()
        _login_if_configured(smtp, settings)
        smtp.send_message(message)


def _login_if_configured(smtp: smtplib.SMTP, settings: Settings) -> None:
    if settings.smtp_user and settings.smtp_password:
        smtp.login(settings.smtp_user, settings.smtp_password)


def _build_email_channel_status(settings: Settings) -> EmailChannelStatus:
    missing_settings: list[str] = []
    sender = settings.smtp_from or settings.smtp_user
    if not settings.smtp_host:
        missing_settings.append("SMTP_HOST")
    if not sender:
        missing_settings.append("SMTP_FROM")

    auth_partial = bool(settings.smtp_user) != bool(settings.smtp_password)
    if auth_partial:
        if not settings.smtp_user:
            missing_settings.append("SMTP_USER")
        if not settings.smtp_password:
            missing_settings.append("SMTP_PASSWORD")

    if not settings.smtp_host or not sender:
        reason = "smtp_not_configured"
        status = "not_configured"
    elif auth_partial:
        reason = "smtp_auth_incomplete"
        status = "misconfigured"
    else:
        reason = None
        status = "ready"

    return EmailChannelStatus(
        status=status,
        configured=reason is None,
        missing_settings=missing_settings,
        host_configured=bool(settings.smtp_host),
        port=settings.smtp_port,
        sender_configured=bool(sender),
        auth_configured=bool(settings.smtp_user and settings.smtp_password),
        tls_mode="ssl" if settings.smtp_port == 465 else "starttls",
        reason=reason,
    )


def _email_channel_test_result_from_run(
    test_run: EmailChannelTestRun,
    *,
    idempotency_replayed: bool,
) -> EmailChannelTestResult:
    return EmailChannelTestResult(
        delivered=test_run.delivered,
        recipient_email=test_run.recipient_email,
        status=_email_channel_status_from_snapshot(test_run.status_snapshot),
        reason=test_run.reason,
        tested_at=test_run.created_at,
        provider_call_attempted=False if idempotency_replayed else test_run.provider_call_attempted,
        idempotency_replayed=idempotency_replayed,
        idempotency_scope=test_run.idempotency_scope,
        idempotency_key_hash=test_run.idempotency_key_hash,
    )


def _email_provider_live_gate_result_from_run(
    gate_run: EmailProviderLiveGateRun,
    *,
    idempotency_replayed: bool,
) -> EmailProviderLiveGateResult:
    return EmailProviderLiveGateResult(
        id=gate_run.id,
        operation=gate_run.operation,
        status=gate_run.status,
        recipient_email=gate_run.recipient_email,
        channel_status=_email_channel_status_from_snapshot(gate_run.status_snapshot),
        blocked_reasons=_snapshot_string_list(
            gate_run.decision_snapshot.get("blocked_reasons")
        ),
        provider_call_allowed=gate_run.provider_call_allowed,
        email_send_allowed=gate_run.email_send_allowed,
        production_write_allowed=gate_run.production_write_allowed,
        provider_call_attempted=False,
        max_provider_calls=gate_run.max_provider_calls,
        audit_fields=_snapshot_string_list(gate_run.decision_snapshot.get("audit_fields")),
        next_required_authorization=str(
            gate_run.decision_snapshot.get("next_required_authorization")
            or "L4_authorized_live_email_send"
        ),
        prepared_at=gate_run.created_at,
        expires_at=gate_run.expires_at,
        idempotency_replayed=idempotency_replayed,
        idempotency_scope=gate_run.idempotency_scope,
        idempotency_key_hash=gate_run.idempotency_key_hash,
    )


def _email_provider_live_send_result_from_run(
    send_run: EmailProviderLiveSendRun,
    *,
    idempotency_replayed: bool,
) -> EmailProviderLiveSendResult:
    return EmailProviderLiveSendResult(
        id=send_run.id,
        gate_run_id=send_run.gate_run_id,
        approval_id=send_run.approval_id,
        operation=send_run.operation,
        status=send_run.status,
        delivered=send_run.delivered,
        recipient_email=send_run.recipient_email,
        channel_status=_email_channel_status_from_snapshot(send_run.status_snapshot),
        blocked_reasons=_snapshot_string_list(
            send_run.decision_snapshot.get("blocked_reasons")
        ),
        reason=send_run.reason,
        send_enabled=send_run.send_enabled,
        live_approval_required=send_run.live_approval_required,
        recipient_allowlisted=send_run.recipient_allowlisted,
        provider_call_allowed=send_run.provider_call_allowed,
        email_send_allowed=send_run.email_send_allowed,
        production_write_allowed=send_run.production_write_allowed,
        provider_call_attempted=False if idempotency_replayed else send_run.provider_call_attempted,
        audit_fields=_snapshot_string_list(send_run.decision_snapshot.get("audit_fields")),
        next_required_authorization=str(
            send_run.decision_snapshot.get("next_required_authorization")
            or "manual_review_before_wider_live_send"
        ),
        sent_at=send_run.created_at,
        idempotency_replayed=idempotency_replayed,
        idempotency_scope=send_run.idempotency_scope,
        idempotency_key_hash=send_run.idempotency_key_hash,
    )


def _email_channel_test_idempotency_key_hash(
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    recipient_email: str,
    idempotency_key: str | None,
) -> str | None:
    if idempotency_key is None:
        return None
    normalized_key = idempotency_key.strip()
    if not normalized_key:
        return None
    return _stable_json_hash(
        {
            "scope": EMAIL_CHANNEL_TEST_IDEMPOTENCY_SCOPE,
            "workspace_id": str(workspace_id),
            "user_id": str(user_id),
            "recipient_email": recipient_email,
            "idempotency_key": normalized_key,
        }
    )


def _email_provider_live_gate_idempotency_key_hash(
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    operation: str,
    recipient_email: str,
    max_provider_calls: int,
    expires_at: datetime | None,
    idempotency_key: str | None,
) -> str | None:
    if idempotency_key is None:
        return None
    normalized_key = idempotency_key.strip()
    if not normalized_key:
        return None
    return _stable_json_hash(
        {
            "scope": EMAIL_PROVIDER_LIVE_GATE_IDEMPOTENCY_SCOPE,
            "workspace_id": str(workspace_id),
            "user_id": str(user_id),
            "operation": operation,
            "recipient_email": recipient_email,
            "max_provider_calls": max_provider_calls,
            "expires_at": expires_at.isoformat() if expires_at is not None else None,
            "idempotency_key": normalized_key,
        }
    )


def _email_provider_live_send_idempotency_key_hash(
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    gate_run_id: uuid.UUID,
    approval_id: str,
    operation: str,
    recipient_email: str,
    idempotency_key: str,
) -> str:
    return _stable_json_hash(
        {
            "scope": EMAIL_PROVIDER_LIVE_SEND_IDEMPOTENCY_SCOPE,
            "workspace_id": str(workspace_id),
            "user_id": str(user_id),
            "gate_run_id": str(gate_run_id),
            "approval_id": approval_id,
            "operation": operation,
            "recipient_email": recipient_email,
            "idempotency_key": idempotency_key,
        }
    )


def _email_channel_status_snapshot(status: EmailChannelStatus) -> dict[str, object]:
    return {
        "status": status.status,
        "configured": status.configured,
        "missing_settings": status.missing_settings,
        "host_configured": status.host_configured,
        "port": status.port,
        "sender_configured": status.sender_configured,
        "auth_configured": status.auth_configured,
        "tls_mode": status.tls_mode,
        "reason": status.reason,
    }


def _email_provider_live_gate_decision_snapshot(
    status: EmailChannelStatus,
) -> dict[str, object]:
    blocked_reasons = [] if status.configured else [status.reason or "email_channel_not_ready"]
    gate_status = "blocked" if blocked_reasons else "ready_pending_live_authorization"
    return {
        "status": gate_status,
        "blocked_reasons": blocked_reasons,
        "provider_call_allowed": False,
        "email_send_allowed": False,
        "production_write_allowed": False,
        "provider_call_attempted": False,
        "preflight_only": True,
        "next_required_authorization": "L4_authorized_live_email_send",
        "audit_fields": [
            "workspace_id",
            "user_id",
            "operation",
            "recipient_email",
            "max_provider_calls",
            "expires_at",
            "status_snapshot",
            "decision_snapshot",
            "provider_call_allowed",
            "email_send_allowed",
            "production_write_allowed",
            "provider_call_attempted",
            "idempotency_scope",
            "idempotency_key_hash",
        ],
    }


def _email_provider_live_send_blocked_reasons(
    *,
    settings: Settings,
    channel_status: EmailChannelStatus,
    gate_run: EmailProviderLiveGateRun,
    operation: str,
    recipient_email: str,
    approval_id: str,
    recipient_allowlisted: bool,
) -> list[str]:
    blocked_reasons: list[str] = []
    if not settings.email_live_send_enabled:
        blocked_reasons.append("email_live_send_disabled")
    if settings.email_live_approval_required and not approval_id:
        blocked_reasons.append("email_live_approval_required")
    if not recipient_allowlisted:
        blocked_reasons.append("recipient_not_allowlisted")
    if not channel_status.configured:
        blocked_reasons.append(channel_status.reason or "email_channel_not_ready")
    if gate_run.status != "ready_pending_live_authorization":
        blocked_reasons.append("provider_live_gate_not_ready")
    if gate_run.operation != operation:
        blocked_reasons.append("operation_mismatch_with_gate_run")
    if gate_run.recipient_email != recipient_email:
        blocked_reasons.append("recipient_mismatch_with_gate_run")
    if _email_provider_live_gate_expired(gate_run.expires_at):
        blocked_reasons.append("provider_live_gate_expired")
    return list(dict.fromkeys(blocked_reasons))


def _email_provider_live_send_status(
    *,
    blocked_reasons: list[str],
    delivery_result: EmailDeliveryResult,
) -> str:
    if blocked_reasons:
        return "blocked"
    if delivery_result.delivered:
        return "sent"
    return "delivery_failed"


def _email_provider_live_send_decision_snapshot(
    *,
    status: str,
    blocked_reasons: list[str],
    delivery_result: EmailDeliveryResult,
    send_enabled: bool,
    live_approval_required: bool,
    recipient_allowlisted: bool,
    provider_call_allowed: bool,
    email_send_allowed: bool,
    provider_call_attempted: bool,
) -> dict[str, object]:
    return {
        "status": status,
        "blocked_reasons": blocked_reasons,
        "delivered": delivery_result.delivered,
        "reason": delivery_result.reason,
        "send_enabled": send_enabled,
        "live_approval_required": live_approval_required,
        "recipient_allowlisted": recipient_allowlisted,
        "provider_call_allowed": provider_call_allowed,
        "email_send_allowed": email_send_allowed,
        "production_write_allowed": False,
        "provider_call_attempted": provider_call_attempted,
        "next_required_authorization": "manual_review_before_wider_live_send",
        "audit_fields": [
            "workspace_id",
            "user_id",
            "gate_run_id",
            "approval_id",
            "operation",
            "recipient_email",
            "status_snapshot",
            "decision_snapshot",
            "send_enabled",
            "live_approval_required",
            "recipient_allowlisted",
            "provider_call_allowed",
            "email_send_allowed",
            "production_write_allowed",
            "provider_call_attempted",
            "idempotency_scope",
            "idempotency_key_hash",
        ],
    }


def _email_provider_live_send_readiness_blockers(
    *,
    settings: Settings,
    channel_status: EmailChannelStatus,
    allowlist_count: int,
) -> list[str]:
    blocked_reasons: list[str] = []
    if not settings.email_live_send_enabled:
        blocked_reasons.append("email_live_send_disabled")
    if allowlist_count == 0:
        blocked_reasons.append("recipient_allowlist_empty")
    if not channel_status.configured:
        blocked_reasons.append(channel_status.reason or "email_channel_not_ready")
    return list(dict.fromkeys(blocked_reasons))


def _email_channel_status_from_snapshot(snapshot: dict[str, object]) -> EmailChannelStatus:
    missing_settings = snapshot.get("missing_settings")
    return EmailChannelStatus(
        status=str(snapshot.get("status") or "unknown"),
        configured=bool(snapshot.get("configured")),
        missing_settings=[
            str(item) for item in missing_settings if isinstance(item, str)
        ]
        if isinstance(missing_settings, list)
        else [],
        host_configured=bool(snapshot.get("host_configured")),
        port=_snapshot_int(snapshot.get("port")),
        sender_configured=bool(snapshot.get("sender_configured")),
        auth_configured=bool(snapshot.get("auth_configured")),
        tls_mode=str(snapshot.get("tls_mode") or "starttls"),
        reason=(
            str(snapshot["reason"])
            if snapshot.get("reason") is not None
            else None
        ),
    )


def _snapshot_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def _snapshot_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _email_recipient_allowlisted(recipient_email: str, allowlist: list[str]) -> bool:
    normalized_recipient = recipient_email.strip().lower()
    normalized_allowlist = {item.strip().lower() for item in allowlist if item.strip()}
    return normalized_recipient in normalized_allowlist


def _email_provider_live_gate_expired(expires_at: datetime | None) -> bool:
    if expires_at is None:
        return False
    normalized = expires_at
    if normalized.tzinfo is None:
        normalized = normalized.replace(tzinfo=UTC)
    return normalized < datetime.now(UTC)


def _stable_json_hash(value: dict[str, object]) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()
