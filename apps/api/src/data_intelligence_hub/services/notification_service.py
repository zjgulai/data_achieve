from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.notification import Notification
from data_intelligence_hub.models.user import User
from data_intelligence_hub.repositories.notifications import (
    create_notification,
    get_notification,
    list_notifications,
)
from data_intelligence_hub.services.exceptions import NotificationNotFoundError


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
