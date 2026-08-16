from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from data_intelligence_hub.schemas.workflow_action_gate import (
    WorkflowRunActionGatesResponse,
)
from data_intelligence_hub.schemas.workflow_attempt_fallback import (
    WorkflowAttemptFallbackEvidenceResponse,
    WorkflowFallbackDecisionEvidenceResponse,
    WorkflowStepAttemptEvidenceResponse,
)
from data_intelligence_hub.schemas.workflow_checkpoint_budget import (
    WorkflowCheckpointBudgetEvidenceResponse,
    WorkflowCheckpointStepEvidenceResponse,
)
from data_intelligence_hub.schemas.workflow_execution import (
    WorkflowRunDetailResponse,
    WorkflowRunResponse,
    WorkflowRunStatus,
    WorkflowStepRunResponse,
    WorkflowStepRunStatus,
)
from data_intelligence_hub.schemas.workflow_provider_health import (
    WorkflowProviderHealthEvidenceResponse,
    WorkflowProviderHealthStepEvidenceResponse,
)
from data_intelligence_hub.services.workflow_execution.action_gate import (
    build_workflow_run_action_gates,
)

WORKSPACE_ID = uuid.uuid4()
PROJECT_ID = uuid.uuid4()
PLAN_ID = uuid.uuid4()
VERSION_ID = uuid.uuid4()
RUN_ID = uuid.uuid4()
STEP_ID = uuid.uuid4()


def _sources(
    *,
    run_status: WorkflowRunStatus,
    step_status: WorkflowStepRunStatus,
    attempt_status: str | None,
    fallback_outcome: str | None,
    budget_status: str,
    checkpoint_terminal: bool | None,
    route_feedback_available: bool,
) -> tuple[
    WorkflowRunDetailResponse,
    WorkflowAttemptFallbackEvidenceResponse,
    WorkflowCheckpointBudgetEvidenceResponse,
    WorkflowProviderHealthEvidenceResponse,
]:
    detail = WorkflowRunDetailResponse.model_construct(
        run=WorkflowRunResponse.model_construct(
            id=RUN_ID,
            workspace_id=WORKSPACE_ID,
            project_id=PROJECT_ID,
            workflow_plan_id=PLAN_ID,
            workflow_version_id=VERSION_ID,
            status=run_status,
        ),
        steps=[
            WorkflowStepRunResponse.model_construct(
                id=STEP_ID,
                status=step_status,
            )
        ],
    )
    attempts = (
        [
            WorkflowStepAttemptEvidenceResponse.model_construct(
                step_run_id=STEP_ID,
                attempt_number=1,
                status=attempt_status,
            )
        ]
        if attempt_status is not None
        else []
    )
    decisions = (
        [
            WorkflowFallbackDecisionEvidenceResponse.model_construct(
                step_run_id=STEP_ID,
                outcome=fallback_outcome,
            )
        ]
        if fallback_outcome is not None
        else []
    )
    attempt_fallback = WorkflowAttemptFallbackEvidenceResponse.model_construct(
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_run_id=RUN_ID,
        attempts=attempts,
        fallback_decisions=decisions,
    )
    checkpoint_steps = (
        [
            WorkflowCheckpointStepEvidenceResponse.model_construct(
                step_run_id=STEP_ID,
                terminal=checkpoint_terminal,
                next_cursor=None if checkpoint_terminal else "cursor-next",
            )
        ]
        if checkpoint_terminal is not None
        else []
    )
    checkpoint_budget = WorkflowCheckpointBudgetEvidenceResponse.model_construct(
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_plan_id=PLAN_ID,
        workflow_version_id=VERSION_ID,
        workflow_run_id=RUN_ID,
        checkpoint_steps=checkpoint_steps,
        budget_status=budget_status,
    )
    provider_health = WorkflowProviderHealthEvidenceResponse.model_construct(
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_run_id=RUN_ID,
        steps=[
            WorkflowProviderHealthStepEvidenceResponse.model_construct(
                step_run_id=STEP_ID,
                route_feedback=object() if route_feedback_available else None,
                route_feedback_match=(
                    "ordered_candidate_match" if route_feedback_available else "not_available"
                ),
            )
        ],
    )
    return detail, attempt_fallback, checkpoint_budget, provider_health


def test_held_run_action_gates_fail_closed_without_mutation_surface() -> None:
    detail, attempts, checkpoint, health = _sources(
        run_status=WorkflowRunStatus.HELD,
        step_status=WorkflowStepRunStatus.FAILED,
        attempt_status="terminal_error",
        fallback_outcome="blocked",
        budget_status="held",
        checkpoint_terminal=False,
        route_feedback_available=False,
    )

    result = build_workflow_run_action_gates(
        detail=detail,
        attempt_fallback=attempts,
        checkpoint_budget=checkpoint,
        provider_health=health,
    )

    assert [item.action for item in result.gates] == [
        "retry",
        "resume",
        "cancel",
        "budget_override",
        "route_switch",
    ]
    assert result.ready_for_review_total == 1
    assert result.blocked_total == 4
    assert result.not_applicable_total == 0
    assert result.available_action_total == 0
    assert result.mutation_endpoints_available is False
    assert result.durable_action_audit_available is False
    assert result.action_mutation_executed is False
    assert result.gates[0].precondition_blocker_codes == ["terminal_failure_not_retryable"]
    assert result.gates[1].precondition_blocker_codes == ["budget_limit_exceeded"]
    assert result.gates[2].precondition_status == "ready_for_review"
    assert result.gates[3].precondition_blocker_codes == ["owner_approval_receipt_unavailable"]
    assert result.gates[4].precondition_blocker_codes == ["fallback_gate_blocked"]
    assert all(item.action_available is False for item in result.gates)


def test_resumable_and_switchable_preconditions_still_require_review() -> None:
    detail, attempts, checkpoint, health = _sources(
        run_status=WorkflowRunStatus.HELD,
        step_status=WorkflowStepRunStatus.FAILED,
        attempt_status="retryable_error",
        fallback_outcome="eligible",
        budget_status="within_limit",
        checkpoint_terminal=False,
        route_feedback_available=True,
    )

    result = build_workflow_run_action_gates(
        detail=detail,
        attempt_fallback=attempts,
        checkpoint_budget=checkpoint,
        provider_health=health,
    )

    assert result.gates[0].precondition_blocker_codes == ["retry_policy_snapshot_unavailable"]
    assert result.gates[1].precondition_status == "ready_for_review"
    assert result.gates[2].precondition_status == "ready_for_review"
    assert result.gates[4].precondition_status == "ready_for_review"
    assert result.ready_for_review_total == 3
    assert result.available_action_total == 0


def test_terminal_run_actions_are_not_applicable() -> None:
    detail, attempts, checkpoint, health = _sources(
        run_status=WorkflowRunStatus.COMPLETED,
        step_status=WorkflowStepRunStatus.COMPLETED,
        attempt_status=None,
        fallback_outcome=None,
        budget_status="not_configured",
        checkpoint_terminal=None,
        route_feedback_available=False,
    )

    result = build_workflow_run_action_gates(
        detail=detail,
        attempt_fallback=attempts,
        checkpoint_budget=checkpoint,
        provider_health=health,
    )

    assert result.ready_for_review_total == 0
    assert result.blocked_total == 0
    assert result.not_applicable_total == 5
    assert all(item.precondition_status == "not_applicable" for item in result.gates)


def test_action_gate_schema_rejects_reordered_or_available_actions() -> None:
    detail, attempts, checkpoint, health = _sources(
        run_status=WorkflowRunStatus.COMPLETED,
        step_status=WorkflowStepRunStatus.COMPLETED,
        attempt_status=None,
        fallback_outcome=None,
        budget_status="not_configured",
        checkpoint_terminal=None,
        route_feedback_available=False,
    )
    payload = build_workflow_run_action_gates(
        detail=detail,
        attempt_fallback=attempts,
        checkpoint_budget=checkpoint,
        provider_health=health,
    ).model_dump(mode="json")

    reordered = {**payload, "gates": list(reversed(payload["gates"]))}
    with pytest.raises(ValidationError, match="workflow_run_action_gate_order_invalid"):
        WorkflowRunActionGatesResponse.model_validate(reordered)

    available = payload.copy()
    available["gates"] = [dict(item) for item in payload["gates"]]
    available["gates"][0]["action_available"] = True
    with pytest.raises(ValidationError):
        WorkflowRunActionGatesResponse.model_validate(available)
