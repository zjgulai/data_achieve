from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.project import Project


async def list_projects(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    domain: str | None = None,
    status: str | None = None,
) -> list[Project]:
    statement = select(Project).where(Project.workspace_id == workspace_id)
    if domain is not None:
        statement = statement.where(Project.domain == domain)
    if status is not None:
        statement = statement.where(Project.status == status)
    statement = statement.order_by(Project.created_at.desc())
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_project(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
) -> Project | None:
    result = await session.execute(
        select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id)
    )
    return result.scalar_one_or_none()
