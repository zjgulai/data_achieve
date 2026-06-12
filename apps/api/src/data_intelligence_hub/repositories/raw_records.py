from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.raw_record import RawRecord


async def list_raw_records(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    source_id: uuid.UUID | None = None,
    task_run_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[RawRecord]:
    statement = select(RawRecord).where(RawRecord.workspace_id == workspace_id)
    if source_id is not None:
        statement = statement.where(RawRecord.source_id == source_id)
    if task_run_id is not None:
        statement = statement.where(RawRecord.task_run_id == task_run_id)
    statement = statement.order_by(RawRecord.collected_at.desc()).limit(limit).offset(offset)
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_raw_record(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    raw_record_id: uuid.UUID,
) -> RawRecord | None:
    result = await session.execute(
        select(RawRecord).where(
            RawRecord.id == raw_record_id,
            RawRecord.workspace_id == workspace_id,
        )
    )
    return result.scalar_one_or_none()


async def get_raw_record_by_hash(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
    content_hash: str,
) -> RawRecord | None:
    result = await session.execute(
        select(RawRecord).where(
            RawRecord.workspace_id == workspace_id,
            RawRecord.source_id == source_id,
            RawRecord.content_hash == content_hash,
        )
    )
    return result.scalar_one_or_none()
