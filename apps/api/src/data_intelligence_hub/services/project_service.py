from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.projects import get_project, list_projects
from data_intelligence_hub.schemas.project import ProjectCreateRequest, ProjectUpdateRequest
from data_intelligence_hub.services.exceptions import (
    ProjectNotActiveError,
    ProjectNotFoundError,
)


async def get_projects(
    session: AsyncSession,
    workspace: Workspace,
    domain: str | None,
    status: str | None,
) -> list[Project]:
    return await list_projects(session, workspace.id, domain=domain, status=status)


async def create_project(
    session: AsyncSession,
    user: User,
    workspace: Workspace,
    payload: ProjectCreateRequest,
) -> Project:
    project = Project(
        workspace_id=workspace.id,
        name=payload.name.strip(),
        description=payload.description,
        domain=payload.domain,
        status="active",
        owner_id=user.id,
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def get_project_or_raise(
    session: AsyncSession,
    workspace: Workspace,
    project_id: uuid.UUID,
) -> Project:
    project = await get_project(session, workspace.id, project_id)
    if project is None:
        raise ProjectNotFoundError
    return project


async def get_active_project_or_raise(
    session: AsyncSession,
    workspace: Workspace,
    project_id: uuid.UUID,
) -> Project:
    project = await get_project_or_raise(session, workspace, project_id)
    if project.status != "active":
        raise ProjectNotActiveError
    return project


async def update_project(
    session: AsyncSession,
    workspace: Workspace,
    project_id: uuid.UUID,
    payload: ProjectUpdateRequest,
) -> Project:
    project = await get_project_or_raise(session, workspace, project_id)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if field == "name" and isinstance(value, str):
            value = value.strip()
        setattr(project, field, value)
    await session.commit()
    await session.refresh(project)
    return project


async def archive_project(
    session: AsyncSession,
    workspace: Workspace,
    project_id: uuid.UUID,
) -> Project:
    project = await get_project_or_raise(session, workspace, project_id)
    project.status = "archived"
    await session.commit()
    await session.refresh(project)
    return project
