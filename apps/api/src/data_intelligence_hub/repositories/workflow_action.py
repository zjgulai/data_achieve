from __future__ import annotations

import uuid

from sqlalchemy import Select, asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.workflow_action import (
    WorkflowRunActionApprovalConsumption,
    WorkflowRunActionApprovalReceiptRecord,
    WorkflowRunActionAuditEvent,
    WorkflowRunActionContext,
    WorkflowRunActionReceiptRecord,
    WorkflowRunActionRequestRecord,
)


def workflow_run_action_context_lock_statement(
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
) -> Select[tuple[WorkflowRunActionContext]]:
    return (
        select(WorkflowRunActionContext)
        .where(
            WorkflowRunActionContext.workspace_id == workspace_id,
            WorkflowRunActionContext.project_id == project_id,
            WorkflowRunActionContext.workflow_run_id == workflow_run_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def get_workflow_run_action_context(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
    for_update: bool = False,
) -> WorkflowRunActionContext | None:
    statement = select(WorkflowRunActionContext).where(
        WorkflowRunActionContext.workspace_id == workspace_id,
        WorkflowRunActionContext.project_id == project_id,
        WorkflowRunActionContext.workflow_run_id == workflow_run_id,
    )
    if for_update:
        statement = workflow_run_action_context_lock_statement(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=workflow_run_id,
        )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def get_workflow_run_action_request_by_idempotency(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    idempotency_scope: str,
    idempotency_key_hash: str,
) -> WorkflowRunActionRequestRecord | None:
    result = await session.execute(
        select(WorkflowRunActionRequestRecord).where(
            WorkflowRunActionRequestRecord.workspace_id == workspace_id,
            WorkflowRunActionRequestRecord.actor_user_id == actor_user_id,
            WorkflowRunActionRequestRecord.idempotency_scope == idempotency_scope,
            WorkflowRunActionRequestRecord.idempotency_key_hash == idempotency_key_hash,
        )
    )
    return result.scalar_one_or_none()


async def get_workflow_run_action_approval_receipt(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
    approval_receipt_id: uuid.UUID,
) -> WorkflowRunActionApprovalReceiptRecord | None:
    result = await session.execute(
        select(WorkflowRunActionApprovalReceiptRecord).where(
            WorkflowRunActionApprovalReceiptRecord.workspace_id == workspace_id,
            WorkflowRunActionApprovalReceiptRecord.project_id == project_id,
            WorkflowRunActionApprovalReceiptRecord.workflow_run_id == workflow_run_id,
            WorkflowRunActionApprovalReceiptRecord.id == approval_receipt_id,
        )
    )
    return result.scalar_one_or_none()


async def get_workflow_run_action_approval_by_idempotency(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    approver_user_id: uuid.UUID,
    idempotency_scope: str,
    idempotency_key_hash: str,
) -> WorkflowRunActionApprovalReceiptRecord | None:
    result = await session.execute(
        select(WorkflowRunActionApprovalReceiptRecord).where(
            WorkflowRunActionApprovalReceiptRecord.workspace_id == workspace_id,
            WorkflowRunActionApprovalReceiptRecord.approver_user_id == approver_user_id,
            WorkflowRunActionApprovalReceiptRecord.idempotency_scope == idempotency_scope,
            WorkflowRunActionApprovalReceiptRecord.idempotency_key_hash == idempotency_key_hash,
        )
    )
    return result.scalar_one_or_none()


async def get_workflow_run_action_receipt_for_request(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    request_id: uuid.UUID,
) -> WorkflowRunActionReceiptRecord | None:
    result = await session.execute(
        select(WorkflowRunActionReceiptRecord).where(
            WorkflowRunActionReceiptRecord.workspace_id == workspace_id,
            WorkflowRunActionReceiptRecord.project_id == project_id,
            WorkflowRunActionReceiptRecord.request_id == request_id,
        )
    )
    return result.scalar_one_or_none()


async def list_workflow_run_action_audit_events(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
    for_update: bool = False,
) -> tuple[WorkflowRunActionAuditEvent, ...]:
    statement = (
        select(WorkflowRunActionAuditEvent)
        .where(
            WorkflowRunActionAuditEvent.workspace_id == workspace_id,
            WorkflowRunActionAuditEvent.project_id == project_id,
            WorkflowRunActionAuditEvent.workflow_run_id == workflow_run_id,
        )
        .order_by(
            asc(WorkflowRunActionAuditEvent.event_number),
            asc(WorkflowRunActionAuditEvent.id),
        )
    )
    if for_update:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    result = await session.execute(statement)
    return tuple(result.scalars().all())


async def add_workflow_run_action_context(
    session: AsyncSession,
    context: WorkflowRunActionContext,
) -> WorkflowRunActionContext:
    session.add(context)
    await session.flush()
    return context


async def add_workflow_run_action_approval_receipt(
    session: AsyncSession,
    approval: WorkflowRunActionApprovalReceiptRecord,
) -> WorkflowRunActionApprovalReceiptRecord:
    session.add(approval)
    await session.flush()
    return approval


async def add_workflow_run_action_request(
    session: AsyncSession,
    request: WorkflowRunActionRequestRecord,
) -> WorkflowRunActionRequestRecord:
    session.add(request)
    await session.flush()
    return request


async def add_workflow_run_action_receipt(
    session: AsyncSession,
    receipt: WorkflowRunActionReceiptRecord,
) -> WorkflowRunActionReceiptRecord:
    session.add(receipt)
    await session.flush()
    return receipt


async def add_workflow_run_action_approval_consumption(
    session: AsyncSession,
    consumption: WorkflowRunActionApprovalConsumption,
) -> WorkflowRunActionApprovalConsumption:
    session.add(consumption)
    await session.flush()
    return consumption


async def add_workflow_run_action_audit_event(
    session: AsyncSession,
    event: WorkflowRunActionAuditEvent,
) -> WorkflowRunActionAuditEvent:
    session.add(event)
    await session.flush()
    return event


__all__ = [
    "add_workflow_run_action_approval_consumption",
    "add_workflow_run_action_approval_receipt",
    "add_workflow_run_action_audit_event",
    "add_workflow_run_action_context",
    "add_workflow_run_action_receipt",
    "add_workflow_run_action_request",
    "get_workflow_run_action_approval_by_idempotency",
    "get_workflow_run_action_approval_receipt",
    "get_workflow_run_action_context",
    "get_workflow_run_action_receipt_for_request",
    "get_workflow_run_action_request_by_idempotency",
    "list_workflow_run_action_audit_events",
    "workflow_run_action_context_lock_statement",
]
