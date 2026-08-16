from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from data_intelligence_hub.api.deps import SessionDep
from data_intelligence_hub.repositories.workspaces import get_demo_workspace
from data_intelligence_hub.schemas.raw_record import RawRecordResponse
from data_intelligence_hub.services.exceptions import RawRecordNotFoundError
from data_intelligence_hub.services.raw_record_service import (
    get_raw_record_or_raise,
    get_raw_records,
)

router = APIRouter(tags=["raw-records"])

@router.get("", response_model=list[RawRecordResponse])
async def list_raw_record_items(
    session: SessionDep,
    source_id: Annotated[uuid.UUID | None, Query()] = None,
    task_run_id: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[RawRecordResponse]:
    workspace = await get_demo_workspace(session)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="demo_workspace_unavailable",
        )
    raw_records = await get_raw_records(
        session,
        workspace,
        source_id=source_id,
        task_run_id=task_run_id,
        limit=limit,
        offset=offset,
    )
    return [RawRecordResponse.model_validate(raw_record) for raw_record in raw_records]

@router.get("/{raw_record_id}", response_model=RawRecordResponse)
async def get_raw_record_item(
    raw_record_id: uuid.UUID,
    session: SessionDep,
) -> RawRecordResponse:
    workspace = await get_demo_workspace(session)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="demo_workspace_unavailable",
        )
    try:
        raw_record = await get_raw_record_or_raise(session, workspace, raw_record_id)
    except RawRecordNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return RawRecordResponse.model_validate(raw_record)
