from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID

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
from data_intelligence_hub.repositories.workflow_executor import (
    list_workflow_cancellation_acknowledgements_for_run,
    list_workflow_cancellation_requests_for_run,
    list_workflow_credential_resolution_permits_for_run,
    list_workflow_execution_dispatches_for_run,
    list_workflow_execution_events_for_run,
    list_workflow_execution_leases_for_run,
    list_workflow_provider_call_audits_for_run,
    list_workflow_provider_call_permits_for_run,
)
from data_intelligence_hub.schemas.workflow_executor import (
    WorkflowCancellationOutcome,
    WorkflowExecutionDispatchState,
    WorkflowExecutionEventType,
    WorkflowExecutionLeaseState,
    WorkflowProviderTransportState,
)
from data_intelligence_hub.schemas.workflow_executor_evidence import (
    WorkflowExecutorAuditEvidence,
    WorkflowExecutorCancellationEvidence,
    WorkflowExecutorDispatchEvidence,
    WorkflowExecutorEventEvidence,
    WorkflowExecutorEvidenceResponse,
    WorkflowExecutorLeaseEvidence,
)

PreflightState = Literal["not_evaluated", "blocked", "eligible"]
BusinessCause = Literal[
    "executor_dispatch_not_created",
    "executor_dispatch_pending",
    "executor_preflight_blocked",
    "executor_waiting_exact_live_authority",
]
BusinessImpact = Literal[
    "workflow_execution_not_started",
    "workflow_execution_waiting",
]
NextAction = Literal[
    "review_action_receipt_and_dispatch_gate",
    "wait_for_disabled_executor_evidence",
    "resolve_preflight_blocker",
    "request_exact_live_provider_authorization",
]
ExecutorEnvironment = Literal["local", "test", "staging", "production"]


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def compose_workflow_executor_evidence(
    *,
    workspace_id: UUID,
    project_id: UUID,
    workflow_run_id: UUID,
    evaluated_at: datetime,
    dispatches: tuple[WorkflowExecutionDispatchRecord, ...],
    leases: tuple[WorkflowExecutionLeaseRecord, ...],
    events: tuple[WorkflowExecutionEventRecord, ...],
    audits: tuple[WorkflowProviderCallAuditRecord, ...],
    cancellation_requests: tuple[WorkflowCancellationRequestRecord, ...],
    cancellation_acknowledgements: tuple[WorkflowCancellationAcknowledgementRecord, ...],
    credential_permits: tuple[WorkflowCredentialResolutionPermitRecord, ...] = (),
    provider_permits: tuple[WorkflowProviderCallPermitRecord, ...] = (),
) -> WorkflowExecutorEvidenceResponse:
    leases_by_dispatch = {item.dispatch_id: item for item in leases}
    events_by_dispatch: dict[UUID, list[WorkflowExecutionEventRecord]] = {}
    audits_by_dispatch: dict[UUID, list[WorkflowProviderCallAuditRecord]] = {}
    requests_by_dispatch: dict[UUID, list[WorkflowCancellationRequestRecord]] = {}
    acknowledgements_by_request = {item.request_id: item for item in cancellation_acknowledgements}
    credential_permits_by_dispatch: dict[UUID, list[WorkflowCredentialResolutionPermitRecord]] = {}
    provider_permits_by_dispatch: dict[UUID, list[WorkflowProviderCallPermitRecord]] = {}
    for event in events:
        events_by_dispatch.setdefault(event.dispatch_id, []).append(event)
    for audit in audits:
        audits_by_dispatch.setdefault(audit.dispatch_id, []).append(audit)
    for request_item in cancellation_requests:
        requests_by_dispatch.setdefault(request_item.dispatch_id, []).append(request_item)
    for credential_permit in credential_permits:
        credential_permits_by_dispatch.setdefault(credential_permit.dispatch_id, []).append(
            credential_permit
        )
    for provider_permit in provider_permits:
        provider_permits_by_dispatch.setdefault(provider_permit.dispatch_id, []).append(
            provider_permit
        )

    response_dispatches: list[WorkflowExecutorDispatchEvidence] = []
    for dispatch in dispatches:
        lease = leases_by_dispatch.get(dispatch.id)
        event_items = sorted(
            events_by_dispatch.get(dispatch.id, []),
            key=lambda item: (item.sequence, str(item.id)),
        )
        audit_items = sorted(
            audits_by_dispatch.get(dispatch.id, []),
            key=lambda item: (item.attempt_ordinal, str(item.id)),
        )
        request_items = sorted(
            requests_by_dispatch.get(dispatch.id, []),
            key=lambda item: (_aware(item.requested_at), str(item.id)),
        )
        request = request_items[-1] if request_items else None
        acknowledgement = (
            acknowledgements_by_request.get(request.id) if request is not None else None
        )
        preflight_events = [
            item
            for item in event_items
            if item.event_type in ("preflight_blocked", "preflight_eligible")
        ]
        preflight_event = preflight_events[-1] if preflight_events else None
        preflight_state: PreflightState = (
            "not_evaluated"
            if preflight_event is None
            else "blocked"
            if preflight_event.event_type == "preflight_blocked"
            else "eligible"
        )
        response_dispatches.append(
            WorkflowExecutorDispatchEvidence(
                id=dispatch.id,
                workflow_step_run_id=dispatch.workflow_step_run_id,
                attempt_generation=dispatch.attempt_generation,
                source_action_request_id=dispatch.source_action_request_id,
                source_action_receipt_id=dispatch.source_action_receipt_id,
                state=cast(WorkflowExecutionDispatchState, dispatch.state),
                created_at=_aware(dispatch.created_at),
                lease=(
                    None
                    if lease is None
                    else WorkflowExecutorLeaseEvidence(
                        id=lease.id,
                        state=cast(WorkflowExecutionLeaseState, lease.state),
                        fencing_token=lease.fencing_token,
                        version=lease.version,
                        heartbeat_at=_aware(lease.heartbeat_at),
                        expires_at=_aware(lease.expires_at),
                        fresh=(lease.state == "active" and evaluated_at < _aware(lease.expires_at)),
                    )
                ),
                last_event=(
                    None
                    if not event_items
                    else WorkflowExecutorEventEvidence(
                        id=event_items[-1].id,
                        sequence=event_items[-1].sequence,
                        event_type=cast(
                            WorkflowExecutionEventType,
                            event_items[-1].event_type,
                        ),
                        event_digest=event_items[-1].event_digest,
                        occurred_at=_aware(event_items[-1].occurred_at),
                    )
                ),
                preflight_state=preflight_state,
                preflight_blocker_codes=(
                    ["workflow_executor_preflight_blocked"] if preflight_state == "blocked" else []
                ),
                next_required_authority=(
                    "exact_live_provider_call_authorization"
                    if preflight_state == "eligible"
                    else None
                ),
                credential_permit_ids=[
                    item.id for item in credential_permits_by_dispatch.get(dispatch.id, [])
                ],
                provider_permit_ids=[
                    item.id for item in provider_permits_by_dispatch.get(dispatch.id, [])
                ],
                audits=[
                    WorkflowExecutorAuditEvidence(
                        id=item.id,
                        attempt_ordinal=item.attempt_ordinal,
                        provider_id=item.provider_id,
                        operation_id=item.operation_id,
                        preflight_id=item.preflight_id,
                        transport_state=cast(
                            WorkflowProviderTransportState,
                            item.transport_state,
                        ),
                        outcome_code=item.outcome_code,
                        environment=cast(ExecutorEnvironment, item.environment),
                        started_at=(None if item.started_at is None else _aware(item.started_at)),
                        finished_at=(
                            None if item.finished_at is None else _aware(item.finished_at)
                        ),
                    )
                    for item in audit_items
                ],
                audit_total=len(audit_items),
                cancellation=WorkflowExecutorCancellationEvidence(
                    requested=request is not None,
                    acknowledged=acknowledgement is not None,
                    request_id=None if request is None else request.id,
                    reason_code=None if request is None else request.reason_code,
                    requested_at=(None if request is None else _aware(request.requested_at)),
                    acknowledgement_id=(None if acknowledgement is None else acknowledgement.id),
                    safe_point=(None if acknowledgement is None else acknowledgement.safe_point),
                    outcome=(
                        None
                        if acknowledgement is None
                        else cast(WorkflowCancellationOutcome, acknowledgement.outcome)
                    ),
                    acknowledged_at=(
                        None if acknowledgement is None else _aware(acknowledgement.acknowledged_at)
                    ),
                ),
            )
        )

    if not response_dispatches:
        cause: BusinessCause = "executor_dispatch_not_created"
        impact: BusinessImpact = "workflow_execution_not_started"
        next_action: NextAction = "review_action_receipt_and_dispatch_gate"
    elif any(item.preflight_state == "eligible" for item in response_dispatches):
        cause = "executor_waiting_exact_live_authority"
        impact = "workflow_execution_waiting"
        next_action = "request_exact_live_provider_authorization"
    elif any(item.preflight_state == "blocked" for item in response_dispatches):
        cause = "executor_preflight_blocked"
        impact = "workflow_execution_not_started"
        next_action = "resolve_preflight_blocker"
    else:
        cause = "executor_dispatch_pending"
        impact = "workflow_execution_waiting"
        next_action = "wait_for_disabled_executor_evidence"

    return WorkflowExecutorEvidenceResponse(
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=workflow_run_id,
        evaluated_at=evaluated_at,
        dispatches=response_dispatches,
        dispatch_total=len(response_dispatches),
        business_cause_code=cause,
        business_impact_code=impact,
        next_action_code=next_action,
    )


async def load_workflow_executor_evidence(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    project_id: UUID,
    workflow_run_id: UUID,
    evaluated_at: datetime,
) -> WorkflowExecutorEvidenceResponse:
    return compose_workflow_executor_evidence(
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=workflow_run_id,
        evaluated_at=evaluated_at,
        dispatches=await list_workflow_execution_dispatches_for_run(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=workflow_run_id,
        ),
        leases=await list_workflow_execution_leases_for_run(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=workflow_run_id,
        ),
        events=await list_workflow_execution_events_for_run(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=workflow_run_id,
        ),
        audits=await list_workflow_provider_call_audits_for_run(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=workflow_run_id,
        ),
        cancellation_requests=await list_workflow_cancellation_requests_for_run(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=workflow_run_id,
        ),
        cancellation_acknowledgements=(
            await list_workflow_cancellation_acknowledgements_for_run(
                session,
                workspace_id=workspace_id,
                project_id=project_id,
                workflow_run_id=workflow_run_id,
            )
        ),
        credential_permits=await list_workflow_credential_resolution_permits_for_run(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=workflow_run_id,
        ),
        provider_permits=await list_workflow_provider_call_permits_for_run(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=workflow_run_id,
        ),
    )


__all__ = ["compose_workflow_executor_evidence", "load_workflow_executor_evidence"]
