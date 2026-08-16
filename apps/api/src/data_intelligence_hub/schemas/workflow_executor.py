from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal, Self, cast
from uuid import UUID

from pydantic import ConfigDict, Field, JsonValue, StringConstraints, model_validator

from data_intelligence_hub.schemas.workflow_execution import (
    Sha256Digest,
    WorkflowExecutionContract,
)

WorkflowExecutionEnvironment = Literal["local", "test", "staging", "production"]
WorkflowExecutionDispatchState = Literal["pending", "claimable", "terminal"]
WorkflowExecutionLeaseState = Literal[
    "active",
    "released",
    "expired",
    "superseded",
    "terminal",
]
WorkflowExecutionEventType = Literal[
    "dispatch_created",
    "dispatch_replayed",
    "lease_claimed",
    "lease_heartbeat",
    "lease_expired",
    "lease_taken_over",
    "lease_released",
    "preflight_blocked",
    "preflight_eligible",
    "credential_permit_issued",
    "credential_permit_consumed",
    "credential_resolution_failed",
    "provider_permit_issued",
    "provider_permit_consumed",
    "provider_permit_revoked",
    "provider_attempting",
    "provider_succeeded",
    "provider_failed",
    "provider_uncertain",
    "cancel_requested",
    "cancel_acknowledged",
    "terminal_committed",
]
WorkflowProviderTransportState = Literal[
    "not_attempted",
    "attempting",
    "succeeded",
    "failed",
    "uncertain",
]
WorkflowCancellationOutcome = Literal[
    "cancelled_before_effect",
    "cancelled_after_current_effect",
    "cancel_pending_external_outcome",
]

ExecutorIdentifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$",
    ),
]
ExecutorReasonCode = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z][a-z0-9_]*$",
    ),
]


def _require_utc(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("workflow_executor_time_utc_required")


def _canonical_json_bytes(value: JsonValue) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256_id(value: JsonValue) -> str:
    return f"sha256:{hashlib.sha256(_canonical_json_bytes(value)).hexdigest()}"


def canonical_workflow_execution_dispatch_key(
    *,
    workspace_id: UUID,
    project_id: UUID,
    workflow_plan_id: UUID,
    workflow_version_id: UUID,
    workflow_run_id: UUID,
    workflow_step_run_id: UUID,
    attempt_generation: int,
    source_action_request_id: UUID | None,
    source_action_receipt_id: UUID | None,
    workflow_version_digest: str,
    execution_policy_digest: str,
) -> str:
    return _sha256_id(
        cast(
            JsonValue,
            {
                "scope": "workflow_execution_dispatch.v1",
                "workspace_id": str(workspace_id),
                "project_id": str(project_id),
                "workflow_plan_id": str(workflow_plan_id),
                "workflow_version_id": str(workflow_version_id),
                "workflow_run_id": str(workflow_run_id),
                "workflow_step_run_id": str(workflow_step_run_id),
                "attempt_generation": attempt_generation,
                "source_action_request_id": (
                    None if source_action_request_id is None else str(source_action_request_id)
                ),
                "source_action_receipt_id": (
                    None if source_action_receipt_id is None else str(source_action_receipt_id)
                ),
                "workflow_version_digest": workflow_version_digest,
                "execution_policy_digest": execution_policy_digest,
            },
        )
    )


def canonical_workflow_provider_side_effect_key(
    *,
    dispatch_key: str,
    provider_id: str,
    operation_id: str,
) -> str:
    return _sha256_id(
        cast(
            JsonValue,
            {
                "scope": "workflow_provider_side_effect.v1",
                "dispatch_key": dispatch_key,
                "provider_id": provider_id,
                "operation_id": operation_id,
            },
        )
    )


class _FrozenWorkflowExecutorContract(WorkflowExecutionContract):
    model_config = ConfigDict(extra="forbid", from_attributes=True, frozen=True)


class WorkflowExecutionDispatch(_FrozenWorkflowExecutorContract):
    schema_version: Literal["workflow_execution_dispatch.v1"] = "workflow_execution_dispatch.v1"
    id: UUID
    workspace_id: UUID
    project_id: UUID
    workflow_plan_id: UUID
    workflow_version_id: UUID
    workflow_run_id: UUID
    workflow_step_run_id: UUID
    attempt_generation: int = Field(ge=0)
    source_action_request_id: UUID | None = None
    source_action_receipt_id: UUID | None = None
    workflow_version_digest: Sha256Digest
    execution_policy_digest: Sha256Digest
    dispatch_key: Sha256Digest
    provider_side_effect_key: Sha256Digest
    state: WorkflowExecutionDispatchState
    created_at: datetime
    database_write: Literal[False] = False
    credential_read_attempted: Literal[False] = False
    provider_call: Literal[False] = False
    network_call: Literal[False] = False
    production_write_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_dispatch(self) -> Self:
        _require_utc(self.created_at)
        if (self.source_action_request_id is None) != (self.source_action_receipt_id is None):
            raise ValueError("workflow_executor_action_lineage_pair_invalid")
        expected_key = canonical_workflow_execution_dispatch_key(
            workspace_id=self.workspace_id,
            project_id=self.project_id,
            workflow_plan_id=self.workflow_plan_id,
            workflow_version_id=self.workflow_version_id,
            workflow_run_id=self.workflow_run_id,
            workflow_step_run_id=self.workflow_step_run_id,
            attempt_generation=self.attempt_generation,
            source_action_request_id=self.source_action_request_id,
            source_action_receipt_id=self.source_action_receipt_id,
            workflow_version_digest=self.workflow_version_digest,
            execution_policy_digest=self.execution_policy_digest,
        )
        if self.dispatch_key != expected_key:
            raise ValueError("workflow_executor_dispatch_key_mismatch")
        return self


class WorkflowExecutionLeaseToken(_FrozenWorkflowExecutorContract):
    schema_version: Literal["workflow_execution_lease_token.v1"] = (
        "workflow_execution_lease_token.v1"
    )
    id: UUID
    dispatch_id: UUID
    workspace_id: UUID
    worker_id: ExecutorIdentifier
    fencing_token: int = Field(ge=1)
    version: int = Field(ge=1)
    claimed_at: datetime
    heartbeat_at: datetime
    expires_at: datetime
    state: WorkflowExecutionLeaseState

    @model_validator(mode="after")
    def validate_lease(self) -> Self:
        for value in (self.claimed_at, self.heartbeat_at, self.expires_at):
            _require_utc(value)
        if not self.claimed_at <= self.heartbeat_at < self.expires_at:
            raise ValueError("workflow_executor_lease_time_order_invalid")
        return self


class WorkflowExecutionEvent(_FrozenWorkflowExecutorContract):
    schema_version: Literal["workflow_execution_event.v1"] = "workflow_execution_event.v1"
    id: UUID
    dispatch_id: UUID
    workspace_id: UUID
    sequence: int = Field(ge=1)
    event_type: WorkflowExecutionEventType
    lease_id: UUID | None = None
    fencing_token: int | None = Field(default=None, ge=1)
    previous_event_digest: Sha256Digest | None
    event_digest: Sha256Digest
    occurred_at: datetime

    @model_validator(mode="after")
    def validate_event(self) -> Self:
        _require_utc(self.occurred_at)
        if (self.sequence == 1) != (self.previous_event_digest is None):
            raise ValueError("workflow_executor_event_chain_invalid")
        if (self.lease_id is None) != (self.fencing_token is None):
            raise ValueError("workflow_executor_event_lease_pair_invalid")
        return self


class _WorkflowExecutionPermit(_FrozenWorkflowExecutorContract):
    id: UUID
    dispatch_id: UUID
    workspace_id: UUID
    workflow_run_id: UUID
    workflow_step_run_id: UUID
    attempt_generation: int = Field(ge=0)
    provider_id: ExecutorIdentifier
    operation_id: ExecutorIdentifier
    environment: WorkflowExecutionEnvironment
    issued_at: datetime
    expires_at: datetime
    consumed_at: datetime | None = None
    revoked_at: datetime | None = None

    @model_validator(mode="after")
    def validate_permit_window(self) -> Self:
        for value in (self.issued_at, self.expires_at, self.consumed_at, self.revoked_at):
            if value is not None:
                _require_utc(value)
        if self.expires_at <= self.issued_at:
            raise ValueError("workflow_executor_permit_expiry_invalid")
        if self.consumed_at is not None and not (
            self.issued_at <= self.consumed_at < self.expires_at
        ):
            raise ValueError("workflow_executor_permit_consumed_time_invalid")
        if self.revoked_at is not None and self.revoked_at < self.issued_at:
            raise ValueError("workflow_executor_permit_revoked_time_invalid")
        if self.consumed_at is not None and self.revoked_at is not None:
            raise ValueError("workflow_executor_permit_terminal_state_invalid")
        return self


class WorkflowCredentialResolutionPermit(_WorkflowExecutionPermit):
    schema_version: Literal["workflow_credential_resolution_permit.v1"] = (
        "workflow_credential_resolution_permit.v1"
    )
    purpose: ExecutorIdentifier
    credential_reference_fingerprint: Sha256Digest


class WorkflowProviderCallPermit(_WorkflowExecutionPermit):
    schema_version: Literal["workflow_provider_call_permit.v1"] = "workflow_provider_call_permit.v1"
    preflight_id: Sha256Digest
    policy_digest: Sha256Digest
    side_effect_key: Sha256Digest
    max_cost_usd: Decimal = Field(ge=0, allow_inf_nan=False)
    max_quota_units: int = Field(ge=0)


class WorkflowProviderCallAudit(_FrozenWorkflowExecutorContract):
    schema_version: Literal["workflow_provider_call_audit.v1"] = "workflow_provider_call_audit.v1"
    id: UUID
    dispatch_id: UUID
    workspace_id: UUID
    workflow_run_id: UUID
    workflow_step_run_id: UUID
    attempt_generation: int = Field(ge=0)
    lease_id: UUID
    fencing_token: int = Field(ge=1)
    provider_id: ExecutorIdentifier
    operation_id: ExecutorIdentifier
    preflight_id: Sha256Digest
    policy_digest: Sha256Digest
    side_effect_key: Sha256Digest
    environment: WorkflowExecutionEnvironment
    attempt_ordinal: int = Field(ge=1)
    transport_state: WorkflowProviderTransportState
    outcome_code: ExecutorReasonCode | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @model_validator(mode="after")
    def validate_audit(self) -> Self:
        for value in (self.started_at, self.finished_at):
            if value is not None:
                _require_utc(value)
        if self.transport_state == "not_attempted":
            if self.started_at is not None or self.finished_at is not None:
                raise ValueError("workflow_executor_audit_not_attempted_time_invalid")
        elif self.transport_state == "attempting":
            if self.started_at is None or self.finished_at is not None:
                raise ValueError("workflow_executor_audit_attempt_time_invalid")
        else:
            if self.started_at is None or self.finished_at is None:
                raise ValueError("workflow_executor_audit_terminal_time_required")
            if self.finished_at < self.started_at:
                raise ValueError("workflow_executor_audit_time_order_invalid")
            if self.outcome_code is None:
                raise ValueError("workflow_executor_audit_outcome_code_required")
        return self


class WorkflowCancellationRequest(_FrozenWorkflowExecutorContract):
    schema_version: Literal["workflow_cancellation_request.v1"] = "workflow_cancellation_request.v1"
    id: UUID
    dispatch_id: UUID
    workspace_id: UUID
    workflow_run_id: UUID
    requested_by_user_id: UUID
    request_key: Sha256Digest
    reason_code: ExecutorReasonCode
    requested_at: datetime
    acknowledged: Literal[False] = False

    @model_validator(mode="after")
    def validate_request_time(self) -> Self:
        _require_utc(self.requested_at)
        return self


class WorkflowCancellationAcknowledgement(_FrozenWorkflowExecutorContract):
    schema_version: Literal["workflow_cancellation_acknowledgement.v1"] = (
        "workflow_cancellation_acknowledgement.v1"
    )
    id: UUID
    request_id: UUID
    dispatch_id: UUID
    workspace_id: UUID
    lease_id: UUID
    fencing_token: int = Field(ge=1)
    safe_point: ExecutorIdentifier
    outcome: WorkflowCancellationOutcome
    acknowledged_at: datetime

    @model_validator(mode="after")
    def validate_acknowledgement_time(self) -> Self:
        _require_utc(self.acknowledged_at)
        return self


__all__ = [
    "ExecutorIdentifier",
    "ExecutorReasonCode",
    "WorkflowCancellationAcknowledgement",
    "WorkflowCancellationOutcome",
    "WorkflowCancellationRequest",
    "WorkflowCredentialResolutionPermit",
    "WorkflowExecutionDispatch",
    "WorkflowExecutionDispatchState",
    "WorkflowExecutionEnvironment",
    "WorkflowExecutionEvent",
    "WorkflowExecutionEventType",
    "WorkflowExecutionLeaseState",
    "WorkflowExecutionLeaseToken",
    "WorkflowProviderCallAudit",
    "WorkflowProviderCallPermit",
    "WorkflowProviderTransportState",
    "canonical_workflow_execution_dispatch_key",
    "canonical_workflow_provider_side_effect_key",
]
