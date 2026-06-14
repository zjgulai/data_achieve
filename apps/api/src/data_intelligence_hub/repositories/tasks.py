from __future__ import annotations

import uuid
from typing import NamedTuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun


class TaskWithLatestRun(NamedTuple):
    task: CollectionTask
    latest_run: TaskRun | None
    project_name: str
    project_domain: str
    source_name: str
    source_url: str | None


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


async def list_tasks_with_latest_run(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    status: str | None = None,
) -> list[TaskWithLatestRun]:
    run_completed_at = func.coalesce(TaskRun.finished_at, TaskRun.created_at)
    latest_runs = (
        select(TaskRun.task_id, func.max(run_completed_at).label("latest_completed_at"))
        .where(TaskRun.workspace_id == workspace_id)
        .group_by(TaskRun.task_id)
        .subquery()
    )
    statement = (
        select(CollectionTask, TaskRun, Project.name, Project.domain, Source.name, Source.url)
        .join(Project, CollectionTask.project_id == Project.id)
        .join(Source, CollectionTask.source_id == Source.id)
        .outerjoin(latest_runs, CollectionTask.id == latest_runs.c.task_id)
        .outerjoin(
            TaskRun,
            (TaskRun.task_id == CollectionTask.id)
            & (
                func.coalesce(TaskRun.finished_at, TaskRun.created_at)
                == latest_runs.c.latest_completed_at
            ),
        )
        .where(CollectionTask.workspace_id == workspace_id)
        .order_by(CollectionTask.created_at.desc())
    )
    if project_id is not None:
        statement = statement.where(CollectionTask.project_id == project_id)
    if status is not None:
        statement = statement.where(CollectionTask.status == status)
    result = await session.execute(statement)
    return [
        TaskWithLatestRun(
            task=task,
            latest_run=latest_run,
            project_name=project_name,
            project_domain=project_domain,
            source_name=source_name,
            source_url=source_url,
        )
        for task, latest_run, project_name, project_domain, source_name, source_url in result.all()
    ]


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
