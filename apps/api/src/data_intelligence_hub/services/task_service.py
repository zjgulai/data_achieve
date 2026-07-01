from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.tasks import (
    TaskWithLatestRun,
    get_task,
    list_task_runs,
    list_tasks_with_latest_run,
)
from data_intelligence_hub.services.collector_service import execute_collection_task
from data_intelligence_hub.services.exceptions import (
    TaskAlreadyRunningError,
    TaskNotFoundError,
    TaskNotRunnableError,
)

TASK_MANUAL_RUN_IDEMPOTENCY_SCOPE = "task_manual_run"
TASK_RUN_IDEMPOTENCY_LOG_STEP = "idempotency_key_recorded"


@dataclass(frozen=True)
class TaskRunResult:
    run: TaskRun
    idempotency_replayed: bool = False
    idempotency_key_hash: str | None = None


async def get_collection_tasks(
    session: AsyncSession,
    workspace: Workspace,
    project_id: uuid.UUID | None,
    status: str | None,
) -> list[TaskWithLatestRun]:
    return await list_tasks_with_latest_run(
        session,
        workspace.id,
        project_id=project_id,
        status=status,
    )


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
    idempotency_key: str | None = None,
) -> TaskRunResult:
    task = await get_task_or_raise(session, workspace, task_id)
    idempotency_key_hash = _manual_task_run_idempotency_key_hash(idempotency_key)
    if idempotency_key_hash is not None:
        existing_run = await _find_manual_task_run_by_idempotency_key_hash(
            session,
            workspace_id=workspace.id,
            task_id=task.id,
            idempotency_key_hash=idempotency_key_hash,
        )
        if existing_run is not None:
            return TaskRunResult(
                run=existing_run,
                idempotency_replayed=True,
                idempotency_key_hash=idempotency_key_hash,
            )
    if task.status == "running":
        raise TaskAlreadyRunningError
    if task.status != "enabled":
        raise TaskNotRunnableError
    run = await execute_collection_task(
        session,
        workspace,
        task,
        idempotency_key_hash=idempotency_key_hash,
    )
    return TaskRunResult(
        run=run,
        idempotency_replayed=False,
        idempotency_key_hash=idempotency_key_hash,
    )


async def get_task_runs(
    session: AsyncSession,
    workspace: Workspace,
    task_id: uuid.UUID,
) -> list[TaskRun]:
    await get_task_or_raise(session, workspace, task_id)
    return await list_task_runs(session, workspace.id, task_id)


def _manual_task_run_idempotency_key_hash(idempotency_key: str | None) -> str | None:
    if idempotency_key is None:
        return None
    normalized_key = idempotency_key.strip()
    if not normalized_key:
        return None
    payload = f"{TASK_MANUAL_RUN_IDEMPOTENCY_SCOPE}:{normalized_key}".encode()
    return hashlib.sha256(payload).hexdigest()


async def _find_manual_task_run_by_idempotency_key_hash(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    idempotency_key_hash: str,
) -> TaskRun | None:
    result = await session.execute(
        select(TaskRun)
        .where(TaskRun.workspace_id == workspace_id, TaskRun.task_id == task_id)
        .order_by(TaskRun.created_at.desc())
    )
    for run in result.scalars().all():
        if _task_run_idempotency_key_hash(run.logs) == idempotency_key_hash:
            return run
    return None


def _task_run_idempotency_key_hash(logs: list[dict[str, Any]]) -> str | None:
    for log in logs:
        if log.get("step") != TASK_RUN_IDEMPOTENCY_LOG_STEP:
            continue
        if log.get("scope") != TASK_MANUAL_RUN_IDEMPOTENCY_SCOPE:
            continue
        idempotency_key_hash = log.get("idempotency_key_hash")
        if isinstance(idempotency_key_hash, str) and idempotency_key_hash:
            return idempotency_key_hash
    return None
