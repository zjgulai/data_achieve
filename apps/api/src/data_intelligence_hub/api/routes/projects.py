from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from data_intelligence_hub.api.deps import AuthContext, SessionDep, get_auth_context
from data_intelligence_hub.schemas.project import (
    ProjectCreateRequest,
    ProjectDomain,
    ProjectResponse,
    ProjectStatus,
    ProjectUpdateRequest,
)
from data_intelligence_hub.services.exceptions import ProjectNotFoundError
from data_intelligence_hub.services.project_service import (
    archive_project,
    create_project,
    get_project_or_raise,
    get_projects,
    update_project,
)

router = APIRouter(tags=["projects"])


@router.get("", response_model=list[ProjectResponse])
async def list_project_items(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    domain: Annotated[ProjectDomain | None, Query()] = None,
    status_filter: Annotated[ProjectStatus | None, Query(alias="status")] = None,
) -> list[ProjectResponse]:
    projects = await get_projects(
        session,
        context.workspace,
        domain=domain,
        status=status_filter,
    )
    return [ProjectResponse.model_validate(project) for project in projects]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project_item(
    payload: ProjectCreateRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> ProjectResponse:
    project = await create_project(session, context.user, context.workspace, payload)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project_item(
    project_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> ProjectResponse:
    try:
        project = await get_project_or_raise(session, context.workspace, project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project_item(
    project_id: uuid.UUID,
    payload: ProjectUpdateRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> ProjectResponse:
    try:
        project = await update_project(session, context.workspace, project_id, payload)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", response_model=ProjectResponse)
async def archive_project_item(
    project_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> ProjectResponse:
    try:
        project = await archive_project(session, context.workspace, project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return ProjectResponse.model_validate(project)
