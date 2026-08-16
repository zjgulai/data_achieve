from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import Select, asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.workflow_execution import (
    StepRun,
    StepRunAttempt,
    WorkflowBudgetAccount,
    WorkflowBudgetLedgerEntry,
    WorkflowFallbackDecision,
    WorkflowRun,
    WorkflowRunRequest,
    WorkflowShadowComparison,
    WorkflowStepCheckpoint,
)
from data_intelligence_hub.models.workflow_plan import WorkflowPlan, WorkflowVersion

MAX_WORKFLOW_RUN_PAGE_SIZE = 100


def _validate_pagination(*, limit: int, offset: int) -> None:
    if not 1 <= limit <= MAX_WORKFLOW_RUN_PAGE_SIZE or offset < 0:
        raise ValueError("workflow_run_pagination_invalid")


def project_lock_statement(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
) -> Select[tuple[Project]]:
    return (
        select(Project)
        .where(Project.workspace_id == workspace_id, Project.id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def workflow_plan_lock_statement(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID,
) -> Select[tuple[WorkflowPlan]]:
    return (
        select(WorkflowPlan)
        .where(
            WorkflowPlan.workspace_id == workspace_id,
            WorkflowPlan.project_id == project_id,
            WorkflowPlan.id == workflow_plan_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def workflow_version_lock_statement(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID,
    workflow_version_id: uuid.UUID,
) -> Select[tuple[WorkflowVersion]]:
    return (
        select(WorkflowVersion)
        .where(
            WorkflowVersion.workspace_id == workspace_id,
            WorkflowVersion.project_id == project_id,
            WorkflowVersion.workflow_plan_id == workflow_plan_id,
            WorkflowVersion.id == workflow_version_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def get_project(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
) -> Project | None:
    result = await session.execute(
        select(Project).where(
            Project.workspace_id == workspace_id,
            Project.id == project_id,
        )
    )
    return result.scalar_one_or_none()


async def get_project_for_update(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
) -> Project | None:
    result = await session.execute(project_lock_statement(workspace_id, project_id))
    return result.scalar_one_or_none()


async def get_workflow_plan(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID,
) -> WorkflowPlan | None:
    result = await session.execute(
        select(WorkflowPlan).where(
            WorkflowPlan.workspace_id == workspace_id,
            WorkflowPlan.project_id == project_id,
            WorkflowPlan.id == workflow_plan_id,
        )
    )
    return result.scalar_one_or_none()


async def get_workflow_plan_for_update(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID,
) -> WorkflowPlan | None:
    result = await session.execute(
        workflow_plan_lock_statement(workspace_id, project_id, workflow_plan_id)
    )
    return result.scalar_one_or_none()


async def get_workflow_version(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID,
    workflow_version_id: uuid.UUID,
) -> WorkflowVersion | None:
    result = await session.execute(
        select(WorkflowVersion).where(
            WorkflowVersion.workspace_id == workspace_id,
            WorkflowVersion.project_id == project_id,
            WorkflowVersion.workflow_plan_id == workflow_plan_id,
            WorkflowVersion.id == workflow_version_id,
        )
    )
    return result.scalar_one_or_none()


async def get_workflow_version_for_update(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID,
    workflow_version_id: uuid.UUID,
) -> WorkflowVersion | None:
    result = await session.execute(
        workflow_version_lock_statement(
            workspace_id,
            project_id,
            workflow_plan_id,
            workflow_version_id,
        )
    )
    return result.scalar_one_or_none()


async def get_workflow_run(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
) -> WorkflowRun | None:
    result = await session.execute(
        select(WorkflowRun).where(
            WorkflowRun.workspace_id == workspace_id,
            WorkflowRun.project_id == project_id,
            WorkflowRun.id == workflow_run_id,
        )
    )
    return result.scalar_one_or_none()


async def list_workflow_runs(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    *,
    workflow_plan_id: uuid.UUID | None = None,
    workflow_version_id: uuid.UUID | None = None,
    limit: int,
    offset: int,
) -> list[WorkflowRun]:
    _validate_pagination(limit=limit, offset=offset)
    statement = (
        select(WorkflowRun)
        .where(
            WorkflowRun.workspace_id == workspace_id,
            WorkflowRun.project_id == project_id,
        )
        .order_by(desc(WorkflowRun.created_at), desc(WorkflowRun.id))
        .limit(limit)
        .offset(offset)
    )
    if workflow_plan_id is not None:
        statement = statement.where(WorkflowRun.workflow_plan_id == workflow_plan_id)
    if workflow_version_id is not None:
        statement = statement.where(WorkflowRun.workflow_version_id == workflow_version_id)
    result = await session.execute(statement)
    return list(result.scalars().all())


async def count_workflow_runs(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    *,
    workflow_plan_id: uuid.UUID | None = None,
    workflow_version_id: uuid.UUID | None = None,
) -> int:
    statement = (
        select(func.count())
        .select_from(WorkflowRun)
        .where(
            WorkflowRun.workspace_id == workspace_id,
            WorkflowRun.project_id == project_id,
        )
    )
    if workflow_plan_id is not None:
        statement = statement.where(WorkflowRun.workflow_plan_id == workflow_plan_id)
    if workflow_version_id is not None:
        statement = statement.where(WorkflowRun.workflow_version_id == workflow_version_id)
    result = await session.execute(statement)
    return int(result.scalar_one())


async def list_step_runs(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
) -> list[StepRun]:
    result = await session.execute(
        select(StepRun)
        .where(
            StepRun.workspace_id == workspace_id,
            StepRun.project_id == project_id,
            StepRun.workflow_run_id == workflow_run_id,
        )
        .order_by(
            asc(StepRun.sequence),
            asc(StepRun.step_ref),
            asc(StepRun.id),
        )
    )
    return list(result.scalars().all())


async def list_step_run_attempts_for_run(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
) -> list[StepRunAttempt]:
    result = await session.execute(
        select(StepRunAttempt)
        .where(
            StepRunAttempt.workspace_id == workspace_id,
            StepRunAttempt.project_id == project_id,
            StepRunAttempt.workflow_run_id == workflow_run_id,
        )
        .order_by(
            asc(StepRunAttempt.step_run_id),
            asc(StepRunAttempt.retry_generation),
            asc(StepRunAttempt.attempt_number),
            asc(StepRunAttempt.id),
        )
    )
    return list(result.scalars().all())


async def list_workflow_fallback_decisions_for_run(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
) -> list[WorkflowFallbackDecision]:
    result = await session.execute(
        select(WorkflowFallbackDecision)
        .where(
            WorkflowFallbackDecision.workspace_id == workspace_id,
            WorkflowFallbackDecision.project_id == project_id,
            WorkflowFallbackDecision.workflow_run_id == workflow_run_id,
        )
        .order_by(
            asc(WorkflowFallbackDecision.step_ref),
            asc(WorkflowFallbackDecision.created_at),
            asc(WorkflowFallbackDecision.id),
        )
    )
    return list(result.scalars().all())


def completed_workflow_run_request_statement(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    idempotency_scope: str,
    idempotency_key_hash: str,
) -> Select[tuple[WorkflowRunRequest]]:
    return select(WorkflowRunRequest).where(
        WorkflowRunRequest.workspace_id == workspace_id,
        WorkflowRunRequest.project_id == project_id,
        WorkflowRunRequest.created_by_user_id == created_by_user_id,
        WorkflowRunRequest.idempotency_scope == idempotency_scope,
        WorkflowRunRequest.idempotency_key_hash == idempotency_key_hash,
        WorkflowRunRequest.outcome.in_(("completed", "held")),
    )


async def get_completed_workflow_run_request(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    idempotency_scope: str,
    idempotency_key_hash: str,
) -> WorkflowRunRequest | None:
    result = await session.execute(
        completed_workflow_run_request_statement(
            workspace_id,
            project_id,
            created_by_user_id,
            idempotency_scope,
            idempotency_key_hash,
        )
    )
    return result.scalar_one_or_none()


async def get_first_workflow_fallback_decision(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
    idempotency_scope: str,
    idempotency_key_hash: str,
) -> WorkflowFallbackDecision | None:
    result = await session.execute(
        select(WorkflowFallbackDecision)
        .where(
            WorkflowFallbackDecision.workspace_id == workspace_id,
            WorkflowFallbackDecision.project_id == project_id,
            WorkflowFallbackDecision.created_by_user_id == created_by_user_id,
            WorkflowFallbackDecision.idempotency_scope == idempotency_scope,
            WorkflowFallbackDecision.idempotency_key_hash == idempotency_key_hash,
        )
        .order_by(
            asc(WorkflowFallbackDecision.created_at),
            asc(WorkflowFallbackDecision.step_ref),
            asc(WorkflowFallbackDecision.id),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def add_workflow_run(
    session: AsyncSession,
    workflow_run: WorkflowRun,
) -> WorkflowRun:
    session.add(workflow_run)
    await session.flush()
    return workflow_run


async def add_step_runs(
    session: AsyncSession,
    step_runs: Sequence[StepRun],
) -> tuple[StepRun, ...]:
    frozen_steps = tuple(step_runs)
    session.add_all(frozen_steps)
    await session.flush()
    return frozen_steps


async def add_step_run_attempts(
    session: AsyncSession,
    attempts: Sequence[StepRunAttempt],
) -> tuple[StepRunAttempt, ...]:
    frozen_attempts = tuple(attempts)
    session.add_all(frozen_attempts)
    await session.flush()
    return frozen_attempts


async def add_workflow_fallback_decision(
    session: AsyncSession,
    decision: WorkflowFallbackDecision,
) -> WorkflowFallbackDecision:
    session.add(decision)
    await session.flush()
    return decision


async def add_workflow_run_request(
    session: AsyncSession,
    run_request: WorkflowRunRequest,
) -> WorkflowRunRequest:
    session.add(run_request)
    await session.flush()
    return run_request


async def add_workflow_shadow_comparisons(
    session: AsyncSession,
    comparisons: Sequence[WorkflowShadowComparison],
) -> tuple[WorkflowShadowComparison, ...]:
    frozen_comparisons = tuple(comparisons)
    session.add_all(frozen_comparisons)
    await session.flush()
    return frozen_comparisons


async def list_workflow_shadow_comparisons(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
) -> tuple[WorkflowShadowComparison, ...]:
    result = await session.execute(
        select(WorkflowShadowComparison)
        .where(
            WorkflowShadowComparison.workspace_id == workspace_id,
            WorkflowShadowComparison.project_id == project_id,
            WorkflowShadowComparison.workflow_run_id == workflow_run_id,
        )
        .order_by(
            asc(WorkflowShadowComparison.requirement_ref),
            asc(WorkflowShadowComparison.id),
        )
    )
    return tuple(result.scalars().all())


async def list_workflow_step_checkpoints(
    session: AsyncSession,
    execution_session_id: uuid.UUID,
    step_ref: str,
) -> tuple[WorkflowStepCheckpoint, ...]:
    result = await session.execute(
        select(WorkflowStepCheckpoint)
        .where(
            WorkflowStepCheckpoint.execution_session_id == execution_session_id,
            WorkflowStepCheckpoint.step_ref == step_ref,
        )
        .order_by(
            asc(WorkflowStepCheckpoint.page_number),
            asc(WorkflowStepCheckpoint.id),
        )
    )
    return tuple(result.scalars().all())


async def list_workflow_step_checkpoints_for_run(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID,
    workflow_version_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
) -> tuple[WorkflowStepCheckpoint, ...]:
    result = await session.execute(
        select(WorkflowStepCheckpoint)
        .where(
            WorkflowStepCheckpoint.execution_session_id == workflow_run_id,
            WorkflowStepCheckpoint.workspace_id == workspace_id,
            WorkflowStepCheckpoint.project_id == project_id,
            WorkflowStepCheckpoint.workflow_plan_id == workflow_plan_id,
            WorkflowStepCheckpoint.workflow_version_id == workflow_version_id,
        )
        .order_by(
            asc(WorkflowStepCheckpoint.step_ref),
            asc(WorkflowStepCheckpoint.page_number),
            asc(WorkflowStepCheckpoint.id),
        )
    )
    return tuple(result.scalars().all())


async def add_workflow_step_checkpoint(
    session: AsyncSession,
    checkpoint: WorkflowStepCheckpoint,
) -> WorkflowStepCheckpoint:
    session.add(checkpoint)
    await session.flush()
    return checkpoint


async def get_workflow_budget_account(
    session: AsyncSession,
    execution_session_id: uuid.UUID,
) -> WorkflowBudgetAccount | None:
    result = await session.execute(
        select(WorkflowBudgetAccount).where(
            WorkflowBudgetAccount.execution_session_id == execution_session_id,
        )
    )
    return result.scalar_one_or_none()


async def get_workflow_budget_account_for_run(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_plan_id: uuid.UUID,
    workflow_version_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
) -> WorkflowBudgetAccount | None:
    result = await session.execute(
        select(WorkflowBudgetAccount).where(
            WorkflowBudgetAccount.execution_session_id == workflow_run_id,
            WorkflowBudgetAccount.workspace_id == workspace_id,
            WorkflowBudgetAccount.project_id == project_id,
            WorkflowBudgetAccount.workflow_plan_id == workflow_plan_id,
            WorkflowBudgetAccount.workflow_version_id == workflow_version_id,
        )
    )
    return result.scalar_one_or_none()


async def get_workflow_budget_account_for_update(
    session: AsyncSession,
    execution_session_id: uuid.UUID,
) -> WorkflowBudgetAccount | None:
    result = await session.execute(
        select(WorkflowBudgetAccount)
        .where(WorkflowBudgetAccount.execution_session_id == execution_session_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def add_workflow_budget_account(
    session: AsyncSession,
    account: WorkflowBudgetAccount,
) -> WorkflowBudgetAccount:
    session.add(account)
    await session.flush()
    return account


async def list_workflow_budget_ledger_entries(
    session: AsyncSession,
    budget_account_id: uuid.UUID,
) -> tuple[WorkflowBudgetLedgerEntry, ...]:
    result = await session.execute(
        select(WorkflowBudgetLedgerEntry)
        .where(WorkflowBudgetLedgerEntry.budget_account_id == budget_account_id)
        .order_by(
            asc(WorkflowBudgetLedgerEntry.entry_number),
            asc(WorkflowBudgetLedgerEntry.id),
        )
    )
    return tuple(result.scalars().all())


async def add_workflow_budget_ledger_entry(
    session: AsyncSession,
    entry: WorkflowBudgetLedgerEntry,
) -> WorkflowBudgetLedgerEntry:
    session.add(entry)
    await session.flush()
    return entry


__all__ = [
    "MAX_WORKFLOW_RUN_PAGE_SIZE",
    "add_step_run_attempts",
    "add_step_runs",
    "add_workflow_budget_account",
    "add_workflow_budget_ledger_entry",
    "add_workflow_fallback_decision",
    "add_workflow_run",
    "add_workflow_run_request",
    "add_workflow_shadow_comparisons",
    "add_workflow_step_checkpoint",
    "completed_workflow_run_request_statement",
    "count_workflow_runs",
    "get_completed_workflow_run_request",
    "get_first_workflow_fallback_decision",
    "get_project",
    "get_project_for_update",
    "get_workflow_plan",
    "get_workflow_plan_for_update",
    "get_workflow_run",
    "get_workflow_version",
    "get_workflow_version_for_update",
    "get_workflow_budget_account",
    "get_workflow_budget_account_for_run",
    "get_workflow_budget_account_for_update",
    "list_step_runs",
    "list_step_run_attempts_for_run",
    "list_workflow_shadow_comparisons",
    "list_workflow_fallback_decisions_for_run",
    "list_workflow_budget_ledger_entries",
    "list_workflow_step_checkpoints",
    "list_workflow_step_checkpoints_for_run",
    "list_workflow_runs",
    "project_lock_statement",
    "workflow_plan_lock_statement",
    "workflow_version_lock_statement",
]
