"""列表富集接口。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from data_intelligence_hub.api.deps import AuthenticatedContextDep, SessionDep
from data_intelligence_hub.repositories.projects import get_project
from data_intelligence_hub.schemas.enrichment import (
    EnrichmentJobDetailResponse,
    EnrichmentJobResponse,
    EnrichmentRowResponse,
    StartEnrichmentRequest,
)
from data_intelligence_hub.services.enrichment_service import (
    EnrichmentError,
    get_job,
    get_rows,
    list_jobs,
    start_enrichment,
)

router = APIRouter(tags=["enrichments"])


@router.post(
    "", response_model=EnrichmentJobResponse, status_code=status.HTTP_202_ACCEPTED
)
async def start_enrichment_job(
    payload: StartEnrichmentRequest,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> EnrichmentJobResponse:
    project = await get_project(session, context.workspace.id, payload.project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="project_not_found"
        )
    try:
        job = await start_enrichment(
            session,
            workspace=context.workspace,
            project_id=payload.project_id,
            name=payload.name,
            query_template=payload.query_template,
            items=payload.items,
            output_schema=payload.output_schema,
        )
    except EnrichmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return EnrichmentJobResponse.model_validate(job)


@router.get("", response_model=list[EnrichmentJobResponse])
async def list_enrichment_jobs(
    session: SessionDep,
    context: AuthenticatedContextDep,
    project_id: uuid.UUID | None = None,
) -> list[EnrichmentJobResponse]:
    jobs = await list_jobs(session, context.workspace.id, project_id)
    return [EnrichmentJobResponse.model_validate(job) for job in jobs]


@router.get("/{job_id}", response_model=EnrichmentJobDetailResponse)
async def get_enrichment_job(
    job_id: uuid.UUID,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> EnrichmentJobDetailResponse:
    job = await get_job(session, context.workspace.id, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="enrichment_job_not_found"
        )
    rows = await get_rows(session, job.id)
    return EnrichmentJobDetailResponse(
        **EnrichmentJobResponse.model_validate(job).model_dump(),
        rows=[EnrichmentRowResponse.model_validate(row) for row in rows],
    )