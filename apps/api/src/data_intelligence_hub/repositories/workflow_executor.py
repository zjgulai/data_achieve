from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Select, asc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.workflow_executor import (
    WorkflowCancellationAcknowledgementRecord,
    WorkflowCancellationRequestRecord,
    WorkflowCredentialResolutionPermitRecord,
    WorkflowExecutionDispatchRecord,
    WorkflowExecutionEventRecord,
    WorkflowExecutionLeaseRecord,
    WorkflowProviderCallAuditRecord,
    WorkflowProviderCallPermitRecord,
)


def workflow_execution_lease_lock_statement(
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    dispatch_id: uuid.UUID,
) -> Select[tuple[WorkflowExecutionLeaseRecord]]:
    return (
        select(WorkflowExecutionLeaseRecord)
        .where(
            WorkflowExecutionLeaseRecord.workspace_id == workspace_id,
            WorkflowExecutionLeaseRecord.project_id == project_id,
            WorkflowExecutionLeaseRecord.dispatch_id == dispatch_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def get_workflow_execution_dispatch_by_key(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    dispatch_key: str,
) -> WorkflowExecutionDispatchRecord | None:
    result = await session.execute(
        select(WorkflowExecutionDispatchRecord).where(
            WorkflowExecutionDispatchRecord.workspace_id == workspace_id,
            WorkflowExecutionDispatchRecord.project_id == project_id,
            WorkflowExecutionDispatchRecord.dispatch_key == dispatch_key,
        )
    )
    return result.scalar_one_or_none()


async def list_workflow_execution_dispatches_for_run(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
) -> tuple[WorkflowExecutionDispatchRecord, ...]:
    result = await session.execute(
        select(WorkflowExecutionDispatchRecord)
        .where(
            WorkflowExecutionDispatchRecord.workspace_id == workspace_id,
            WorkflowExecutionDispatchRecord.project_id == project_id,
            WorkflowExecutionDispatchRecord.workflow_run_id == workflow_run_id,
        )
        .order_by(
            asc(WorkflowExecutionDispatchRecord.created_at),
            asc(WorkflowExecutionDispatchRecord.id),
        )
    )
    return tuple(result.scalars().all())


async def list_workflow_execution_leases_for_run(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
) -> tuple[WorkflowExecutionLeaseRecord, ...]:
    result = await session.execute(
        select(WorkflowExecutionLeaseRecord)
        .where(
            WorkflowExecutionLeaseRecord.workspace_id == workspace_id,
            WorkflowExecutionLeaseRecord.project_id == project_id,
            WorkflowExecutionLeaseRecord.workflow_run_id == workflow_run_id,
        )
        .order_by(
            asc(WorkflowExecutionLeaseRecord.created_at),
            asc(WorkflowExecutionLeaseRecord.id),
        )
    )
    return tuple(result.scalars().all())


async def list_workflow_execution_events_for_run(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
) -> tuple[WorkflowExecutionEventRecord, ...]:
    result = await session.execute(
        select(WorkflowExecutionEventRecord)
        .where(
            WorkflowExecutionEventRecord.workspace_id == workspace_id,
            WorkflowExecutionEventRecord.project_id == project_id,
            WorkflowExecutionEventRecord.workflow_run_id == workflow_run_id,
        )
        .order_by(
            asc(WorkflowExecutionEventRecord.dispatch_id),
            asc(WorkflowExecutionEventRecord.sequence),
            asc(WorkflowExecutionEventRecord.id),
        )
    )
    return tuple(result.scalars().all())


async def list_workflow_provider_call_audits_for_run(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
) -> tuple[WorkflowProviderCallAuditRecord, ...]:
    result = await session.execute(
        select(WorkflowProviderCallAuditRecord)
        .where(
            WorkflowProviderCallAuditRecord.workspace_id == workspace_id,
            WorkflowProviderCallAuditRecord.project_id == project_id,
            WorkflowProviderCallAuditRecord.workflow_run_id == workflow_run_id,
        )
        .order_by(
            asc(WorkflowProviderCallAuditRecord.dispatch_id),
            asc(WorkflowProviderCallAuditRecord.attempt_ordinal),
            asc(WorkflowProviderCallAuditRecord.id),
        )
    )
    return tuple(result.scalars().all())


async def list_workflow_credential_resolution_permits_for_run(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
) -> tuple[WorkflowCredentialResolutionPermitRecord, ...]:
    result = await session.execute(
        select(WorkflowCredentialResolutionPermitRecord)
        .where(
            WorkflowCredentialResolutionPermitRecord.workspace_id == workspace_id,
            WorkflowCredentialResolutionPermitRecord.project_id == project_id,
            WorkflowCredentialResolutionPermitRecord.workflow_run_id == workflow_run_id,
        )
        .order_by(
            asc(WorkflowCredentialResolutionPermitRecord.created_at),
            asc(WorkflowCredentialResolutionPermitRecord.id),
        )
    )
    return tuple(result.scalars().all())


async def list_workflow_provider_call_permits_for_run(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
) -> tuple[WorkflowProviderCallPermitRecord, ...]:
    result = await session.execute(
        select(WorkflowProviderCallPermitRecord)
        .where(
            WorkflowProviderCallPermitRecord.workspace_id == workspace_id,
            WorkflowProviderCallPermitRecord.project_id == project_id,
            WorkflowProviderCallPermitRecord.workflow_run_id == workflow_run_id,
        )
        .order_by(
            asc(WorkflowProviderCallPermitRecord.created_at),
            asc(WorkflowProviderCallPermitRecord.id),
        )
    )
    return tuple(result.scalars().all())


async def list_workflow_cancellation_requests_for_run(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
) -> tuple[WorkflowCancellationRequestRecord, ...]:
    result = await session.execute(
        select(WorkflowCancellationRequestRecord)
        .where(
            WorkflowCancellationRequestRecord.workspace_id == workspace_id,
            WorkflowCancellationRequestRecord.project_id == project_id,
            WorkflowCancellationRequestRecord.workflow_run_id == workflow_run_id,
        )
        .order_by(
            asc(WorkflowCancellationRequestRecord.requested_at),
            asc(WorkflowCancellationRequestRecord.id),
        )
    )
    return tuple(result.scalars().all())


async def list_workflow_cancellation_acknowledgements_for_run(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
) -> tuple[WorkflowCancellationAcknowledgementRecord, ...]:
    result = await session.execute(
        select(WorkflowCancellationAcknowledgementRecord)
        .where(
            WorkflowCancellationAcknowledgementRecord.workspace_id == workspace_id,
            WorkflowCancellationAcknowledgementRecord.project_id == project_id,
            WorkflowCancellationAcknowledgementRecord.workflow_run_id == workflow_run_id,
        )
        .order_by(
            asc(WorkflowCancellationAcknowledgementRecord.acknowledged_at),
            asc(WorkflowCancellationAcknowledgementRecord.id),
        )
    )
    return tuple(result.scalars().all())


async def get_workflow_execution_lease(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    dispatch_id: uuid.UUID,
    for_update: bool = False,
) -> WorkflowExecutionLeaseRecord | None:
    statement = select(WorkflowExecutionLeaseRecord).where(
        WorkflowExecutionLeaseRecord.workspace_id == workspace_id,
        WorkflowExecutionLeaseRecord.project_id == project_id,
        WorkflowExecutionLeaseRecord.dispatch_id == dispatch_id,
    )
    if for_update:
        statement = workflow_execution_lease_lock_statement(
            workspace_id=workspace_id,
            project_id=project_id,
            dispatch_id=dispatch_id,
        )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def list_workflow_execution_events(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    dispatch_id: uuid.UUID,
) -> tuple[WorkflowExecutionEventRecord, ...]:
    result = await session.execute(
        select(WorkflowExecutionEventRecord)
        .where(
            WorkflowExecutionEventRecord.workspace_id == workspace_id,
            WorkflowExecutionEventRecord.project_id == project_id,
            WorkflowExecutionEventRecord.dispatch_id == dispatch_id,
        )
        .order_by(
            asc(WorkflowExecutionEventRecord.sequence),
            asc(WorkflowExecutionEventRecord.id),
        )
    )
    return tuple(result.scalars().all())


async def list_workflow_provider_call_audits(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    dispatch_id: uuid.UUID,
) -> tuple[WorkflowProviderCallAuditRecord, ...]:
    result = await session.execute(
        select(WorkflowProviderCallAuditRecord)
        .where(
            WorkflowProviderCallAuditRecord.workspace_id == workspace_id,
            WorkflowProviderCallAuditRecord.project_id == project_id,
            WorkflowProviderCallAuditRecord.dispatch_id == dispatch_id,
        )
        .order_by(
            asc(WorkflowProviderCallAuditRecord.attempt_ordinal),
            asc(WorkflowProviderCallAuditRecord.id),
        )
    )
    return tuple(result.scalars().all())


async def get_workflow_cancellation_request_by_key(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    request_key: str,
) -> WorkflowCancellationRequestRecord | None:
    result = await session.execute(
        select(WorkflowCancellationRequestRecord).where(
            WorkflowCancellationRequestRecord.workspace_id == workspace_id,
            WorkflowCancellationRequestRecord.project_id == project_id,
            WorkflowCancellationRequestRecord.request_key == request_key,
        )
    )
    return result.scalar_one_or_none()


async def get_workflow_cancellation_acknowledgement(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    request_id: uuid.UUID,
) -> WorkflowCancellationAcknowledgementRecord | None:
    result = await session.execute(
        select(WorkflowCancellationAcknowledgementRecord).where(
            WorkflowCancellationAcknowledgementRecord.workspace_id == workspace_id,
            WorkflowCancellationAcknowledgementRecord.project_id == project_id,
            WorkflowCancellationAcknowledgementRecord.request_id == request_id,
        )
    )
    return result.scalar_one_or_none()


async def add_workflow_execution_dispatch(
    session: AsyncSession,
    dispatch: WorkflowExecutionDispatchRecord,
) -> WorkflowExecutionDispatchRecord:
    session.add(dispatch)
    await session.flush()
    return dispatch


async def add_workflow_execution_lease(
    session: AsyncSession,
    lease: WorkflowExecutionLeaseRecord,
) -> WorkflowExecutionLeaseRecord:
    session.add(lease)
    await session.flush()
    return lease


async def add_workflow_execution_event(
    session: AsyncSession,
    event: WorkflowExecutionEventRecord,
) -> WorkflowExecutionEventRecord:
    session.add(event)
    await session.flush()
    return event


async def add_workflow_credential_resolution_permit(
    session: AsyncSession,
    permit: WorkflowCredentialResolutionPermitRecord,
) -> WorkflowCredentialResolutionPermitRecord:
    session.add(permit)
    await session.flush()
    return permit


async def add_workflow_provider_call_permit(
    session: AsyncSession,
    permit: WorkflowProviderCallPermitRecord,
) -> WorkflowProviderCallPermitRecord:
    session.add(permit)
    await session.flush()
    return permit


async def add_workflow_provider_call_audit(
    session: AsyncSession,
    audit: WorkflowProviderCallAuditRecord,
) -> WorkflowProviderCallAuditRecord:
    session.add(audit)
    await session.flush()
    return audit


async def add_workflow_cancellation_request(
    session: AsyncSession,
    request: WorkflowCancellationRequestRecord,
) -> WorkflowCancellationRequestRecord:
    session.add(request)
    await session.flush()
    return request


async def add_workflow_cancellation_acknowledgement(
    session: AsyncSession,
    acknowledgement: WorkflowCancellationAcknowledgementRecord,
) -> WorkflowCancellationAcknowledgementRecord:
    session.add(acknowledgement)
    await session.flush()
    return acknowledgement


async def consume_workflow_credential_resolution_permit(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    permit_id: uuid.UUID,
    consumed_at: datetime,
) -> WorkflowCredentialResolutionPermitRecord | None:
    result = await session.execute(
        update(WorkflowCredentialResolutionPermitRecord)
        .where(
            WorkflowCredentialResolutionPermitRecord.workspace_id == workspace_id,
            WorkflowCredentialResolutionPermitRecord.project_id == project_id,
            WorkflowCredentialResolutionPermitRecord.id == permit_id,
            WorkflowCredentialResolutionPermitRecord.consumed_at.is_(None),
            WorkflowCredentialResolutionPermitRecord.revoked_at.is_(None),
            WorkflowCredentialResolutionPermitRecord.issued_at <= consumed_at,
            WorkflowCredentialResolutionPermitRecord.expires_at > consumed_at,
        )
        .values(consumed_at=consumed_at)
        .returning(WorkflowCredentialResolutionPermitRecord)
    )
    return result.scalar_one_or_none()


async def consume_workflow_provider_call_permit(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    permit_id: uuid.UUID,
    consumed_at: datetime,
) -> WorkflowProviderCallPermitRecord | None:
    result = await session.execute(
        update(WorkflowProviderCallPermitRecord)
        .where(
            WorkflowProviderCallPermitRecord.workspace_id == workspace_id,
            WorkflowProviderCallPermitRecord.project_id == project_id,
            WorkflowProviderCallPermitRecord.id == permit_id,
            WorkflowProviderCallPermitRecord.consumed_at.is_(None),
            WorkflowProviderCallPermitRecord.revoked_at.is_(None),
            WorkflowProviderCallPermitRecord.issued_at <= consumed_at,
            WorkflowProviderCallPermitRecord.expires_at > consumed_at,
        )
        .values(consumed_at=consumed_at)
        .returning(WorkflowProviderCallPermitRecord)
    )
    return result.scalar_one_or_none()


__all__ = [
    "add_workflow_cancellation_acknowledgement",
    "add_workflow_cancellation_request",
    "add_workflow_credential_resolution_permit",
    "add_workflow_execution_dispatch",
    "add_workflow_execution_event",
    "add_workflow_execution_lease",
    "add_workflow_provider_call_audit",
    "add_workflow_provider_call_permit",
    "consume_workflow_credential_resolution_permit",
    "consume_workflow_provider_call_permit",
    "get_workflow_cancellation_acknowledgement",
    "get_workflow_cancellation_request_by_key",
    "get_workflow_execution_dispatch_by_key",
    "get_workflow_execution_lease",
    "list_workflow_execution_events",
    "list_workflow_execution_dispatches_for_run",
    "list_workflow_execution_events_for_run",
    "list_workflow_execution_leases_for_run",
    "list_workflow_credential_resolution_permits_for_run",
    "list_workflow_cancellation_acknowledgements_for_run",
    "list_workflow_cancellation_requests_for_run",
    "list_workflow_provider_call_audits",
    "list_workflow_provider_call_audits_for_run",
    "list_workflow_provider_call_permits_for_run",
    "workflow_execution_lease_lock_statement",
]
