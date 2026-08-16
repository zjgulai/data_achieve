from __future__ import annotations

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from data_intelligence_hub.schemas.provider_health import (
    ProviderHealthRouteFeedbackResponse,
    ProviderHealthSnapshotResponse,
    ProviderHealthStatus,
)
from data_intelligence_hub.schemas.workflow_execution import (
    WorkflowExecutionContract,
    WorkflowFixtureReadBoundary,
)

WorkflowProviderHealthRoutingState = Literal[
    "not_observed",
    "routing_active",
    "routing_expired",
]
WorkflowProviderHealthStatus = Literal[
    "not_observed",
    "unknown",
    "healthy",
    "degraded",
    "unhealthy",
]


class WorkflowProviderHealthCandidateEvidenceResponse(WorkflowExecutionContract):
    implementation_id: str = Field(min_length=1, max_length=500)
    selected_for_run: bool
    health_status: WorkflowProviderHealthStatus
    routing_state: WorkflowProviderHealthRoutingState
    snapshot: ProviderHealthSnapshotResponse | None = None

    @model_validator(mode="after")
    def validate_candidate_evidence(self) -> Self:
        if self.snapshot is None:
            if self.health_status != "not_observed" or self.routing_state != "not_observed":
                raise ValueError("workflow_provider_health_empty_candidate_invalid")
            return self
        if self.snapshot.implementation_id != self.implementation_id:
            raise ValueError("workflow_provider_health_candidate_identity_invalid")
        if self.health_status != self.snapshot.status:
            raise ValueError("workflow_provider_health_candidate_status_invalid")
        if self.routing_state == "not_observed":
            raise ValueError("workflow_provider_health_candidate_routing_state_invalid")
        return self


class WorkflowProviderHealthStepEvidenceResponse(WorkflowExecutionContract):
    step_run_id: UUID
    step_ref: str = Field(min_length=1, max_length=500)
    requirement_ref: str = Field(min_length=1, max_length=500)
    platform_id: str = Field(min_length=1, max_length=200)
    resource_type: str = Field(min_length=1, max_length=200)
    operation: str = Field(min_length=1, max_length=200)
    selected_implementation_id: str = Field(min_length=1, max_length=500)
    candidates: list[WorkflowProviderHealthCandidateEvidenceResponse] = Field(min_length=1)
    route_feedback: ProviderHealthRouteFeedbackResponse | None = None
    route_feedback_match: Literal["not_available", "ordered_candidate_match"]
    route_decision_applied_to_run: Literal[False] = False

    @model_validator(mode="after")
    def validate_step_evidence(self) -> Self:
        candidate_ids = [item.implementation_id for item in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("workflow_provider_health_candidate_duplicate")
        selected = [item for item in self.candidates if item.selected_for_run]
        if (
            len(selected) != 1
            or selected[0].implementation_id != self.selected_implementation_id
            or candidate_ids[0] != self.selected_implementation_id
        ):
            raise ValueError("workflow_provider_health_selected_candidate_invalid")
        if self.route_feedback is None:
            if self.route_feedback_match != "not_available":
                raise ValueError("workflow_provider_health_feedback_state_invalid")
            return self
        feedback = self.route_feedback
        if (
            self.route_feedback_match != "ordered_candidate_match"
            or feedback.platform_id != self.platform_id
            or feedback.resource_type != self.resource_type
            or feedback.operation != self.operation
            or feedback.original_candidate_order != candidate_ids
            or set(feedback.adjusted_candidate_order) != set(candidate_ids)
            or feedback.health_probe_attempted
            or feedback.catalog_mutation_applied
            or feedback.automatic_route_switch_executed
        ):
            raise ValueError("workflow_provider_health_feedback_identity_invalid")
        return self


class WorkflowProviderHealthEvidenceResponse(WorkflowFixtureReadBoundary):
    schema_version: Literal["workflow_provider_health_evidence.v1"] = (
        "workflow_provider_health_evidence.v1"
    )
    workspace_id: UUID
    project_id: UUID
    workflow_run_id: UUID
    read_at: datetime
    steps: list[WorkflowProviderHealthStepEvidenceResponse]
    step_total: int = Field(ge=0)
    observed_candidate_total: int = Field(ge=0)
    routing_active_candidate_total: int = Field(ge=0)
    attention_candidate_total: int = Field(ge=0)
    route_feedback_total: int = Field(ge=0)
    health_probe_attempted: Literal[False] = False
    catalog_mutation_applied: Literal[False] = False
    automatic_route_switch_executed: Literal[False] = False
    route_switch_action_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_provider_health_evidence(self) -> Self:
        if self.step_total != len(self.steps):
            raise ValueError("workflow_provider_health_step_total_invalid")
        if len({item.step_run_id for item in self.steps}) != len(self.steps):
            raise ValueError("workflow_provider_health_step_duplicate")
        candidates = [candidate for step in self.steps for candidate in step.candidates]
        if self.observed_candidate_total != sum(
            candidate.snapshot is not None for candidate in candidates
        ):
            raise ValueError("workflow_provider_health_observed_total_invalid")
        if self.routing_active_candidate_total != sum(
            candidate.routing_state == "routing_active" for candidate in candidates
        ):
            raise ValueError("workflow_provider_health_active_total_invalid")
        attention_statuses: set[ProviderHealthStatus] = {"degraded", "unhealthy"}
        if self.attention_candidate_total != sum(
            candidate.health_status in attention_statuses for candidate in candidates
        ):
            raise ValueError("workflow_provider_health_attention_total_invalid")
        if self.route_feedback_total != sum(step.route_feedback is not None for step in self.steps):
            raise ValueError("workflow_provider_health_feedback_total_invalid")
        return self


__all__ = [
    "WorkflowProviderHealthCandidateEvidenceResponse",
    "WorkflowProviderHealthEvidenceResponse",
    "WorkflowProviderHealthRoutingState",
    "WorkflowProviderHealthStatus",
    "WorkflowProviderHealthStepEvidenceResponse",
]
