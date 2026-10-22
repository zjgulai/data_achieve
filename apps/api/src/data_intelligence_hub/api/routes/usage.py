"""用量与成本接口。

按工作区隔离。返回总量、按提供方、按端点与按天的聚合。
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from data_intelligence_hub.api.deps import AuthenticatedContextDep, SessionDep
from data_intelligence_hub.services.usage_service import get_usage_summary

router = APIRouter(tags=["usage"])


@router.get("/summary")
async def usage_summary(
    session: SessionDep,
    context: AuthenticatedContextDep,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    project_id: Annotated[uuid.UUID | None, Query()] = None,
) -> dict[str, object]:
    return await get_usage_summary(
        session,
        workspace_id=context.workspace.id,
        days=days,
        project_id=project_id,
    )