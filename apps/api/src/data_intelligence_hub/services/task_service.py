from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.tasks import get_task, list_task_runs, list_tasks
from data_intelligence_hub.services.collector_service import execute_collection_task
from data_intelligence_hub.services.exceptions import (
    TaskAlreadyRunningError,
    TaskNotFoundError,
    TaskNotRunnableError,
)


async def get_collection_tasks(
    session: AsyncSession,
    workspace: Workspace,
    project_id: uuid.UUID | None,
    status: str | None,
) -> list[CollectionTask]:
    return await list_tasks(session, workspace.id, project_id=project_id, status=status)


async def get_task_or_raise(
    session: AsyncSession,
    workspace: Workspace,
    task_id: uuid.UUID,
) -> CollectionTask:
    task = await get_task(session, workspace.id, task_id)
    if task is None:
        raise TaskNotFoundError
    return task


async def pause_task(
    session: AsyncSession,
    workspace: Workspace,
    task_id: uuid.UUID,
) -> CollectionTask:
    task = await get_task_or_raise(session, workspace, task_id)
    task.status = "paused"
    await session.commit()
    await session.refresh(task)
    return task


async def resume_task(
    session: AsyncSession,
    workspace: Workspace,
    task_id: uuid.UUID,
) -> CollectionTask:
    task = await get_task_or_raise(session, workspace, task_id)
    task.status = "enabled"
    await session.commit()
    await session.refresh(task)
    return task


async def run_task_now(
    session: AsyncSession,
    workspace: Workspace,
    task_id: uuid.UUID,
) -> TaskRun:
    task = await get_task_or_raise(session, workspace, task_id)
    if task.status == "running":
        raise TaskAlreadyRunningError
    if task.status != "enabled":
        raise TaskNotRunnableError
    return await execute_collection_task(session, workspace, task)


async def get_task_runs(
    session: AsyncSession,
    workspace: Workspace,
    task_id: uuid.UUID,
) -> list[TaskRun]:
    await get_task_or_raise(session, workspace, task_id)
    return await list_task_runs(session, workspace.id, task_id)
