from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from data_intelligence_hub.api.deps import AuthContext, SessionDep, get_auth_context
from data_intelligence_hub.collectors.base import CollectorError
from data_intelligence_hub.schemas.toolkit import (
    ToolkitMethodCardDraftListResponse,
    ToolkitMethodCardDraftRequest,
    ToolkitMethodCardDraftResponse,
    ToolkitOverviewResponse,
    ToolkitPreflightReportResponse,
    ToolkitPreflightRequest,
)
from data_intelligence_hub.services.toolkit_method_card_service import (
    list_method_card_drafts,
    save_method_card_draft,
)
from data_intelligence_hub.services.toolkit_preflight_service import run_toolkit_preflight
from data_intelligence_hub.services.toolkit_service import get_toolkit_overview

router = APIRouter(tags=["toolkit"])


@router.get("", response_model=ToolkitOverviewResponse)
async def get_toolkit(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> ToolkitOverviewResponse:
    return await get_toolkit_overview(session, context.workspace.id)


@router.post("/preflight", response_model=ToolkitPreflightReportResponse)
async def preflight_toolkit_url(
    payload: ToolkitPreflightRequest,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> ToolkitPreflightReportResponse:
    del context
    try:
        return await run_toolkit_preflight(payload)
    except CollectorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/method-card-drafts", response_model=ToolkitMethodCardDraftListResponse)
async def get_method_card_drafts(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> ToolkitMethodCardDraftListResponse:
    return ToolkitMethodCardDraftListResponse(
        drafts=await list_method_card_drafts(session, context.workspace.id)
    )


@router.post(
    "/method-card-drafts",
    response_model=ToolkitMethodCardDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_method_card_draft(
    payload: ToolkitMethodCardDraftRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> ToolkitMethodCardDraftResponse:
    return await save_method_card_draft(session, context.workspace, payload)
