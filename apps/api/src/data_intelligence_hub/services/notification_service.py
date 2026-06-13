from __future__ import annotations

import asyncio
import smtplib
import uuid
from dataclasses import dataclass
from email.message import EmailMessage

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.core.config import Settings, get_settings
from data_intelligence_hub.models.notification import Notification
from data_intelligence_hub.models.user import User
from data_intelligence_hub.repositories.notifications import (
    create_notification,
    get_notification,
    list_notifications,
)
from data_intelligence_hub.services.exceptions import NotificationNotFoundError

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class EmailDeliveryResult:
    delivered: bool
    reason: str | None = None


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


async def send_email_notification(
    recipient_email: str,
    subject: str,
    body: str,
) -> EmailDeliveryResult:
    settings = get_settings()
    smtp_host = settings.smtp_host
    sender = settings.smtp_from or settings.smtp_user
    if not smtp_host or not sender:
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
