from __future__ import annotations

from decimal import Decimal
from typing import Literal, Self, cast

from pydantic import ConfigDict, Field, JsonValue, model_validator

from data_intelligence_hub.schemas.capability_catalog import CapabilityStatus
from data_intelligence_hub.schemas.workflow_execution import (
    Sha256Digest,
    WorkflowExecutionContract,
)
from data_intelligence_hub.schemas.workflow_planner import AuthReadiness
from data_intelligence_hub.services.workflow_planner.fingerprint import sha256_id

FallbackEvidenceStatus = Literal["verified", "unavailable"]
FallbackApprovalStatus = Literal[
    "not_required",
    "approved",
    "pending",
    "rejected",
    "unavailable",
]
FallbackGateName = Literal[
    "trigger",
    "policy",
    "credential",
    "budget",
    "fields",
    "evidence",
    "approval",
]

RETRYABLE_FALLBACK_FAILURE_CODES = frozenset(
    {
        "step_network_unavailable",
        "step_rate_limited",
        "step_timeout",
    }
)


class _FrozenFallbackContract(WorkflowExecutionContract):
    model_config = ConfigDict(extra="forbid", from_attributes=True, frozen=True)


class FallbackGateReplayInput(_FrozenFallbackContract):
    primary_failure_code: str = Field(min_length=1, max_length=100)
    primary_assertion_id: str = Field(min_length=1, max_length=500)
    primary_implementation_id: str = Field(min_length=1, max_length=500)
    fallback_assertion_id: str | None = Field(default=None, min_length=1, max_length=500)
    fallback_implementation_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
    )
    fallback_capability_status: CapabilityStatus | None = None
    fallback_route_eligible: bool
    credential_status: AuthReadiness
    policy_authorized: bool
    policy_evidence_refs: list[str] = Field(max_length=64)
    budget_evidence_status: FallbackEvidenceStatus
    budget_unit_cost_usd: Decimal | None = Field(default=None, ge=0)
    budget_ceiling_usd: Decimal | None = Field(default=None, ge=0)
    field_evidence_status: FallbackEvidenceStatus
    required_fields: list[str] = Field(max_length=256)
    missing_required_fields: list[str] = Field(max_length=256)
    primary_missing_optional_fields: list[str] = Field(max_length=256)
    fallback_missing_optional_fields: list[str] = Field(max_length=256)
    fallback_evidence_refs: list[str] = Field(max_length=64)
    approval_required: bool
    approval_status: FallbackApprovalStatus
    approval_reasons: list[str] = Field(max_length=64)

    @model_validator(mode="after")
    def validate_gate_evidence(self) -> Self:
        candidate_parts = (
            self.fallback_assertion_id,
            self.fallback_implementation_id,
            self.fallback_capability_status,
        )
        if any(item is None for item in candidate_parts) != all(
            item is None for item in candidate_parts
        ):
            raise ValueError("fallback_candidate_identity_invalid")
        if self.approval_required and self.approval_status == "not_required":
            raise ValueError("fallback_approval_status_invalid")
        if not self.approval_required and self.approval_status != "not_required":
            raise ValueError("fallback_approval_status_invalid")
        if (
            self.budget_evidence_status == "verified"
            and self.budget_ceiling_usd is not None
            and self.budget_unit_cost_usd is None
        ):
            raise ValueError("fallback_budget_evidence_invalid")
        for values in (
            self.policy_evidence_refs,
            self.required_fields,
            self.missing_required_fields,
            self.primary_missing_optional_fields,
            self.fallback_missing_optional_fields,
            self.fallback_evidence_refs,
            self.approval_reasons,
        ):
            if len(values) != len(set(values)) or any(not item for item in values):
                raise ValueError("fallback_gate_evidence_invalid")
        return self


class FallbackGateResult(_FrozenFallbackContract):
    gate: FallbackGateName
    status: Literal["passed", "blocked"]
    code: str = Field(min_length=1, max_length=100)
    evidence_refs: list[str] = Field(max_length=128)


class FallbackFieldDifference(_FrozenFallbackContract):
    evidence_status: FallbackEvidenceStatus
    required_fields: list[str]
    missing_required_fields: list[str]
    primary_missing_optional_fields: list[str]
    fallback_missing_optional_fields: list[str]


class FallbackCostSnapshot(_FrozenFallbackContract):
    evidence_status: FallbackEvidenceStatus
    currency: Literal["USD"] = "USD"
    unit_cost_usd: Decimal | None
    ceiling_usd: Decimal | None
    within_ceiling: bool | None


class FallbackDecisionDraft(_FrozenFallbackContract):
    contract_version: Literal["workflow_fallback_gate_replay.v1"]
    decision_digest: Sha256Digest
    primary_failure_code: str
    primary_assertion_id: str
    primary_implementation_id: str
    fallback_assertion_id: str | None
    fallback_implementation_id: str | None
    outcome: Literal["eligible", "blocked"]
    gates: list[FallbackGateResult]
    field_difference: FallbackFieldDifference
    cost_snapshot: FallbackCostSnapshot
    evidence_refs: list[str]
    approval_required: bool
    approval_status: FallbackApprovalStatus
    switch_executed: Literal[False] = False
    provider_call_attempted: Literal[False] = False
    credential_read_attempted: Literal[False] = False
    actor_run: Literal[False] = False
    browser_run: Literal[False] = False
    llm_call: Literal[False] = False
    production_write_allowed: Literal[False] = False


def _gate(
    name: FallbackGateName,
    *,
    passed: bool,
    code: str,
    evidence_refs: list[str] | None = None,
) -> FallbackGateResult:
    return FallbackGateResult(
        gate=name,
        status="passed" if passed else "blocked",
        code=code,
        evidence_refs=sorted(set(evidence_refs or [])),
    )


def compile_fallback_gate_replay(
    replay: FallbackGateReplayInput,
) -> FallbackDecisionDraft:
    candidate_available = replay.fallback_implementation_id is not None
    trigger_passed = replay.primary_failure_code in RETRYABLE_FALLBACK_FAILURE_CODES
    policy_passed = bool(
        candidate_available
        and replay.policy_authorized
        and replay.fallback_route_eligible
        and replay.fallback_capability_status is CapabilityStatus.VERIFIED
    )
    credential_passed = bool(
        candidate_available
        and replay.credential_status in {AuthReadiness.NOT_REQUIRED, AuthReadiness.READY}
    )

    within_ceiling: bool | None = None
    if not candidate_available:
        budget_passed = False
        budget_code = "fallback_candidate_unavailable"
    elif replay.budget_ceiling_usd is None:
        budget_passed = True
        budget_code = "fallback_budget_not_applicable"
    elif replay.budget_evidence_status == "unavailable":
        budget_passed = False
        budget_code = "fallback_budget_evidence_unavailable"
    elif replay.budget_unit_cost_usd is None:
        budget_passed = False
        budget_code = "fallback_budget_cost_unknown"
    else:
        within_ceiling = replay.budget_unit_cost_usd <= replay.budget_ceiling_usd
        budget_passed = within_ceiling
        budget_code = (
            "fallback_budget_within_ceiling"
            if within_ceiling
            else "fallback_budget_ceiling_exceeded"
        )

    if not candidate_available:
        fields_passed = False
        fields_code = "fallback_candidate_unavailable"
    elif replay.field_evidence_status == "unavailable":
        fields_passed = False
        fields_code = "fallback_field_evidence_unavailable"
    elif replay.missing_required_fields:
        fields_passed = False
        fields_code = "fallback_required_fields_missing"
    else:
        fields_passed = True
        fields_code = "fallback_required_fields_satisfied"

    evidence_passed = bool(candidate_available and replay.fallback_evidence_refs)
    approval_passed = replay.approval_status in {"not_required", "approved"}
    gates = [
        _gate(
            "trigger",
            passed=trigger_passed,
            code=(
                "fallback_trigger_retryable_failure"
                if trigger_passed
                else "fallback_trigger_terminal_failure"
            ),
        ),
        _gate(
            "policy",
            passed=policy_passed,
            code=(
                "fallback_policy_passed"
                if policy_passed
                else (
                    "fallback_candidate_unavailable"
                    if not candidate_available
                    else "fallback_policy_blocked"
                )
            ),
            evidence_refs=replay.policy_evidence_refs,
        ),
        _gate(
            "credential",
            passed=credential_passed,
            code=(
                "fallback_credential_passed"
                if credential_passed
                else "fallback_credential_unavailable"
            ),
        ),
        _gate("budget", passed=budget_passed, code=budget_code),
        _gate("fields", passed=fields_passed, code=fields_code),
        _gate(
            "evidence",
            passed=evidence_passed,
            code=(
                "fallback_evidence_present" if evidence_passed else "fallback_evidence_unavailable"
            ),
            evidence_refs=replay.fallback_evidence_refs,
        ),
        _gate(
            "approval",
            passed=approval_passed,
            code=(
                "fallback_approval_passed"
                if approval_passed
                else f"fallback_approval_{replay.approval_status}"
            ),
        ),
    ]
    field_difference = FallbackFieldDifference(
        evidence_status=replay.field_evidence_status,
        required_fields=sorted(set(replay.required_fields)),
        missing_required_fields=sorted(set(replay.missing_required_fields)),
        primary_missing_optional_fields=sorted(set(replay.primary_missing_optional_fields)),
        fallback_missing_optional_fields=sorted(set(replay.fallback_missing_optional_fields)),
    )
    cost_snapshot = FallbackCostSnapshot(
        evidence_status=replay.budget_evidence_status,
        unit_cost_usd=replay.budget_unit_cost_usd,
        ceiling_usd=replay.budget_ceiling_usd,
        within_ceiling=within_ceiling,
    )
    payload = cast(
        dict[str, JsonValue],
        {
            "contract_version": "workflow_fallback_gate_replay.v1",
            "primary_failure_code": replay.primary_failure_code,
            "primary_assertion_id": replay.primary_assertion_id,
            "primary_implementation_id": replay.primary_implementation_id,
            "fallback_assertion_id": replay.fallback_assertion_id,
            "fallback_implementation_id": replay.fallback_implementation_id,
            "outcome": (
                "eligible" if all(item.status == "passed" for item in gates) else "blocked"
            ),
            "gates": [item.model_dump(mode="json") for item in gates],
            "field_difference": field_difference.model_dump(mode="json"),
            "cost_snapshot": cost_snapshot.model_dump(mode="json"),
            "evidence_refs": sorted(
                set(replay.policy_evidence_refs + replay.fallback_evidence_refs)
            ),
            "approval_required": replay.approval_required,
            "approval_status": replay.approval_status,
            "switch_executed": False,
            "provider_call_attempted": False,
            "credential_read_attempted": False,
            "actor_run": False,
            "browser_run": False,
            "llm_call": False,
            "production_write_allowed": False,
        },
    )
    return FallbackDecisionDraft.model_validate(
        {
            **payload,
            "decision_digest": sha256_id(cast(JsonValue, payload)),
        }
    )


__all__ = [
    "FallbackDecisionDraft",
    "FallbackGateReplayInput",
    "FallbackGateResult",
    "compile_fallback_gate_replay",
]
