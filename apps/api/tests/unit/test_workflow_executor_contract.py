from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from data_intelligence_hub.schemas.workflow_executor import (
    WorkflowCancellationAcknowledgement,
    WorkflowCancellationRequest,
    WorkflowCredentialResolutionPermit,
    WorkflowExecutionDispatch,
    WorkflowExecutionEvent,
    WorkflowExecutionLeaseToken,
    WorkflowProviderCallAudit,
    WorkflowProviderCallPermit,
    canonical_workflow_execution_dispatch_key,
    canonical_workflow_provider_side_effect_key,
)

WORKSPACE_ID = UUID("20000000-0000-4000-8000-000000000001")
PROJECT_ID = UUID("20000000-0000-4000-8000-000000000002")
PLAN_ID = UUID("20000000-0000-4000-8000-000000000003")
VERSION_ID = UUID("20000000-0000-4000-8000-000000000004")
RUN_ID = UUID("20000000-0000-4000-8000-000000000005")
STEP_ID = UUID("20000000-0000-4000-8000-000000000006")
REQUEST_ID = UUID("20000000-0000-4000-8000-000000000007")
RECEIPT_ID = UUID("20000000-0000-4000-8000-000000000008")
DISPATCH_ID = UUID("20000000-0000-4000-8000-000000000009")
LEASE_ID = UUID("20000000-0000-4000-8000-000000000010")
PERMIT_ID = UUID("20000000-0000-4000-8000-000000000011")
AUDIT_ID = UUID("20000000-0000-4000-8000-000000000012")
CANCEL_ID = UUID("20000000-0000-4000-8000-000000000013")
ACK_ID = UUID("20000000-0000-4000-8000-000000000014")
EVENT_ID = UUID("20000000-0000-4000-8000-000000000015")
NOW = datetime(2026, 7, 28, 9, 0, tzinfo=UTC)
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
        attempt_generation=1,
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
        attempt_generation=1,
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


def _lease() -> WorkflowExecutionLeaseToken:
    return WorkflowExecutionLeaseToken(
        id=LEASE_ID,
        dispatch_id=DISPATCH_ID,
        workspace_id=WORKSPACE_ID,
        worker_id="worker-local-01",
        fencing_token=1,
        version=1,
        claimed_at=NOW,
        heartbeat_at=NOW,
        expires_at=NOW + timedelta(seconds=30),
        state="active",
    )


def test_dispatch_identity_is_deterministic_tenant_scoped_and_lease_independent() -> None:
    dispatch = _dispatch()

    assert dispatch.dispatch_key == canonical_workflow_execution_dispatch_key(
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_plan_id=PLAN_ID,
        workflow_version_id=VERSION_ID,
        workflow_run_id=RUN_ID,
        workflow_step_run_id=STEP_ID,
        attempt_generation=1,
        source_action_request_id=REQUEST_ID,
        source_action_receipt_id=RECEIPT_ID,
        workflow_version_digest=DIGEST_A,
        execution_policy_digest=DIGEST_B,
    )
    assert dispatch.dispatch_key != canonical_workflow_execution_dispatch_key(
        workspace_id=UUID("20000000-0000-4000-8000-000000000099"),
        project_id=PROJECT_ID,
        workflow_plan_id=PLAN_ID,
        workflow_version_id=VERSION_ID,
        workflow_run_id=RUN_ID,
        workflow_step_run_id=STEP_ID,
        attempt_generation=1,
        source_action_request_id=REQUEST_ID,
        source_action_receipt_id=RECEIPT_ID,
        workflow_version_digest=DIGEST_A,
        execution_policy_digest=DIGEST_B,
    )
    assert "worker-local-01" not in dispatch.provider_side_effect_key


def test_executor_contracts_are_frozen_strict_and_require_utc() -> None:
    dispatch = _dispatch()
    with pytest.raises(ValidationError):
        dispatch.state = "terminal"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        WorkflowExecutionDispatch.model_validate(
            {**dispatch.model_dump(mode="json"), "unexpected": True}
        )
    with pytest.raises(ValidationError, match="workflow_executor_time_utc_required"):
        WorkflowExecutionDispatch.model_validate(
            {**dispatch.model_dump(), "created_at": NOW.replace(tzinfo=None)}
        )


def test_lease_event_and_hash_chain_contracts_fail_closed() -> None:
    lease = _lease()
    first = WorkflowExecutionEvent(
        id=EVENT_ID,
        dispatch_id=DISPATCH_ID,
        workspace_id=WORKSPACE_ID,
        sequence=1,
        event_type="lease_claimed",
        lease_id=lease.id,
        fencing_token=lease.fencing_token,
        previous_event_digest=None,
        event_digest=DIGEST_C,
        occurred_at=NOW,
    )
    assert first.previous_event_digest is None
    with pytest.raises(ValidationError, match="workflow_executor_event_chain_invalid"):
        WorkflowExecutionEvent.model_validate({**first.model_dump(mode="json"), "sequence": 2})
    with pytest.raises(ValidationError, match="workflow_executor_lease_time_order_invalid"):
        WorkflowExecutionLeaseToken.model_validate(
            {**lease.model_dump(), "expires_at": NOW - timedelta(seconds=1)}
        )


def test_permits_bind_exact_non_secret_identity_and_budget() -> None:
    credential = WorkflowCredentialResolutionPermit(
        id=PERMIT_ID,
        dispatch_id=DISPATCH_ID,
        workspace_id=WORKSPACE_ID,
        workflow_run_id=RUN_ID,
        workflow_step_run_id=STEP_ID,
        attempt_generation=1,
        provider_id="youtube.v3",
        operation_id="youtube.search.list",
        purpose="workflow_provider_call",
        credential_reference_fingerprint=DIGEST_C,
        environment="local",
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    provider = WorkflowProviderCallPermit(
        id=UUID("20000000-0000-4000-8000-000000000016"),
        dispatch_id=DISPATCH_ID,
        workspace_id=WORKSPACE_ID,
        workflow_run_id=RUN_ID,
        workflow_step_run_id=STEP_ID,
        attempt_generation=1,
        provider_id="youtube.v3",
        operation_id="youtube.search.list",
        preflight_id=DIGEST_A,
        policy_digest=DIGEST_B,
        side_effect_key=DIGEST_D,
        environment="local",
        max_cost_usd=Decimal("0.50"),
        max_quota_units=100,
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )

    serialized = repr(
        (
            credential.model_dump(mode="json"),
            provider.model_dump(mode="json"),
        )
    )
    assert "YOUTUBE_API_KEY" not in serialized
    assert "secret:" not in serialized
    assert credential.consumed_at is None
    assert provider.revoked_at is None
    with pytest.raises(ValidationError, match="workflow_executor_permit_expiry_invalid"):
        WorkflowProviderCallPermit.model_validate({**provider.model_dump(), "expires_at": NOW})


def test_audit_and_cancellation_keep_attempt_request_and_acknowledgement_distinct() -> None:
    audit = WorkflowProviderCallAudit(
        id=AUDIT_ID,
        dispatch_id=DISPATCH_ID,
        workspace_id=WORKSPACE_ID,
        workflow_run_id=RUN_ID,
        workflow_step_run_id=STEP_ID,
        attempt_generation=1,
        lease_id=LEASE_ID,
        fencing_token=1,
        provider_id="youtube.v3",
        operation_id="youtube.search.list",
        preflight_id=DIGEST_A,
        policy_digest=DIGEST_B,
        side_effect_key=DIGEST_D,
        environment="local",
        attempt_ordinal=1,
        transport_state="attempting",
        started_at=NOW,
    )
    request = WorkflowCancellationRequest(
        id=CANCEL_ID,
        dispatch_id=DISPATCH_ID,
        workspace_id=WORKSPACE_ID,
        workflow_run_id=RUN_ID,
        requested_by_user_id=REQUEST_ID,
        request_key=DIGEST_A,
        reason_code="cancel_operator_request",
        requested_at=NOW,
    )
    acknowledgement = WorkflowCancellationAcknowledgement(
        id=ACK_ID,
        request_id=request.id,
        dispatch_id=DISPATCH_ID,
        workspace_id=WORKSPACE_ID,
        lease_id=LEASE_ID,
        fencing_token=1,
        safe_point="before_provider_transport",
        outcome="cancelled_before_effect",
        acknowledged_at=NOW + timedelta(seconds=1),
    )

    assert audit.finished_at is None
    assert request.acknowledged is False
    assert acknowledgement.request_id == request.id
    with pytest.raises(ValidationError, match="workflow_executor_audit_terminal_time_required"):
        WorkflowProviderCallAudit.model_validate(
            {**audit.model_dump(mode="json"), "transport_state": "succeeded"}
        )
