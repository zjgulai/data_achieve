from __future__ import annotations

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from data_intelligence_hub.schemas.workflow_execution import (
    Sha256Digest,
    WorkflowExecutionContract,
    WorkflowFixtureReadBoundary,
)
from data_intelligence_hub.schemas.workflow_executor import (
    WorkflowCancellationOutcome,
    WorkflowExecutionDispatchState,
    WorkflowExecutionEventType,
    WorkflowExecutionLeaseState,
    WorkflowProviderTransportState,
)


class WorkflowExecutorLeaseEvidence(WorkflowExecutionContract):
    id: UUID
    state: WorkflowExecutionLeaseState
    fencing_token: int = Field(ge=1)
    version: int = Field(ge=1)
    heartbeat_at: datetime
    expires_at: datetime
    fresh: bool


class WorkflowExecutorEventEvidence(WorkflowExecutionContract):
    id: UUID
    sequence: int = Field(ge=1)
    event_type: WorkflowExecutionEventType
    event_digest: Sha256Digest
    occurred_at: datetime


class WorkflowExecutorAuditEvidence(WorkflowExecutionContract):
    id: UUID
    attempt_ordinal: int = Field(ge=1)
    provider_id: str = Field(min_length=1, max_length=128)
    operation_id: str = Field(min_length=1, max_length=128)
    preflight_id: Sha256Digest
    transport_state: WorkflowProviderTransportState
    outcome_code: str | None = Field(default=None, min_length=1, max_length=100)
    environment: Literal["local", "test", "staging", "production"]
    started_at: datetime | None = None
    finished_at: datetime | None = None


class WorkflowExecutorCancellationEvidence(WorkflowExecutionContract):
    requested: bool
    acknowledged: bool
    request_id: UUID | None = None
    reason_code: str | None = Field(default=None, min_length=1, max_length=100)
    requested_at: datetime | None = None
    acknowledgement_id: UUID | None = None
    safe_point: str | None = Field(default=None, min_length=1, max_length=128)
    outcome: WorkflowCancellationOutcome | None = None
    acknowledged_at: datetime | None = None

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        request_values = (self.request_id, self.reason_code, self.requested_at)
        acknowledgement_values = (
            self.acknowledgement_id,
            self.safe_point,
            self.outcome,
            self.acknowledged_at,
        )
        if self.requested != all(value is not None for value in request_values):
            raise ValueError("workflow_executor_cancel_request_state_invalid")
        if self.acknowledged != all(value is not None for value in acknowledgement_values):
            raise ValueError("workflow_executor_cancel_ack_state_invalid")
        if self.acknowledged and not self.requested:
            raise ValueError("workflow_executor_cancel_ack_without_request")
        return self


class WorkflowExecutorDispatchEvidence(WorkflowExecutionContract):
    id: UUID
    workflow_step_run_id: UUID
    attempt_generation: int = Field(ge=0)
    source_action_request_id: UUID | None = None
    source_action_receipt_id: UUID | None = None
    state: WorkflowExecutionDispatchState
    created_at: datetime
    lease: WorkflowExecutorLeaseEvidence | None = None
    last_event: WorkflowExecutorEventEvidence | None = None
    preflight_state: Literal["not_evaluated", "blocked", "eligible"]
    preflight_blocker_codes: list[str]
    next_required_authority: Literal["exact_live_provider_call_authorization"] | None
    credential_permit_ids: list[UUID]
    provider_permit_ids: list[UUID]
    audits: list[WorkflowExecutorAuditEvidence]
    audit_total: int = Field(ge=0)
    budget_reservation_state: Literal["not_recorded"] = "not_recorded"
    cancellation: WorkflowExecutorCancellationEvidence

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.audit_total != len(self.audits):
            raise ValueError("workflow_executor_audit_total_invalid")
        if (self.preflight_state == "eligible") != (
            self.next_required_authority == "exact_live_provider_call_authorization"
        ):
            raise ValueError("workflow_executor_preflight_authority_state_invalid")
        if self.preflight_state == "blocked" and not self.preflight_blocker_codes:
            raise ValueError("workflow_executor_preflight_blocker_missing")
        if self.preflight_state != "blocked" and self.preflight_blocker_codes:
            raise ValueError("workflow_executor_preflight_blocker_unexpected")
        return self


class WorkflowExecutorEvidenceResponse(WorkflowFixtureReadBoundary):
    schema_version: Literal["workflow_executor_evidence.v1"] = "workflow_executor_evidence.v1"
    workspace_id: UUID
    project_id: UUID
    workflow_run_id: UUID
    evidence_grade: Literal["L2_fixture_local"] = "L2_fixture_local"
    environment: Literal["local"] = "local"
    evaluated_at: datetime
    dispatches: list[WorkflowExecutorDispatchEvidence]
    dispatch_total: int = Field(ge=0)
    business_cause_code: Literal[
        "executor_dispatch_not_created",
        "executor_dispatch_pending",
        "executor_preflight_blocked",
        "executor_waiting_exact_live_authority",
    ]
    business_impact_code: Literal[
        "workflow_execution_not_started",
        "workflow_execution_waiting",
    ]
    next_action_code: Literal[
        "review_action_receipt_and_dispatch_gate",
        "wait_for_disabled_executor_evidence",
        "resolve_preflight_blocker",
        "request_exact_live_provider_authorization",
    ]
    client_construction: Literal[False] = False
    network_call: Literal[False] = False
    live_provider_proof: Literal[False] = False

    @model_validator(mode="after")
    def validate_dispatch_total(self) -> Self:
        if self.dispatch_total != len(self.dispatches):
            raise ValueError("workflow_executor_dispatch_total_invalid")
        return self


__all__ = [
    "WorkflowExecutorAuditEvidence",
    "WorkflowExecutorCancellationEvidence",
    "WorkflowExecutorDispatchEvidence",
    "WorkflowExecutorEvidenceResponse",
    "WorkflowExecutorEventEvidence",
    "WorkflowExecutorLeaseEvidence",
]
