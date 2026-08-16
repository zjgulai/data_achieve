from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from data_intelligence_hub.api.deps import SessionDep
from data_intelligence_hub.repositories.workspaces import get_demo_workspace
from data_intelligence_hub.schemas.entity import EntityResponse, EntitySnapshotResponse
from data_intelligence_hub.schemas.signal import SignalResponse
from data_intelligence_hub.services.entity_service import (
    get_entities,
    get_entity_or_raise,
    get_snapshots_for_entity,
)
from data_intelligence_hub.services.exceptions import EntityNotFoundError
from data_intelligence_hub.services.signal_service import get_signals_for_entity

router = APIRouter(tags=["entities"])

@router.get("", response_model=list[EntityResponse])
async def list_entity_items(
    session: SessionDep,
    entity_type: Annotated[str | None, Query()] = None,
    domain: Annotated[str | None, Query()] = None,
    project_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[EntityResponse]:
    workspace = await get_demo_workspace(session)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="demo_workspace_unavailable",
        )
    entities = await get_entities(
        session,
        workspace,
        entity_type=entity_type,
        domain=domain,
        project_id=project_id,
    )
    return [EntityResponse.model_validate(entity) for entity in entities]

@router.get("/{entity_id}", response_model=EntityResponse)
async def get_entity_item(
    entity_id: uuid.UUID,
    session: SessionDep,
) -> EntityResponse:
    workspace = await get_demo_workspace(session)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="demo_workspace_unavailable",
        )
    try:
        entity = await get_entity_or_raise(session, workspace, entity_id)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return EntityResponse.model_validate(entity)

@router.get("/{entity_id}/snapshots", response_model=list[EntitySnapshotResponse])
async def list_entity_snapshot_items(
    entity_id: uuid.UUID,
    session: SessionDep,
) -> list[EntitySnapshotResponse]:
    workspace = await get_demo_workspace(session)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="demo_workspace_unavailable",
        )
    try:
        snapshots = await get_snapshots_for_entity(session, workspace, entity_id)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return [EntitySnapshotResponse.model_validate(snapshot) for snapshot in snapshots]

@router.get("/{entity_id}/signals", response_model=list[SignalResponse])
async def list_entity_signal_items(
    entity_id: uuid.UUID,
    session: SessionDep,
) -> list[SignalResponse]:
    workspace = await get_demo_workspace(session)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="demo_workspace_unavailable",
        )
    try:
        signals = await get_signals_for_entity(session, workspace, entity_id)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return [SignalResponse.from_model(signal) for signal in signals]
