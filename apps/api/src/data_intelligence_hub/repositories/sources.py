from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.source import Source


async def list_sources(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    source_type: str | None = None,
) -> list[Source]:
    statement = select(Source).where(Source.workspace_id == workspace_id)
    if project_id is not None:
        statement = statement.where(Source.project_id == project_id)
    if source_type is not None:
        statement = statement.where(Source.type == source_type)
    statement = statement.order_by(Source.created_at.desc())
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_source(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
) -> Source | None:
    result = await session.execute(
        select(Source).where(Source.id == source_id, Source.workspace_id == workspace_id)
    )
    return result.scalar_one_or_none()
