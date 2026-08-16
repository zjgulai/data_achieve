from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.workflow_action import (
    WorkflowRunActionReceiptRecord,
    WorkflowRunActionRequestRecord,
)
from data_intelligence_hub.models.workflow_execution import StepRun, WorkflowRun
from data_intelligence_hub.models.workflow_executor import WorkflowExecutionDispatchRecord
from data_intelligence_hub.repositories.workflow_executor import (
    add_workflow_execution_dispatch,
    get_workflow_execution_dispatch_by_key,
)
from data_intelligence_hub.schemas.workflow_action_command import (
    ResumeActionParameters,
    RetryActionParameters,
)
from data_intelligence_hub.schemas.workflow_executor import (
    WorkflowCancellationAcknowledgement,
    WorkflowCancellationRequest,
    WorkflowExecutionDispatch,
    WorkflowExecutionLeaseToken,
    WorkflowProviderCallAudit,
    canonical_workflow_execution_dispatch_key,
    canonical_workflow_provider_side_effect_key,
)
from data_intelligence_hub.services.workflow_execution.executor_contract import (
    WorkflowExecutionPreflightDecision,
    compile_workflow_execution_preflight,
)


class DisabledCredentialResolver(Protocol):
    def __call__(self, *args: object, **kwargs: object) -> object: ...


class DisabledClientFactory(Protocol):
    def __call__(self, *args: object, **kwargs: object) -> object: ...


class DisabledExecutorTransport(Protocol):
    def __call__(self, *args: object, **kwargs: object) -> object: ...


@dataclass(frozen=True, slots=True)
class DisabledExecutorPreflightResult:
    preflight: WorkflowExecutionPreflightDecision
    stop_reason: Literal[
        "workflow_executor_preflight_blocked",
        "exact_live_provider_call_authorization",
    ]
    credential_read_attempted: Literal[False] = False
    client_construction: Literal[False] = False
    provider_call: Literal[False] = False
    network_call: Literal[False] = False


@dataclass(frozen=True, slots=True)
class FixtureExecutorTransportResult:
    classification: str
    fixture_transport_invoked: Literal[True] = True
    evidence_grade: Literal["L2_fixture_local"] = "L2_fixture_local"
    credential_read_attempted: Literal[False] = False
    client_construction: Literal[False] = False
    provider_call: Literal[False] = False
    network_call: Literal[False] = False
    live_provider_proof: Literal[False] = False


@dataclass(frozen=True, slots=True)
class DisabledExecutorLifecycleResult:
    preflight: DisabledExecutorPreflightResult
    dispatch_id: UUID
    lease_id: UUID
    fencing_token: int
    call_audit_id: UUID
    call_audit_state: Literal["not_attempted"]
    budget_reservation_id: UUID
    budget_reserved: Literal[True]
    cancellation_request_id: UUID | None
    cancellation_acknowledgement_id: UUID | None
    cancellation_acknowledged: bool
    evidence_grade: Literal["L2_fixture_local"] = "L2_fixture_local"
    credential_read_attempted: Literal[False] = False
    client_construction: Literal[False] = False
    provider_call: Literal[False] = False
    network_call: Literal[False] = False
    live_provider_proof: Literal[False] = False


class ExecutorCompositionError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


async def add_action_dispatches_for_accepted_action(
    session: AsyncSession,
    *,
    run: WorkflowRun,
    steps: tuple[StepRun, ...],
    request_record: WorkflowRunActionRequestRecord,
    receipt_record: WorkflowRunActionReceiptRecord,
    parameters: RetryActionParameters | ResumeActionParameters,
    created_at: datetime,
) -> tuple[WorkflowExecutionDispatchRecord, ...]:
    """Persist pending work intent in the accepted action transaction."""

    if not steps:
        raise ExecutorCompositionError("workflow_executor_dispatch_step_required")
    execution_policy_digest = (
        parameters.retry_policy_digest
        if isinstance(parameters, RetryActionParameters)
        else parameters.budget_policy_digest
    )
    dispatches: list[WorkflowExecutionDispatchRecord] = []
    for step in steps:
        dispatch_key = canonical_workflow_execution_dispatch_key(
            workspace_id=run.workspace_id,
            project_id=run.project_id,
            workflow_plan_id=run.workflow_plan_id,
            workflow_version_id=run.workflow_version_id,
            workflow_run_id=run.id,
            workflow_step_run_id=step.id,
            attempt_generation=step.retry_generation,
            source_action_request_id=request_record.id,
            source_action_receipt_id=receipt_record.id,
            workflow_version_digest=run.preview_fingerprint,
            execution_policy_digest=execution_policy_digest,
        )
        existing = await get_workflow_execution_dispatch_by_key(
            session,
            workspace_id=run.workspace_id,
            project_id=run.project_id,
            dispatch_key=dispatch_key,
        )
        if existing is not None:
            dispatches.append(existing)
            continue
        record = WorkflowExecutionDispatchRecord(
            workspace_id=run.workspace_id,
            project_id=run.project_id,
            workflow_plan_id=run.workflow_plan_id,
            workflow_version_id=run.workflow_version_id,
            workflow_run_id=run.id,
            workflow_step_run_id=step.id,
            attempt_generation=step.retry_generation,
            source_action_request_id=request_record.id,
            source_action_receipt_id=receipt_record.id,
            workflow_version_digest=run.preview_fingerprint,
            execution_policy_digest=execution_policy_digest,
            dispatch_key=dispatch_key,
            provider_side_effect_key=canonical_workflow_provider_side_effect_key(
                dispatch_key=dispatch_key,
                provider_id=step.implementation_id,
                operation_id=step.operation,
            ),
            state="pending",
            created_at=created_at,
            database_write=False,
            credential_read_attempted=False,
            provider_call=False,
            network_call=False,
            production_write_allowed=False,
        )
        dispatches.append(await add_workflow_execution_dispatch(session, record))
    return tuple(dispatches)


def compose_disabled_executor_preflight(
    dispatch: WorkflowExecutionDispatch,
    lease: WorkflowExecutionLeaseToken,
    *,
    preflight_id: str,
    eligible: bool,
    blocker_codes: tuple[str, ...],
    evaluated_at: datetime,
    credential_resolver: DisabledCredentialResolver,
    client_factory: DisabledClientFactory,
    transport: DisabledExecutorTransport,
) -> DisabledExecutorPreflightResult:
    """Compile preflight while the three live dependencies remain unreachable.

    The injected dependencies are intentionally accepted but never invoked in
    Phase F3. Their presence makes the disabled boundary executable in tests
    without importing a credential vault, an official client, or a transport.
    """

    del credential_resolver, client_factory, transport
    preflight = compile_workflow_execution_preflight(
        dispatch,
        lease,
        preflight_id=preflight_id,
        eligible=eligible,
        blocker_codes=blocker_codes,
        evaluated_at=evaluated_at,
    )
    return DisabledExecutorPreflightResult(
        preflight=preflight,
        stop_reason=(
            "exact_live_provider_call_authorization"
            if preflight.eligible
            else "workflow_executor_preflight_blocked"
        ),
    )


def exercise_fixture_executor_transport(
    dispatch: WorkflowExecutionDispatch,
    *,
    transport: Callable[[WorkflowExecutionDispatch], object],
) -> FixtureExecutorTransportResult:
    """Exercise an injected local fixture transport without live side effects."""

    response = transport(dispatch)
    classification = "fixture_response"
    if isinstance(response, Mapping):
        candidate = response.get("classification")
        if isinstance(candidate, str) and candidate:
            classification = candidate
    return FixtureExecutorTransportResult(classification=classification)


def compose_disabled_executor_lifecycle(
    dispatch: WorkflowExecutionDispatch,
    lease: WorkflowExecutionLeaseToken,
    *,
    preflight_id: str,
    eligible: bool,
    blocker_codes: tuple[str, ...],
    evaluated_at: datetime,
    call_audit: WorkflowProviderCallAudit,
    budget_reservation_id: UUID,
    budget_policy_digest: str,
    budget_side_effect_key: str,
    cancellation_request: WorkflowCancellationRequest | None,
    cancellation_acknowledgement: WorkflowCancellationAcknowledgement | None,
    credential_resolver: DisabledCredentialResolver,
    client_factory: DisabledClientFactory,
    transport: DisabledExecutorTransport,
) -> DisabledExecutorLifecycleResult:
    """Compose durable lifecycle evidence while every live boundary is closed."""

    preflight = compose_disabled_executor_preflight(
        dispatch,
        lease,
        preflight_id=preflight_id,
        eligible=eligible,
        blocker_codes=blocker_codes,
        evaluated_at=evaluated_at,
        credential_resolver=credential_resolver,
        client_factory=client_factory,
        transport=transport,
    )
    if lease.dispatch_id != dispatch.id or lease.workspace_id != dispatch.workspace_id:
        raise ExecutorCompositionError("workflow_executor_lease_lineage_mismatch")
    if (
        call_audit.dispatch_id != dispatch.id
        or call_audit.workspace_id != dispatch.workspace_id
        or call_audit.workflow_run_id != dispatch.workflow_run_id
        or call_audit.workflow_step_run_id != dispatch.workflow_step_run_id
        or call_audit.attempt_generation != dispatch.attempt_generation
        or call_audit.lease_id != lease.id
        or call_audit.fencing_token != lease.fencing_token
        or call_audit.preflight_id != preflight.preflight.preflight_id
        or call_audit.side_effect_key != dispatch.provider_side_effect_key
    ):
        raise ExecutorCompositionError("workflow_executor_call_audit_lineage_mismatch")
    if call_audit.transport_state != "not_attempted":
        raise ExecutorCompositionError("workflow_executor_live_transport_state_forbidden")
    if (
        call_audit.policy_digest != budget_policy_digest
        or call_audit.side_effect_key != budget_side_effect_key
    ):
        raise ExecutorCompositionError("workflow_executor_budget_reservation_lineage_mismatch")

    request_id: UUID | None = None
    acknowledgement_id: UUID | None = None
    if cancellation_request is not None:
        if (
            cancellation_request.dispatch_id != dispatch.id
            or cancellation_request.workspace_id != dispatch.workspace_id
            or cancellation_request.workflow_run_id != dispatch.workflow_run_id
        ):
            raise ExecutorCompositionError(
                "workflow_executor_cancellation_request_lineage_mismatch"
            )
        request_id = cancellation_request.id
    if cancellation_acknowledgement is not None:
        if cancellation_request is None:
            raise ExecutorCompositionError("workflow_executor_cancellation_request_required")
        if (
            cancellation_acknowledgement.request_id != cancellation_request.id
            or cancellation_acknowledgement.dispatch_id != dispatch.id
            or cancellation_acknowledgement.workspace_id != dispatch.workspace_id
            or cancellation_acknowledgement.lease_id != lease.id
            or cancellation_acknowledgement.fencing_token != lease.fencing_token
        ):
            raise ExecutorCompositionError(
                "workflow_executor_cancellation_acknowledgement_lineage_mismatch"
            )
        acknowledgement_id = cancellation_acknowledgement.id

    return DisabledExecutorLifecycleResult(
        preflight=preflight,
        dispatch_id=dispatch.id,
        lease_id=lease.id,
        fencing_token=lease.fencing_token,
        call_audit_id=call_audit.id,
        call_audit_state="not_attempted",
        budget_reservation_id=budget_reservation_id,
        budget_reserved=True,
        cancellation_request_id=request_id,
        cancellation_acknowledgement_id=acknowledgement_id,
        cancellation_acknowledged=acknowledgement_id is not None,
    )


__all__ = [
    "DisabledClientFactory",
    "DisabledCredentialResolver",
    "DisabledExecutorLifecycleResult",
    "DisabledExecutorPreflightResult",
    "DisabledExecutorTransport",
    "ExecutorCompositionError",
    "FixtureExecutorTransportResult",
    "add_action_dispatches_for_accepted_action",
    "compose_disabled_executor_preflight",
    "compose_disabled_executor_lifecycle",
    "exercise_fixture_executor_transport",
]
