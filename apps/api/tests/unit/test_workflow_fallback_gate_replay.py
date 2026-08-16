from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from data_intelligence_hub.services.workflow_execution.fallback import (
    FallbackGateReplayInput,
    compile_fallback_gate_replay,
)


def _input(**updates: object) -> FallbackGateReplayInput:
    payload: dict[str, object] = {
        "primary_failure_code": "step_network_unavailable",
        "primary_assertion_id": "fixture.primary:content:search_discover",
        "primary_implementation_id": "fixture.primary",
        "fallback_assertion_id": "fixture.fallback:content:search_discover",
        "fallback_implementation_id": "fixture.fallback",
        "fallback_capability_status": "verified",
        "fallback_route_eligible": True,
        "credential_status": "not_required",
        "policy_authorized": True,
        "policy_evidence_refs": ["policy:fixture-routing.v1"],
        "budget_evidence_status": "verified",
        "budget_unit_cost_usd": Decimal("0.02"),
        "budget_ceiling_usd": Decimal("0.05"),
        "field_evidence_status": "verified",
        "required_fields": ["id", "text", "url"],
        "missing_required_fields": [],
        "primary_missing_optional_fields": ["metrics"],
        "fallback_missing_optional_fields": ["author", "metrics"],
        "fallback_evidence_refs": ["evidence:fixture.fallback:content:search_discover"],
        "approval_required": False,
        "approval_status": "not_required",
        "approval_reasons": [],
    }
    payload.update(updates)
    return FallbackGateReplayInput.model_validate(payload)


def test_all_gates_pass_only_with_complete_authoritative_evidence() -> None:
    decision = compile_fallback_gate_replay(_input())

    assert decision.outcome == "eligible"
    assert decision.switch_executed is False
    assert [item.gate for item in decision.gates] == [
        "trigger",
        "policy",
        "credential",
        "budget",
        "fields",
        "evidence",
        "approval",
    ]
    assert {item.status for item in decision.gates} == {"passed"}
    assert decision.cost_snapshot.unit_cost_usd == Decimal("0.02")
    assert decision.cost_snapshot.within_ceiling is True
    assert decision.field_difference.missing_required_fields == []
    assert decision.decision_digest.startswith("sha256:")


def test_unknown_cost_fields_and_pending_approval_block_without_switching() -> None:
    decision = compile_fallback_gate_replay(
        _input(
            budget_evidence_status="unavailable",
            budget_unit_cost_usd=None,
            field_evidence_status="unavailable",
            approval_required=True,
            approval_status="pending",
            approval_reasons=["owner_approval_required"],
        )
    )
    gates = {item.gate: item for item in decision.gates}

    assert decision.outcome == "blocked"
    assert gates["budget"].code == "fallback_budget_evidence_unavailable"
    assert gates["fields"].code == "fallback_field_evidence_unavailable"
    assert gates["approval"].code == "fallback_approval_pending"
    assert decision.switch_executed is False


def test_terminal_primary_failure_and_missing_candidate_fail_closed() -> None:
    decision = compile_fallback_gate_replay(
        _input(
            primary_failure_code="step_request_rejected",
            fallback_assertion_id=None,
            fallback_implementation_id=None,
            fallback_capability_status=None,
            fallback_route_eligible=False,
            credential_status="not_checked",
            policy_authorized=False,
            fallback_evidence_refs=[],
            budget_evidence_status="unavailable",
            budget_unit_cost_usd=None,
            field_evidence_status="unavailable",
        )
    )
    gates = {item.gate: item for item in decision.gates}

    assert decision.outcome == "blocked"
    assert gates["trigger"].code == "fallback_trigger_terminal_failure"
    assert gates["policy"].code == "fallback_candidate_unavailable"
    assert gates["evidence"].code == "fallback_evidence_unavailable"


def test_input_rejects_partial_candidate_identity_and_inconsistent_approval() -> None:
    with pytest.raises(ValidationError, match="fallback_candidate_identity_invalid"):
        _input(fallback_assertion_id=None)
    with pytest.raises(ValidationError, match="fallback_approval_status_invalid"):
        _input(approval_required=True, approval_status="not_required")


def test_decision_digest_is_deterministic_and_sensitive_to_gate_evidence() -> None:
    first = compile_fallback_gate_replay(_input())
    second = compile_fallback_gate_replay(_input())
    changed = compile_fallback_gate_replay(
        _input(policy_evidence_refs=["policy:fixture-routing.v2"])
    )

    assert first == second
    assert first.decision_digest != changed.decision_digest
