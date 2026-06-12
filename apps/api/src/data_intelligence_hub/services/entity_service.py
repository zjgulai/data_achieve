from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.entity import Entity, EntitySnapshot
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.entities import (
    get_entity,
    list_entities,
    list_entity_snapshots,
)
from data_intelligence_hub.services.exceptions import EntityNotFoundError


async def get_entities(
    session: AsyncSession,
    workspace: Workspace,
    entity_type: str | None,
    domain: str | None,
    project_id: uuid.UUID | None,
) -> list[Entity]:
    return await list_entities(
        session,
        workspace.id,
        entity_type=entity_type,
        domain=domain,
        project_id=project_id,
    )


async def get_entity_or_raise(
    session: AsyncSession,
    workspace: Workspace,
    entity_id: uuid.UUID,
) -> Entity:
    entity = await get_entity(session, workspace.id, entity_id)
    if entity is None:
        raise EntityNotFoundError
    return entity


async def get_snapshots_for_entity(
    session: AsyncSession,
    workspace: Workspace,
    entity_id: uuid.UUID,
) -> list[EntitySnapshot]:
    await get_entity_or_raise(session, workspace, entity_id)
    return await list_entity_snapshots(session, entity_id)
