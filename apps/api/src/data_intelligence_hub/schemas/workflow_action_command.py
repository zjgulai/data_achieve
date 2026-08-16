from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal, Self, cast
from uuid import UUID

from pydantic import (
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
    model_validator,
)

from data_intelligence_hub.schemas.workflow_action_gate import (
    WORKFLOW_RUN_ACTION_ORDER,
    WorkflowRunAction,
    WorkflowRunActionGatesResponse,
    WorkflowRunActionPreconditionBlockerCode,
    WorkflowRunActionPreconditionStatus,
)
from data_intelligence_hub.schemas.workflow_execution import (
    Sha256Digest,
    WorkflowExecutionContract,
    WorkflowFixtureReadBoundary,
    WorkflowRunStatus,
)

WorkflowActionApprovalKind = Literal[
    "owner_confirmation",
    "owner_policy_override",
    "owner_route_override",
]
WorkflowActionReasonCode = Literal[
    "retry_after_retryable_failure",
    "resume_from_confirmed_checkpoint",
    "cancel_operator_request",
    "cancel_policy_violation",
    "budget_override_business_exception",
    "route_switch_verified_fallback",
    "override_revoked_before_consumption",
]
WorkflowActionAvailabilityBlockerCode = Literal[
    "workflow_action_owner_required",
    "workflow_action_approval_required",
    "workflow_action_persistence_unavailable",
    "workflow_action_executor_ack_unavailable",
]
WorkflowActionOutcome = Literal[
    "accepted",
    "accepted_pending_executor_ack",
]
WorkflowActionReceiptNextActionCode = Literal[
    "await_fixture_executor",
    "refresh_workflow_run",
    "workflow_run_cancelled",
    "review_resume_after_budget_override",
    "review_retry_after_route_override",
]

WORKFLOW_ACTION_APPROVAL_KIND_BY_ACTION: dict[
    WorkflowRunAction,
    WorkflowActionApprovalKind,
] = {
    "retry": "owner_confirmation",
    "resume": "owner_confirmation",
    "cancel": "owner_confirmation",
    "budget_override": "owner_policy_override",
    "route_switch": "owner_route_override",
}
WORKFLOW_ACTION_REASON_CODES_BY_ACTION: dict[
    WorkflowRunAction,
    frozenset[WorkflowActionReasonCode],
] = {
    "retry": frozenset({"retry_after_retryable_failure"}),
    "resume": frozenset({"resume_from_confirmed_checkpoint"}),
    "cancel": frozenset({"cancel_operator_request", "cancel_policy_violation"}),
    "budget_override": frozenset(
        {
            "budget_override_business_exception",
            "override_revoked_before_consumption",
        }
    ),
    "route_switch": frozenset(
        {
            "route_switch_verified_fallback",
            "override_revoked_before_consumption",
        }
    ),
}

WorkflowActionReason = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
ImplementationId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=500,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$",
    ),
]

_CONTROL_CHARACTER_RE = re.compile(r"[\x00-\x1f\x7f]")
_SENSITIVE_REASON_RE = re.compile(
    r"(?i)(authorization\s*:|bearer\s+|api[_ -]?key|password|"
    r"access[_ -]?token|refresh[_ -]?token|secret[_ -]?key|"
    r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|"
    r"\b(?:\+?\d[\d ()-]{7,}\d)\b|"
    r"\b(?:\d[ -]*?){13,19}\b)"
)


class _FrozenWorkflowActionContract(WorkflowExecutionContract):
    model_config = ConfigDict(extra="forbid", from_attributes=True, frozen=True)


class RetryActionParameters(_FrozenWorkflowActionContract):
    action: Literal["retry"] = "retry"
    target_step_run_ids: list[UUID] = Field(min_length=1, max_length=128)
    expected_retry_generation: int = Field(ge=0)
    attempt_evidence_digest: Sha256Digest
    retry_policy_digest: Sha256Digest

    @model_validator(mode="after")
    def validate_target_steps(self) -> Self:
        if len(self.target_step_run_ids) != len(set(self.target_step_run_ids)):
            raise ValueError("workflow_action_retry_target_duplicate")
        return self


class ResumeActionParameters(_FrozenWorkflowActionContract):
    action: Literal["resume"] = "resume"
    checkpoint_digest: Sha256Digest
    budget_policy_digest: Sha256Digest
    budget_ledger_digest: Sha256Digest


class CancelActionParameters(_FrozenWorkflowActionContract):
    action: Literal["cancel"] = "cancel"
    cancel_scope: Literal["held_run", "running_run"]


class BudgetOverrideActionParameters(_FrozenWorkflowActionContract):
    action: Literal["budget_override"] = "budget_override"
    request_limit: int = Field(ge=0)
    item_limit: int = Field(ge=0)
    quota_unit_limit: int = Field(ge=0)
    cost_limit_usd: Decimal = Field(ge=0, allow_inf_nan=False)
    time_limit_ms: int = Field(ge=1)
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def validate_expiry_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("workflow_action_expiry_timezone_required")
        return value


class RouteSwitchActionParameters(_FrozenWorkflowActionContract):
    action: Literal["route_switch"] = "route_switch"
    step_run_id: UUID
    primary_implementation_id: ImplementationId
    fallback_implementation_id: ImplementationId
    fallback_decision_digest: Sha256Digest
    field_difference_digest: Sha256Digest
    cost_digest: Sha256Digest
    provider_health_digest: Sha256Digest

    @model_validator(mode="after")
    def validate_route_identity(self) -> Self:
        if self.primary_implementation_id == self.fallback_implementation_id:
            raise ValueError("workflow_action_route_identity_invalid")
        return self


WorkflowActionParameters = Annotated[
    RetryActionParameters
    | ResumeActionParameters
    | CancelActionParameters
    | BudgetOverrideActionParameters
    | RouteSwitchActionParameters,
    Field(discriminator="action"),
]


class _WorkflowActionProposal(_FrozenWorkflowActionContract):
    action: WorkflowRunAction
    expected_action_context_version: int = Field(ge=1)
    expected_run_status: WorkflowRunStatus
    action_gate_digest: Sha256Digest
    reason_code: WorkflowActionReasonCode
    reason: WorkflowActionReason
    parameters: WorkflowActionParameters

    @field_validator("reason", mode="after")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        if _CONTROL_CHARACTER_RE.search(value) or _SENSITIVE_REASON_RE.search(value):
            raise ValueError("workflow_action_reason_invalid")
        return value

    @model_validator(mode="after")
    def validate_action_proposal(self) -> Self:
        if self.parameters.action != self.action:
            raise ValueError("workflow_action_parameters_invalid")
        if self.reason_code not in WORKFLOW_ACTION_REASON_CODES_BY_ACTION[self.action]:
            raise ValueError("workflow_action_reason_code_invalid")
        if self.action == "cancel":
            if self.expected_run_status not in {
                WorkflowRunStatus.HELD,
                WorkflowRunStatus.RUNNING,
            }:
                raise ValueError("workflow_action_expected_status_invalid")
            expected_scope = (
                "held_run" if self.expected_run_status is WorkflowRunStatus.HELD else "running_run"
            )
            if (
                not isinstance(self.parameters, CancelActionParameters)
                or self.parameters.cancel_scope != expected_scope
            ):
                raise ValueError("workflow_action_cancel_scope_invalid")
        elif self.expected_run_status is not WorkflowRunStatus.HELD:
            raise ValueError("workflow_action_expected_status_invalid")
        return self


class WorkflowActionApprovalRequest(_WorkflowActionProposal):
    schema_version: Literal["workflow_action_approval_request.v1"] = (
        "workflow_action_approval_request.v1"
    )
    approval_kind: WorkflowActionApprovalKind

    @model_validator(mode="after")
    def validate_approval_kind(self) -> Self:
        if self.approval_kind != WORKFLOW_ACTION_APPROVAL_KIND_BY_ACTION[self.action]:
            raise ValueError("workflow_action_approval_kind_invalid")
        return self


class WorkflowRunActionRequest(_WorkflowActionProposal):
    schema_version: Literal["workflow_run_action_request.v1"] = "workflow_run_action_request.v1"
    approval_receipt_id: UUID


WorkflowActionProposalRequest = WorkflowActionApprovalRequest | WorkflowRunActionRequest


class WorkflowRunActionGateV2Evidence(_FrozenWorkflowActionContract):
    action: WorkflowRunAction
    precondition_status: WorkflowRunActionPreconditionStatus
    precondition_blocker_codes: list[WorkflowRunActionPreconditionBlockerCode] = Field(
        max_length=16
    )
    submission_available: bool
    availability_blocker_codes: list[WorkflowActionAvailabilityBlockerCode] = Field(max_length=8)
    approval_kind: WorkflowActionApprovalKind
    approval_receipt_required: Literal[True] = True
    evidence_refs: list[str] = Field(min_length=1, max_length=32)
    expires_at: datetime

    @model_validator(mode="after")
    def validate_submission_gate(self) -> Self:
        if len(self.precondition_blocker_codes) != len(set(self.precondition_blocker_codes)):
            raise ValueError("workflow_run_action_precondition_blocker_duplicate")
        if len(self.availability_blocker_codes) != len(set(self.availability_blocker_codes)):
            raise ValueError("workflow_action_availability_blocker_duplicate")
        if len(self.evidence_refs) != len(set(self.evidence_refs)) or any(
            not value for value in self.evidence_refs
        ):
            raise ValueError("workflow_run_action_evidence_refs_invalid")
        if self.approval_kind != WORKFLOW_ACTION_APPROVAL_KIND_BY_ACTION[self.action]:
            raise ValueError("workflow_action_approval_kind_invalid")
        if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
            raise ValueError("workflow_action_expiry_timezone_required")
        expected_available = (
            self.precondition_status == "ready_for_review"
            and not self.precondition_blocker_codes
            and not self.availability_blocker_codes
        )
        if self.submission_available != expected_available:
            raise ValueError("workflow_action_submission_availability_invalid")
        if self.precondition_status == "ready_for_review":
            if self.precondition_blocker_codes:
                raise ValueError("workflow_run_action_ready_blockers_invalid")
        elif not self.precondition_blocker_codes:
            raise ValueError("workflow_run_action_blockers_required")
        return self


class WorkflowRunActionGatesV2Response(WorkflowFixtureReadBoundary):
    schema_version: Literal["workflow_run_action_gates.v2"] = "workflow_run_action_gates.v2"
    workspace_id: UUID
    project_id: UUID
    workflow_plan_id: UUID
    workflow_version_id: UUID
    workflow_run_id: UUID
    run_status: WorkflowRunStatus
    action_gate_digest: Sha256Digest
    action_context_version: int = Field(ge=1)
    gates: list[WorkflowRunActionGateV2Evidence] = Field(
        min_length=5,
        max_length=5,
    )
    ready_for_review_total: int = Field(ge=0, le=5)
    blocked_total: int = Field(ge=0, le=5)
    not_applicable_total: int = Field(ge=0, le=5)
    available_action_total: int = Field(ge=0, le=5)
    mutation_endpoints_available: Literal[True] = True
    durable_action_audit_available: Literal[True] = True
    action_mutation_executed: Literal[False] = False

    @model_validator(mode="after")
    def validate_action_gates(self) -> Self:
        if tuple(item.action for item in self.gates) != WORKFLOW_RUN_ACTION_ORDER:
            raise ValueError("workflow_run_action_gate_order_invalid")
        expected = {
            "ready_for_review": self.ready_for_review_total,
            "blocked": self.blocked_total,
            "not_applicable": self.not_applicable_total,
        }
        for status, total in expected.items():
            if total != sum(item.precondition_status == status for item in self.gates):
                raise ValueError("workflow_run_action_gate_total_invalid")
        if self.available_action_total != sum(item.submission_available for item in self.gates):
            raise ValueError("workflow_action_available_total_invalid")
        return self


WorkflowRunActionGatesCurrentResponse = Annotated[
    WorkflowRunActionGatesResponse | WorkflowRunActionGatesV2Response,
    Field(discriminator="schema_version"),
]


class WorkflowActionApprovalReceipt(_FrozenWorkflowActionContract):
    schema_version: Literal["workflow_action_approval_receipt.v1"] = (
        "workflow_action_approval_receipt.v1"
    )
    id: UUID
    workspace_id: UUID
    project_id: UUID
    workflow_run_id: UUID
    approver_user_id: UUID
    action: WorkflowRunAction
    approval_kind: WorkflowActionApprovalKind
    proposal_digest: Sha256Digest
    expected_action_context_version: int = Field(ge=1)
    expected_run_status: WorkflowRunStatus
    action_gate_digest: Sha256Digest
    evidence_digests: list[Sha256Digest] = Field(min_length=1, max_length=32)
    reason_code: WorkflowActionReasonCode
    reason: WorkflowActionReason
    issued_at: datetime
    expires_at: datetime
    database_write: bool = False
    idempotent_replay: bool = False
    provider_call: Literal[False] = False
    credential_read_attempted: Literal[False] = False
    execution_started: Literal[False] = False
    production_write_allowed: Literal[False] = False

    @field_validator("reason", mode="after")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        if _CONTROL_CHARACTER_RE.search(value) or _SENSITIVE_REASON_RE.search(value):
            raise ValueError("workflow_action_reason_invalid")
        return value

    @model_validator(mode="after")
    def validate_approval_receipt(self) -> Self:
        if self.approval_kind != WORKFLOW_ACTION_APPROVAL_KIND_BY_ACTION[self.action]:
            raise ValueError("workflow_action_approval_kind_invalid")
        if self.reason_code not in WORKFLOW_ACTION_REASON_CODES_BY_ACTION[self.action]:
            raise ValueError("workflow_action_reason_code_invalid")
        if self.issued_at.tzinfo is None or self.issued_at.utcoffset() is None:
            raise ValueError("workflow_action_approval_time_invalid")
        if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
            raise ValueError("workflow_action_approval_time_invalid")
        if not self.issued_at < self.expires_at <= self.issued_at + timedelta(minutes=15):
            raise ValueError("workflow_action_approval_expiry_invalid")
        if len(self.evidence_digests) != len(set(self.evidence_digests)):
            raise ValueError("workflow_action_approval_evidence_duplicate")
        if self.idempotent_replay and self.database_write:
            raise ValueError("workflow_action_replay_write_invalid")
        return self


class WorkflowActionReceipt(_FrozenWorkflowActionContract):
    schema_version: Literal["workflow_action_receipt.v1"] = "workflow_action_receipt.v1"
    id: UUID
    request_id: UUID
    workspace_id: UUID
    project_id: UUID
    workflow_run_id: UUID
    action: WorkflowRunAction
    outcome: WorkflowActionOutcome
    before_action_context_version: int = Field(ge=1)
    after_action_context_version: int = Field(ge=1)
    before_run_status: WorkflowRunStatus
    after_run_status: WorkflowRunStatus
    state_changed: bool
    database_write: bool
    idempotent_replay: bool
    provider_call: Literal[False] = False
    credential_read_attempted: Literal[False] = False
    execution_started: Literal[False] = False
    production_write_allowed: Literal[False] = False
    next_action_code: WorkflowActionReceiptNextActionCode
    receipt_digest: Sha256Digest
    created_at: datetime

    @model_validator(mode="after")
    def validate_receipt(self) -> Self:
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("workflow_action_receipt_time_invalid")
        if self.idempotent_replay:
            if self.database_write:
                raise ValueError("workflow_action_replay_write_invalid")
        elif not self.database_write:
            raise ValueError("workflow_action_accept_write_required")
        expected_after_version = self.before_action_context_version + 1
        if self.after_action_context_version != expected_after_version:
            raise ValueError("workflow_action_context_version_invalid")
        if self.outcome == "accepted_pending_executor_ack" and self.action != "cancel":
            raise ValueError("workflow_action_pending_ack_invalid")
        return self


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


def _proposal_payload(
    request: WorkflowActionProposalRequest,
) -> dict[str, JsonValue]:
    payload = request.model_dump(mode="json")
    payload.pop("schema_version", None)
    payload.pop("approval_receipt_id", None)
    payload.pop("approval_kind", None)
    return cast(dict[str, JsonValue], payload)


def canonical_workflow_action_proposal_hash(
    *,
    workspace_id: UUID,
    project_id: UUID,
    workflow_run_id: UUID,
    request: WorkflowActionProposalRequest,
) -> str:
    return _sha256_id(
        cast(
            JsonValue,
            {
                "scope": "workflow_action_proposal.v1",
                "workspace_id": str(workspace_id),
                "project_id": str(project_id),
                "workflow_run_id": str(workflow_run_id),
                "proposal": _proposal_payload(request),
            },
        )
    )


def canonical_workflow_action_request_hash(
    *,
    workspace_id: UUID,
    project_id: UUID,
    workflow_run_id: UUID,
    request: WorkflowRunActionRequest,
) -> str:
    return _sha256_id(
        cast(
            JsonValue,
            {
                "scope": (f"workflow_run_action.v1:{project_id}:{workflow_run_id}"),
                "workspace_id": str(workspace_id),
                "project_id": str(project_id),
                "workflow_run_id": str(workflow_run_id),
                "request": cast(
                    JsonValue,
                    request.model_dump(mode="json"),
                ),
            },
        )
    )


__all__ = [
    "WORKFLOW_ACTION_APPROVAL_KIND_BY_ACTION",
    "WORKFLOW_ACTION_REASON_CODES_BY_ACTION",
    "BudgetOverrideActionParameters",
    "CancelActionParameters",
    "ResumeActionParameters",
    "RetryActionParameters",
    "RouteSwitchActionParameters",
    "WorkflowActionApprovalKind",
    "WorkflowActionApprovalReceipt",
    "WorkflowActionApprovalRequest",
    "WorkflowActionAvailabilityBlockerCode",
    "WorkflowActionOutcome",
    "WorkflowActionParameters",
    "WorkflowActionProposalRequest",
    "WorkflowActionReasonCode",
    "WorkflowActionReceipt",
    "WorkflowActionReceiptNextActionCode",
    "WorkflowRunActionGateV2Evidence",
    "WorkflowRunActionGatesCurrentResponse",
    "WorkflowRunActionGatesV2Response",
    "WorkflowRunActionRequest",
    "canonical_workflow_action_proposal_hash",
    "canonical_workflow_action_request_hash",
]
