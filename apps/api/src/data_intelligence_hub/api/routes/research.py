"""异步深度研究接口。"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from data_intelligence_hub.api.deps import AuthenticatedContextDep, SessionDep
from data_intelligence_hub.mcp_runtime.run_service import (
    get_run_detail,
    list_run_records,
)
from data_intelligence_hub.models.run import Run
from data_intelligence_hub.repositories.projects import get_project
from data_intelligence_hub.services.research_service import (
    ResearchError,
    start_research,
)

router = APIRouter(tags=["research"])


class StartResearchRequest(BaseModel):
    project_id: uuid.UUID
    query: str = Field(min_length=1, max_length=2000)
    effort: str = Field(default="medium", max_length=20)
    output_schema: dict[str, Any] | None = None
    max_cost_dollars: float = Field(default=5, ge=1, le=100)
    timeout_seconds: int = Field(default=600, ge=30, le=1800)
    label: str | None = Field(default=None, max_length=120)


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def start_research_run(
    payload: StartResearchRequest,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> dict[str, object]:
    project = await get_project(session, context.workspace.id, payload.project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="project_not_found"
        )
    try:
        run_id = await start_research(
            session,
            workspace=context.workspace,
            project_id=payload.project_id,
            query=payload.query,
            effort=payload.effort,
            output_schema=payload.output_schema,
            max_cost_dollars=payload.max_cost_dollars,
            timeout_seconds=payload.timeout_seconds,
            label=payload.label,
        )
    except ResearchError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return {"run_id": str(run_id), "status": "queued"}


@router.get("/{run_id}")
async def get_research_run(
    run_id: uuid.UUID,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> dict[str, object]:
    run = await session.get(Run, run_id)
    if run is None or run.workspace_id != context.workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="run_not_found"
        )
    detail = await get_run_detail(run_id)
    records = await list_run_records(run_id, limit=20)
    return {"run": detail, "records": records}