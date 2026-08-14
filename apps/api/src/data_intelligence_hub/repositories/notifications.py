from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.notification import (
    EmailChannelTestRun,
    EmailProviderLiveGateRun,
    EmailProviderLiveSendRun,
    Notification,
)


async def create_notification(
    session: AsyncSession,
    notification: Notification,
) -> Notification:
    session.add(notification)
    await session.flush()
    return notification


async def create_email_channel_test_run(
    session: AsyncSession,
    test_run: EmailChannelTestRun,
) -> EmailChannelTestRun:
    session.add(test_run)
    await session.flush()
    return test_run


async def create_email_provider_live_gate_run(
    session: AsyncSession,
    gate_run: EmailProviderLiveGateRun,
) -> EmailProviderLiveGateRun:
    session.add(gate_run)
    await session.flush()
    return gate_run


async def create_email_provider_live_send_run(
    session: AsyncSession,
    send_run: EmailProviderLiveSendRun,
) -> EmailProviderLiveSendRun:
    session.add(send_run)
    await session.flush()
    return send_run


async def get_email_channel_test_run_by_idempotency_key_hash(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    idempotency_scope: str,
    idempotency_key_hash: str,
) -> EmailChannelTestRun | None:
    result = await session.execute(
        select(EmailChannelTestRun)
        .where(
            EmailChannelTestRun.workspace_id == workspace_id,
            EmailChannelTestRun.user_id == user_id,
            EmailChannelTestRun.idempotency_scope == idempotency_scope,
            EmailChannelTestRun.idempotency_key_hash == idempotency_key_hash,
        )
        .order_by(EmailChannelTestRun.created_at.desc(), EmailChannelTestRun.id.desc())
    )
    return result.scalars().first()


async def get_email_provider_live_gate_run_by_idempotency_key_hash(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    idempotency_scope: str,
    idempotency_key_hash: str,
) -> EmailProviderLiveGateRun | None:
    result = await session.execute(
        select(EmailProviderLiveGateRun)
        .where(
            EmailProviderLiveGateRun.workspace_id == workspace_id,
            EmailProviderLiveGateRun.user_id == user_id,
            EmailProviderLiveGateRun.idempotency_scope == idempotency_scope,
            EmailProviderLiveGateRun.idempotency_key_hash == idempotency_key_hash,
        )
        .order_by(
            EmailProviderLiveGateRun.created_at.desc(),
            EmailProviderLiveGateRun.id.desc(),
        )
    )
    return result.scalars().first()


async def get_email_provider_live_gate_run(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    gate_run_id: uuid.UUID,
) -> EmailProviderLiveGateRun | None:
    result = await session.execute(
        select(EmailProviderLiveGateRun).where(
            EmailProviderLiveGateRun.id == gate_run_id,
            EmailProviderLiveGateRun.workspace_id == workspace_id,
            EmailProviderLiveGateRun.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_email_provider_live_send_run_by_idempotency_key_hash(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    idempotency_scope: str,
    idempotency_key_hash: str,
) -> EmailProviderLiveSendRun | None:
    result = await session.execute(
        select(EmailProviderLiveSendRun)
        .where(
            EmailProviderLiveSendRun.workspace_id == workspace_id,
            EmailProviderLiveSendRun.user_id == user_id,
            EmailProviderLiveSendRun.idempotency_scope == idempotency_scope,
            EmailProviderLiveSendRun.idempotency_key_hash == idempotency_key_hash,
        )
        .order_by(
            EmailProviderLiveSendRun.created_at.desc(),
            EmailProviderLiveSendRun.id.desc(),
        )
    )
    return result.scalars().first()


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


async def get_notification_by_reference(
    session: AsyncSession,
    user_id: uuid.UUID,
    reference_type: str,
    reference_id: uuid.UUID,
    notification_type: str | None = None,
) -> Notification | None:
    statement = select(Notification).where(
        Notification.user_id == user_id,
        Notification.reference_type == reference_type,
        Notification.reference_id == reference_id,
    )
    if notification_type is not None:
        statement = statement.where(Notification.notification_type == notification_type)
    result = await session.execute(statement.order_by(Notification.created_at.desc()))
    return result.scalars().first()


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
