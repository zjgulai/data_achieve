from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.notification import Notification


async def create_notification(
    session: AsyncSession,
    notification: Notification,
) -> Notification:
    session.add(notification)
    await session.flush()
    return notification


async def list_notifications(
    session: AsyncSession,
    user_id: uuid.UUID,
    is_read: bool | None = None,
) -> list[Notification]:
    statement = select(Notification).where(Notification.user_id == user_id)
    if is_read is not None:
        statement = statement.where(Notification.is_read == is_read)
    statement = statement.order_by(Notification.created_at.desc())
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_notification(
    session: AsyncSession,
    user_id: uuid.UUID,
    notification_id: uuid.UUID,
) -> Notification | None:
    result = await session.execute(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.id == notification_id,
        )
    )
    return result.scalar_one_or_none()


async def list_notifications_by_ids(
    session: AsyncSession,
    user_id: uuid.UUID,
    notification_ids: list[uuid.UUID],
) -> list[Notification]:
    if not notification_ids:
        return []
    result = await session.execute(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.id.in_(notification_ids),
        )
    )
    return list(result.scalars().all())
