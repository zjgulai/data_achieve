from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from data_intelligence_hub.api.deps import SessionDep
from data_intelligence_hub.repositories.workspaces import get_demo_workspace
from data_intelligence_hub.schemas.dashboard import DashboardOverviewResponse
from data_intelligence_hub.services.dashboard_service import get_dashboard_overview

router = APIRouter(tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverviewResponse)
async def get_dashboard_overview_item(
    session: SessionDep,
    project_id: Annotated[uuid.UUID | None, Query()] = None,
    domain: Annotated[str | None, Query()] = None,
    from_time: Annotated[datetime | None, Query(alias="from")] = None,
    to_time: Annotated[datetime | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> DashboardOverviewResponse:
    workspace = await get_demo_workspace(session)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="demo_workspace_unavailable",
        )
    return await get_dashboard_overview(
        session=session,
        workspace=workspace,
        project_id=project_id,
        domain=domain,
        from_time=from_time,
        to_time=to_time,
        limit=limit,
    )
