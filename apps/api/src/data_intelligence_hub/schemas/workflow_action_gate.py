from __future__ import annotations

from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from data_intelligence_hub.schemas.workflow_execution import (
    WorkflowExecutionContract,
    WorkflowFixtureReadBoundary,
    WorkflowRunStatus,
)

WorkflowRunAction = Literal[
    "retry",
    "resume",
    "cancel",
    "budget_override",
    "route_switch",
]
WorkflowRunActionPreconditionStatus = Literal[
    "ready_for_review",
    "blocked",
    "not_applicable",
]
WorkflowRunActionPreconditionBlockerCode = Literal[
    "run_state_not_retryable",
    "failed_step_unavailable",
    "retry_evidence_unavailable",
    "terminal_failure_not_retryable",
    "retry_policy_snapshot_unavailable",
    "run_state_not_resumable",
    "resume_checkpoint_unavailable",
    "resume_checkpoint_terminal",
    "budget_account_unavailable",
    "budget_limit_exceeded",
    "run_state_not_cancellable",
    "budget_not_held",
    "owner_approval_receipt_unavailable",
    "run_state_not_switchable",
    "fallback_decision_unavailable",
    "fallback_gate_blocked",
    "route_feedback_unavailable",
]
WorkflowRunActionAvailabilityBlockerCode = Literal[
    "mutation_endpoint_unavailable",
    "durable_action_audit_unavailable",
]
WorkflowRunActionNextActionCode = Literal[
    "no_action_required",
    "inspect_retry_evidence",
    "restore_checkpoint_budget",
    "review_resume_request",
    "review_cancel_request",
    "request_budget_override_approval",
    "resolve_fallback_gates",
    "review_route_switch",
]

WORKFLOW_RUN_ACTION_ORDER: tuple[WorkflowRunAction, ...] = (
    "retry",
    "resume",
    "cancel",
    "budget_override",
    "route_switch",
)
WORKFLOW_RUN_ACTION_AVAILABILITY_BLOCKERS: tuple[
    WorkflowRunActionAvailabilityBlockerCode,
    ...,
] = (
    "mutation_endpoint_unavailable",
    "durable_action_audit_unavailable",
)


class WorkflowRunActionGateEvidenceResponse(WorkflowExecutionContract):
    action: WorkflowRunAction
    precondition_status: WorkflowRunActionPreconditionStatus
    action_available: Literal[False] = False
    precondition_blocker_codes: list[WorkflowRunActionPreconditionBlockerCode] = Field(
        max_length=16
    )
    availability_blocker_codes: list[WorkflowRunActionAvailabilityBlockerCode] = Field(
        min_length=2,
        max_length=2,
    )
    next_action_code: WorkflowRunActionNextActionCode
    evidence_refs: list[str] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_action_gate(self) -> Self:
        if len(self.precondition_blocker_codes) != len(set(self.precondition_blocker_codes)):
            raise ValueError("workflow_run_action_precondition_blocker_duplicate")
        if tuple(self.availability_blocker_codes) != (WORKFLOW_RUN_ACTION_AVAILABILITY_BLOCKERS):
            raise ValueError("workflow_run_action_availability_blockers_invalid")
        if len(self.evidence_refs) != len(set(self.evidence_refs)) or any(
            not item for item in self.evidence_refs
        ):
            raise ValueError("workflow_run_action_evidence_refs_invalid")
        if self.precondition_status == "ready_for_review":
            if self.precondition_blocker_codes:
                raise ValueError("workflow_run_action_ready_blockers_invalid")
        elif not self.precondition_blocker_codes:
            raise ValueError("workflow_run_action_blockers_required")
        return self


class WorkflowRunActionGatesResponse(WorkflowFixtureReadBoundary):
    schema_version: Literal["workflow_run_action_gates.v1"] = "workflow_run_action_gates.v1"
    workspace_id: UUID
    project_id: UUID
    workflow_plan_id: UUID
    workflow_version_id: UUID
    workflow_run_id: UUID
    run_status: WorkflowRunStatus
    gates: list[WorkflowRunActionGateEvidenceResponse] = Field(
        min_length=5,
        max_length=5,
    )
    ready_for_review_total: int = Field(ge=0, le=5)
    blocked_total: int = Field(ge=0, le=5)
    not_applicable_total: int = Field(ge=0, le=5)
    available_action_total: Literal[0] = 0
    mutation_endpoints_available: Literal[False] = False
    durable_action_audit_available: Literal[False] = False
    action_mutation_executed: Literal[False] = False

    @model_validator(mode="after")
    def validate_action_gates(self) -> Self:
        if tuple(item.action for item in self.gates) != WORKFLOW_RUN_ACTION_ORDER:
            raise ValueError("workflow_run_action_gate_order_invalid")
        expected = {
            "ready_for_review": self.ready_for_review_total,
            "blocked": self.blocked_total,
            "not_applicable": self.not_applicable_total,
        }
        for status, total in expected.items():
            if total != sum(item.precondition_status == status for item in self.gates):
                raise ValueError("workflow_run_action_gate_total_invalid")
        if any(item.action_available for item in self.gates):
            raise ValueError("workflow_run_action_available_invalid")
        return self


__all__ = [
    "WORKFLOW_RUN_ACTION_AVAILABILITY_BLOCKERS",
    "WORKFLOW_RUN_ACTION_ORDER",
    "WorkflowRunAction",
    "WorkflowRunActionAvailabilityBlockerCode",
    "WorkflowRunActionGateEvidenceResponse",
    "WorkflowRunActionGatesResponse",
    "WorkflowRunActionNextActionCode",
    "WorkflowRunActionPreconditionBlockerCode",
    "WorkflowRunActionPreconditionStatus",
]
