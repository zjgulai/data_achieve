from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, StringConstraints, model_validator

from data_intelligence_hub.schemas.workflow_execution import (
    Sha256Digest,
    WorkflowExecutionContract,
    WorkflowFixtureBoundary,
)

ProviderHealthOutcome = Literal[
    "succeeded",
    "timeout",
    "rate_limited",
    "transient_error",
    "terminal_error",
]
ProviderHealthStatus = Literal["unknown", "healthy", "degraded", "unhealthy"]
ProviderHealthReference = Annotated[
    str,
    StringConstraints(min_length=1, max_length=500),
]
ProviderHealthIdentifier = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=200,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$",
    ),
]


def _require_unique(values: list[str], *, code: str) -> list[str]:
    if len(values) != len(set(values)):
        raise ValueError(code)
    return values


class ProviderHealthObservation(WorkflowExecutionContract):
    observation_id: ProviderHealthIdentifier
    observed_at: datetime
    outcome: ProviderHealthOutcome
    latency_ms: int = Field(ge=0, le=3_600_000)
    evidence_refs: list[ProviderHealthReference] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_observation(self) -> Self:
        _require_unique(
            self.evidence_refs,
            code="provider_health_observation_evidence_duplicate",
        )
        return self


class ProviderHealthAggregationPolicy(WorkflowExecutionContract):
    min_sample_size: int = Field(default=3, ge=1, le=10_000)
    degraded_success_rate_bps: int = Field(default=9_500, ge=0, le=10_000)
    unhealthy_success_rate_bps: int = Field(default=8_000, ge=0, le=10_000)
    degraded_p95_latency_ms: int = Field(default=2_000, ge=1, le=3_600_000)
    unhealthy_p95_latency_ms: int = Field(default=5_000, ge=1, le=3_600_000)
    routing_ttl_hours: int = Field(default=24, ge=1, le=168)
    evidence_retention_days: int = Field(default=90, ge=1, le=365)

    @model_validator(mode="after")
    def validate_thresholds(self) -> Self:
        if self.unhealthy_success_rate_bps > self.degraded_success_rate_bps:
            raise ValueError("provider_health_success_threshold_order_invalid")
        if self.unhealthy_p95_latency_ms < self.degraded_p95_latency_ms:
            raise ValueError("provider_health_latency_threshold_order_invalid")
        if self.evidence_retention_days * 24 <= self.routing_ttl_hours:
            raise ValueError("provider_health_retention_window_invalid")
        return self


class ProviderHealthSnapshotRequest(WorkflowExecutionContract):
    workspace_id: UUID
    project_id: UUID
    platform_id: ProviderHealthIdentifier
    implementation_id: ProviderHealthIdentifier
    resource_type: ProviderHealthIdentifier
    operation: ProviderHealthIdentifier
    window_started_at: datetime
    window_ended_at: datetime
    observations: list[ProviderHealthObservation] = Field(min_length=1, max_length=10_000)
    evidence_refs: list[ProviderHealthReference] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        if self.window_ended_at <= self.window_started_at:
            raise ValueError("provider_health_window_invalid")
        observation_ids = [item.observation_id for item in self.observations]
        _require_unique(
            observation_ids,
            code="provider_health_observation_id_duplicate",
        )
        for observation in self.observations:
            if not self.window_started_at <= observation.observed_at <= self.window_ended_at:
                raise ValueError("provider_health_observation_outside_window")
        _require_unique(
            self.evidence_refs,
            code="provider_health_snapshot_evidence_duplicate",
        )
        return self


class ProviderHealthSnapshotResponse(WorkflowFixtureBoundary):
    id: UUID
    workspace_id: UUID
    project_id: UUID
    contract_version: Literal["provider_health_snapshot.v1"]
    scope_key: Sha256Digest
    aggregation_key: Sha256Digest
    snapshot_version: int = Field(ge=1)
    platform_id: ProviderHealthIdentifier
    implementation_id: ProviderHealthIdentifier
    resource_type: ProviderHealthIdentifier
    operation: ProviderHealthIdentifier
    window_started_at: datetime
    window_ended_at: datetime
    evaluated_at: datetime
    status: ProviderHealthStatus
    sample_count: int = Field(ge=1)
    success_count: int = Field(ge=0)
    timeout_count: int = Field(ge=0)
    rate_limited_count: int = Field(ge=0)
    transient_error_count: int = Field(ge=0)
    terminal_error_count: int = Field(ge=0)
    success_rate_bps: int = Field(ge=0, le=10_000)
    p95_latency_ms: int = Field(ge=0, le=3_600_000)
    reason_codes: list[ProviderHealthReference] = Field(min_length=1, max_length=64)
    policy_snapshot: dict[str, int]
    observation_manifest: list[dict[str, object]] = Field(min_length=1)
    evidence_refs: list[ProviderHealthReference] = Field(min_length=1, max_length=512)
    previous_snapshot_digest: Sha256Digest | None = None
    snapshot_digest: Sha256Digest
    routing_valid_until: datetime
    evidence_retain_until: datetime
    health_probe_attempted: Literal[False] = False

    @model_validator(mode="after")
    def validate_counts_and_retention(self) -> Self:
        if (
            self.success_count
            + self.timeout_count
            + self.rate_limited_count
            + self.transient_error_count
            + self.terminal_error_count
            != self.sample_count
        ):
            raise ValueError("provider_health_snapshot_counts_invalid")
        if not self.evaluated_at < self.routing_valid_until < self.evidence_retain_until:
            raise ValueError("provider_health_snapshot_retention_invalid")
        _require_unique(
            self.reason_codes,
            code="provider_health_snapshot_reason_duplicate",
        )
        _require_unique(
            self.evidence_refs,
            code="provider_health_snapshot_evidence_duplicate",
        )
        return self


class ProviderHealthSnapshotResult(WorkflowFixtureBoundary):
    snapshot: ProviderHealthSnapshotResponse
    snapshot_written: bool
    snapshot_replay: bool


class ProviderHealthRouteCandidate(WorkflowExecutionContract):
    implementation_id: ProviderHealthIdentifier
    baseline_score_bps: int = Field(ge=0, le=10_000)
    evidence_refs: list[ProviderHealthReference] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_candidate(self) -> Self:
        _require_unique(
            self.evidence_refs,
            code="provider_health_candidate_evidence_duplicate",
        )
        return self


class ProviderHealthRoutingPolicy(WorkflowExecutionContract):
    degraded_penalty_bps: int = Field(default=1_000, ge=0, le=10_000)
    unhealthy_penalty_bps: int = Field(default=5_000, ge=0, le=10_000)
    feedback_retention_days: int = Field(default=180, ge=1, le=730)

    @model_validator(mode="after")
    def validate_penalties(self) -> Self:
        if self.unhealthy_penalty_bps < self.degraded_penalty_bps:
            raise ValueError("provider_health_penalty_order_invalid")
        return self


class ProviderHealthRouteFeedbackRequest(WorkflowExecutionContract):
    workspace_id: UUID
    project_id: UUID
    route_key: ProviderHealthReference
    platform_id: ProviderHealthIdentifier
    resource_type: ProviderHealthIdentifier
    operation: ProviderHealthIdentifier
    candidates: list[ProviderHealthRouteCandidate] = Field(min_length=2, max_length=25)
    evidence_refs: list[ProviderHealthReference] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_candidates(self) -> Self:
        implementation_ids = [item.implementation_id for item in self.candidates]
        _require_unique(
            implementation_ids,
            code="provider_health_route_candidate_duplicate",
        )
        _require_unique(
            self.evidence_refs,
            code="provider_health_feedback_evidence_duplicate",
        )
        return self


class ProviderHealthRouteFeedbackResponse(WorkflowFixtureBoundary):
    id: UUID
    workspace_id: UUID
    project_id: UUID
    contract_version: Literal["provider_health_route_feedback.v1"]
    route_key: ProviderHealthReference
    feedback_key: Sha256Digest
    feedback_version: int = Field(ge=1)
    platform_id: ProviderHealthIdentifier
    resource_type: ProviderHealthIdentifier
    operation: ProviderHealthIdentifier
    original_candidate_order: list[ProviderHealthIdentifier] = Field(min_length=2)
    adjusted_candidate_order: list[ProviderHealthIdentifier] = Field(min_length=2)
    candidate_score_manifest: list[dict[str, object]] = Field(min_length=2)
    source_snapshot_manifest: list[dict[str, object]] = Field(min_length=2)
    ranking_changed: bool
    reason_codes: list[ProviderHealthReference] = Field(min_length=1, max_length=128)
    evidence_refs: list[ProviderHealthReference] = Field(min_length=1, max_length=512)
    previous_feedback_digest: Sha256Digest | None = None
    feedback_digest: Sha256Digest
    evaluated_at: datetime
    evidence_retain_until: datetime
    health_probe_attempted: Literal[False] = False
    catalog_mutation_applied: Literal[False] = False
    automatic_route_switch_executed: Literal[False] = False

    @model_validator(mode="after")
    def validate_feedback(self) -> Self:
        if set(self.original_candidate_order) != set(self.adjusted_candidate_order):
            raise ValueError("provider_health_feedback_candidate_set_invalid")
        if self.ranking_changed != (self.original_candidate_order != self.adjusted_candidate_order):
            raise ValueError("provider_health_feedback_ranking_state_invalid")
        if self.evidence_retain_until <= self.evaluated_at:
            raise ValueError("provider_health_feedback_retention_invalid")
        _require_unique(
            self.reason_codes,
            code="provider_health_feedback_reason_duplicate",
        )
        _require_unique(
            self.evidence_refs,
            code="provider_health_feedback_evidence_duplicate",
        )
        return self


class ProviderHealthRouteFeedbackResult(WorkflowFixtureBoundary):
    feedback: ProviderHealthRouteFeedbackResponse
    feedback_written: bool
    feedback_replay: bool


__all__ = [
    "ProviderHealthAggregationPolicy",
    "ProviderHealthObservation",
    "ProviderHealthOutcome",
    "ProviderHealthRouteCandidate",
    "ProviderHealthRouteFeedbackRequest",
    "ProviderHealthRouteFeedbackResponse",
    "ProviderHealthRouteFeedbackResult",
    "ProviderHealthRoutingPolicy",
    "ProviderHealthSnapshotRequest",
    "ProviderHealthSnapshotResponse",
    "ProviderHealthSnapshotResult",
    "ProviderHealthStatus",
]
