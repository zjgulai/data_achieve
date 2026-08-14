from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self, cast
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    SerializerFunctionWrapHandler,
    StringConstraints,
    field_serializer,
    field_validator,
    model_validator,
)

from data_intelligence_hub.schemas.capability_catalog import PlatformId
from data_intelligence_hub.schemas.project import ProjectStatus
from data_intelligence_hub.schemas.workflow_planner import (
    FlowMode,
    MatchMode,
    MonitoringScopeType,
    PlanningInput,
    PlanningStatus,
    WorkflowPlanPreview,
)

Sha256Fingerprint = Annotated[
    str,
    StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$"),
]
WorkflowPlanStatus = Literal["previewed"]
WorkflowPlanSaveOutcome = Literal["created", "semantic_no_op"]


class WorkflowPlanPersistenceContract(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class WorkflowExecutionBoundary(WorkflowPlanPersistenceContract):
    provider_call: Literal[False] = False
    actor_run: Literal[False] = False
    browser_run: Literal[False] = False
    llm_call: Literal[False] = False
    workflow_run_created: Literal[False] = False
    execution_authorized: Literal[False] = False


class WorkflowPlanReadBoundary(WorkflowExecutionBoundary):
    database_write: Literal[False] = False
    plan_changed: Literal[False] = False


class WorkflowPlanCreateRequest(WorkflowPlanPersistenceContract):
    name: str = Field(min_length=1, max_length=200)
    preview_input: PlanningInput
    expected_preview_fingerprint: Sha256Fingerprint

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class WorkflowVersionCreateRequest(WorkflowPlanPersistenceContract):
    preview_input: PlanningInput
    expected_preview_fingerprint: Sha256Fingerprint
    expected_current_version_id: UUID


class WorkflowPlanResponse(WorkflowPlanPersistenceContract):
    id: UUID
    workspace_id: UUID
    project_id: UUID
    created_by_user_id: UUID
    name: str
    flow_mode: FlowMode
    status: WorkflowPlanStatus
    current_version_id: UUID
    current_version_number: int = Field(ge=1)
    planning_status: PlanningStatus
    scope_count: int = Field(ge=0)
    query_term_count: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class WorkflowVersionSummaryResponse(WorkflowPlanPersistenceContract):
    id: UUID
    workspace_id: UUID
    project_id: UUID
    workflow_plan_id: UUID
    created_by_user_id: UUID
    version_number: int = Field(ge=1)
    planning_status: PlanningStatus
    planner_contract_version: str
    catalog_snapshot_id: str
    policy_version: str
    mode_template_version: str
    query_versions: dict[PlatformId, str]
    preview_fingerprint: Sha256Fingerprint
    created_at: datetime


class WorkflowVersionResponse(WorkflowVersionSummaryResponse):
    editable_input: PlanningInput
    preview: WorkflowPlanPreview

    @field_serializer("editable_input", mode="wrap")
    def serialize_editable_input(
        self,
        value: PlanningInput,
        handler: SerializerFunctionWrapHandler,
    ) -> dict[str, JsonValue]:
        serialized = cast(
            dict[str, JsonValue],
            handler(value),
        )
        result = dict(serialized)
        if value.flow_mode is FlowMode.BATCH_RESEARCH:
            result.pop("schedule_intent", None)
        return result


class MonitoringScopeResponse(WorkflowPlanPersistenceContract):
    id: UUID
    workspace_id: UUID
    project_id: UUID
    created_by_user_id: UUID
    scope_key: str
    scope_type: MonitoringScopeType
    canonical_term: str | None
    aliases: list[str]
    include_terms: list[str]
    exclude_terms: list[str]
    official_accounts: list[str]
    seed_urls: list[str]
    effective_languages: list[str]
    effective_regions: list[str]
    effective_platforms: list[PlatformId]
    match_mode: MatchMode
    created_at: datetime


class WorkflowPlanSaveResponse(WorkflowExecutionBoundary):
    database_write: bool
    plan_changed: bool
    outcome: WorkflowPlanSaveOutcome
    idempotent_replay: bool
    plan: WorkflowPlanResponse
    version: WorkflowVersionResponse

    @model_validator(mode="after")
    def validate_attempt_flags(self) -> Self:
        valid = False
        if self.idempotent_replay:
            valid = not self.database_write and not self.plan_changed
        elif self.outcome == "created":
            valid = self.database_write and self.plan_changed
        else:
            valid = self.database_write and not self.plan_changed
        if not valid:
            raise ValueError("save_attempt_flags_invalid")
        return self


class WorkflowPlanListResponse(WorkflowPlanReadBoundary):
    project_status: ProjectStatus
    items: list[WorkflowPlanResponse]
    total: int = Field(ge=0)
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class WorkflowVersionListResponse(WorkflowPlanReadBoundary):
    project_status: ProjectStatus
    items: list[WorkflowVersionSummaryResponse]
    total: int = Field(ge=0)
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class MonitoringScopeListResponse(WorkflowPlanReadBoundary):
    project_status: ProjectStatus
    items: list[MonitoringScopeResponse]
    total: int = Field(ge=0)
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class WorkflowPlanDetailResponse(WorkflowPlanReadBoundary):
    project_status: ProjectStatus
    plan: WorkflowPlanResponse
    current_version: WorkflowVersionResponse


class WorkflowVersionDetailResponse(WorkflowPlanReadBoundary):
    project_status: ProjectStatus
    plan: WorkflowPlanResponse
    version: WorkflowVersionResponse


class WorkflowPlanCompareChange(WorkflowPlanPersistenceContract):
    field: str
    before: JsonValue | None = None
    after: JsonValue | None = None


class WorkflowPlanCompareSection(WorkflowPlanPersistenceContract):
    key: str
    changes: list[WorkflowPlanCompareChange]


class WorkflowPlanVersionCompareResponse(WorkflowPlanReadBoundary):
    project_status: ProjectStatus
    plan: WorkflowPlanResponse
    base_version: WorkflowVersionSummaryResponse
    target_version: WorkflowVersionSummaryResponse
    same_version: bool
    sections: list[WorkflowPlanCompareSection]


def normalize_idempotency_key(value: str) -> str:
    normalized = value.strip()
    if not 12 <= len(normalized) <= 200:
        raise ValueError("idempotency_key_invalid")
    return normalized


def serialize_preview_snapshot(preview: WorkflowPlanPreview) -> dict[str, JsonValue]:
    return cast(dict[str, JsonValue], preview.model_dump(mode="json"))


__all__ = [
    "MonitoringScopeListResponse",
    "MonitoringScopeResponse",
    "Sha256Fingerprint",
    "WorkflowPlanCompareChange",
    "WorkflowPlanCompareSection",
    "WorkflowPlanCreateRequest",
    "WorkflowPlanDetailResponse",
    "WorkflowPlanListResponse",
    "WorkflowPlanReadBoundary",
    "WorkflowPlanResponse",
    "WorkflowPlanSaveOutcome",
    "WorkflowPlanSaveResponse",
    "WorkflowPlanStatus",
    "WorkflowPlanVersionCompareResponse",
    "WorkflowVersionCreateRequest",
    "WorkflowVersionDetailResponse",
    "WorkflowVersionListResponse",
    "WorkflowVersionResponse",
    "WorkflowVersionSummaryResponse",
    "normalize_idempotency_key",
    "serialize_preview_snapshot",
]
