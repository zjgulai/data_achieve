from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from data_intelligence_hub.api.deps import SessionDep, WorkspaceDep
from data_intelligence_hub.repositories.users import get_user_by_id
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
    workspace: WorkspaceDep,
    project_id: Annotated[uuid.UUID | None, Query()] = None,
    type_filter: Annotated[str | None, Query(alias="type")] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    domain: Annotated[str | None, Query()] = None,
    sort: Annotated[str | None, Query()] = None,
) -> list[IntelligenceResponse]:
    items = await get_intelligence_items(
        session,
        workspace,
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
    workspace: WorkspaceDep,
) -> IntelligenceResponse:
    try:
        result = await get_intelligence_or_raise(session, workspace, intelligence_id)
    except IntelligenceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return IntelligenceResponse.from_model(result.item, evidence_count=result.evidence_count)

@router.patch("/{intelligence_id}/status", response_model=IntelligenceResponse)
async def patch_intelligence_status(
    intelligence_id: uuid.UUID,
    payload: IntelligenceStatusUpdateRequest,
    session: SessionDep,
    workspace: WorkspaceDep,
) -> IntelligenceResponse:
    try:
        result = await update_intelligence_status(
            session,
            workspace,
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
    workspace: WorkspaceDep,
) -> list[EvidenceResponse]:
    try:
        evidences = await get_evidences_for_intelligence(
            session,
            workspace,
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
    workspace: WorkspaceDep,
) -> IntelligenceFeedbackResponse:
    # 反馈必须挂在某个用户名下，而模型里 user_id 是非空外键。
    # 去认证改造后这里一度传 None，于是每次提交反馈必然 500。
    # 演示工作区的所有者就是这条无鉴权路径的归属人。
    author = await get_user_by_id(session, workspace.owner_id)
    if author is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="demo_workspace_owner_unavailable",
        )
    try:
        feedback = await submit_intelligence_feedback(
            session,
            workspace,
            intelligence_id,
            author.id,
            payload.feedback_type,
            payload.comment,
        )
    except IntelligenceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return IntelligenceFeedbackResponse.from_model(feedback)
