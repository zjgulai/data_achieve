from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from data_intelligence_hub.api.deps import AuthContext, SessionDep, get_auth_context
from data_intelligence_hub.schemas.source import (
    SourceCreateRequest,
    SourceResponse,
    SourceTestResponse,
    SourceType,
    SourceUpdateRequest,
)
from data_intelligence_hub.schemas.task import CollectionTaskResponse
from data_intelligence_hub.services.exceptions import (
    CollectorConfigError,
    CollectorNotFoundError,
    ProjectNotFoundError,
    SourceNotFoundError,
)
from data_intelligence_hub.services.source_service import (
    create_source,
    disable_source,
    enable_source,
    get_source_or_raise,
    get_sources,
    test_source_config,
    update_source,
)

router = APIRouter(tags=["sources"])


@router.get("", response_model=list[SourceResponse])
async def list_source_items(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    project_id: Annotated[uuid.UUID | None, Query()] = None,
    type_filter: Annotated[SourceType | None, Query(alias="type")] = None,
) -> list[SourceResponse]:
    sources = await get_sources(session, context.workspace, project_id, type_filter)
    return [SourceResponse.model_validate(source) for source in sources]


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source_item(
    payload: SourceCreateRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> SourceResponse:
    try:
        source = await create_source(session, context.workspace, payload)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except (CollectorNotFoundError, CollectorConfigError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    return SourceResponse.model_validate(source)


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source_item(
    source_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> SourceResponse:
    try:
        source = await get_source_or_raise(session, context.workspace, source_id)
    except SourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return SourceResponse.model_validate(source)


@router.patch("/{source_id}", response_model=SourceResponse)
async def update_source_item(
    source_id: uuid.UUID,
    payload: SourceUpdateRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> SourceResponse:
    try:
        source = await update_source(session, context.workspace, source_id, payload)
    except SourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except CollectorConfigError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    return SourceResponse.model_validate(source)


@router.post("/{source_id}/test", response_model=SourceTestResponse)
async def test_source_item(
    source_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> SourceTestResponse:
    try:
        source = await test_source_config(session, context.workspace, source_id)
    except SourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except (CollectorNotFoundError, CollectorConfigError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    return SourceTestResponse(
        status="config_valid",
        collector_type=source.type,
        message="Config is valid. Manual task run can collect raw records.",
    )


@router.post("/{source_id}/enable", response_model=CollectionTaskResponse)
async def enable_source_item(
    source_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> CollectionTaskResponse:
    try:
        _, task = await enable_source(session, context.workspace, source_id)
    except SourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except (CollectorNotFoundError, CollectorConfigError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    return CollectionTaskResponse.from_task(task)


@router.post("/{source_id}/disable", response_model=SourceResponse)
async def disable_source_item(
    source_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> SourceResponse:
    try:
        source, _ = await disable_source(session, context.workspace, source_id)
    except SourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return SourceResponse.model_validate(source)
