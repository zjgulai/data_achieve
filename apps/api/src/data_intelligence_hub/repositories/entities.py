from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.entity import Entity, EntitySnapshot


async def list_entities(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    entity_type: str | None = None,
    domain: str | None = None,
    project_id: uuid.UUID | None = None,
) -> list[Entity]:
    statement = select(Entity).where(Entity.workspace_id == workspace_id)
    if entity_type is not None:
        statement = statement.where(Entity.entity_type == entity_type)
    if domain is not None:
        statement = statement.where(Entity.domain == domain)
    if project_id is not None:
        statement = statement.where(Entity.project_id == project_id)
    statement = statement.order_by(Entity.last_seen_at.desc())
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_entity(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    entity_id: uuid.UUID,
) -> Entity | None:
    result = await session.execute(
        select(Entity).where(Entity.id == entity_id, Entity.workspace_id == workspace_id)
    )
    return result.scalar_one_or_none()


async def get_entity_by_external_id(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    entity_type: str,
    external_id: str,
) -> Entity | None:
    result = await session.execute(
        select(Entity).where(
            Entity.workspace_id == workspace_id,
            Entity.entity_type == entity_type,
            Entity.external_id == external_id,
        )
    )
    return result.scalar_one_or_none()


async def list_entity_snapshots(
    session: AsyncSession,
    entity_id: uuid.UUID,
) -> list[EntitySnapshot]:
    result = await session.execute(
        select(EntitySnapshot)
        .where(EntitySnapshot.entity_id == entity_id)
        .order_by(EntitySnapshot.captured_at.desc())
    )
    return list(result.scalars().all())


async def get_entity_snapshot(
    session: AsyncSession,
    snapshot_id: uuid.UUID,
) -> EntitySnapshot | None:
    result = await session.execute(
        select(EntitySnapshot).where(EntitySnapshot.id == snapshot_id)
    )
    return result.scalar_one_or_none()
