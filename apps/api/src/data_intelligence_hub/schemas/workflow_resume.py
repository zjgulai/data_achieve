from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, StringConstraints, model_validator

from data_intelligence_hub.schemas.workflow_execution import (
    FixtureProfileId,
    Sha256Digest,
    WorkflowExecutionContract,
    WorkflowFixtureBoundary,
)

CheckpointCursor = Annotated[
    str,
    StringConstraints(min_length=1, max_length=1000),
]
CheckpointReference = Annotated[
    str,
    StringConstraints(min_length=1, max_length=500),
]


class WorkflowStepResumeIdentity(WorkflowExecutionContract):
    execution_session_id: UUID
    workspace_id: UUID
    project_id: UUID
    workflow_plan_id: UUID
    workflow_version_id: UUID
    step_ref: CheckpointReference
    requirement_ref: CheckpointReference
    implementation_id: CheckpointReference
    fixture_profile_id: FixtureProfileId
    fixture_profile_hash: Sha256Digest
    step_input_digest: Sha256Digest


class WorkflowCheckpointPageResult(WorkflowExecutionContract):
    records_count: int = Field(ge=0)
    next_cursor: CheckpointCursor | None = None
    output_digest: Sha256Digest
    terminal: bool
    evidence_refs: list[CheckpointReference] = Field(min_length=1, max_length=64)
    provider_call_attempted: Literal[False] = False
    credential_read_attempted: Literal[False] = False
    actor_run: Literal[False] = False
    browser_run: Literal[False] = False
    llm_call: Literal[False] = False
    raw_record_write: Literal[False] = False
    dataset_write: Literal[False] = False
    production_write_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_cursor_state(self) -> Self:
        if self.terminal == (self.next_cursor is not None):
            raise ValueError("workflow_checkpoint_page_cursor_state_invalid")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("workflow_checkpoint_evidence_refs_duplicate")
        return self


class WorkflowStepCheckpointResponse(WorkflowExecutionContract):
    id: UUID
    execution_session_id: UUID
    workspace_id: UUID
    project_id: UUID
    workflow_plan_id: UUID
    workflow_version_id: UUID
    step_ref: CheckpointReference
    requirement_ref: CheckpointReference
    implementation_id: CheckpointReference
    contract_version: Literal["workflow_step_checkpoint.v1"]
    fixture_profile_id: FixtureProfileId
    fixture_profile_hash: Sha256Digest
    step_input_digest: Sha256Digest
    page_number: int = Field(ge=1)
    cursor_before: CheckpointCursor | None = None
    cursor_before_digest: Sha256Digest
    cursor_after: CheckpointCursor | None = None
    cursor_after_digest: Sha256Digest | None = None
    side_effect_key_hash: Sha256Digest
    page_output_digest: Sha256Digest
    checkpoint_digest: Sha256Digest
    records_count: int = Field(ge=0)
    terminal: bool
    evidence_refs: list[CheckpointReference] = Field(min_length=1, max_length=64)
    provider_call_attempted: Literal[False] = False
    credential_read_attempted: Literal[False] = False
    actor_run: Literal[False] = False
    browser_run: Literal[False] = False
    llm_call: Literal[False] = False
    raw_record_write: Literal[False] = False
    dataset_write: Literal[False] = False
    production_write_allowed: Literal[False] = False
    confirmed_at: datetime
    created_at: datetime

    @model_validator(mode="after")
    def validate_cursor_state(self) -> Self:
        if self.page_number == 1 and self.cursor_before is not None:
            raise ValueError("workflow_checkpoint_first_cursor_invalid")
        if self.page_number > 1 and self.cursor_before is None:
            raise ValueError("workflow_checkpoint_resume_cursor_required")
        if self.terminal:
            if self.cursor_after is not None or self.cursor_after_digest is not None:
                raise ValueError("workflow_checkpoint_terminal_cursor_invalid")
        elif self.cursor_after is None or self.cursor_after_digest is None:
            raise ValueError("workflow_checkpoint_next_cursor_required")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("workflow_checkpoint_evidence_refs_duplicate")
        return self


class WorkflowStepResumeResult(WorkflowFixtureBoundary):
    checkpoint_contract_version: Literal["workflow_step_checkpoint.v1"] = (
        "workflow_step_checkpoint.v1"
    )
    execution_session_id: UUID
    step_ref: CheckpointReference
    resumed_from_page: int = Field(ge=0)
    pages_executed: int = Field(ge=0)
    database_writes: int = Field(ge=0)
    checkpoint_replay: bool
    terminal: bool
    next_cursor: CheckpointCursor | None = None
    records_count: int = Field(ge=0)
    checkpoints: list[WorkflowStepCheckpointResponse]

    @model_validator(mode="after")
    def validate_resume_state(self) -> Self:
        if self.database_writes != self.pages_executed:
            raise ValueError("workflow_checkpoint_write_count_invalid")
        if self.checkpoint_replay and (
            self.pages_executed != 0 or self.database_writes != 0 or not self.terminal
        ):
            raise ValueError("workflow_checkpoint_replay_state_invalid")
        if self.terminal == (self.next_cursor is not None):
            raise ValueError("workflow_checkpoint_result_cursor_state_invalid")
        return self


__all__ = [
    "CheckpointCursor",
    "WorkflowCheckpointPageResult",
    "WorkflowStepCheckpointResponse",
    "WorkflowStepResumeIdentity",
    "WorkflowStepResumeResult",
]
