from __future__ import annotations

from collections import defaultdict

from data_intelligence_hub.schemas.workflow_action_gate import (
    WORKFLOW_RUN_ACTION_AVAILABILITY_BLOCKERS,
    WorkflowRunAction,
    WorkflowRunActionGateEvidenceResponse,
    WorkflowRunActionGatesResponse,
    WorkflowRunActionNextActionCode,
    WorkflowRunActionPreconditionBlockerCode,
    WorkflowRunActionPreconditionStatus,
)
from data_intelligence_hub.schemas.workflow_attempt_fallback import (
    WorkflowAttemptFallbackEvidenceResponse,
)
from data_intelligence_hub.schemas.workflow_checkpoint_budget import (
    WorkflowCheckpointBudgetEvidenceResponse,
)
from data_intelligence_hub.schemas.workflow_execution import (
    WorkflowRunDetailResponse,
    WorkflowRunStatus,
    WorkflowStepRunStatus,
)
from data_intelligence_hub.schemas.workflow_provider_health import (
    WorkflowProviderHealthEvidenceResponse,
)


def _gate(
    *,
    action: WorkflowRunAction,
    status: WorkflowRunActionPreconditionStatus,
    blockers: list[WorkflowRunActionPreconditionBlockerCode],
    next_action: WorkflowRunActionNextActionCode,
    evidence_refs: list[str],
) -> WorkflowRunActionGateEvidenceResponse:
    return WorkflowRunActionGateEvidenceResponse(
        action=action,
        precondition_status=status,
        precondition_blocker_codes=blockers,
        availability_blocker_codes=list(WORKFLOW_RUN_ACTION_AVAILABILITY_BLOCKERS),
        next_action_code=next_action,
        evidence_refs=evidence_refs,
    )


def _validate_sources(
    *,
    detail: WorkflowRunDetailResponse,
    attempt_fallback: WorkflowAttemptFallbackEvidenceResponse,
    checkpoint_budget: WorkflowCheckpointBudgetEvidenceResponse,
    provider_health: WorkflowProviderHealthEvidenceResponse,
) -> None:
    run = detail.run
    owner = (run.workspace_id, run.project_id, run.id)
    if (
        (
            attempt_fallback.workspace_id,
            attempt_fallback.project_id,
            attempt_fallback.workflow_run_id,
        )
        != owner
        or (
            checkpoint_budget.workspace_id,
            checkpoint_budget.project_id,
            checkpoint_budget.workflow_run_id,
        )
        != owner
        or (
            provider_health.workspace_id,
            provider_health.project_id,
            provider_health.workflow_run_id,
        )
        != owner
        or checkpoint_budget.workflow_plan_id != run.workflow_plan_id
        or checkpoint_budget.workflow_version_id != run.workflow_version_id
    ):
        raise ValueError("workflow_run_action_gate_source_owner_invalid")

    detail_step_ids = {item.id for item in detail.steps}
    if any(item.step_run_id not in detail_step_ids for item in attempt_fallback.attempts) or any(
        item.step_run_id not in detail_step_ids for item in attempt_fallback.fallback_decisions
    ):
        raise ValueError("workflow_run_action_gate_attempt_step_invalid")
    if any(
        item.step_run_id not in detail_step_ids for item in checkpoint_budget.checkpoint_steps
    ) or any(item.step_run_id not in detail_step_ids for item in provider_health.steps):
        raise ValueError("workflow_run_action_gate_evidence_step_invalid")


def build_workflow_run_action_gates(
    *,
    detail: WorkflowRunDetailResponse,
    attempt_fallback: WorkflowAttemptFallbackEvidenceResponse,
    checkpoint_budget: WorkflowCheckpointBudgetEvidenceResponse,
    provider_health: WorkflowProviderHealthEvidenceResponse,
) -> WorkflowRunActionGatesResponse:
    _validate_sources(
        detail=detail,
        attempt_fallback=attempt_fallback,
        checkpoint_budget=checkpoint_budget,
        provider_health=provider_health,
    )
    run = detail.run
    state_ref = f"workflow-run:{run.id}:state"
    attempt_ref = f"workflow-run:{run.id}:attempt-fallback-evidence"
    checkpoint_ref = f"workflow-run:{run.id}:checkpoint-budget-evidence"
    health_ref = f"workflow-run:{run.id}:provider-health-evidence"
    failed_step_ids = {
        item.id for item in detail.steps if item.status == WorkflowStepRunStatus.FAILED
    }

    attempts_by_step = defaultdict(list)
    for attempt in attempt_fallback.attempts:
        attempts_by_step[attempt.step_run_id].append(attempt)
    latest_failed_attempts = [
        max(attempts_by_step[step_id], key=lambda item: item.attempt_number)
        for step_id in failed_step_ids
        if attempts_by_step[step_id]
    ]

    if run.status != WorkflowRunStatus.HELD:
        retry_gate = _gate(
            action="retry",
            status="not_applicable",
            blockers=["run_state_not_retryable"],
            next_action="no_action_required",
            evidence_refs=[state_ref, attempt_ref],
        )
    elif not failed_step_ids:
        retry_gate = _gate(
            action="retry",
            status="blocked",
            blockers=["failed_step_unavailable"],
            next_action="inspect_retry_evidence",
            evidence_refs=[state_ref, attempt_ref],
        )
    elif len(latest_failed_attempts) != len(failed_step_ids):
        retry_gate = _gate(
            action="retry",
            status="blocked",
            blockers=["retry_evidence_unavailable"],
            next_action="inspect_retry_evidence",
            evidence_refs=[state_ref, attempt_ref],
        )
    elif any(item.status == "terminal_error" for item in latest_failed_attempts):
        retry_gate = _gate(
            action="retry",
            status="blocked",
            blockers=["terminal_failure_not_retryable"],
            next_action="inspect_retry_evidence",
            evidence_refs=[state_ref, attempt_ref],
        )
    else:
        retry_gate = _gate(
            action="retry",
            status="blocked",
            blockers=["retry_policy_snapshot_unavailable"],
            next_action="inspect_retry_evidence",
            evidence_refs=[state_ref, attempt_ref],
        )

    resumable_checkpoints = [
        item
        for item in checkpoint_budget.checkpoint_steps
        if not item.terminal and item.next_cursor is not None
    ]
    if run.status != WorkflowRunStatus.HELD:
        resume_gate = _gate(
            action="resume",
            status="not_applicable",
            blockers=["run_state_not_resumable"],
            next_action="no_action_required",
            evidence_refs=[state_ref, checkpoint_ref],
        )
    elif not checkpoint_budget.checkpoint_steps:
        resume_gate = _gate(
            action="resume",
            status="blocked",
            blockers=["resume_checkpoint_unavailable"],
            next_action="restore_checkpoint_budget",
            evidence_refs=[state_ref, checkpoint_ref],
        )
    elif not resumable_checkpoints:
        resume_gate = _gate(
            action="resume",
            status="blocked",
            blockers=["resume_checkpoint_terminal"],
            next_action="restore_checkpoint_budget",
            evidence_refs=[state_ref, checkpoint_ref],
        )
    elif checkpoint_budget.budget_status == "not_configured":
        resume_gate = _gate(
            action="resume",
            status="blocked",
            blockers=["budget_account_unavailable"],
            next_action="restore_checkpoint_budget",
            evidence_refs=[state_ref, checkpoint_ref],
        )
    elif checkpoint_budget.budget_status == "held":
        resume_gate = _gate(
            action="resume",
            status="blocked",
            blockers=["budget_limit_exceeded"],
            next_action="restore_checkpoint_budget",
            evidence_refs=[state_ref, checkpoint_ref],
        )
    else:
        resume_gate = _gate(
            action="resume",
            status="ready_for_review",
            blockers=[],
            next_action="review_resume_request",
            evidence_refs=[state_ref, checkpoint_ref],
        )

    if run.status in {WorkflowRunStatus.RUNNING, WorkflowRunStatus.HELD}:
        cancel_gate = _gate(
            action="cancel",
            status="ready_for_review",
            blockers=[],
            next_action="review_cancel_request",
            evidence_refs=[state_ref],
        )
    else:
        cancel_gate = _gate(
            action="cancel",
            status="not_applicable",
            blockers=["run_state_not_cancellable"],
            next_action="no_action_required",
            evidence_refs=[state_ref],
        )

    if run.status != WorkflowRunStatus.HELD or checkpoint_budget.budget_status != "held":
        budget_override_gate = _gate(
            action="budget_override",
            status="not_applicable",
            blockers=["budget_not_held"],
            next_action="no_action_required",
            evidence_refs=[state_ref, checkpoint_ref],
        )
    else:
        budget_override_gate = _gate(
            action="budget_override",
            status="blocked",
            blockers=["owner_approval_receipt_unavailable"],
            next_action="request_budget_override_approval",
            evidence_refs=[state_ref, checkpoint_ref],
        )

    failed_decisions = [
        item for item in attempt_fallback.fallback_decisions if item.step_run_id in failed_step_ids
    ]
    if run.status != WorkflowRunStatus.HELD:
        route_switch_gate = _gate(
            action="route_switch",
            status="not_applicable",
            blockers=["run_state_not_switchable"],
            next_action="no_action_required",
            evidence_refs=[state_ref, attempt_ref, health_ref],
        )
    elif not failed_decisions:
        route_switch_gate = _gate(
            action="route_switch",
            status="blocked",
            blockers=["fallback_decision_unavailable"],
            next_action="resolve_fallback_gates",
            evidence_refs=[state_ref, attempt_ref, health_ref],
        )
    elif any(item.outcome != "eligible" for item in failed_decisions):
        route_switch_gate = _gate(
            action="route_switch",
            status="blocked",
            blockers=["fallback_gate_blocked"],
            next_action="resolve_fallback_gates",
            evidence_refs=[state_ref, attempt_ref, health_ref],
        )
    elif not all(
        any(
            step.step_run_id == decision.step_run_id
            and step.route_feedback is not None
            and step.route_feedback_match == "ordered_candidate_match"
            for step in provider_health.steps
        )
        for decision in failed_decisions
    ):
        route_switch_gate = _gate(
            action="route_switch",
            status="blocked",
            blockers=["route_feedback_unavailable"],
            next_action="resolve_fallback_gates",
            evidence_refs=[state_ref, attempt_ref, health_ref],
        )
    else:
        route_switch_gate = _gate(
            action="route_switch",
            status="ready_for_review",
            blockers=[],
            next_action="review_route_switch",
            evidence_refs=[state_ref, attempt_ref, health_ref],
        )

    gates = [
        retry_gate,
        resume_gate,
        cancel_gate,
        budget_override_gate,
        route_switch_gate,
    ]
    return WorkflowRunActionGatesResponse(
        workspace_id=run.workspace_id,
        project_id=run.project_id,
        workflow_plan_id=run.workflow_plan_id,
        workflow_version_id=run.workflow_version_id,
        workflow_run_id=run.id,
        run_status=run.status,
        gates=gates,
        ready_for_review_total=sum(
            item.precondition_status == "ready_for_review" for item in gates
        ),
        blocked_total=sum(item.precondition_status == "blocked" for item in gates),
        not_applicable_total=sum(item.precondition_status == "not_applicable" for item in gates),
    )


__all__ = ["build_workflow_run_action_gates"]
