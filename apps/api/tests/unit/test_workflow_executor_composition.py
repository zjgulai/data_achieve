from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from data_intelligence_hub.schemas.workflow_executor import (
    WorkflowCancellationAcknowledgement,
    WorkflowCancellationRequest,
    WorkflowExecutionDispatch,
    WorkflowExecutionLeaseToken,
    WorkflowProviderCallAudit,
    canonical_workflow_execution_dispatch_key,
    canonical_workflow_provider_side_effect_key,
)
from data_intelligence_hub.services.workflow_execution.executor_composition import (
    compose_disabled_executor_lifecycle,
    compose_disabled_executor_preflight,
    exercise_fixture_executor_transport,
)

NOW = datetime(2026, 7, 28, 1, 0, tzinfo=UTC)
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


class _ForbiddenDependency:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, *_args: object, **_kwargs: object) -> object:
        self.calls += 1
        raise AssertionError("disabled dependency must not be invoked")


class _FixtureTransport:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, dispatch: WorkflowExecutionDispatch) -> dict[str, str]:
        self.calls += 1
        return {"dispatch_id": str(dispatch.id), "classification": "fixture_success"}


def _dispatch_and_lease() -> tuple[WorkflowExecutionDispatch, WorkflowExecutionLeaseToken]:
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    version_id = uuid.uuid4()
    run_id = uuid.uuid4()
    step_id = uuid.uuid4()
    request_id = uuid.uuid4()
    receipt_id = uuid.uuid4()
    dispatch_key = canonical_workflow_execution_dispatch_key(
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_plan_id=plan_id,
        workflow_version_id=version_id,
        workflow_run_id=run_id,
        workflow_step_run_id=step_id,
        attempt_generation=1,
        source_action_request_id=request_id,
        source_action_receipt_id=receipt_id,
        workflow_version_digest=DIGEST_A,
        execution_policy_digest=DIGEST_B,
    )
    dispatch = WorkflowExecutionDispatch(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_plan_id=plan_id,
        workflow_version_id=version_id,
        workflow_run_id=run_id,
        workflow_step_run_id=step_id,
        attempt_generation=1,
        source_action_request_id=request_id,
        source_action_receipt_id=receipt_id,
        workflow_version_digest=DIGEST_A,
        execution_policy_digest=DIGEST_B,
        dispatch_key=dispatch_key,
        provider_side_effect_key=canonical_workflow_provider_side_effect_key(
            dispatch_key=dispatch_key,
            provider_id="youtube.fixture",
            operation_id="search",
        ),
        state="claimable",
        created_at=NOW,
    )
    lease = WorkflowExecutionLeaseToken(
        id=uuid.uuid4(),
        dispatch_id=dispatch.id,
        workspace_id=workspace_id,
        worker_id="fixture-worker",
        fencing_token=1,
        version=1,
        claimed_at=NOW,
        heartbeat_at=NOW,
        expires_at=NOW + timedelta(seconds=30),
        state="active",
    )
    return dispatch, lease


def test_blocked_and_eligible_preflight_stop_before_every_live_dependency() -> None:
    dispatch, lease = _dispatch_and_lease()
    resolver = _ForbiddenDependency()
    client_factory = _ForbiddenDependency()
    transport = _ForbiddenDependency()

    blocked = compose_disabled_executor_preflight(
        dispatch,
        lease,
        preflight_id=DIGEST_A,
        eligible=False,
        blocker_codes=("workflow_executor_policy_changed",),
        evaluated_at=NOW + timedelta(seconds=1),
        credential_resolver=resolver,
        client_factory=client_factory,
        transport=transport,
    )
    eligible = compose_disabled_executor_preflight(
        dispatch,
        lease,
        preflight_id=DIGEST_B,
        eligible=True,
        blocker_codes=(),
        evaluated_at=NOW + timedelta(seconds=1),
        credential_resolver=resolver,
        client_factory=client_factory,
        transport=transport,
    )

    assert blocked.stop_reason == "workflow_executor_preflight_blocked"
    assert eligible.stop_reason == "exact_live_provider_call_authorization"
    assert blocked.preflight.eligible is False
    assert eligible.preflight.eligible is True
    assert resolver.calls == client_factory.calls == transport.calls == 0
    assert blocked.credential_read_attempted is False
    assert blocked.client_construction is False
    assert blocked.provider_call is False
    assert blocked.network_call is False
    assert eligible.credential_read_attempted is False
    assert eligible.client_construction is False
    assert eligible.provider_call is False
    assert eligible.network_call is False


def test_fixture_transport_lifecycle_is_not_labeled_live_or_provider_proof() -> None:
    dispatch, _lease = _dispatch_and_lease()
    transport = _FixtureTransport()

    result = exercise_fixture_executor_transport(dispatch, transport=transport)

    assert transport.calls == 1
    assert result.fixture_transport_invoked is True
    assert result.classification == "fixture_success"
    assert result.evidence_grade == "L2_fixture_local"
    assert result.credential_read_attempted is False
    assert result.client_construction is False
    assert result.provider_call is False
    assert result.network_call is False
    assert result.live_provider_proof is False


def test_disabled_lifecycle_composes_durable_evidence_without_live_authority() -> None:
    dispatch, lease = _dispatch_and_lease()
    resolver = _ForbiddenDependency()
    client_factory = _ForbiddenDependency()
    transport = _ForbiddenDependency()
    request = WorkflowCancellationRequest(
        id=uuid.uuid4(),
        dispatch_id=dispatch.id,
        workspace_id=dispatch.workspace_id,
        workflow_run_id=dispatch.workflow_run_id,
        requested_by_user_id=uuid.uuid4(),
        request_key=DIGEST_A,
        reason_code="owner_requested",
        requested_at=NOW + timedelta(seconds=2),
    )
    acknowledgement = WorkflowCancellationAcknowledgement(
        id=uuid.uuid4(),
        request_id=request.id,
        dispatch_id=dispatch.id,
        workspace_id=dispatch.workspace_id,
        lease_id=lease.id,
        fencing_token=lease.fencing_token,
        safe_point="before_provider_call",
        outcome="cancelled_before_effect",
        acknowledged_at=NOW + timedelta(seconds=3),
    )
    audit = WorkflowProviderCallAudit(
        id=uuid.uuid4(),
        dispatch_id=dispatch.id,
        workspace_id=dispatch.workspace_id,
        workflow_run_id=dispatch.workflow_run_id,
        workflow_step_run_id=dispatch.workflow_step_run_id,
        attempt_generation=dispatch.attempt_generation,
        lease_id=lease.id,
        fencing_token=lease.fencing_token,
        provider_id="youtube.fixture",
        operation_id="search",
        preflight_id=DIGEST_B,
        policy_digest=DIGEST_A,
        side_effect_key=dispatch.provider_side_effect_key,
        environment="local",
        attempt_ordinal=1,
        transport_state="not_attempted",
    )

    result = compose_disabled_executor_lifecycle(
        dispatch,
        lease,
        preflight_id=DIGEST_B,
        eligible=True,
        blocker_codes=(),
        evaluated_at=NOW + timedelta(seconds=1),
        call_audit=audit,
        budget_reservation_id=uuid.uuid4(),
        budget_policy_digest=DIGEST_A,
        budget_side_effect_key=dispatch.provider_side_effect_key,
        cancellation_request=request,
        cancellation_acknowledgement=acknowledgement,
        credential_resolver=resolver,
        client_factory=client_factory,
        transport=transport,
    )

    assert result.preflight.stop_reason == "exact_live_provider_call_authorization"
    assert result.call_audit_state == "not_attempted"
    assert result.budget_reserved is True
    assert result.cancellation_request_id == request.id
    assert result.cancellation_acknowledgement_id == acknowledgement.id
    assert result.cancellation_acknowledged is True
    assert resolver.calls == client_factory.calls == transport.calls == 0
    assert result.credential_read_attempted is False
    assert result.client_construction is False
    assert result.provider_call is False
    assert result.network_call is False
    assert result.live_provider_proof is False
