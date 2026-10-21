"""``/api/runs`` 的运行端点。

五个端点都按 ``context.workspace`` 隔离。
跨工作区一律返回 404。不返回 403，避免泄露资源存在性。
所有端点都使用 ``get_authenticated_context``。无有效 cookie 一律 401。

路由层负责提交事务。仓储只调用 ``flush``。
路由不写 SQL。读写全部经过 ``repositories/runs.py``。
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.api.deps import (
    AuthContext,
    SessionDep,
    get_authenticated_context,
)
from data_intelligence_hub.models.run import Run, RunOutcome, RunStatus, RunStepStatus
from data_intelligence_hub.repositories import runs as runs_repository
from data_intelligence_hub.repositories.projects import get_project
from data_intelligence_hub.repositories.tasks import get_task
from data_intelligence_hub.schemas.run import (
    RunCreateRequest,
    RunOutcomeResponse,
    RunResponse,
    RunStepResponse,
)

router = APIRouter(tags=["runs"])

# 可取消的两个状态。终态不得再取消。
_CANCELLABLE_STATUSES = frozenset({RunStatus.QUEUED, RunStatus.RUNNING})


def _hash_idempotency_key(key: str) -> str:
    """把幂等键转成 64 位十六进制摘要。数据库只存摘要。"""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


async def _get_run_or_404(
    session: AsyncSession,
    context: AuthContext,
    run_id: uuid.UUID,
) -> Run:
    """按当前工作区取运行。未命中一律 404。"""
    run = await runs_repository.get_run(
        session,
        workspace_id=context.workspace.id,
        run_id=run_id,
    )
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="run_not_found",
        )
    return run


@router.post("", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    body: RunCreateRequest,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> RunResponse:
    """创建一行 ``status=queued`` 的运行。

    先确认项目属于当前工作区。跨工作区返回 404。
    带幂等键时先查后插。并发重复由部分唯一索引兜底。
    冲突后回滚并重查，返回已有行。

    ``runs`` 表没有 ``endpoint_type`` 列。本端点只校验该字段。
    执行时的端点由绑定的采集任务决定。见 ``services/run_executor.py``。
    """
    workspace_id = context.workspace.id

    if await get_project(session, workspace_id, body.project_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="project_not_found",
        )
    if body.task_id is not None:
        task = await get_task(session, workspace_id, body.task_id)
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="task_not_found",
            )

    idempotency_key_hash = (
        _hash_idempotency_key(body.idempotency_key)
        if body.idempotency_key is not None
        else None
    )

    async def _insert() -> Run:
        return await runs_repository.create_run(
            session,
            workspace_id=workspace_id,
            project_id=body.project_id,
            task_id=body.task_id,
            status=RunStatus.QUEUED,
            trigger=body.trigger,
            idempotency_key_hash=idempotency_key_hash,
        )

    try:
        run = await _insert()
        await session.commit()
    except IntegrityError:
        # 并发重复提交时唯一索引拒绝插入。回滚后重查同一幂等键。
        await session.rollback()
        if idempotency_key_hash is None:
            raise
        run = await _insert()
        await session.commit()

    return RunResponse.model_validate(run)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> RunResponse:
    """按运行 ID 返回详情。跨工作区返回 404。"""
    run = await _get_run_or_404(session, context, run_id)
    return RunResponse.model_validate(run)


@router.post("/{run_id}/cancel", response_model=RunResponse)
async def cancel_run(
    run_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> RunResponse:
    """取消一次运行。

    只允许从 ``queued`` 或 ``running`` 转到 ``cancelled``。
    终态返回 409。
    """
    run = await _get_run_or_404(session, context, run_id)
    current_status = RunStatus(run.status)
    if current_status not in _CANCELLABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="run_not_cancellable",
        )

    try:
        updated = await runs_repository.transition_run(
            session,
            workspace_id=context.workspace.id,
            run_id=run_id,
            status=RunStatus.CANCELLED,
        )
    except ValueError as exc:
        # 同一运行可能被并发取消。迁移表会拒绝第二次迁移。
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="run_not_cancellable",
        ) from exc

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="run_not_found",
        )

    await session.commit()
    return RunResponse.model_validate(updated)


@router.get("/{run_id}/steps", response_model=list[RunStepResponse])
async def list_run_steps(
    run_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> list[RunStepResponse]:
    """按 ``step_index`` 升序返回运行的步骤。跨工作区返回 404。"""
    run = await _get_run_or_404(session, context, run_id)
    steps = await runs_repository.list_steps(session, run_id=run.id)
    return [RunStepResponse.model_validate(step) for step in steps]


@router.get("/{run_id}/outcome", response_model=RunOutcomeResponse)
async def get_run_outcome(
    run_id: uuid.UUID,
    session: SessionDep,
    context: Annotated[AuthContext, Depends(get_authenticated_context)],
) -> RunOutcomeResponse:
    """返回运行结果聚合。

    步骤计数按 ``RunStepStatus`` 分组。七个状态全部出现。缺失的取 0。
    """
    run = await _get_run_or_404(session, context, run_id)
    steps = await runs_repository.list_steps(session, run_id=run.id)

    step_counts = {item.value: 0 for item in RunStepStatus}
    for step in steps:
        step_counts[step.status] = step_counts.get(step.status, 0) + 1

    return RunOutcomeResponse(
        run_id=run.id,
        status=RunStatus(run.status),
        outcome=None if run.outcome is None else RunOutcome(run.outcome),
        records_count=run.records_count,
        evidence_grade=run.evidence_grade,
        total_cost_usd=run.total_cost_usd,
        step_counts=step_counts,
        total_steps=len(steps),
        finished_at=run.finished_at,
    )


__all__ = ["router"]
