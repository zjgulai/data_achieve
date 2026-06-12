from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.entity import EntitySnapshot
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.signal import Signal


async def list_signals(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    entity_id: uuid.UUID | None = None,
    signal_type: str | None = None,
    severity: str | None = None,
) -> list[Signal]:
    statement = select(Signal).where(Signal.workspace_id == workspace_id)
    if project_id is not None:
        statement = statement.where(Signal.project_id == project_id)
    if entity_id is not None:
        statement = statement.where(Signal.entity_id == entity_id)
    if signal_type is not None:
        statement = statement.where(Signal.signal_type == signal_type)
    if severity is not None:
        statement = statement.where(Signal.severity == severity)
    statement = statement.order_by(Signal.detected_at.desc())
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_signal(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    signal_id: uuid.UUID,
) -> Signal | None:
    result = await session.execute(
        select(Signal).where(Signal.workspace_id == workspace_id, Signal.id == signal_id)
    )
    return result.scalar_one_or_none()


async def get_signal_by_snapshot_pair(
    session: AsyncSession,
    signal_type: str,
    previous_snapshot_id: uuid.UUID,
    current_snapshot_id: uuid.UUID,
) -> Signal | None:
    result = await session.execute(
        select(Signal).where(
            Signal.signal_type == signal_type,
            Signal.previous_snapshot_id == previous_snapshot_id,
            Signal.current_snapshot_id == current_snapshot_id,
        )
    )
    return result.scalar_one_or_none()


async def list_recent_snapshots_for_entity(
    session: AsyncSession,
    entity_id: uuid.UUID,
    limit: int = 2,
) -> list[EntitySnapshot]:
    result = await session.execute(
        select(EntitySnapshot)
        .where(EntitySnapshot.entity_id == entity_id)
        .order_by(EntitySnapshot.captured_at.desc(), EntitySnapshot.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_recent_snapshots_for_source(
    session: AsyncSession,
    source_id: uuid.UUID,
    limit: int = 2,
) -> list[EntitySnapshot]:
    result = await session.execute(
        select(EntitySnapshot)
        .join(RawRecord, RawRecord.id == EntitySnapshot.raw_record_id)
        .where(RawRecord.source_id == source_id)
        .order_by(EntitySnapshot.captured_at.desc(), EntitySnapshot.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
