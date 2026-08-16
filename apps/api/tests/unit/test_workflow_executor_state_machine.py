from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from data_intelligence_hub.schemas.workflow_executor import (
    WorkflowCancellationRequest,
    WorkflowCredentialResolutionPermit,
    WorkflowExecutionDispatch,
    WorkflowProviderCallAudit,
    WorkflowProviderCallPermit,
    canonical_workflow_execution_dispatch_key,
    canonical_workflow_provider_side_effect_key,
)
from data_intelligence_hub.services.workflow_execution.executor_contract import (
    WorkflowExecutorContractError,
    acknowledge_workflow_cancellation,
    claim_workflow_execution_dispatch,
    compile_workflow_execution_preflight,
    compile_workflow_execution_terminal_outcome,
    consume_workflow_credential_resolution_permit,
    consume_workflow_provider_call_permit,
    heartbeat_workflow_execution_lease,
    release_workflow_execution_lease,
    takeover_workflow_execution_lease,
)

WORKSPACE_ID = UUID("30000000-0000-4000-8000-000000000001")
PROJECT_ID = UUID("30000000-0000-4000-8000-000000000002")
PLAN_ID = UUID("30000000-0000-4000-8000-000000000003")
VERSION_ID = UUID("30000000-0000-4000-8000-000000000004")
RUN_ID = UUID("30000000-0000-4000-8000-000000000005")
STEP_ID = UUID("30000000-0000-4000-8000-000000000006")
REQUEST_ID = UUID("30000000-0000-4000-8000-000000000007")
RECEIPT_ID = UUID("30000000-0000-4000-8000-000000000008")
DISPATCH_ID = UUID("30000000-0000-4000-8000-000000000009")
LEASE_ID = UUID("30000000-0000-4000-8000-000000000010")
NOW = datetime(2026, 7, 28, 10, 0, tzinfo=UTC)
DIGEST_A = f"sha256:{'a' * 64}"
DIGEST_B = f"sha256:{'b' * 64}"
DIGEST_C = f"sha256:{'c' * 64}"
DIGEST_D = f"sha256:{'d' * 64}"


def _dispatch() -> WorkflowExecutionDispatch:
    dispatch_key = canonical_workflow_execution_dispatch_key(
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_plan_id=PLAN_ID,
        workflow_version_id=VERSION_ID,
        workflow_run_id=RUN_ID,
        workflow_step_run_id=STEP_ID,
        attempt_generation=2,
        source_action_request_id=REQUEST_ID,
        source_action_receipt_id=RECEIPT_ID,
        workflow_version_digest=DIGEST_A,
        execution_policy_digest=DIGEST_B,
    )
    return WorkflowExecutionDispatch(
        id=DISPATCH_ID,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_plan_id=PLAN_ID,
        workflow_version_id=VERSION_ID,
        workflow_run_id=RUN_ID,
        workflow_step_run_id=STEP_ID,
        attempt_generation=2,
        source_action_request_id=REQUEST_ID,
        source_action_receipt_id=RECEIPT_ID,
        workflow_version_digest=DIGEST_A,
        execution_policy_digest=DIGEST_B,
        dispatch_key=dispatch_key,
        provider_side_effect_key=canonical_workflow_provider_side_effect_key(
            dispatch_key=dispatch_key,
            provider_id="youtube.v3",
            operation_id="youtube.search.list",
        ),
        state="claimable",
        created_at=NOW,
    )


def _claim():
    return claim_workflow_execution_dispatch(
        _dispatch(),
        lease_id=LEASE_ID,
        worker_id="worker-a",
        claimed_at=NOW,
        lease_duration_seconds=30,
    )


def _credential_permit(*, environment: str = "local", expires_at: datetime | None = None):
    return WorkflowCredentialResolutionPermit(
        id=UUID("30000000-0000-4000-8000-000000000011"),
        dispatch_id=DISPATCH_ID,
        workspace_id=WORKSPACE_ID,
        workflow_run_id=RUN_ID,
        workflow_step_run_id=STEP_ID,
        attempt_generation=2,
        provider_id="youtube.v3",
        operation_id="youtube.search.list",
        purpose="workflow_provider_call",
        credential_reference_fingerprint=DIGEST_C,
        environment=environment,
        issued_at=NOW,
        expires_at=expires_at or NOW + timedelta(minutes=5),
    )


def _provider_permit(*, environment: str = "local", expires_at: datetime | None = None):
    return WorkflowProviderCallPermit(
        id=UUID("30000000-0000-4000-8000-000000000012"),
        dispatch_id=DISPATCH_ID,
        workspace_id=WORKSPACE_ID,
        workflow_run_id=RUN_ID,
        workflow_step_run_id=STEP_ID,
        attempt_generation=2,
        provider_id="youtube.v3",
        operation_id="youtube.search.list",
        preflight_id=DIGEST_A,
        policy_digest=DIGEST_B,
        side_effect_key=_dispatch().provider_side_effect_key,
        environment=environment,
        max_cost_usd=Decimal("0.50"),
        max_quota_units=100,
        issued_at=NOW,
        expires_at=expires_at or NOW + timedelta(minutes=5),
    )


def test_claim_heartbeat_release_and_takeover_keep_monotonic_fencing() -> None:
    lease = _claim()
    heartbeat = heartbeat_workflow_execution_lease(
        lease,
        presented_fencing_token=1,
        presented_version=1,
        heartbeat_at=NOW + timedelta(seconds=10),
        lease_duration_seconds=30,
    )
    released = release_workflow_execution_lease(
        heartbeat,
        presented_fencing_token=1,
        presented_version=2,
        released_at=NOW + timedelta(seconds=15),
    )

    assert heartbeat.version == 2
    assert heartbeat.expires_at == NOW + timedelta(seconds=40)
    assert released.state == "released"
    assert released.version == 3

    expired = _claim().model_copy(update={"expires_at": NOW + timedelta(seconds=5)})
    replacement = takeover_workflow_execution_lease(
        expired,
        lease_id=UUID("30000000-0000-4000-8000-000000000099"),
        worker_id="worker-b",
        taken_over_at=NOW + timedelta(seconds=5),
        lease_duration_seconds=30,
    )
    assert replacement.fencing_token == 2
    assert replacement.version == 1
    assert replacement.worker_id == "worker-b"


def test_stale_fencing_version_and_live_lease_takeover_fail_closed() -> None:
    lease = _claim()
    invalid_calls = (
        (
            "workflow_executor_fencing_token_stale",
            lambda: heartbeat_workflow_execution_lease(
                lease,
                presented_fencing_token=0,
                presented_version=1,
                heartbeat_at=NOW + timedelta(seconds=1),
                lease_duration_seconds=30,
            ),
        ),
        (
            "workflow_executor_lease_version_stale",
            lambda: release_workflow_execution_lease(
                lease,
                presented_fencing_token=1,
                presented_version=2,
                released_at=NOW + timedelta(seconds=1),
            ),
        ),
        (
            "workflow_executor_lease_unavailable",
            lambda: takeover_workflow_execution_lease(
                lease,
                lease_id=UUID("30000000-0000-4000-8000-000000000099"),
                worker_id="worker-b",
                taken_over_at=NOW + timedelta(seconds=1),
                lease_duration_seconds=30,
            ),
        ),
    )
    for expected_code, invalid_call in invalid_calls:
        with pytest.raises(WorkflowExecutorContractError, match=f"^{expected_code}$"):
            invalid_call()

    with pytest.raises(
        WorkflowExecutorContractError,
        match="^workflow_executor_lease_duration_invalid$",
    ):
        claim_workflow_execution_dispatch(
            _dispatch(),
            lease_id=LEASE_ID,
            worker_id="worker-a",
            claimed_at=NOW,
            lease_duration_seconds=1.5,  # type: ignore[arg-type]
        )


def test_preflight_never_authorizes_provider_call() -> None:
    lease = _claim()
    blocked = compile_workflow_execution_preflight(
        _dispatch(),
        lease,
        preflight_id=DIGEST_A,
        eligible=False,
        blocker_codes=("request_budget_exceeded",),
        evaluated_at=NOW + timedelta(seconds=1),
    )
    eligible = compile_workflow_execution_preflight(
        _dispatch(),
        lease,
        preflight_id=DIGEST_A,
        eligible=True,
        blocker_codes=(),
        evaluated_at=NOW + timedelta(seconds=1),
    )

    assert blocked.next_required_authority is None
    assert blocked.provider_call_allowed is False
    assert eligible.next_required_authority == "credential_resolution_permit"
    assert eligible.provider_call_allowed is False


def test_credential_permit_is_single_use_expiring_and_environment_bound() -> None:
    consumed = consume_workflow_credential_resolution_permit(
        _credential_permit(),
        _dispatch(),
        provider_id="youtube.v3",
        operation_id="youtube.search.list",
        purpose="workflow_provider_call",
        environment="local",
        consumed_at=NOW + timedelta(seconds=1),
    )
    assert consumed.consumed_at == NOW + timedelta(seconds=1)

    invalid_permits = (
        (
            "workflow_executor_credential_permit_consumed",
            consumed,
            "local",
            NOW + timedelta(seconds=2),
        ),
        (
            "workflow_executor_credential_permit_environment_mismatch",
            _credential_permit(environment="staging"),
            "local",
            NOW + timedelta(seconds=1),
        ),
        (
            "workflow_executor_credential_permit_expired",
            _credential_permit(expires_at=NOW + timedelta(seconds=1)),
            "local",
            NOW + timedelta(seconds=1),
        ),
    )
    for expected_code, permit, environment, consumed_at in invalid_permits:
        with pytest.raises(WorkflowExecutorContractError, match=f"^{expected_code}$"):
            consume_workflow_credential_resolution_permit(
                permit,
                _dispatch(),
                provider_id="youtube.v3",
                operation_id="youtube.search.list",
                purpose="workflow_provider_call",
                environment=environment,
                consumed_at=consumed_at,
            )


def test_provider_permit_binds_preflight_side_effect_environment_and_budget() -> None:
    consumed = consume_workflow_provider_call_permit(
        _provider_permit(),
        _dispatch(),
        preflight_id=DIGEST_A,
        policy_digest=DIGEST_B,
        provider_id="youtube.v3",
        operation_id="youtube.search.list",
        environment="local",
        reserved_cost_usd=Decimal("0.25"),
        reserved_quota_units=50,
        consumed_at=NOW + timedelta(seconds=1),
    )
    assert consumed.consumed_at == NOW + timedelta(seconds=1)

    with pytest.raises(
        WorkflowExecutorContractError,
        match="^workflow_executor_provider_permit_environment_mismatch$",
    ):
        consume_workflow_provider_call_permit(
            _provider_permit(environment="staging"),
            _dispatch(),
            preflight_id=DIGEST_A,
            policy_digest=DIGEST_B,
            provider_id="youtube.v3",
            operation_id="youtube.search.list",
            environment="local",
            reserved_cost_usd=Decimal("0.25"),
            reserved_quota_units=50,
            consumed_at=NOW + timedelta(seconds=1),
        )
    with pytest.raises(
        WorkflowExecutorContractError,
        match="^workflow_executor_provider_permit_budget_exceeded$",
    ):
        consume_workflow_provider_call_permit(
            _provider_permit(),
            _dispatch(),
            preflight_id=DIGEST_A,
            policy_digest=DIGEST_B,
            provider_id="youtube.v3",
            operation_id="youtube.search.list",
            environment="local",
            reserved_cost_usd=Decimal("0.75"),
            reserved_quota_units=50,
            consumed_at=NOW + timedelta(seconds=1),
        )


def test_terminal_outcome_requires_current_fence_and_holds_uncertain_result() -> None:
    lease = _claim()
    audit = WorkflowProviderCallAudit(
        id=UUID("30000000-0000-4000-8000-000000000013"),
        dispatch_id=DISPATCH_ID,
        workspace_id=WORKSPACE_ID,
        workflow_run_id=RUN_ID,
        workflow_step_run_id=STEP_ID,
        attempt_generation=2,
        lease_id=LEASE_ID,
        fencing_token=1,
        provider_id="youtube.v3",
        operation_id="youtube.search.list",
        preflight_id=DIGEST_A,
        policy_digest=DIGEST_B,
        side_effect_key=_dispatch().provider_side_effect_key,
        environment="local",
        attempt_ordinal=1,
        transport_state="attempting",
        started_at=NOW,
    )
    outcome = compile_workflow_execution_terminal_outcome(
        _dispatch(),
        lease,
        audit,
        presented_fencing_token=1,
        presented_version=1,
        outcome="uncertain",
        completed_at=NOW + timedelta(seconds=2),
    )

    assert outcome.audit.transport_state == "uncertain"
    assert outcome.dispatch_state == "terminal"
    assert outcome.recovery_state == "held_manual_review"
    assert outcome.retry_allowed is False

    failed = compile_workflow_execution_terminal_outcome(
        _dispatch(),
        lease,
        audit,
        presented_fencing_token=1,
        presented_version=1,
        outcome="failed",
        completed_at=NOW + timedelta(seconds=2),
    )
    assert failed.audit.transport_state == "failed"
    assert failed.retry_allowed is False
    with pytest.raises(
        WorkflowExecutorContractError,
        match="^workflow_executor_fencing_token_stale$",
    ):
        compile_workflow_execution_terminal_outcome(
            _dispatch(),
            lease,
            audit,
            presented_fencing_token=2,
            presented_version=1,
            outcome="succeeded",
            completed_at=NOW + timedelta(seconds=2),
        )


def test_cancellation_intent_requires_current_worker_acknowledgement() -> None:
    lease = _claim()
    request = WorkflowCancellationRequest(
        id=UUID("30000000-0000-4000-8000-000000000014"),
        dispatch_id=DISPATCH_ID,
        workspace_id=WORKSPACE_ID,
        workflow_run_id=RUN_ID,
        requested_by_user_id=REQUEST_ID,
        request_key=DIGEST_A,
        reason_code="cancel_operator_request",
        requested_at=NOW,
    )
    acknowledgement = acknowledge_workflow_cancellation(
        request,
        lease,
        acknowledgement_id=UUID("30000000-0000-4000-8000-000000000015"),
        presented_fencing_token=1,
        presented_version=1,
        safe_point="before_provider_transport",
        outcome="cancelled_before_effect",
        acknowledged_at=NOW + timedelta(seconds=1),
    )

    assert request.acknowledged is False
    assert acknowledgement.request_id == request.id
    with pytest.raises(
        WorkflowExecutorContractError,
        match="^workflow_executor_fencing_token_stale$",
    ):
        acknowledge_workflow_cancellation(
            request,
            lease,
            acknowledgement_id=UUID("30000000-0000-4000-8000-000000000016"),
            presented_fencing_token=0,
            presented_version=1,
            safe_point="before_provider_transport",
            outcome="cancelled_before_effect",
            acknowledged_at=NOW + timedelta(seconds=1),
        )
