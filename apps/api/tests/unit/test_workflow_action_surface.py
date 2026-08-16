from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

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
from data_intelligence_hub.services.workflow_execution.action_surface import (
    build_workflow_run_action_surface,
)

NOW = datetime(2026, 7, 27, 13, 0, tzinfo=UTC)
WORKSPACE_ID = uuid.uuid4()
PROJECT_ID = uuid.uuid4()
PLAN_ID = uuid.uuid4()
VERSION_ID = uuid.uuid4()
RUN_ID = uuid.uuid4()
STEP_ID = uuid.uuid4()


def _sources(
    run_status: WorkflowRunStatus,
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
                status=WorkflowStepRunStatus.FAILED,
            )
        ],
    )
    attempt_fallback = WorkflowAttemptFallbackEvidenceResponse.model_construct(
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_run_id=RUN_ID,
        attempts=[
            WorkflowStepAttemptEvidenceResponse.model_construct(
                step_run_id=STEP_ID,
                attempt_number=1,
                status="terminal_error",
            )
        ],
        fallback_decisions=[
            WorkflowFallbackDecisionEvidenceResponse.model_construct(
                step_run_id=STEP_ID,
                outcome="blocked",
            )
        ],
    )
    checkpoint_budget = WorkflowCheckpointBudgetEvidenceResponse.model_construct(
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_plan_id=PLAN_ID,
        workflow_version_id=VERSION_ID,
        workflow_run_id=RUN_ID,
        checkpoint_steps=[
            WorkflowCheckpointStepEvidenceResponse.model_construct(
                step_run_id=STEP_ID,
                terminal=False,
                next_cursor="cursor-next",
            )
        ],
        budget_status="held",
    )
    provider_health = WorkflowProviderHealthEvidenceResponse.model_construct(
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_run_id=RUN_ID,
        steps=[
            WorkflowProviderHealthStepEvidenceResponse.model_construct(
                step_run_id=STEP_ID,
                route_feedback=None,
                route_feedback_match="not_available",
            )
        ],
    )
    return detail, attempt_fallback, checkpoint_budget, provider_health


def test_v2_surface_exposes_only_exact_held_cancel_and_binds_command_evidence() -> None:
    detail, attempts, checkpoint, health = _sources(WorkflowRunStatus.HELD)

    surface = build_workflow_run_action_surface(
        detail=detail,
        attempt_fallback=attempts,
        checkpoint_budget=checkpoint,
        provider_health=health,
        action_context_version=3,
        evaluated_at=NOW,
    )

    assert surface.response.schema_version == "workflow_run_action_gates.v2"
    assert surface.response.action_context_version == 3
    assert [item.action for item in surface.response.gates] == [
        "retry",
        "resume",
        "cancel",
        "budget_override",
        "route_switch",
    ]
    assert [item.action for item in surface.response.gates if item.submission_available] == [
        "cancel"
    ]
    assert surface.response.available_action_total == 1
    assert surface.evidence.action_gate_digest == surface.response.action_gate_digest
    assert surface.evidence.evidence_digests == (surface.response.action_gate_digest,)
    assert surface.evidence.budget_held is True
    assert surface.evidence.provider_call is False
    assert surface.evidence.credential_read_attempted is False


def test_v2_surface_keeps_running_cancel_blocked_without_executor_ack() -> None:
    detail, attempts, checkpoint, health = _sources(WorkflowRunStatus.RUNNING)

    surface = build_workflow_run_action_surface(
        detail=detail,
        attempt_fallback=attempts,
        checkpoint_budget=checkpoint,
        provider_health=health,
        action_context_version=1,
        evaluated_at=NOW,
    )

    cancel = next(item for item in surface.response.gates if item.action == "cancel")
    assert cancel.submission_available is False
    assert cancel.precondition_status == "ready_for_review"
    assert cancel.precondition_blocker_codes == []
    assert cancel.availability_blocker_codes == ["workflow_action_executor_ack_unavailable"]
    assert surface.response.available_action_total == 0


def test_surface_digest_is_stable_across_read_time_but_expiry_moves() -> None:
    detail, attempts, checkpoint, health = _sources(WorkflowRunStatus.HELD)

    first = build_workflow_run_action_surface(
        detail=detail,
        attempt_fallback=attempts,
        checkpoint_budget=checkpoint,
        provider_health=health,
        action_context_version=1,
        evaluated_at=NOW,
    )
    second = build_workflow_run_action_surface(
        detail=detail,
        attempt_fallback=attempts,
        checkpoint_budget=checkpoint,
        provider_health=health,
        action_context_version=1,
        evaluated_at=NOW + timedelta(seconds=5),
    )

    assert first.response.action_gate_digest == second.response.action_gate_digest
    assert first.response.gates[2].expires_at < second.response.gates[2].expires_at
