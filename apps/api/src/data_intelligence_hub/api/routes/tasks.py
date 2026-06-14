from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from data_intelligence_hub.api.deps import AuthContext, SessionDep, get_auth_context
from data_intelligence_hub.schemas.task import CollectionTaskResponse, TaskRunResponse
from data_intelligence_hub.services.exceptions import (
    TaskAlreadyRunningError,
    TaskNotFoundError,
    TaskNotRunnableError,
)
from data_intelligence_hub.services.task_service import (
    get_collection_tasks,
    get_task_or_raise,
    get_task_runs,
    pause_task,
    resume_task,
    run_task_now,
)

router = APIRouter(tags=["tasks"])


@router.get("", response_model=list[CollectionTaskResponse])
async def list_task_items(
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    project_id: Annotated[uuid.UUID | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[CollectionTaskResponse]:
    tasks = await get_collection_tasks(session, context.workspace, project_id, status_filter)
    return [
        CollectionTaskResponse.from_task(task.task, latest_run=task.latest_run)
        for task in tasks
    ]


@router.get("/{task_id}", response_model=CollectionTaskResponse)
async def get_task_item(
    task_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> CollectionTaskResponse:
    try:
        task = await get_task_or_raise(session, context.workspace, task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return CollectionTaskResponse.from_task(task)


@router.post("/{task_id}/run", response_model=TaskRunResponse, status_code=status.HTTP_201_CREATED)
async def run_task_item(
    task_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> TaskRunResponse:
    try:
        run = await run_task_now(session, context.workspace, task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except (TaskAlreadyRunningError, TaskNotRunnableError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    return TaskRunResponse.model_validate(run)


@router.post("/{task_id}/pause", response_model=CollectionTaskResponse)
async def pause_task_item(
    task_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> CollectionTaskResponse:
    try:
        task = await pause_task(session, context.workspace, task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return CollectionTaskResponse.from_task(task)


@router.post("/{task_id}/resume", response_model=CollectionTaskResponse)
async def resume_task_item(
    task_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> CollectionTaskResponse:
    try:
        task = await resume_task(session, context.workspace, task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return CollectionTaskResponse.from_task(task)


@router.get("/{task_id}/runs", response_model=list[TaskRunResponse])
async def list_task_run_items(
    task_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> list[TaskRunResponse]:
    try:
        runs = await get_task_runs(session, context.workspace, task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return [TaskRunResponse.model_validate(run) for run in runs]
