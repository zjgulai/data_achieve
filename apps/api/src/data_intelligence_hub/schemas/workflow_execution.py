from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityOperation,
    PlatformId,
    ResourceType,
)
from data_intelligence_hub.schemas.project import ProjectStatus
from data_intelligence_hub.schemas.workflow_planner import RoutePlanPreview

Sha256Digest = Annotated[
    str,
    StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$"),
]
FixtureProfileId = Annotated[
    str,
    StringConstraints(
        min_length=3,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9._-]*$",
    ),
]


class WorkflowExecutionContract(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class WorkflowRunStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    DEGRADED = "degraded"
    HELD = "held"
    CANCELLED = "cancelled"
    EMPTY_VALID = "empty_valid"


class WorkflowStepRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowFixtureBoundary(WorkflowExecutionContract):
    execution_mode: Literal["fixture"] = "fixture"
    live_execution_authorized: Literal[False] = False
    provider_call: Literal[False] = False
    provider_call_attempted: Literal[False] = False
    credential_read_attempted: Literal[False] = False
    actor_run: Literal[False] = False
    browser_run: Literal[False] = False
    llm_call: Literal[False] = False
    raw_record_write: Literal[False] = False
    dataset_write: Literal[False] = False
    production_write_allowed: Literal[False] = False


class WorkflowFixtureReadBoundary(WorkflowFixtureBoundary):
    database_write: Literal[False] = False


class WorkflowFixtureRunCreateRequest(WorkflowExecutionContract):
    expected_preview_fingerprint: Sha256Digest
    fixture_profile_id: FixtureProfileId


class WorkflowRunResponse(WorkflowExecutionContract):
    id: UUID
    workspace_id: UUID
    project_id: UUID
    workflow_plan_id: UUID
    workflow_version_id: UUID
    workflow_template_id: UUID | None = None
    workflow_template_revision_id: UUID | None = None
    created_by_user_id: UUID
    execution_contract_version: Literal["workflow_execution_fixture.v1"]
    execution_mode: Literal["fixture"]
    status: WorkflowRunStatus
    planner_contract_version: str = Field(min_length=1, max_length=200)
    preview_fingerprint: Sha256Digest
    catalog_snapshot_id: str = Field(min_length=1, max_length=500)
    policy_version: str = Field(min_length=1, max_length=200)
    mode_template_version: str = Field(min_length=1, max_length=200)
    query_versions: dict[PlatformId, str]
    fixture_profile_id: FixtureProfileId
    fixture_profile_hash: Sha256Digest
    total_steps: int = Field(ge=1)
    completed_steps: int = Field(ge=0)
    records_count: int = Field(ge=0)
    status_reason_code: str | None = Field(default=None, min_length=1, max_length=100)
    impact_code: str | None = Field(default=None, min_length=1, max_length=100)
    missing_fields: list[str] = Field(default_factory=list, max_length=256)
    recovery_action_codes: list[str] = Field(default_factory=list, max_length=64)
    provider_call_attempted: Literal[False] = False
    credential_read_attempted: Literal[False] = False
    actor_run: Literal[False] = False
    browser_run: Literal[False] = False
    llm_call: Literal[False] = False
    production_write_allowed: Literal[False] = False
    started_at: datetime
    finished_at: datetime | None = None
    created_at: datetime

    @model_validator(mode="after")
    def validate_template_lineage_pair(self) -> Self:
        if (self.workflow_template_id is None) != (
            self.workflow_template_revision_id is None
        ):
            raise ValueError("workflow_run_template_lineage_pair_invalid")
        return self

    @model_validator(mode="after")
    def validate_state_snapshot(self) -> Self:
        from data_intelligence_hub.services.workflow_execution.state_machine import (
            validate_workflow_run_state_snapshot,
        )

        validate_workflow_run_state_snapshot(
            self.status,
            total_steps=self.total_steps,
            completed_steps=self.completed_steps,
            records_count=self.records_count,
            status_reason_code=self.status_reason_code,
            impact_code=self.impact_code,
            missing_fields=self.missing_fields,
            recovery_action_codes=self.recovery_action_codes,
            finished_at=self.finished_at,
        )
        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("workflow_run_time_order_invalid")
        return self


class WorkflowStepRunResponse(WorkflowExecutionContract):
    id: UUID
    workflow_run_id: UUID
    workspace_id: UUID
    project_id: UUID
    step_ref: str = Field(min_length=1, max_length=500)
    requirement_ref: str = Field(min_length=1, max_length=500)
    sequence: int = Field(ge=1)
    platform: PlatformId
    resource_type: ResourceType
    operation: CapabilityOperation
    assertion_id: str = Field(min_length=1, max_length=500)
    implementation_id: str = Field(min_length=1, max_length=500)
    route_plan_snapshot: RoutePlanPreview
    evidence_refs: list[str] = Field(min_length=1, max_length=64)
    fixture_case_id: str | None = Field(default=None, min_length=1, max_length=200)
    fixture_content_hash: Sha256Digest | None = None
    input_digest: Sha256Digest
    output_digest: Sha256Digest | None = None
    idempotency_scope: str = Field(min_length=1, max_length=500)
    idempotency_key_hash: Sha256Digest
    status: WorkflowStepRunStatus
    records_count: int = Field(ge=0)
    provider_call_attempted: Literal[False] = False
    credential_read_attempted: Literal[False] = False
    actor_run: Literal[False] = False
    browser_run: Literal[False] = False
    llm_call: Literal[False] = False
    production_write_allowed: Literal[False] = False
    started_at: datetime
    finished_at: datetime | None = None
    created_at: datetime

    @model_validator(mode="after")
    def validate_frozen_route_and_time(self) -> Self:
        if self.route_plan_snapshot.requirement_ref != self.requirement_ref:
            raise ValueError("workflow_step_route_requirement_mismatch")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("workflow_step_evidence_refs_duplicate")
        receipt_fields = (
            self.fixture_case_id,
            self.fixture_content_hash,
            self.output_digest,
        )
        if self.status is WorkflowStepRunStatus.COMPLETED:
            if any(item is None for item in receipt_fields):
                raise ValueError("workflow_step_receipt_required")
            if self.finished_at is None or self.finished_at < self.started_at:
                raise ValueError("workflow_step_time_order_invalid")
        elif self.status in {
            WorkflowStepRunStatus.FAILED,
            WorkflowStepRunStatus.CANCELLED,
        }:
            if any(item is not None for item in receipt_fields) or self.records_count != 0:
                raise ValueError("workflow_step_failure_receipt_invalid")
            if self.finished_at is None or self.finished_at < self.started_at:
                raise ValueError("workflow_step_time_order_invalid")
        elif self.finished_at is not None:
            raise ValueError("workflow_step_active_finished_at_invalid")
        return self


def _validate_step_order(
    steps: list[WorkflowStepRunResponse],
) -> list[WorkflowStepRunResponse]:
    order = [(item.sequence, item.step_ref) for item in steps]
    if order != sorted(order) or len({item.step_ref for item in steps}) != len(steps):
        raise ValueError("workflow_step_order_invalid")
    return steps


class WorkflowFixtureRunCreateResponse(WorkflowFixtureBoundary):
    database_write: bool
    idempotent_replay: bool
    run: WorkflowRunResponse
    steps: list[WorkflowStepRunResponse]

    @model_validator(mode="after")
    def validate_attempt_and_steps(self) -> Self:
        if self.database_write == self.idempotent_replay:
            raise ValueError("fixture_run_attempt_flags_invalid")
        _validate_step_order(self.steps)
        if self.run.status in {
            WorkflowRunStatus.COMPLETED,
            WorkflowRunStatus.DEGRADED,
            WorkflowRunStatus.EMPTY_VALID,
        }:
            if len(self.steps) != self.run.total_steps:
                raise ValueError("workflow_run_step_count_invalid")
        elif len(self.steps) > self.run.total_steps:
            raise ValueError("workflow_run_step_count_invalid")
        if any(item.workflow_run_id != self.run.id for item in self.steps):
            raise ValueError("workflow_run_step_owner_invalid")
        return self


class WorkflowRunListResponse(WorkflowFixtureReadBoundary):
    project_status: ProjectStatus
    items: list[WorkflowRunResponse]
    total: int = Field(ge=0)
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class WorkflowRunDetailResponse(WorkflowFixtureReadBoundary):
    project_status: ProjectStatus
    run: WorkflowRunResponse
    steps: list[WorkflowStepRunResponse]

    @model_validator(mode="after")
    def validate_steps(self) -> Self:
        _validate_step_order(self.steps)
        if self.run.status in {
            WorkflowRunStatus.COMPLETED,
            WorkflowRunStatus.DEGRADED,
            WorkflowRunStatus.EMPTY_VALID,
        }:
            if len(self.steps) != self.run.total_steps:
                raise ValueError("workflow_run_step_count_invalid")
        elif len(self.steps) > self.run.total_steps:
            raise ValueError("workflow_run_step_count_invalid")
        if any(item.workflow_run_id != self.run.id for item in self.steps):
            raise ValueError("workflow_run_step_owner_invalid")
        return self


def normalize_workflow_execution_idempotency_key(value: str) -> str:
    normalized = value.strip()
    if not 12 <= len(normalized) <= 200:
        raise ValueError("idempotency_key_invalid")
    return normalized


__all__ = [
    "FixtureProfileId",
    "Sha256Digest",
    "WorkflowExecutionContract",
    "WorkflowFixtureBoundary",
    "WorkflowFixtureReadBoundary",
    "WorkflowFixtureRunCreateRequest",
    "WorkflowFixtureRunCreateResponse",
    "WorkflowRunDetailResponse",
    "WorkflowRunListResponse",
    "WorkflowRunResponse",
    "WorkflowRunStatus",
    "WorkflowStepRunResponse",
    "WorkflowStepRunStatus",
    "normalize_workflow_execution_idempotency_key",
]
