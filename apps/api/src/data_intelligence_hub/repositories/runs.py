"""``runs`` 与 ``run_steps`` 表的读写。

仓储只做查询、插入与更新，并调用 ``flush``。
事务提交权留给服务层或脚本入口。本模块不调用 ``commit``。
读写运行必须带 ``workspace_id`` 隔离。
状态迁移只允许前向。终态不得回到 ``running``。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.run import (
    Run,
    RunOutcome,
    RunStatus,
    RunStep,
    RunStepStatus,
)

# 运行状态迁移表。终态的目标集合为空。
RUN_TRANSITIONS: Final[dict[RunStatus, frozenset[RunStatus]]] = {
    RunStatus.QUEUED: frozenset(
        {RunStatus.RUNNING, RunStatus.FAILED, RunStatus.CANCELLED}
    ),
    RunStatus.RUNNING: frozenset(
        {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}
    ),
    RunStatus.COMPLETED: frozenset(),
    RunStatus.FAILED: frozenset(),
    RunStatus.CANCELLED: frozenset(),
}

TERMINAL_RUN_STATUSES: Final[frozenset[RunStatus]] = frozenset(
    {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}
)

# 步骤状态迁移表。终态的目标集合为空。
STEP_TRANSITIONS: Final[dict[RunStepStatus, frozenset[RunStepStatus]]] = {
    RunStepStatus.PENDING: frozenset(
        {
            RunStepStatus.RUNNING,
            RunStepStatus.SUCCESS,
            RunStepStatus.EMPTY,
            RunStepStatus.CONFIG_GATED,
            RunStepStatus.FAILED,
            RunStepStatus.SKIPPED,
        }
    ),
    RunStepStatus.RUNNING: frozenset(
        {
            RunStepStatus.SUCCESS,
            RunStepStatus.EMPTY,
            RunStepStatus.CONFIG_GATED,
            RunStepStatus.FAILED,
            RunStepStatus.SKIPPED,
        }
    ),
    RunStepStatus.SUCCESS: frozenset(),
    RunStepStatus.EMPTY: frozenset(),
    RunStepStatus.CONFIG_GATED: frozenset(),
    RunStepStatus.FAILED: frozenset(),
    RunStepStatus.SKIPPED: frozenset(),
}

TERMINAL_STEP_STATUSES: Final[frozenset[RunStepStatus]] = frozenset(
    {
        RunStepStatus.SUCCESS,
        RunStepStatus.EMPTY,
        RunStepStatus.CONFIG_GATED,
        RunStepStatus.FAILED,
        RunStepStatus.SKIPPED,
    }
)


def _coerce_run_status(value: RunStatus | str) -> RunStatus:
    """把输入转成运行状态。非法值直接拒绝。"""
    try:
        return RunStatus(value)
    except ValueError as exc:
        raise ValueError(f"非法的运行状态: {value!r}") from exc


def _coerce_step_status(value: RunStepStatus | str) -> RunStepStatus:
    """把输入转成步骤状态。非法值直接拒绝。"""
    try:
        return RunStepStatus(value)
    except ValueError as exc:
        raise ValueError(f"非法的步骤状态: {value!r}") from exc


def _coerce_outcome(value: RunOutcome | str) -> RunOutcome:
    """把输入转成运行结果。非法值直接拒绝。"""
    try:
        return RunOutcome(value)
    except ValueError as exc:
        raise ValueError(f"非法的运行结果: {value!r}") from exc


async def find_by_idempotency_key(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    idempotency_key_hash: str,
) -> Run | None:
    """按工作区与幂等键摘要查一行。未命中时返回 None。

    这是幂等重放的唯一查询入口。路由在全部前置校验之前调用它，
    这样重放返回的是首次创建的那一行，不会被当下的配置变化挡住。
    ``create_run`` 内部也调用它，避免两处各写一份查询。
    """
    return await session.scalar(
        select(Run).where(
            Run.workspace_id == workspace_id,
            Run.idempotency_key_hash == idempotency_key_hash,
        )
    )


async def create_run(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    task_id: uuid.UUID | None = None,
    workflow_version_id: uuid.UUID | None = None,
    status: RunStatus | str = RunStatus.QUEUED,
    outcome: RunOutcome | str | None = None,
    execution_mode: str = "live",
    trigger: str = "manual",
    idempotency_key_hash: str | None = None,
    evidence_grade: str | None = None,
    records_count: int = 0,
    error_message: str | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    lease_expires_at: datetime | None = None,
) -> Run:
    """插入一次运行并 flush。

    ``task_id`` 可空是存储层属性。所有对外入口必须拦住缺少绑定来源的请求。
    计划型运行将来会带 ``plan_id`` 而不是 ``task_id``。

    带幂等键时先查后插。已存在时返回原行，不新增。
    数据库唯一索引拦住并发下的重复插入。
    """
    if idempotency_key_hash is not None:
        existing = await session.scalar(
            select(Run).where(
                Run.workspace_id == workspace_id,
                Run.idempotency_key_hash == idempotency_key_hash,
            )
        )
        if existing is not None:
            return existing

    record = Run(
        workspace_id=workspace_id,
        project_id=project_id,
        task_id=task_id,
        workflow_version_id=workflow_version_id,
        status=_coerce_run_status(status).value,
        outcome=None if outcome is None else _coerce_outcome(outcome).value,
        execution_mode=execution_mode,
        trigger=trigger,
        idempotency_key_hash=idempotency_key_hash,
        evidence_grade=evidence_grade,
        records_count=records_count,
        error_message=error_message,
        started_at=started_at,
        finished_at=finished_at,
        lease_expires_at=lease_expires_at,
    )
    session.add(record)
    await session.flush()
    return record


async def get_run(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    run_id: uuid.UUID,
) -> Run | None:
    """按工作区与运行 ID 查一行。未命中时返回 None。"""
    result = await session.execute(
        select(Run).where(
            Run.id == run_id,
            Run.workspace_id == workspace_id,
        )
    )
    return result.scalar_one_or_none()


async def list_runs(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    status: RunStatus | str | None = None,
) -> list[Run]:
    """按工作区与项目返回运行。结果按创建时间倒序。"""
    query: Select[tuple[Run]] = select(Run).where(
        Run.workspace_id == workspace_id,
        Run.project_id == project_id,
    )
    if status is not None:
        query = query.where(Run.status == _coerce_run_status(status).value)
    query = query.order_by(Run.created_at.desc(), Run.id)
    result = await session.execute(query)
    return list(result.scalars().all())


async def transition_run(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    run_id: uuid.UUID,
    status: RunStatus | str,
    outcome: RunOutcome | str | None = None,
    error_message: str | None = None,
    records_count: int | None = None,
    evidence_grade: str | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    lease_expires_at: datetime | None = None,
) -> Run | None:
    """迁移一次运行的状态。

    未命中时返回 None。非法迁移抛出 ``ValueError``。
    进入 ``running`` 时补开始时间。进入终态时补结束时间。
    """
    record = await get_run(session, workspace_id=workspace_id, run_id=run_id)
    if record is None:
        return None

    current = _coerce_run_status(record.status)
    target = _coerce_run_status(status)
    if target not in RUN_TRANSITIONS[current]:
        raise ValueError(f"非法的运行状态迁移: {current.value} -> {target.value}")

    record.status = target.value
    if outcome is not None:
        record.outcome = _coerce_outcome(outcome).value
    if error_message is not None:
        record.error_message = error_message
    if records_count is not None:
        record.records_count = records_count
    if evidence_grade is not None:
        record.evidence_grade = evidence_grade
    if lease_expires_at is not None:
        record.lease_expires_at = lease_expires_at
    if started_at is not None:
        record.started_at = started_at
    elif target is RunStatus.RUNNING and record.started_at is None:
        record.started_at = datetime.now(UTC)
    if finished_at is not None:
        record.finished_at = finished_at
    elif target in TERMINAL_RUN_STATUSES and record.finished_at is None:
        record.finished_at = datetime.now(UTC)

    await session.flush()
    return record


async def add_step(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    step_index: int,
    endpoint_type: str,
    collector_type: str,
    task_run_id: uuid.UUID | None = None,
    status: RunStepStatus | str = RunStepStatus.PENDING,
    outcome: RunOutcome | str | None = None,
    records_count: int = 0,
    unit: str | None = None,
    quantity: Decimal | None = None,
    unit_price: Decimal | None = None,
    total_cost_usd: Decimal | None = None,
    error_message: str | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> RunStep:
    """插入一个运行步骤并 flush。

    成本四列来自契约 §4.1。金额必须是 Decimal，不接受 float。
    """
    record = RunStep(
        run_id=run_id,
        step_index=step_index,
        endpoint_type=endpoint_type,
        collector_type=collector_type,
        task_run_id=task_run_id,
        status=_coerce_step_status(status).value,
        outcome=None if outcome is None else _coerce_outcome(outcome).value,
        records_count=records_count,
        unit=unit,
        quantity=quantity,
        unit_price=unit_price,
        total_cost_usd=total_cost_usd,
        error_message=error_message,
        started_at=started_at,
        finished_at=finished_at,
    )
    session.add(record)
    await session.flush()
    return record


async def list_steps(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
) -> list[RunStep]:
    """按 ``step_index`` 升序返回一个运行的步骤。"""
    result = await session.execute(
        select(RunStep)
        .where(RunStep.run_id == run_id)
        .order_by(RunStep.step_index)
    )
    return list(result.scalars().all())


async def transition_step(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    step_id: uuid.UUID,
    status: RunStepStatus | str,
    outcome: RunOutcome | str | None = None,
    error_message: str | None = None,
    records_count: int | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> RunStep | None:
    """迁移一个步骤的状态。

    未命中时返回 None。非法迁移抛出 ``ValueError``。
    进入 ``running`` 时补开始时间。进入终态时补结束时间。
    """
    result = await session.execute(
        select(RunStep).where(
            RunStep.id == step_id,
            RunStep.run_id == run_id,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None

    current = _coerce_step_status(record.status)
    target = _coerce_step_status(status)
    if target not in STEP_TRANSITIONS[current]:
        raise ValueError(f"非法的步骤状态迁移: {current.value} -> {target.value}")

    record.status = target.value
    if outcome is not None:
        record.outcome = _coerce_outcome(outcome).value
    if error_message is not None:
        record.error_message = error_message
    if records_count is not None:
        record.records_count = records_count
    if started_at is not None:
        record.started_at = started_at
    elif target is RunStepStatus.RUNNING and record.started_at is None:
        record.started_at = datetime.now(UTC)
    if finished_at is not None:
        record.finished_at = finished_at
    elif target in TERMINAL_STEP_STATUSES and record.finished_at is None:
        record.finished_at = datetime.now(UTC)

    await session.flush()
    return record


__all__ = [
    "RUN_TRANSITIONS",
    "STEP_TRANSITIONS",
    "TERMINAL_RUN_STATUSES",
    "TERMINAL_STEP_STATUSES",
    "add_step",
    "create_run",
    "get_run",
    "list_runs",
    "list_steps",
    "transition_run",
    "transition_step",
]
