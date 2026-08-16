from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from data_intelligence_hub.schemas.workflow_action_command import (
    RetryActionParameters,
    WorkflowActionApprovalReceipt,
    WorkflowRunActionRequest,
    canonical_workflow_action_proposal_hash,
)
from data_intelligence_hub.schemas.workflow_execution import (
    WorkflowRunStatus,
    WorkflowStepRunStatus,
)
from data_intelligence_hub.services.workflow_execution.action_authorization import (
    WorkflowActionStateContext,
    authorize_workflow_action,
    compile_workflow_action_state_effect,
)

WORKSPACE_ID = UUID("10000000-0000-4000-8000-000000000001")
PROJECT_ID = UUID("10000000-0000-4000-8000-000000000002")
RUN_ID = UUID("10000000-0000-4000-8000-000000000003")
STEP_ID = UUID("10000000-0000-4000-8000-000000000004")
OWNER_ID = UUID("10000000-0000-4000-8000-000000000005")
OTHER_USER_ID = UUID("10000000-0000-4000-8000-000000000006")
APPROVAL_ID = UUID("10000000-0000-4000-8000-000000000007")
NOW = datetime(2026, 7, 27, 10, 0, tzinfo=UTC)
DIGEST_A = f"sha256:{'a' * 64}"
DIGEST_B = f"sha256:{'b' * 64}"
DIGEST_C = f"sha256:{'c' * 64}"


def _request() -> WorkflowRunActionRequest:
    return WorkflowRunActionRequest(
        action="retry",
        expected_action_context_version=2,
        expected_run_status=WorkflowRunStatus.HELD,
        action_gate_digest=DIGEST_A,
        approval_receipt_id=APPROVAL_ID,
        reason_code="retry_after_retryable_failure",
        reason="Retry the exact failed fixture step after Owner review.",
        parameters=RetryActionParameters(
            target_step_run_ids=[STEP_ID],
            expected_retry_generation=0,
            attempt_evidence_digest=DIGEST_B,
            retry_policy_digest=DIGEST_C,
        ),
    )


def _approval(
    request: WorkflowRunActionRequest,
    *,
    approver_user_id: UUID = OWNER_ID,
    expires_at: datetime | None = None,
) -> WorkflowActionApprovalReceipt:
    return WorkflowActionApprovalReceipt(
        id=APPROVAL_ID,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_run_id=RUN_ID,
        approver_user_id=approver_user_id,
        action=request.action,
        approval_kind="owner_confirmation",
        proposal_digest=canonical_workflow_action_proposal_hash(
            workspace_id=WORKSPACE_ID,
            project_id=PROJECT_ID,
            workflow_run_id=RUN_ID,
            request=request,
        ),
        expected_action_context_version=request.expected_action_context_version,
        expected_run_status=request.expected_run_status,
        action_gate_digest=request.action_gate_digest,
        evidence_digests=[DIGEST_B, DIGEST_C],
        reason_code=request.reason_code,
        reason=request.reason,
        issued_at=NOW,
        expires_at=expires_at or NOW + timedelta(minutes=15),
    )


def test_exact_owner_and_exact_approval_authorize_submission() -> None:
    request = _request()
    result = authorize_workflow_action(
        actor_user_id=OWNER_ID,
        workspace_owner_id=OWNER_ID,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_run_id=RUN_ID,
        request=request,
        approval=_approval(request),
        evaluated_at=NOW + timedelta(minutes=1),
    )

    assert result.authorized is True
    assert result.blocker_code is None
    assert result.provider_call is False
    assert result.credential_read_attempted is False
    assert result.execution_started is False


def test_approval_cannot_authorize_before_its_issue_time() -> None:
    request = _request()
    result = authorize_workflow_action(
        actor_user_id=OWNER_ID,
        workspace_owner_id=OWNER_ID,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_run_id=RUN_ID,
        request=request,
        approval=_approval(request),
        evaluated_at=NOW - timedelta(seconds=1),
    )

    assert result.authorized is False
    assert result.blocker_code == "workflow_action_approval_mismatch"


@pytest.mark.parametrize(
    (
        "actor_user_id",
        "approver_user_id",
        "expires_at",
        "approval_consumed",
        "approval_revoked",
        "expected_blocker",
    ),
    [
        (
            OTHER_USER_ID,
            OWNER_ID,
            NOW + timedelta(minutes=15),
            False,
            False,
            "workflow_action_owner_required",
        ),
        (
            OWNER_ID,
            OTHER_USER_ID,
            NOW + timedelta(minutes=15),
            False,
            False,
            "workflow_action_approval_mismatch",
        ),
        (
            OWNER_ID,
            OWNER_ID,
            NOW + timedelta(seconds=30),
            False,
            False,
            "workflow_action_approval_expired",
        ),
        (
            OWNER_ID,
            OWNER_ID,
            NOW + timedelta(minutes=15),
            True,
            False,
            "workflow_action_approval_consumed",
        ),
        (
            OWNER_ID,
            OWNER_ID,
            NOW + timedelta(minutes=15),
            False,
            True,
            "workflow_action_approval_revoked",
        ),
    ],
)
def test_authorization_fails_closed(
    actor_user_id: UUID,
    approver_user_id: UUID,
    expires_at: datetime,
    approval_consumed: bool,
    approval_revoked: bool,
    expected_blocker: str,
) -> None:
    request = _request()
    approval = _approval(
        request,
        approver_user_id=approver_user_id,
        expires_at=expires_at,
    )
    result = authorize_workflow_action(
        actor_user_id=actor_user_id,
        workspace_owner_id=OWNER_ID,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_run_id=RUN_ID,
        request=request,
        approval=approval,
        evaluated_at=NOW + timedelta(minutes=1),
        approval_consumed=approval_consumed,
        approval_revoked=approval_revoked,
    )

    assert result.authorized is False
    assert result.blocker_code == expected_blocker


def test_retry_effect_prepares_new_generation_without_starting_execution() -> None:
    effect = compile_workflow_action_state_effect(
        action="retry",
        context=WorkflowActionStateContext(
            run_status=WorkflowRunStatus.HELD,
            target_step_statuses=(WorkflowStepRunStatus.FAILED,),
            retry_generation=0,
            retry_policy_available=True,
        ),
    )

    assert effect.accepted is True
    assert effect.run_status_after is WorkflowRunStatus.READY
    assert effect.target_step_statuses_after == (WorkflowStepRunStatus.PENDING,)
    assert effect.retry_generation_after == 1
    assert effect.execution_started is False
    assert effect.provider_call is False


def test_resume_prepares_ready_without_advancing_cursor() -> None:
    effect = compile_workflow_action_state_effect(
        action="resume",
        context=WorkflowActionStateContext(
            run_status=WorkflowRunStatus.HELD,
            checkpoint_available=True,
            checkpoint_terminal=False,
            budget_within_limit=True,
            failed_step_requires_retry=False,
        ),
    )

    assert effect.accepted is True
    assert effect.run_status_after is WorkflowRunStatus.READY
    assert effect.cursor_advanced is False
    assert effect.execution_started is False


def test_held_cancel_is_terminal_but_running_cancel_stays_unavailable() -> None:
    held = compile_workflow_action_state_effect(
        action="cancel",
        context=WorkflowActionStateContext(run_status=WorkflowRunStatus.HELD),
    )
    running = compile_workflow_action_state_effect(
        action="cancel",
        context=WorkflowActionStateContext(run_status=WorkflowRunStatus.RUNNING),
    )

    assert held.accepted is True
    assert held.run_status_after is WorkflowRunStatus.CANCELLED
    assert running.accepted is False
    assert running.blocker_code == "workflow_action_executor_ack_unavailable"
    assert running.run_status_after is WorkflowRunStatus.RUNNING


@pytest.mark.parametrize(
    ("action", "context"),
    [
        (
            "budget_override",
            WorkflowActionStateContext(
                run_status=WorkflowRunStatus.HELD,
                budget_held=True,
            ),
        ),
        (
            "route_switch",
            WorkflowActionStateContext(
                run_status=WorkflowRunStatus.HELD,
                route_switch_eligible=True,
            ),
        ),
    ],
)
def test_override_effects_leave_run_held(
    action: str,
    context: WorkflowActionStateContext,
) -> None:
    effect = compile_workflow_action_state_effect(action=action, context=context)

    assert effect.accepted is True
    assert effect.run_status_after is WorkflowRunStatus.HELD
    assert effect.state_changed is False
    assert effect.execution_started is False


def test_retry_rejects_nonfailed_steps_and_generation_ceiling() -> None:
    wrong_status = compile_workflow_action_state_effect(
        action="retry",
        context=WorkflowActionStateContext(
            run_status=WorkflowRunStatus.HELD,
            target_step_statuses=(WorkflowStepRunStatus.COMPLETED,),
            retry_generation=0,
            retry_policy_available=True,
        ),
    )
    ceiling = compile_workflow_action_state_effect(
        action="retry",
        context=WorkflowActionStateContext(
            run_status=WorkflowRunStatus.HELD,
            target_step_statuses=(WorkflowStepRunStatus.FAILED,),
            retry_generation=3,
            retry_generation_limit=3,
            retry_policy_available=True,
        ),
    )

    assert wrong_status.blocker_code == "workflow_action_retry_step_state_invalid"
    assert ceiling.blocker_code == "workflow_action_retry_generation_exhausted"
