from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.task import CollectionTask, TaskRun


async def get_task_by_source(
    session: AsyncSession,
    source_id: uuid.UUID,
) -> CollectionTask | None:
    result = await session.execute(
        select(CollectionTask).where(CollectionTask.source_id == source_id)
    )
    return result.scalar_one_or_none()


async def list_tasks(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    status: str | None = None,
) -> list[CollectionTask]:
    statement = select(CollectionTask).where(CollectionTask.workspace_id == workspace_id)
    if project_id is not None:
        statement = statement.where(CollectionTask.project_id == project_id)
    if status is not None:
        statement = statement.where(CollectionTask.status == status)
    statement = statement.order_by(CollectionTask.created_at.desc())
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_task(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
) -> CollectionTask | None:
    result = await session.execute(
        select(CollectionTask).where(
            CollectionTask.id == task_id,
            CollectionTask.workspace_id == workspace_id,
        )
    )
    return result.scalar_one_or_none()


async def list_task_runs(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
) -> list[TaskRun]:
    statement = (
        select(TaskRun)
        .where(TaskRun.workspace_id == workspace_id, TaskRun.task_id == task_id)
        .order_by(TaskRun.created_at.desc())
    )
    result = await session.execute(statement)
    return list(result.scalars().all())
