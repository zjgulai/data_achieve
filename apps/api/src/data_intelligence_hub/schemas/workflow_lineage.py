from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal, Self, cast
from uuid import UUID

from pydantic import Field, JsonValue, StringConstraints, field_validator, model_validator

from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityOperation,
    PlatformId,
    ResourceType,
)
from data_intelligence_hub.schemas.workflow_execution import (
    Sha256Digest,
    WorkflowExecutionContract,
    WorkflowFixtureReadBoundary,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import sha256_id

DatasetName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]


class WorkflowProviderPayloadRecord(WorkflowExecutionContract):
    record_type: str = Field(min_length=1, max_length=50)
    source_url: str | None = Field(default=None, max_length=4000)
    collected_at: datetime
    content: dict[str, JsonValue]

    @field_validator("collected_at")
    @classmethod
    def require_timezone_aware_timestamp(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("provider_payload_timestamp_timezone_required")
        return value.astimezone(UTC)


def compute_workflow_provider_payload_digest(
    records: list[WorkflowProviderPayloadRecord],
) -> Sha256Digest:
    payload = cast(JsonValue, [item.model_dump(mode="json") for item in records])
    return sha256_id(payload)


class WorkflowProviderPayloadEnvelope(WorkflowExecutionContract):
    contract_version: Literal["workflow_provider_payload.v1"]
    fixture_profile_id: str = Field(min_length=3, max_length=100)
    fixture_case_id: str = Field(min_length=1, max_length=200)
    implementation_id: str = Field(min_length=1, max_length=500)
    platform: PlatformId
    resource_type: ResourceType
    operation: CapabilityOperation
    evidence_refs: list[str] = Field(min_length=1, max_length=64)
    records_count: int = Field(ge=1, le=1000)
    records: list[WorkflowProviderPayloadRecord] = Field(min_length=1, max_length=1000)
    payload_digest: Sha256Digest

    @model_validator(mode="after")
    def validate_payload(self) -> Self:
        if len(self.records) != self.records_count:
            raise ValueError("provider_payload_count_mismatch")
        if any(not item or len(item) > 500 for item in self.evidence_refs):
            raise ValueError("provider_payload_evidence_ref_invalid")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("provider_payload_evidence_ref_duplicate")
        record_digests = [sha256_id(cast(JsonValue, item.content)) for item in self.records]
        if len(record_digests) != len(set(record_digests)):
            raise ValueError("provider_payload_record_duplicate")
        if self.payload_digest != compute_workflow_provider_payload_digest(self.records):
            raise ValueError("provider_payload_digest_mismatch")
        return self


class WorkflowLineageMaterializationRequest(WorkflowExecutionContract):
    dataset_name: DatasetName
    expected_lineage_digest: Sha256Digest

    @field_validator("dataset_name")
    @classmethod
    def reject_control_characters(cls, value: str) -> str:
        if any(ord(character) < 32 for character in value):
            raise ValueError("dataset_name_invalid")
        return value


class WorkflowLineageMaterializationResponse(WorkflowExecutionContract):
    contract_version: Literal["workflow_lineage_materialization.v1"]
    materialization_id: UUID
    workflow_run_id: UUID
    dataset_id: UUID
    dataset_version_id: UUID
    dataset_version_number: int = Field(ge=1)
    raw_record_ids: list[UUID] = Field(min_length=1, max_length=1000)
    records_count: int = Field(ge=1, le=1000)
    lineage_digest: Sha256Digest
    database_write: bool
    idempotent_replay: bool
    raw_record_write: bool
    dataset_write: bool
    provider_call: Literal[False] = False
    provider_call_attempted: Literal[False] = False
    credential_read_attempted: Literal[False] = False
    actor_run: Literal[False] = False
    browser_run: Literal[False] = False
    llm_call: Literal[False] = False
    production_write_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_attempt(self) -> Self:
        if self.database_write == self.idempotent_replay:
            raise ValueError("materialization_attempt_flags_invalid")
        if self.database_write != self.raw_record_write:
            raise ValueError("materialization_raw_record_write_invalid")
        if self.database_write != self.dataset_write:
            raise ValueError("materialization_dataset_write_invalid")
        if len(self.raw_record_ids) != self.records_count:
            raise ValueError("materialization_record_count_mismatch")
        return self


class WorkflowProviderLineagePreview(WorkflowExecutionContract):
    step_run_id: UUID
    implementation_id: str = Field(min_length=1, max_length=500)
    platform: PlatformId
    resource_type: ResourceType
    operation: CapabilityOperation
    fixture_case_id: str = Field(min_length=1, max_length=200)
    fixture_content_hash: Sha256Digest
    output_digest: Sha256Digest
    records_count: int = Field(ge=1)
    evidence_refs: list[str] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_evidence_refs(self) -> Self:
        if any(not item or len(item) > 500 for item in self.evidence_refs):
            raise ValueError("workflow_lineage_evidence_ref_invalid")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("workflow_lineage_evidence_ref_duplicate")
        return self


class WorkflowRawRecordLineagePreview(WorkflowExecutionContract):
    source_task_run_id: UUID | None = None
    source_step_run_ids: list[UUID] = Field(min_length=1, max_length=64)
    materialized_raw_record_ids: list[UUID] = Field(default_factory=list, max_length=1000)
    expected_record_count: int = Field(ge=1)
    raw_record_write: Literal[False] = False
    materialized: bool = False
    blocked_reasons: list[str] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def validate_materialized_records(self) -> Self:
        if self.materialized != bool(self.materialized_raw_record_ids):
            raise ValueError("workflow_lineage_raw_record_materialized_invalid")
        if self.materialized and (
            len(self.materialized_raw_record_ids) != self.expected_record_count
        ):
            raise ValueError("workflow_lineage_raw_record_count_invalid")
        return self


class WorkflowDatasetLineagePreview(WorkflowExecutionContract):
    dataset_id: UUID | None = None
    dataset_version_id: UUID | None = None
    source_step_run_ids: list[UUID] = Field(min_length=1, max_length=64)
    source_raw_record_ids: list[UUID] = Field(default_factory=list, max_length=1000)
    expected_record_count: int = Field(ge=1)
    dataset_write: Literal[False] = False
    materialized: bool = False
    blocked_reasons: list[str] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def validate_materialized_dataset(self) -> Self:
        identity_complete = self.dataset_id is not None and self.dataset_version_id is not None
        if (self.dataset_id is None) != (self.dataset_version_id is None):
            raise ValueError("workflow_lineage_dataset_identity_partial")
        if self.materialized != identity_complete:
            raise ValueError("workflow_lineage_dataset_materialized_invalid")
        if self.materialized and len(self.source_raw_record_ids) != self.expected_record_count:
            raise ValueError("workflow_lineage_dataset_record_count_invalid")
        return self


class WorkflowRunLineagePreview(WorkflowFixtureReadBoundary):
    schema_version: Literal["workflow_lineage_preview.v2"]
    workflow_run_id: UUID
    workspace_id: UUID
    project_id: UUID
    lineage_digest: Sha256Digest
    materialization_eligible: bool
    provider_evidence: list[WorkflowProviderLineagePreview] = Field(
        min_length=1,
        max_length=64,
    )
    raw_record: WorkflowRawRecordLineagePreview
    dataset: WorkflowDatasetLineagePreview
    blocked_reasons: list[str] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def validate_source_alignment(self) -> Self:
        provider_step_ids = [item.step_run_id for item in self.provider_evidence]
        if len(provider_step_ids) != len(set(provider_step_ids)):
            raise ValueError("workflow_lineage_step_duplicate")
        if provider_step_ids != self.raw_record.source_step_run_ids:
            raise ValueError("workflow_lineage_raw_record_source_mismatch")
        if provider_step_ids != self.dataset.source_step_run_ids:
            raise ValueError("workflow_lineage_dataset_source_mismatch")
        expected_record_count = sum(item.records_count for item in self.provider_evidence)
        if expected_record_count != self.raw_record.expected_record_count:
            raise ValueError("workflow_lineage_raw_record_count_mismatch")
        if expected_record_count != self.dataset.expected_record_count:
            raise ValueError("workflow_lineage_dataset_count_mismatch")
        if self.raw_record.materialized != self.dataset.materialized:
            raise ValueError("workflow_lineage_materialized_state_mismatch")
        if self.dataset.source_raw_record_ids != self.raw_record.materialized_raw_record_ids:
            raise ValueError("workflow_lineage_materialized_record_ids_mismatch")
        if self.materialization_eligible == bool(self.blocked_reasons):
            raise ValueError("workflow_lineage_eligibility_invalid")
        return self


__all__ = [
    "DatasetName",
    "WorkflowLineageMaterializationRequest",
    "WorkflowLineageMaterializationResponse",
    "WorkflowProviderPayloadEnvelope",
    "WorkflowProviderPayloadRecord",
    "WorkflowDatasetLineagePreview",
    "WorkflowProviderLineagePreview",
    "WorkflowRawRecordLineagePreview",
    "WorkflowRunLineagePreview",
    "compute_workflow_provider_payload_digest",
]
