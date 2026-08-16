from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from data_intelligence_hub.schemas.capability_catalog import (
    AccessChannel,
    CapabilityConstraint,
    CapabilityEvidence,
    CapabilityImplementation,
    CapabilityOperation,
    CapabilityScoreProfile,
    CapabilityStatus,
    DeliveryForm,
    DeploymentMode,
    PlatformId,
    ResourceType,
)
from data_intelligence_hub.schemas.capability_discovery import (
    CapabilityDiscoveryParserId,
    validate_fixture_id,
)

SHA256_FINGERPRINT_PATTERN = r"^sha256:[0-9a-f]{64}$"
Sha256Fingerprint = Annotated[str, Field(pattern=SHA256_FINGERPRINT_PATTERN)]
ReasonText = Annotated[str, Field(min_length=1, max_length=2000)]
EvidenceRef = Annotated[str, Field(min_length=1, max_length=500)]


class CapabilityGovernanceContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CapabilityGovernancePermission(StrEnum):
    READ = "read"
    REVIEW = "review"
    PUBLISH = "publish"


class CapabilityCandidateVerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    REJECTED = "rejected"


class CapabilityVerificationTaskType(StrEnum):
    INITIAL_REVIEW = "initial_review"
    EVIDENCE_REFRESH = "evidence_refresh"
    SEMANTIC_DRIFT = "semantic_drift"


class CapabilityVerificationTaskStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class CapabilityVerificationAction(StrEnum):
    VERIFY = "verify"
    REJECT = "reject"
    DEPRECATE = "deprecate"


class CapabilityCandidateIntakeClassification(StrEnum):
    FIRST_OBSERVATION = "first_observation"
    SEMANTIC_EXACT_REPLAY = "semantic_exact_replay"
    EVIDENCE_REFRESH = "evidence_refresh"
    SEMANTIC_DRIFT = "semantic_drift"


class CapabilityGovernancePermissionSet(CapabilityGovernanceContract):
    can_read: bool
    can_review: bool
    can_publish: bool

    @model_validator(mode="after")
    def validate_permission_implication(self) -> Self:
        if (self.can_review or self.can_publish) and not self.can_read:
            raise ValueError("governance_read_permission_required")
        return self


class CapabilityGovernanceImportRequest(CapabilityGovernanceContract):
    schema_version: Literal["capability_governance_import_request.v1"]
    fixture_ids: list[str] = Field(min_length=1, max_length=4)
    expected_preview_fingerprint: Sha256Fingerprint

    @field_validator("fixture_ids")
    @classmethod
    def validate_fixture_ids(cls, value: list[str]) -> list[str]:
        for fixture_id in value:
            validate_fixture_id(fixture_id)
        if len(value) != len(set(value)):
            raise ValueError("duplicate_fixture_id")
        return value


class CapabilityGovernanceCanonicalAssertionInput(CapabilityGovernanceContract):
    assertion_id: Annotated[str, Field(min_length=1, max_length=500)]
    implementation_id: Annotated[str, Field(min_length=1, max_length=500)]
    resource_type: ResourceType
    operation: CapabilityOperation
    support_status: CapabilityStatus
    source_resource_group: Annotated[str, Field(min_length=1, max_length=500)]
    region_scope: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(max_length=32)
    purpose_scope: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(max_length=32)
    auth_scope: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(max_length=32)
    field_contract: dict[str, JsonValue]
    constraints: list[CapabilityConstraint] = Field(max_length=64)
    score_profile: CapabilityScoreProfile
    evidence_refs: list[EvidenceRef] = Field(min_length=1, max_length=64)

    @field_validator("support_status")
    @classmethod
    def validate_publishable_support_status(
        cls,
        value: CapabilityStatus,
    ) -> CapabilityStatus:
        allowed = {
            CapabilityStatus.VERIFIED,
            CapabilityStatus.PARTIAL,
            CapabilityStatus.BLOCKED,
            CapabilityStatus.UNSUPPORTED,
            CapabilityStatus.DEPRECATED,
        }
        if value not in allowed:
            raise ValueError("canonical_support_status_invalid")
        return value

    @field_validator("evidence_refs")
    @classmethod
    def validate_unique_evidence_refs(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("duplicate_evidence_ref")
        return value


class CapabilityGovernanceReviewRequest(CapabilityGovernanceContract):
    schema_version: Literal["capability_governance_review_request.v1"]
    expected_task_version: int = Field(ge=1)
    action: CapabilityVerificationAction
    reason: ReasonText
    canonical_implementation: CapabilityImplementation | None = None
    canonical_assertion: CapabilityGovernanceCanonicalAssertionInput | None = None

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("review_reason_required")
        return normalized

    @model_validator(mode="after")
    def validate_action_bundle(self) -> Self:
        if self.action is CapabilityVerificationAction.REJECT:
            if self.canonical_implementation is not None or self.canonical_assertion is not None:
                raise ValueError("reject_canonical_bundle_forbidden")
            return self

        if self.canonical_implementation is None or self.canonical_assertion is None:
            raise ValueError("canonical_bundle_required")
        if (
            self.canonical_implementation.implementation_id
            != self.canonical_assertion.implementation_id
        ):
            raise ValueError("canonical_bundle_implementation_mismatch")

        status = self.canonical_assertion.support_status
        if self.action is CapabilityVerificationAction.DEPRECATE:
            if status is not CapabilityStatus.DEPRECATED:
                raise ValueError("deprecate_status_required")
        elif status is CapabilityStatus.DEPRECATED:
            raise ValueError("verify_deprecated_status_forbidden")
        return self


class UpsertVerifiedAssertionOperation(CapabilityGovernanceContract):
    operation: Literal["upsert_verified_assertion"]
    verification_decision_id: UUID


class RemoveAssertionOperation(CapabilityGovernanceContract):
    operation: Literal["remove_assertion"]
    verification_decision_id: UUID
    logical_assertion_key: Sha256Fingerprint


CapabilityGovernancePublicationOperation = Annotated[
    UpsertVerifiedAssertionOperation | RemoveAssertionOperation,
    Field(discriminator="operation"),
]


class CapabilityGovernancePublicationCreateRequest(CapabilityGovernanceContract):
    schema_version: Literal["capability_governance_publication_request.v1"]
    expected_parent_revision_id: UUID | None
    reason: ReasonText
    operations: list[CapabilityGovernancePublicationOperation] = Field(
        min_length=1,
        max_length=100,
    )

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("publication_reason_required")
        return normalized

    @model_validator(mode="after")
    def validate_unique_decisions(self) -> Self:
        decision_ids = [item.verification_decision_id for item in self.operations]
        if len(decision_ids) != len(set(decision_ids)):
            raise ValueError("duplicate_verification_decision")
        return self


class CapabilityGovernancePublicationRollbackRequest(CapabilityGovernanceContract):
    schema_version: Literal["capability_governance_rollback_request.v1"]
    expected_current_revision_id: UUID
    target_revision_id: UUID
    reason: ReasonText

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("rollback_reason_required")
        return normalized

    @model_validator(mode="after")
    def validate_distinct_target(self) -> Self:
        if self.expected_current_revision_id == self.target_revision_id:
            raise ValueError("rollback_target_must_differ")
        return self


class CapabilityGovernanceWriteAttempt(CapabilityGovernanceContract):
    database_write: bool
    domain_changed: bool
    idempotent_replay: bool
    provider_call: Literal[False] = False
    actor_run: Literal[False] = False
    browser_run: Literal[False] = False
    llm_call: Literal[False] = False
    workflow_run_created: Literal[False] = False
    database_migration: Literal[False] = False
    production_write_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_attempt_flags(self) -> Self:
        valid = (
            self.idempotent_replay and not self.database_write and not self.domain_changed
        ) or (not self.idempotent_replay and self.database_write)
        if not valid:
            raise ValueError("write_attempt_flags_invalid")
        return self


class CapabilityGovernanceCandidateIntakeResult(CapabilityGovernanceContract):
    candidate_key: Sha256Fingerprint
    candidate_version_id: UUID
    semantic_version: int = Field(ge=1)
    classification: CapabilityCandidateIntakeClassification
    verification_task_id: UUID | None
    evidence_added_count: int = Field(ge=0)


class CapabilityGovernanceImportResponse(CapabilityGovernanceWriteAttempt):
    schema_version: Literal["capability_governance_import_response.v1"]
    request_id: UUID
    batch_id: UUID | None
    preview_fingerprint: Sha256Fingerprint
    outcome: Literal[
        "first_observation",
        "semantic_exact_replay",
        "evidence_refresh",
        "semantic_drift",
        "mixed",
    ]
    candidates: list[CapabilityGovernanceCandidateIntakeResult] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_domain_result(self) -> Self:
        if self.idempotent_replay:
            return self
        classifications = {item.classification for item in self.candidates}
        has_domain_change = classifications != {
            CapabilityCandidateIntakeClassification.SEMANTIC_EXACT_REPLAY
        }
        if self.domain_changed != has_domain_change:
            raise ValueError("intake_domain_change_mismatch")
        if (self.batch_id is not None) != self.domain_changed:
            raise ValueError("intake_batch_change_mismatch")
        return self


class CapabilityGovernanceReviewResponse(CapabilityGovernanceWriteAttempt):
    schema_version: Literal["capability_governance_review_response.v1"]
    request_id: UUID
    decision_id: UUID
    task_id: UUID
    candidate_version_id: UUID
    task_version: int = Field(ge=1)
    action: CapabilityVerificationAction
    verification_status: Literal["verified", "rejected"]
    reviewed_at: datetime

    @field_validator("reviewed_at")
    @classmethod
    def validate_reviewed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("reviewed_at_timezone_required")
        return value


class CapabilityGovernancePublicationResponse(CapabilityGovernanceWriteAttempt):
    schema_version: Literal["capability_governance_publication_response.v1"]
    publication_kind: Literal["publish", "rollback"]
    request_id: UUID
    revision_id: UUID
    revision_number: int = Field(ge=1)
    parent_revision_id: UUID | None
    restored_from_revision_id: UUID | None
    catalog_snapshot_id: Sha256Fingerprint
    head_version: int = Field(ge=1)
    operation_count: int = Field(ge=0, le=100)
    published_at: datetime

    @field_validator("published_at")
    @classmethod
    def validate_published_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("published_at_timezone_required")
        return value


class CapabilityGovernanceProposedImplementationResponse(CapabilityGovernanceContract):
    schema_version: Literal["capability_proposed_implementation_preview.v1"]
    proposed_implementation_id: Annotated[str, Field(min_length=1, max_length=500)]
    provider_id: Annotated[str, Field(min_length=1, max_length=500)]
    platform: PlatformId
    access_channel: AccessChannel
    delivery_form: DeliveryForm
    deployment_mode: DeploymentMode
    source_label: Annotated[str, Field(min_length=1, max_length=500)]
    claimed_auth_mode: Annotated[str, Field(min_length=1, max_length=500)]
    claimed_required_credentials: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(
        max_length=32
    )
    claimed_limitations: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(
        max_length=64
    )


class CapabilityGovernanceCandidateAssertionResponse(CapabilityGovernanceContract):
    schema_version: Literal["capability_candidate_assertion_preview.v1"]
    candidate_id: Annotated[str, Field(min_length=1, max_length=500)]
    proposed_implementation_id: Annotated[str, Field(min_length=1, max_length=500)]
    platform: PlatformId
    access_channel: AccessChannel
    resource_type: ResourceType
    operation: CapabilityOperation
    support_status: Literal["candidate"]
    verification_status: Literal["unverified"]
    executable: Literal[False]
    publishable: Literal[False]
    claimed_field_contract: dict[str, JsonValue]
    claimed_constraints: list[CapabilityConstraint] = Field(max_length=64)
    region_scope: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(max_length=32)
    purpose_scope: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(max_length=32)
    auth_scope: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(max_length=32)
    parser_id: CapabilityDiscoveryParserId
    candidate_fingerprint: Sha256Fingerprint


class CapabilityGovernanceCandidateResponse(CapabilityGovernanceContract):
    id: UUID
    candidate_key: Sha256Fingerprint
    semantic_version: int = Field(ge=1)
    candidate_fingerprint: Sha256Fingerprint
    predecessor_id: UUID | None
    proposed_implementation: CapabilityGovernanceProposedImplementationResponse
    candidate_assertion: CapabilityGovernanceCandidateAssertionResponse
    first_seen_batch_id: UUID
    created_at: datetime


class CapabilityGovernanceDecisionResponse(CapabilityGovernanceContract):
    id: UUID
    verification_task_id: UUID
    candidate_version_id: UUID
    action: CapabilityVerificationAction
    verification_status: Literal["verified", "rejected"]
    reviewer_user_id: UUID
    reviewed_at: datetime
    reason: ReasonText
    canonical_bundle: dict[str, JsonValue] | None


class CapabilityGovernanceVerificationTaskResponse(CapabilityGovernanceContract):
    id: UUID
    candidate_version_id: UUID
    task_type: CapabilityVerificationTaskType
    status: CapabilityVerificationTaskStatus
    task_version: int = Field(ge=1)
    opened_at: datetime
    resolved_at: datetime | None
    decision_id: UUID | None


class CapabilityGovernanceCandidateListResponse(CapabilityGovernanceContract):
    schema_version: Literal["capability_governance_candidate_list.v1"]
    permissions: CapabilityGovernancePermissionSet
    items: list[CapabilityGovernanceCandidateResponse] = Field(max_length=100)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class CapabilityGovernanceCandidateDetailResponse(CapabilityGovernanceContract):
    schema_version: Literal["capability_governance_candidate_detail.v1"]
    candidate: CapabilityGovernanceCandidateResponse
    evidence: list[CapabilityEvidence] = Field(max_length=64)
    open_verification_task: CapabilityGovernanceVerificationTaskResponse | None
    latest_decision: CapabilityGovernanceDecisionResponse | None


class CapabilityGovernanceVerificationTaskListResponse(CapabilityGovernanceContract):
    schema_version: Literal["capability_governance_verification_task_list.v1"]
    items: list[CapabilityGovernanceVerificationTaskResponse] = Field(max_length=100)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class CapabilityGovernanceVerificationTaskDetailResponse(CapabilityGovernanceContract):
    schema_version: Literal["capability_governance_verification_task_detail.v1"]
    task: CapabilityGovernanceVerificationTaskResponse
    candidate: CapabilityGovernanceCandidateResponse
    evidence: list[CapabilityEvidence] = Field(max_length=64)
    decision: CapabilityGovernanceDecisionResponse | None


class CapabilityGovernancePublicationRevisionResponse(CapabilityGovernanceContract):
    id: UUID
    revision_number: int = Field(ge=1)
    parent_revision_id: UUID | None
    restored_from_revision_id: UUID | None
    catalog_snapshot_id: Sha256Fingerprint
    publisher_user_id: UUID
    published_at: datetime
    reason: ReasonText
    operations: list[dict[str, JsonValue]] = Field(max_length=100)
    is_current: bool


class CapabilityGovernancePublicationListResponse(CapabilityGovernanceContract):
    schema_version: Literal["capability_governance_publication_list.v1"]
    items: list[CapabilityGovernancePublicationRevisionResponse] = Field(max_length=100)
    current_revision_id: UUID | None
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class CapabilityGovernancePublicationDetailResponse(CapabilityGovernanceContract):
    schema_version: Literal["capability_governance_publication_detail.v1"]
    revision: CapabilityGovernancePublicationRevisionResponse
    current_revision_id: UUID | None


def normalize_governance_idempotency_key(value: str) -> str:
    normalized = value.strip()
    if not 12 <= len(normalized) <= 200:
        raise ValueError("idempotency_key_invalid")
    return normalized
