from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from data_intelligence_hub.api.deps import AuthContext, SessionDep, get_auth_context
from data_intelligence_hub.collectors.base import CollectorError
from data_intelligence_hub.schemas.toolkit import (
    ToolkitOverviewResponse,
    ToolkitPreflightReportResponse,
    ToolkitPreflightRequest,
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
