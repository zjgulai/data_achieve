from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from data_intelligence_hub.schemas.workflow_action_command import (
    WORKFLOW_ACTION_APPROVAL_KIND_BY_ACTION,
    WorkflowActionApprovalReceipt,
    WorkflowRunActionRequest,
    canonical_workflow_action_proposal_hash,
)
from data_intelligence_hub.schemas.workflow_action_gate import WorkflowRunAction
from data_intelligence_hub.schemas.workflow_execution import (
    WorkflowRunStatus,
    WorkflowStepRunStatus,
)

WorkflowActionAuthorizationBlockerCode = Literal[
    "workflow_action_owner_required",
    "workflow_action_approval_mismatch",
    "workflow_action_approval_expired",
    "workflow_action_approval_consumed",
    "workflow_action_approval_revoked",
]
WorkflowActionStateBlockerCode = Literal[
    "workflow_action_state_conflict",
    "workflow_action_retry_target_unavailable",
    "workflow_action_retry_step_state_invalid",
    "workflow_action_retry_policy_unavailable",
    "workflow_action_retry_generation_exhausted",
    "workflow_action_resume_checkpoint_unavailable",
    "workflow_action_resume_checkpoint_terminal",
    "workflow_action_resume_budget_blocked",
    "workflow_action_resume_retry_required",
    "workflow_action_budget_not_held",
    "workflow_action_route_switch_blocked",
    "workflow_action_executor_ack_unavailable",
]


@dataclass(frozen=True, slots=True)
class WorkflowActionAuthorizationResult:
    authorized: bool
    blocker_code: WorkflowActionAuthorizationBlockerCode | None
    provider_call: Literal[False] = False
    credential_read_attempted: Literal[False] = False
    execution_started: Literal[False] = False
    production_write_allowed: Literal[False] = False


@dataclass(frozen=True, slots=True)
class WorkflowActionStateContext:
    run_status: WorkflowRunStatus
    target_step_statuses: tuple[WorkflowStepRunStatus, ...] = ()
    retry_generation: int = 0
    retry_generation_limit: int = 3
    retry_policy_available: bool = False
    checkpoint_available: bool = False
    checkpoint_terminal: bool = False
    budget_within_limit: bool = False
    failed_step_requires_retry: bool = False
    budget_held: bool = False
    route_switch_eligible: bool = False

    def __post_init__(self) -> None:
        if self.retry_generation < 0:
            raise ValueError("workflow_action_retry_generation_invalid")
        if self.retry_generation_limit < 0:
            raise ValueError("workflow_action_retry_generation_limit_invalid")


@dataclass(frozen=True, slots=True)
class WorkflowActionStateEffect:
    action: WorkflowRunAction
    accepted: bool
    blocker_code: WorkflowActionStateBlockerCode | None
    run_status_before: WorkflowRunStatus
    run_status_after: WorkflowRunStatus
    target_step_statuses_before: tuple[WorkflowStepRunStatus, ...]
    target_step_statuses_after: tuple[WorkflowStepRunStatus, ...]
    retry_generation_before: int
    retry_generation_after: int
    state_changed: bool
    cursor_advanced: Literal[False] = False
    provider_call: Literal[False] = False
    credential_read_attempted: Literal[False] = False
    execution_started: Literal[False] = False
    production_write_allowed: Literal[False] = False


def _authorization_result(
    blocker_code: WorkflowActionAuthorizationBlockerCode | None,
) -> WorkflowActionAuthorizationResult:
    return WorkflowActionAuthorizationResult(
        authorized=blocker_code is None,
        blocker_code=blocker_code,
    )


def authorize_workflow_action(
    *,
    actor_user_id: UUID,
    workspace_owner_id: UUID,
    workspace_id: UUID,
    project_id: UUID,
    workflow_run_id: UUID,
    request: WorkflowRunActionRequest,
    approval: WorkflowActionApprovalReceipt,
    evaluated_at: datetime,
    approval_consumed: bool = False,
    approval_revoked: bool = False,
) -> WorkflowActionAuthorizationResult:
    if actor_user_id != workspace_owner_id:
        return _authorization_result("workflow_action_owner_required")

    proposal_digest = canonical_workflow_action_proposal_hash(
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=workflow_run_id,
        request=request,
    )
    approval_matches = all(
        (
            approval.id == request.approval_receipt_id,
            approval.workspace_id == workspace_id,
            approval.project_id == project_id,
            approval.workflow_run_id == workflow_run_id,
            approval.approver_user_id == actor_user_id,
            approval.action == request.action,
            approval.approval_kind == WORKFLOW_ACTION_APPROVAL_KIND_BY_ACTION[request.action],
            approval.proposal_digest == proposal_digest,
            approval.expected_action_context_version == request.expected_action_context_version,
            approval.expected_run_status == request.expected_run_status,
            approval.action_gate_digest == request.action_gate_digest,
            approval.reason_code == request.reason_code,
            approval.reason == request.reason,
        )
    )
    if not approval_matches:
        return _authorization_result("workflow_action_approval_mismatch")
    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        return _authorization_result("workflow_action_approval_expired")
    if evaluated_at < approval.issued_at:
        return _authorization_result("workflow_action_approval_mismatch")
    if evaluated_at >= approval.expires_at:
        return _authorization_result("workflow_action_approval_expired")
    if approval_consumed:
        return _authorization_result("workflow_action_approval_consumed")
    if approval_revoked:
        return _authorization_result("workflow_action_approval_revoked")
    return _authorization_result(None)


def _state_effect(
    *,
    action: WorkflowRunAction,
    context: WorkflowActionStateContext,
    accepted: bool,
    blocker_code: WorkflowActionStateBlockerCode | None,
    run_status_after: WorkflowRunStatus | None = None,
    target_step_statuses_after: tuple[WorkflowStepRunStatus, ...] | None = None,
    retry_generation_after: int | None = None,
    state_changed: bool = False,
) -> WorkflowActionStateEffect:
    return WorkflowActionStateEffect(
        action=action,
        accepted=accepted,
        blocker_code=blocker_code,
        run_status_before=context.run_status,
        run_status_after=run_status_after or context.run_status,
        target_step_statuses_before=context.target_step_statuses,
        target_step_statuses_after=(
            target_step_statuses_after
            if target_step_statuses_after is not None
            else context.target_step_statuses
        ),
        retry_generation_before=context.retry_generation,
        retry_generation_after=(
            retry_generation_after
            if retry_generation_after is not None
            else context.retry_generation
        ),
        state_changed=state_changed,
    )


def compile_workflow_action_state_effect(
    *,
    action: WorkflowRunAction,
    context: WorkflowActionStateContext,
) -> WorkflowActionStateEffect:
    if action == "cancel" and context.run_status is WorkflowRunStatus.RUNNING:
        return _state_effect(
            action=action,
            context=context,
            accepted=False,
            blocker_code="workflow_action_executor_ack_unavailable",
        )
    if context.run_status is not WorkflowRunStatus.HELD:
        return _state_effect(
            action=action,
            context=context,
            accepted=False,
            blocker_code="workflow_action_state_conflict",
        )

    if action == "retry":
        if not context.target_step_statuses:
            return _state_effect(
                action=action,
                context=context,
                accepted=False,
                blocker_code="workflow_action_retry_target_unavailable",
            )
        if any(
            status is not WorkflowStepRunStatus.FAILED for status in context.target_step_statuses
        ):
            return _state_effect(
                action=action,
                context=context,
                accepted=False,
                blocker_code="workflow_action_retry_step_state_invalid",
            )
        if not context.retry_policy_available:
            return _state_effect(
                action=action,
                context=context,
                accepted=False,
                blocker_code="workflow_action_retry_policy_unavailable",
            )
        if context.retry_generation >= context.retry_generation_limit:
            return _state_effect(
                action=action,
                context=context,
                accepted=False,
                blocker_code="workflow_action_retry_generation_exhausted",
            )
        return _state_effect(
            action=action,
            context=context,
            accepted=True,
            blocker_code=None,
            run_status_after=WorkflowRunStatus.READY,
            target_step_statuses_after=tuple(
                WorkflowStepRunStatus.PENDING for _ in context.target_step_statuses
            ),
            retry_generation_after=context.retry_generation + 1,
            state_changed=True,
        )

    if action == "resume":
        if not context.checkpoint_available:
            return _state_effect(
                action=action,
                context=context,
                accepted=False,
                blocker_code="workflow_action_resume_checkpoint_unavailable",
            )
        if context.checkpoint_terminal:
            return _state_effect(
                action=action,
                context=context,
                accepted=False,
                blocker_code="workflow_action_resume_checkpoint_terminal",
            )
        if not context.budget_within_limit:
            return _state_effect(
                action=action,
                context=context,
                accepted=False,
                blocker_code="workflow_action_resume_budget_blocked",
            )
        if context.failed_step_requires_retry:
            return _state_effect(
                action=action,
                context=context,
                accepted=False,
                blocker_code="workflow_action_resume_retry_required",
            )
        return _state_effect(
            action=action,
            context=context,
            accepted=True,
            blocker_code=None,
            run_status_after=WorkflowRunStatus.READY,
            state_changed=True,
        )

    if action == "cancel":
        return _state_effect(
            action=action,
            context=context,
            accepted=True,
            blocker_code=None,
            run_status_after=WorkflowRunStatus.CANCELLED,
            state_changed=True,
        )

    if action == "budget_override":
        if not context.budget_held:
            return _state_effect(
                action=action,
                context=context,
                accepted=False,
                blocker_code="workflow_action_budget_not_held",
            )
        return _state_effect(
            action=action,
            context=context,
            accepted=True,
            blocker_code=None,
            state_changed=False,
        )

    if not context.route_switch_eligible:
        return _state_effect(
            action=action,
            context=context,
            accepted=False,
            blocker_code="workflow_action_route_switch_blocked",
        )
    return _state_effect(
        action=action,
        context=context,
        accepted=True,
        blocker_code=None,
        state_changed=False,
    )


__all__ = [
    "WorkflowActionAuthorizationBlockerCode",
    "WorkflowActionAuthorizationResult",
    "WorkflowActionStateBlockerCode",
    "WorkflowActionStateContext",
    "WorkflowActionStateEffect",
    "authorize_workflow_action",
    "compile_workflow_action_state_effect",
]
