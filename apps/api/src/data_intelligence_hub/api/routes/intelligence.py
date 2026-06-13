from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from data_intelligence_hub.api.deps import AuthContext, SessionDep, get_auth_context
from data_intelligence_hub.schemas.intelligence import (
    EvidenceResponse,
    IntelligenceFeedbackRequest,
    IntelligenceFeedbackResponse,
    IntelligenceResponse,
    IntelligenceStatusUpdateRequest,
)
from data_intelligence_hub.services.exceptions import IntelligenceNotFoundError
from data_intelligence_hub.services.intelligence_service import (
    get_evidences_for_intelligence,
    get_intelligence_items,
    get_intelligence_or_raise,
    submit_intelligence_feedback,
    update_intelligence_status,
)

router = APIRouter(tags=["intelligence"])


@router.get("", response_model=list[IntelligenceResponse])
async def list_intelligence(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    project_id: Annotated[uuid.UUID | None, Query()] = None,
    type_filter: Annotated[str | None, Query(alias="type")] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    domain: Annotated[str | None, Query()] = None,
    sort: Annotated[str | None, Query()] = None,
) -> list[IntelligenceResponse]:
    items = await get_intelligence_items(
        session,
        context.workspace,
        project_id=project_id,
        intelligence_type=type_filter,
        status=status_filter,
        domain=domain,
        sort=sort,
    )
    return [
        IntelligenceResponse.from_model(item.item, evidence_count=item.evidence_count)
        for item in items
    ]


@router.get("/{intelligence_id}", response_model=IntelligenceResponse)
async def get_intelligence(
    intelligence_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> IntelligenceResponse:
    try:
        result = await get_intelligence_or_raise(session, context.workspace, intelligence_id)
    except IntelligenceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return IntelligenceResponse.from_model(result.item, evidence_count=result.evidence_count)


@router.patch("/{intelligence_id}/status", response_model=IntelligenceResponse)
async def patch_intelligence_status(
    intelligence_id: uuid.UUID,
    payload: IntelligenceStatusUpdateRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> IntelligenceResponse:
    try:
        result = await update_intelligence_status(
            session,
            context.workspace,
            intelligence_id,
            payload.status,
        )
    except IntelligenceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return IntelligenceResponse.from_model(result.item, evidence_count=result.evidence_count)


@router.get("/{intelligence_id}/evidences", response_model=list[EvidenceResponse])
async def list_intelligence_evidences(
    intelligence_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> list[EvidenceResponse]:
    try:
        evidences = await get_evidences_for_intelligence(
            session,
            context.workspace,
            intelligence_id,
        )
    except IntelligenceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return [
        EvidenceResponse.from_model(
            evidence.evidence,
            screenshot_url=evidence.screenshot_url,
            signal=evidence.signal,
            entity=evidence.entity,
            raw_record=evidence.raw_record,
            task_run=evidence.task_run,
            source=evidence.source,
        )
        for evidence in evidences
    ]


@router.post(
    "/{intelligence_id}/feedback",
    response_model=IntelligenceFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_intelligence_feedback(
    intelligence_id: uuid.UUID,
    payload: IntelligenceFeedbackRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> IntelligenceFeedbackResponse:
    try:
        feedback = await submit_intelligence_feedback(
            session,
            context.workspace,
            intelligence_id,
            context.user.id,
            payload.feedback_type,
            payload.comment,
        )
    except IntelligenceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return IntelligenceFeedbackResponse.from_model(feedback)
