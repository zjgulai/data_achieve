from __future__ import annotations

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from data_intelligence_hub.schemas.project import ProjectStatus
from data_intelligence_hub.schemas.workflow_plan_persistence import (
    WorkflowExecutionBoundary,
    WorkflowPlanSaveResponse,
)
from data_intelligence_hub.schemas.workflow_planner import PlanningInput


class WorkflowTemplateContract(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class WorkflowTemplateCreateRequest(WorkflowTemplateContract):
    name: str = Field(min_length=1, max_length=200)
    template_key: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    definition: PlanningInput

    @field_validator("name", "template_key", mode="before")
    @classmethod
    def trim_required_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("description", mode="before")
    @classmethod
    def trim_description(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        trimmed = value.strip()
        return trimmed or None


class WorkflowTemplateMetadataUpdateRequest(WorkflowTemplateContract):
    expected_revision_id: UUID
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name", "description", mode="before")
    @classmethod
    def trim_optional_text(cls, value: object) -> object:
        if value is None:
            return None
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_metadata_change(self) -> Self:
        if self.name is None and "description" not in self.model_fields_set:
            raise ValueError("workflow_template_metadata_patch_empty")
        return self


class WorkflowTemplateRevisionCreateRequest(WorkflowTemplateContract):
    expected_revision_id: UUID
    definition: PlanningInput


class WorkflowTemplateInstantiateRequest(WorkflowTemplateContract):
    revision_id: UUID
    name: str = Field(min_length=1, max_length=200)

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class WorkflowTemplateRevisionResponse(WorkflowExecutionBoundary):
    id: UUID
    workspace_id: UUID
    project_id: UUID
    workflow_template_id: UUID
    created_by_user_id: UUID
    revision_number: int = Field(ge=1)
    definition: PlanningInput
    definition_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    created_at: datetime


class WorkflowTemplateResponse(WorkflowExecutionBoundary):
    id: UUID
    workspace_id: UUID
    project_id: UUID
    created_by_user_id: UUID
    name: str
    template_key: str
    description: str | None
    status: Literal["draft", "previewed", "approved", "active", "paused", "archived"]
    current_revision_id: UUID | None
    current_revision: WorkflowTemplateRevisionResponse | None = None
    created_at: datetime
    updated_at: datetime


class WorkflowTemplateListResponse(WorkflowExecutionBoundary):
    database_write: Literal[False] = False
    project_status: ProjectStatus
    items: list[WorkflowTemplateResponse]
    total: int = Field(ge=0)
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class WorkflowTemplateDetailResponse(WorkflowExecutionBoundary):
    database_write: Literal[False] = False
    project_status: ProjectStatus
    template: WorkflowTemplateResponse
    current_revision: WorkflowTemplateRevisionResponse


class WorkflowTemplateRevisionListResponse(WorkflowExecutionBoundary):
    database_write: Literal[False] = False
    project_status: ProjectStatus
    template: WorkflowTemplateResponse
    items: list[WorkflowTemplateRevisionResponse]
    total: int = Field(ge=0)
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class WorkflowTemplateMutationResponse(WorkflowExecutionBoundary):
    database_write: bool
    idempotent_replay: bool
    outcome: Literal["created", "updated"]
    template: WorkflowTemplateResponse
    revision: WorkflowTemplateRevisionResponse | None = None

    @model_validator(mode="after")
    def validate_flags(self) -> Self:
        if self.idempotent_replay and self.database_write:
            raise ValueError("template_mutation_replay_write_invalid")
        if not self.idempotent_replay and not self.database_write:
            raise ValueError("template_mutation_write_flag_invalid")
        if self.outcome == "created" and self.revision is None:
            raise ValueError("template_create_revision_missing")
        return self


WorkflowTemplateCreateResponse = WorkflowTemplateMutationResponse
WorkflowTemplateRevisionCreateResponse = WorkflowTemplateMutationResponse
WorkflowTemplateMetadataUpdateResponse = WorkflowTemplateMutationResponse
WorkflowTemplateInstantiateResponse = WorkflowPlanSaveResponse


__all__ = [
    "WorkflowTemplateCreateRequest",
    "WorkflowTemplateCreateResponse",
    "WorkflowTemplateDetailResponse",
    "WorkflowTemplateInstantiateRequest",
    "WorkflowTemplateInstantiateResponse",
    "WorkflowTemplateListResponse",
    "WorkflowTemplateMetadataUpdateRequest",
    "WorkflowTemplateMetadataUpdateResponse",
    "WorkflowTemplateRevisionCreateRequest",
    "WorkflowTemplateRevisionCreateResponse",
    "WorkflowTemplateRevisionListResponse",
    "WorkflowTemplateRevisionResponse",
    "WorkflowTemplateResponse",
]
