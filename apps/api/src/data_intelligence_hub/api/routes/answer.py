"""工作区问答接口。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from data_intelligence_hub.api.deps import AuthenticatedContextDep, SessionDep
from data_intelligence_hub.repositories.projects import get_project
from data_intelligence_hub.services.answer_service import workspace_answer

router = APIRouter(tags=["answer"])


class AnswerRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    project_id: uuid.UUID | None = None
    limit: int = Field(default=5, ge=1, le=20)


@router.post("")
async def answer_question(
    payload: AnswerRequest,
    session: SessionDep,
    context: AuthenticatedContextDep,
) -> dict[str, object]:
    if payload.project_id is not None:
        project = await get_project(session, context.workspace.id, payload.project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="project_not_found"
            )
    return await workspace_answer(
        session,
        workspace_id=context.workspace.id,
        project_id=payload.project_id,
        query=payload.query,
        limit=payload.limit,
    )