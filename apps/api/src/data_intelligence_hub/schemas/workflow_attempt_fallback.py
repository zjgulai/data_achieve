from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from data_intelligence_hub.schemas.workflow_execution import (
    Sha256Digest,
    WorkflowExecutionContract,
    WorkflowFixtureReadBoundary,
)

WorkflowStepAttemptStatus = Literal[
    "succeeded",
    "retryable_error",
    "timeout",
    "terminal_error",
]
FallbackGateName = Literal[
    "trigger",
    "policy",
    "credential",
    "budget",
    "fields",
    "evidence",
    "approval",
]
FallbackApprovalStatus = Literal[
    "not_required",
    "approved",
    "pending",
    "rejected",
    "unavailable",
]
FallbackEvidenceStatus = Literal["verified", "unavailable"]

_FALLBACK_GATE_ORDER: tuple[FallbackGateName, ...] = (
    "trigger",
    "policy",
    "credential",
    "budget",
    "fields",
    "evidence",
    "approval",
)


class WorkflowStepAttemptEvidenceResponse(WorkflowExecutionContract):
    id: UUID
    workspace_id: UUID
    project_id: UUID
    workflow_run_id: UUID
    step_run_id: UUID
    retry_generation: int = Field(default=0, ge=0)
    attempt_number: int = Field(ge=1, le=4)
    attempt_key_hash: Sha256Digest
    status: WorkflowStepAttemptStatus
    error_code: str | None = Field(default=None, min_length=1, max_length=100)
    backoff_ms: int = Field(ge=0, le=60_000)
    provider_call_attempted: Literal[False] = False
    credential_read_attempted: Literal[False] = False
    actor_run: Literal[False] = False
    browser_run: Literal[False] = False
    llm_call: Literal[False] = False
    production_write_allowed: Literal[False] = False
    started_at: datetime
    finished_at: datetime
    created_at: datetime

    @model_validator(mode="after")
    def validate_outcome_and_time(self) -> Self:
        if self.status == "succeeded":
            if self.error_code is not None or self.backoff_ms != 0:
                raise ValueError("workflow_step_attempt_outcome_invalid")
        elif self.error_code is None:
            raise ValueError("workflow_step_attempt_outcome_invalid")
        if self.finished_at < self.started_at:
            raise ValueError("workflow_step_attempt_time_order_invalid")
        return self


class WorkflowFallbackGateEvidenceResponse(WorkflowExecutionContract):
    gate: FallbackGateName
    status: Literal["passed", "blocked"]
    code: str = Field(min_length=1, max_length=100)
    evidence_refs: list[str] = Field(default_factory=list, max_length=128)

    @model_validator(mode="after")
    def validate_evidence_refs(self) -> Self:
        if len(self.evidence_refs) != len(set(self.evidence_refs)) or any(
            not item for item in self.evidence_refs
        ):
            raise ValueError("workflow_fallback_gate_evidence_invalid")
        return self


class WorkflowFallbackFieldDifferenceResponse(WorkflowExecutionContract):
    evidence_status: FallbackEvidenceStatus
    required_fields: list[str] = Field(default_factory=list, max_length=256)
    missing_required_fields: list[str] = Field(default_factory=list, max_length=256)
    primary_missing_optional_fields: list[str] = Field(
        default_factory=list,
        max_length=256,
    )
    fallback_missing_optional_fields: list[str] = Field(
        default_factory=list,
        max_length=256,
    )

    @model_validator(mode="after")
    def validate_field_evidence(self) -> Self:
        for values in (
            self.required_fields,
            self.missing_required_fields,
            self.primary_missing_optional_fields,
            self.fallback_missing_optional_fields,
        ):
            if len(values) != len(set(values)) or any(not item for item in values):
                raise ValueError("workflow_fallback_field_evidence_invalid")
        return self


class WorkflowFallbackCostEvidenceResponse(WorkflowExecutionContract):
    evidence_status: FallbackEvidenceStatus
    currency: Literal["USD"] = "USD"
    unit_cost_usd: Decimal | None = Field(default=None, ge=0)
    ceiling_usd: Decimal | None = Field(default=None, ge=0)
    within_ceiling: bool | None = None

    @model_validator(mode="after")
    def validate_cost_evidence(self) -> Self:
        if self.evidence_status == "unavailable" and self.within_ceiling is not None:
            raise ValueError("workflow_fallback_cost_evidence_invalid")
        if self.within_ceiling is not None and (
            self.unit_cost_usd is None or self.ceiling_usd is None
        ):
            raise ValueError("workflow_fallback_cost_evidence_invalid")
        return self


class WorkflowFallbackDecisionEvidenceResponse(WorkflowExecutionContract):
    id: UUID
    workspace_id: UUID
    project_id: UUID
    workflow_plan_id: UUID
    workflow_version_id: UUID
    workflow_run_id: UUID
    step_run_id: UUID
    created_by_user_id: UUID
    step_ref: str = Field(min_length=1, max_length=500)
    requirement_ref: str = Field(min_length=1, max_length=500)
    contract_version: Literal["workflow_fallback_gate_replay.v1"]
    decision_digest: Sha256Digest
    primary_failure_code: str = Field(min_length=1, max_length=100)
    primary_assertion_id: str = Field(min_length=1, max_length=500)
    primary_implementation_id: str = Field(min_length=1, max_length=500)
    fallback_assertion_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
    )
    fallback_implementation_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
    )
    outcome: Literal["eligible", "blocked"]
    gates: list[WorkflowFallbackGateEvidenceResponse] = Field(
        validation_alias="gate_snapshot",
        min_length=7,
        max_length=7,
    )
    field_difference: WorkflowFallbackFieldDifferenceResponse
    cost_snapshot: WorkflowFallbackCostEvidenceResponse
    evidence_refs: list[str] = Field(default_factory=list, max_length=128)
    approval_required: bool
    approval_status: FallbackApprovalStatus
    switch_executed: Literal[False] = False
    provider_call_attempted: Literal[False] = False
    credential_read_attempted: Literal[False] = False
    actor_run: Literal[False] = False
    browser_run: Literal[False] = False
    llm_call: Literal[False] = False
    production_write_allowed: Literal[False] = False
    created_at: datetime

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        if (self.fallback_assertion_id is None) != (self.fallback_implementation_id is None):
            raise ValueError("workflow_fallback_candidate_identity_invalid")
        if self.outcome == "eligible" and self.fallback_implementation_id is None:
            raise ValueError("workflow_fallback_candidate_identity_invalid")
        if tuple(item.gate for item in self.gates) != _FALLBACK_GATE_ORDER:
            raise ValueError("workflow_fallback_gate_order_invalid")
        all_passed = all(item.status == "passed" for item in self.gates)
        if (self.outcome == "eligible") != all_passed:
            raise ValueError("workflow_fallback_outcome_invalid")
        if self.approval_required == (self.approval_status == "not_required"):
            raise ValueError("workflow_fallback_approval_status_invalid")
        if len(self.evidence_refs) != len(set(self.evidence_refs)) or any(
            not item for item in self.evidence_refs
        ):
            raise ValueError("workflow_fallback_evidence_refs_invalid")
        return self


class WorkflowAttemptFallbackEvidenceResponse(WorkflowFixtureReadBoundary):
    schema_version: Literal["workflow_attempt_fallback_evidence.v1"] = (
        "workflow_attempt_fallback_evidence.v1"
    )
    workspace_id: UUID
    project_id: UUID
    workflow_run_id: UUID
    attempts: list[WorkflowStepAttemptEvidenceResponse]
    fallback_decisions: list[WorkflowFallbackDecisionEvidenceResponse]
    attempt_total: int = Field(ge=0)
    fallback_decision_total: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_evidence_ownership_and_counts(self) -> Self:
        if self.attempt_total != len(self.attempts):
            raise ValueError("workflow_step_attempt_total_invalid")
        if self.fallback_decision_total != len(self.fallback_decisions):
            raise ValueError("workflow_fallback_decision_total_invalid")
        if len({item.id for item in self.attempts}) != len(self.attempts):
            raise ValueError("workflow_step_attempt_duplicate")
        if len({item.id for item in self.fallback_decisions}) != len(self.fallback_decisions):
            raise ValueError("workflow_fallback_decision_duplicate")

        attempts_by_step_generation: dict[tuple[UUID, int], list[int]] = {}
        for attempt in self.attempts:
            if (
                attempt.workspace_id != self.workspace_id
                or attempt.project_id != self.project_id
                or attempt.workflow_run_id != self.workflow_run_id
            ):
                raise ValueError("workflow_step_attempt_owner_invalid")
            attempts_by_step_generation.setdefault(
                (attempt.step_run_id, attempt.retry_generation),
                [],
            ).append(attempt.attempt_number)
        for numbers in attempts_by_step_generation.values():
            if sorted(numbers) != list(range(1, len(numbers) + 1)):
                raise ValueError("workflow_step_attempt_sequence_invalid")

        decision_steps: set[UUID] = set()
        for decision in self.fallback_decisions:
            if (
                decision.workspace_id != self.workspace_id
                or decision.project_id != self.project_id
                or decision.workflow_run_id != self.workflow_run_id
            ):
                raise ValueError("workflow_fallback_decision_owner_invalid")
            if decision.step_run_id in decision_steps:
                raise ValueError("workflow_fallback_decision_step_duplicate")
            decision_steps.add(decision.step_run_id)
        return self


__all__ = [
    "FallbackApprovalStatus",
    "FallbackEvidenceStatus",
    "FallbackGateName",
    "WorkflowAttemptFallbackEvidenceResponse",
    "WorkflowFallbackCostEvidenceResponse",
    "WorkflowFallbackDecisionEvidenceResponse",
    "WorkflowFallbackFieldDifferenceResponse",
    "WorkflowFallbackGateEvidenceResponse",
    "WorkflowStepAttemptEvidenceResponse",
    "WorkflowStepAttemptStatus",
]
