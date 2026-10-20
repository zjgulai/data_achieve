from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Response, status
from sqlalchemy import select

from data_intelligence_hub.api.deps import SessionDep, WorkspaceDep
from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.repositories.scheduler import get_latest_scheduler_tick
from data_intelligence_hub.repositories.tasks import list_task_runs_by_ids
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
    workspace: WorkspaceDep,
    project_id: Annotated[uuid.UUID | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[CollectionTaskResponse]:
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
    workspace: WorkspaceDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    project_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[TaskRunResponse]:
    q = (
        select(TaskRun, CollectionTask)
        .join(CollectionTask, CollectionTask.id == TaskRun.task_id)
        .where(TaskRun.workspace_id == workspace.id)
        .order_by(TaskRun.created_at.desc())
        .limit(limit)
    )
    if status_filter:
        q = q.where(TaskRun.status == status_filter)
    if project_id is not None:
        # 按项目过滤：运行属于任务，任务属于项目。
        q = q.where(CollectionTask.project_id == project_id)
    result = await session.execute(q)
    return [
        TaskRunResponse.from_run(run, task=task)
        for run, task in result.all()
    ]

@router.get("/runs/{run_id}", response_model=TaskRunResponse)
async def get_task_run_item(
    run_id: uuid.UUID,
    session: SessionDep,
    workspace: WorkspaceDep,
) -> TaskRunResponse:
    # 单条查询同样按 workspace 过滤；不存在与跨 workspace 统一返回 404。
    runs = await list_task_runs_by_ids(session, workspace.id, {run_id})
    run = runs.get(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="task_run_not_found",
        )
    task = await session.get(CollectionTask, run.task_id)
    return TaskRunResponse.from_run(run, task=task)

@router.get("/{task_id}", response_model=CollectionTaskResponse)
async def get_task_item(
    task_id: uuid.UUID,
    session: SessionDep,
    workspace: WorkspaceDep,
) -> CollectionTaskResponse:
    try:
        task = await get_task_or_raise(session, workspace, task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return CollectionTaskResponse.from_task(task)

@router.post("/{task_id}/run", response_model=TaskRunResponse, status_code=status.HTTP_201_CREATED)
async def run_task_item(
    task_id: uuid.UUID,
    session: SessionDep,
    workspace: WorkspaceDep,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> TaskRunResponse:
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
    workspace: WorkspaceDep,
) -> CollectionTaskResponse:
    try:
        task = await pause_task(session, workspace, task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return CollectionTaskResponse.from_task(task)

@router.post("/{task_id}/resume", response_model=CollectionTaskResponse)
async def resume_task_item(
    task_id: uuid.UUID,
    session: SessionDep,
    workspace: WorkspaceDep,
) -> CollectionTaskResponse:
    try:
        task = await resume_task(session, workspace, task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return CollectionTaskResponse.from_task(task)

@router.get("/{task_id}/runs", response_model=list[TaskRunResponse])
async def list_task_run_items(
    task_id: uuid.UUID,
    session: SessionDep,
    workspace: WorkspaceDep,
) -> list[TaskRunResponse]:
    try:
        runs = await get_task_runs(session, workspace, task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return [TaskRunResponse.from_run(run) for run in runs]
