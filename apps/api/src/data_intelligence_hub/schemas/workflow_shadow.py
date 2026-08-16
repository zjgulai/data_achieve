from __future__ import annotations

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from data_intelligence_hub.schemas.workflow_execution import (
    FixtureProfileId,
    Sha256Digest,
    WorkflowExecutionContract,
    WorkflowFixtureReadBoundary,
)

ShadowEquivalenceStatus = Literal["equivalent", "different"]
ShadowRoutingRecommendation = Literal[
    "eligible_for_governance_review",
    "keep_primary_investigate_shadow",
]


class WorkflowShadowDifferenceEvidence(WorkflowExecutionContract):
    sampled_record_keys: list[str] = Field(min_length=1, max_length=100)
    matched_record_keys: list[str] = Field(default_factory=list, max_length=100)
    mismatched_record_keys: list[str] = Field(default_factory=list, max_length=100)
    primary_only_record_keys: list[str] = Field(default_factory=list, max_length=100)
    shadow_only_record_keys: list[str] = Field(default_factory=list, max_length=100)
    missing_required_fields: list[str] = Field(default_factory=list, max_length=256)
    primary_only_fields: list[str] = Field(default_factory=list, max_length=256)
    shadow_only_fields: list[str] = Field(default_factory=list, max_length=256)

    @model_validator(mode="after")
    def validate_sample_partition(self) -> Self:
        groups = (
            self.matched_record_keys,
            self.mismatched_record_keys,
            self.primary_only_record_keys,
            self.shadow_only_record_keys,
        )
        flattened = [item for group in groups for item in group]
        if len(flattened) != len(set(flattened)):
            raise ValueError("workflow_shadow_record_partition_overlap")
        if sorted(flattened) != sorted(self.sampled_record_keys):
            raise ValueError("workflow_shadow_record_partition_incomplete")
        return self


class WorkflowShadowComparisonResponse(WorkflowFixtureReadBoundary):
    id: UUID
    workspace_id: UUID
    project_id: UUID
    workflow_run_id: UUID
    step_run_id: UUID
    requirement_ref: str = Field(min_length=1, max_length=500)
    contract_version: Literal["workflow_shadow_comparison.v1"]
    comparison_digest: Sha256Digest
    primary_implementation_id: str = Field(min_length=1, max_length=500)
    shadow_implementation_id: str = Field(min_length=1, max_length=500)
    fixture_profile_id: FixtureProfileId
    fixture_profile_hash: Sha256Digest
    primary_fixture_case_id: str = Field(min_length=1, max_length=200)
    primary_fixture_content_hash: Sha256Digest
    shadow_fixture_case_id: str = Field(min_length=1, max_length=200)
    shadow_fixture_content_hash: Sha256Digest
    sample_rate: float = Field(gt=0, le=1)
    max_items: int = Field(ge=1, le=100)
    sampled_items: int = Field(ge=1, le=100)
    matched_items: int = Field(ge=0, le=100)
    mismatched_items: int = Field(ge=0, le=100)
    primary_only_items: int = Field(ge=0, le=100)
    shadow_only_items: int = Field(ge=0, le=100)
    equivalence_status: ShadowEquivalenceStatus
    difference_evidence: WorkflowShadowDifferenceEvidence
    routing_recommendation: ShadowRoutingRecommendation
    evidence_refs: list[str] = Field(min_length=1, max_length=128)
    catalog_mutation_applied: Literal[False] = False
    route_ranking_mutation_applied: Literal[False] = False
    created_at: datetime

    @model_validator(mode="after")
    def validate_counts_and_recommendation(self) -> Self:
        partition_count = (
            self.matched_items
            + self.mismatched_items
            + self.primary_only_items
            + self.shadow_only_items
        )
        if partition_count != self.sampled_items:
            raise ValueError("workflow_shadow_sample_count_invalid")
        evidence = self.difference_evidence
        if (
            self.matched_items != len(evidence.matched_record_keys)
            or self.mismatched_items != len(evidence.mismatched_record_keys)
            or self.primary_only_items != len(evidence.primary_only_record_keys)
            or self.shadow_only_items != len(evidence.shadow_only_record_keys)
        ):
            raise ValueError("workflow_shadow_evidence_count_invalid")
        equivalent = self.equivalence_status == "equivalent"
        if equivalent != (partition_count == self.matched_items):
            raise ValueError("workflow_shadow_equivalence_invalid")
        expected_recommendation = (
            "eligible_for_governance_review"
            if equivalent
            else "keep_primary_investigate_shadow"
        )
        if self.routing_recommendation != expected_recommendation:
            raise ValueError("workflow_shadow_recommendation_invalid")
        return self


class WorkflowShadowComparisonListResponse(WorkflowFixtureReadBoundary):
    items: list[WorkflowShadowComparisonResponse]
    total: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_total(self) -> Self:
        if self.total != len(self.items):
            raise ValueError("workflow_shadow_total_invalid")
        return self


__all__ = [
    "ShadowEquivalenceStatus",
    "ShadowRoutingRecommendation",
    "WorkflowShadowComparisonListResponse",
    "WorkflowShadowComparisonResponse",
    "WorkflowShadowDifferenceEvidence",
]
