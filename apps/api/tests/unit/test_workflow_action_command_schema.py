from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import TypeAdapter, ValidationError

from data_intelligence_hub.schemas.workflow_action_command import (
    WORKFLOW_ACTION_APPROVAL_KIND_BY_ACTION,
    BudgetOverrideActionParameters,
    CancelActionParameters,
    ResumeActionParameters,
    RetryActionParameters,
    RouteSwitchActionParameters,
    WorkflowActionApprovalReceipt,
    WorkflowActionApprovalRequest,
    WorkflowActionReceipt,
    WorkflowRunActionGatesCurrentResponse,
    WorkflowRunActionGatesV2Response,
    WorkflowRunActionGateV2Evidence,
    WorkflowRunActionRequest,
    canonical_workflow_action_proposal_hash,
    canonical_workflow_action_request_hash,
)
from data_intelligence_hub.schemas.workflow_action_gate import (
    WORKFLOW_RUN_ACTION_ORDER,
    WorkflowRunActionGatesResponse,
)
from data_intelligence_hub.schemas.workflow_execution import WorkflowRunStatus

WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000001")
PROJECT_ID = UUID("00000000-0000-4000-8000-000000000002")
PLAN_ID = UUID("00000000-0000-4000-8000-000000000003")
VERSION_ID = UUID("00000000-0000-4000-8000-000000000004")
RUN_ID = UUID("00000000-0000-4000-8000-000000000005")
STEP_ID = UUID("00000000-0000-4000-8000-000000000006")
OWNER_ID = UUID("00000000-0000-4000-8000-000000000007")
APPROVAL_ID = UUID("00000000-0000-4000-8000-000000000008")
REQUEST_ID = UUID("00000000-0000-4000-8000-000000000009")
RECEIPT_ID = UUID("00000000-0000-4000-8000-000000000010")
NOW = datetime(2026, 7, 27, 9, 0, tzinfo=UTC)
DIGEST_A = f"sha256:{'a' * 64}"
DIGEST_B = f"sha256:{'b' * 64}"
DIGEST_C = f"sha256:{'c' * 64}"


def _retry_request() -> WorkflowRunActionRequest:
    return WorkflowRunActionRequest(
        action="retry",
        expected_action_context_version=3,
        expected_run_status=WorkflowRunStatus.HELD,
        action_gate_digest=DIGEST_A,
        approval_receipt_id=APPROVAL_ID,
        reason_code="retry_after_retryable_failure",
        reason="Retry the failed fixture step after evidence review.",
        parameters=RetryActionParameters(
            target_step_run_ids=[STEP_ID],
            expected_retry_generation=0,
            attempt_evidence_digest=DIGEST_B,
            retry_policy_digest=DIGEST_C,
        ),
    )


def _v2_gate(
    action: str,
    *,
    submission_available: bool,
) -> WorkflowRunActionGateV2Evidence:
    precondition_status = "ready_for_review" if submission_available else "blocked"
    return WorkflowRunActionGateV2Evidence(
        action=action,
        precondition_status=precondition_status,
        precondition_blocker_codes=([] if submission_available else ["retry_evidence_unavailable"]),
        submission_available=submission_available,
        availability_blocker_codes=(
            [] if submission_available else ["workflow_action_approval_required"]
        ),
        approval_kind=WORKFLOW_ACTION_APPROVAL_KIND_BY_ACTION[action],
        evidence_refs=[f"workflow-action:{action}"],
        expires_at=NOW + timedelta(minutes=15),
    )


def test_v2_action_gates_preserve_v1_and_require_strict_discrimination() -> None:
    gates = [
        _v2_gate(action, submission_available=action == "cancel")
        for action in WORKFLOW_RUN_ACTION_ORDER
    ]
    response = WorkflowRunActionGatesV2Response(
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_plan_id=PLAN_ID,
        workflow_version_id=VERSION_ID,
        workflow_run_id=RUN_ID,
        run_status=WorkflowRunStatus.HELD,
        action_gate_digest=DIGEST_A,
        action_context_version=3,
        gates=gates,
        ready_for_review_total=1,
        blocked_total=4,
        not_applicable_total=0,
        available_action_total=1,
    )

    adapter = TypeAdapter(WorkflowRunActionGatesCurrentResponse)
    assert adapter.validate_python(response.model_dump(mode="json")).schema_version == (
        "workflow_run_action_gates.v2"
    )
    assert WorkflowRunActionGatesResponse.model_fields["schema_version"].default == (
        "workflow_run_action_gates.v1"
    )

    reordered = response.model_dump(mode="json")
    reordered["gates"] = list(reversed(reordered["gates"]))
    with pytest.raises(ValidationError, match="workflow_run_action_gate_order_invalid"):
        WorkflowRunActionGatesV2Response.model_validate(reordered)


def test_v2_gate_never_conflates_precondition_with_submission_authority() -> None:
    with pytest.raises(
        ValidationError,
        match="workflow_action_submission_availability_invalid",
    ):
        _v2_gate("resume", submission_available=True).model_copy(
            update={"availability_blocker_codes": ["workflow_action_approval_required"]}
        ).model_validate(
            {
                **_v2_gate("resume", submission_available=True).model_dump(mode="json"),
                "availability_blocker_codes": ["workflow_action_approval_required"],
            }
        )

    with pytest.raises(ValidationError, match="workflow_action_approval_kind_invalid"):
        WorkflowRunActionGateV2Evidence.model_validate(
            {
                **_v2_gate("budget_override", submission_available=True).model_dump(mode="json"),
                "approval_kind": "owner_confirmation",
            }
        )


def test_action_request_is_strict_typed_and_forbids_client_actor_fields() -> None:
    request = _retry_request()

    assert request.parameters.action == "retry"
    assert request.reason == "Retry the failed fixture step after evidence review."
    with pytest.raises(ValidationError):
        WorkflowRunActionRequest.model_validate(
            {**request.model_dump(mode="json"), "actor_user_id": str(OWNER_ID)}
        )
    with pytest.raises(ValidationError, match="workflow_action_parameters_invalid"):
        WorkflowRunActionRequest.model_validate(
            {
                **request.model_dump(mode="json"),
                "action": "resume",
            }
        )


def test_approval_request_is_exact_and_forbids_client_approver_fields() -> None:
    request = _retry_request()
    approval_request = WorkflowActionApprovalRequest(
        action=request.action,
        approval_kind="owner_confirmation",
        expected_action_context_version=request.expected_action_context_version,
        expected_run_status=request.expected_run_status,
        action_gate_digest=request.action_gate_digest,
        reason_code=request.reason_code,
        reason=request.reason,
        parameters=request.parameters,
    )

    assert approval_request.approval_kind == "owner_confirmation"
    with pytest.raises(ValidationError):
        WorkflowActionApprovalRequest.model_validate(
            {
                **approval_request.model_dump(mode="json"),
                "approver_user_id": str(OWNER_ID),
            }
        )


def test_approval_and_command_share_the_same_canonical_proposal_digest() -> None:
    request = _retry_request()
    approval_request = WorkflowActionApprovalRequest(
        action=request.action,
        approval_kind="owner_confirmation",
        expected_action_context_version=request.expected_action_context_version,
        expected_run_status=request.expected_run_status,
        action_gate_digest=request.action_gate_digest,
        reason_code=request.reason_code,
        reason=request.reason,
        parameters=request.parameters,
    )

    assert canonical_workflow_action_proposal_hash(
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_run_id=RUN_ID,
        request=approval_request,
    ) == canonical_workflow_action_proposal_hash(
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_run_id=RUN_ID,
        request=request,
    )


@pytest.mark.parametrize(
    ("parameters", "reason_code"),
    [
        (
            ResumeActionParameters(
                checkpoint_digest=DIGEST_A,
                budget_policy_digest=DIGEST_B,
                budget_ledger_digest=DIGEST_C,
            ),
            "resume_from_confirmed_checkpoint",
        ),
        (
            CancelActionParameters(cancel_scope="held_run"),
            "cancel_operator_request",
        ),
        (
            BudgetOverrideActionParameters(
                request_limit=10,
                item_limit=100,
                quota_unit_limit=500,
                cost_limit_usd=Decimal("4.25"),
                time_limit_ms=60_000,
                expires_at=NOW + timedelta(hours=1),
            ),
            "budget_override_business_exception",
        ),
        (
            RouteSwitchActionParameters(
                step_run_id=STEP_ID,
                primary_implementation_id="youtube.primary.v1",
                fallback_implementation_id="youtube.fallback.v1",
                fallback_decision_digest=DIGEST_A,
                field_difference_digest=DIGEST_B,
                cost_digest=DIGEST_C,
                provider_health_digest=f"sha256:{'d' * 64}",
            ),
            "route_switch_verified_fallback",
        ),
    ],
)
def test_each_action_parameter_contract_matches_its_reason(
    parameters: object,
    reason_code: str,
) -> None:
    request = WorkflowRunActionRequest(
        action=parameters.action,  # type: ignore[attr-defined]
        expected_action_context_version=1,
        expected_run_status=WorkflowRunStatus.HELD,
        action_gate_digest=DIGEST_A,
        approval_receipt_id=APPROVAL_ID,
        reason_code=reason_code,
        reason="Owner reviewed the exact fixture action evidence.",
        parameters=parameters,
    )

    assert request.parameters.action == request.action


def test_reason_and_budget_values_fail_closed() -> None:
    payload = _retry_request().model_dump(mode="json")
    with pytest.raises(ValidationError, match="workflow_action_reason_invalid"):
        WorkflowRunActionRequest.model_validate(
            {**payload, "reason": "Authorization: Bearer secret-value"}
        )
    with pytest.raises(ValidationError, match="workflow_action_reason_invalid"):
        WorkflowRunActionRequest.model_validate({**payload, "reason": "bad\u0007reason"})
    with pytest.raises(ValidationError):
        BudgetOverrideActionParameters(
            request_limit=10,
            item_limit=100,
            quota_unit_limit=500,
            cost_limit_usd=Decimal("Infinity"),
            time_limit_ms=60_000,
            expires_at=NOW + timedelta(hours=1),
        )


def test_canonical_request_hash_is_deterministic_tenant_scoped_and_secret_free() -> None:
    request = _retry_request()
    digest = canonical_workflow_action_request_hash(
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_run_id=RUN_ID,
        request=request,
    )
    assert digest == canonical_workflow_action_request_hash(
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_run_id=RUN_ID,
        request=WorkflowRunActionRequest.model_validate(request.model_dump(mode="json")),
    )
    assert digest != canonical_workflow_action_request_hash(
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_run_id=UUID("00000000-0000-4000-8000-000000000099"),
        request=request,
    )
    assert digest.startswith("sha256:")
    assert "secret" not in repr(request).lower()


def test_approval_receipt_is_exact_expiring_and_immutable() -> None:
    request = _retry_request()
    proposal_digest = canonical_workflow_action_proposal_hash(
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_run_id=RUN_ID,
        request=request,
    )
    receipt = WorkflowActionApprovalReceipt(
        id=APPROVAL_ID,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_run_id=RUN_ID,
        approver_user_id=OWNER_ID,
        action="retry",
        approval_kind="owner_confirmation",
        proposal_digest=proposal_digest,
        expected_action_context_version=3,
        expected_run_status=WorkflowRunStatus.HELD,
        action_gate_digest=DIGEST_A,
        evidence_digests=[DIGEST_B, DIGEST_C],
        reason_code="retry_after_retryable_failure",
        reason="Retry the failed fixture step after evidence review.",
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=15),
    )

    assert "consumed" not in type(receipt).model_fields
    assert "revoked" not in type(receipt).model_fields
    with pytest.raises(ValidationError):
        receipt.approver_user_id = UUID(  # type: ignore[misc]
            "00000000-0000-4000-8000-000000000099"
        )
    with pytest.raises(ValidationError, match="workflow_action_approval_expiry_invalid"):
        WorkflowActionApprovalReceipt.model_validate(
            {
                **receipt.model_dump(mode="json"),
                "expires_at": NOW.isoformat(),
            }
        )


def test_action_receipt_enforces_replay_and_non_live_boundaries() -> None:
    receipt = WorkflowActionReceipt(
        id=RECEIPT_ID,
        request_id=REQUEST_ID,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_run_id=RUN_ID,
        action="retry",
        outcome="accepted",
        before_action_context_version=3,
        after_action_context_version=4,
        before_run_status=WorkflowRunStatus.HELD,
        after_run_status=WorkflowRunStatus.READY,
        state_changed=True,
        database_write=True,
        idempotent_replay=False,
        next_action_code="await_fixture_executor",
        receipt_digest=DIGEST_A,
        created_at=NOW,
    )

    assert receipt.provider_call is False
    assert receipt.credential_read_attempted is False
    assert receipt.execution_started is False
    assert receipt.production_write_allowed is False

    replay = WorkflowActionReceipt.model_validate(
        {
            **receipt.model_dump(mode="json"),
            "database_write": False,
            "idempotent_replay": True,
        }
    )
    assert replay.after_action_context_version == 4
    assert replay.database_write is False

    with pytest.raises(ValidationError, match="workflow_action_replay_write_invalid"):
        WorkflowActionReceipt.model_validate(
            {
                **receipt.model_dump(mode="json"),
                "idempotent_replay": True,
            }
        )
    with pytest.raises(ValidationError):
        WorkflowActionReceipt.model_validate(
            {
                **receipt.model_dump(mode="json"),
                "provider_call": True,
            }
        )
