from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Response, status
from sqlalchemy import select

from data_intelligence_hub.api.deps import SessionDep
from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.models.task import TaskRun
from data_intelligence_hub.repositories.scheduler import get_latest_scheduler_tick
from data_intelligence_hub.repositories.workspaces import get_demo_workspace
from data_intelligence_hub.schemas.scheduler import SchedulerOverviewResponse
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
    project_id: Annotated[uuid.UUID | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[CollectionTaskResponse]:
    workspace = await get_demo_workspace(session)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="demo_workspace_unavailable",
        )
    tasks = await get_collection_tasks(session, workspace, project_id, status_filter)
    return [
        CollectionTaskResponse.from_task(
            task.task,
            latest_run=task.latest_run,
            project_name=task.project_name,
            project_domain=task.project_domain,
            source_name=task.source_name,
            source_url=task.source_url,
        )
        for task in tasks
    ]

@router.get("/scheduler/overview", response_model=SchedulerOverviewResponse)
async def get_scheduler_overview_item(
    session: SessionDep,
) -> SchedulerOverviewResponse:
    latest_tick = await get_latest_scheduler_tick(session)
    return SchedulerOverviewResponse.from_tick(
        enabled=get_settings().scheduler_enabled,
        latest_tick=latest_tick,
    )

@router.get("/runs", response_model=list[TaskRunResponse])
async def list_all_task_run_items(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[TaskRunResponse]:
    workspace = await get_demo_workspace(session)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="demo_workspace_unavailable",
        )
    q = (
        select(TaskRun)
        .where(TaskRun.workspace_id == workspace.id)
        .order_by(TaskRun.created_at.desc())
        .limit(limit)
    )
    if status_filter:
        q = q.where(TaskRun.status == status_filter)
    result = await session.execute(q)
    runs = result.scalars().all()
    return [TaskRunResponse.from_run(run) for run in runs]

@router.get("/{task_id}", response_model=CollectionTaskResponse)
async def get_task_item(
    task_id: uuid.UUID,
    session: SessionDep,
) -> CollectionTaskResponse:
    workspace = await get_demo_workspace(session)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="demo_workspace_unavailable",
        )
    try:
        task = await get_task_or_raise(session, workspace, task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return CollectionTaskResponse.from_task(task)

@router.post("/{task_id}/run", response_model=TaskRunResponse, status_code=status.HTTP_201_CREATED)
async def run_task_item(
    task_id: uuid.UUID,
    session: SessionDep,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> TaskRunResponse:
    workspace = await get_demo_workspace(session)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="demo_workspace_unavailable",
        )
    try:
        result = await run_task_now(
            session,
            workspace,
            task_id,
            idempotency_key=idempotency_key,
        )
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except (TaskAlreadyRunningError, TaskNotRunnableError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    if result.idempotency_replayed:
        response.status_code = status.HTTP_200_OK
    return TaskRunResponse.from_run(
        result.run,
        idempotency_replayed=result.idempotency_replayed,
        idempotency_key_hash=result.idempotency_key_hash,
    )

@router.post("/{task_id}/pause", response_model=CollectionTaskResponse)
async def pause_task_item(
    task_id: uuid.UUID,
    session: SessionDep,
) -> CollectionTaskResponse:
    workspace = await get_demo_workspace(session)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="demo_workspace_unavailable",
        )
    try:
        task = await pause_task(session, workspace, task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return CollectionTaskResponse.from_task(task)

@router.post("/{task_id}/resume", response_model=CollectionTaskResponse)
async def resume_task_item(
    task_id: uuid.UUID,
    session: SessionDep,
) -> CollectionTaskResponse:
    workspace = await get_demo_workspace(session)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="demo_workspace_unavailable",
        )
    try:
        task = await resume_task(session, workspace, task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return CollectionTaskResponse.from_task(task)

@router.get("/{task_id}/runs", response_model=list[TaskRunResponse])
async def list_task_run_items(
    task_id: uuid.UUID,
    session: SessionDep,
) -> list[TaskRunResponse]:
    workspace = await get_demo_workspace(session)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="demo_workspace_unavailable",
        )
    try:
        runs = await get_task_runs(session, workspace, task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return [TaskRunResponse.from_run(run) for run in runs]
