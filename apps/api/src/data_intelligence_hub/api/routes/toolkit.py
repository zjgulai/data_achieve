from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from data_intelligence_hub.api.deps import AuthContext, SessionDep, get_auth_context
from data_intelligence_hub.schemas.toolkit import ToolkitOverviewResponse
from data_intelligence_hub.services.toolkit_service import get_toolkit_overview

router = APIRouter(tags=["toolkit"])


@router.get("", response_model=ToolkitOverviewResponse)
async def get_toolkit(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> ToolkitOverviewResponse:
    return await get_toolkit_overview(session, context.workspace)
