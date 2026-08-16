from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from data_intelligence_hub.schemas.workflow_attempt_fallback import (
    WorkflowAttemptFallbackEvidenceResponse,
    WorkflowFallbackDecisionEvidenceResponse,
    WorkflowStepAttemptEvidenceResponse,
)

NOW = datetime(2026, 7, 24, 9, 0, tzinfo=UTC)


def _attempt(**overrides: object) -> WorkflowStepAttemptEvidenceResponse:
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "workspace_id": uuid.uuid4(),
        "project_id": uuid.uuid4(),
        "workflow_run_id": uuid.uuid4(),
        "step_run_id": uuid.uuid4(),
        "attempt_number": 1,
        "attempt_key_hash": "sha256:" + "a" * 64,
        "status": "succeeded",
        "error_code": None,
        "backoff_ms": 0,
        "started_at": NOW,
        "finished_at": NOW + timedelta(seconds=1),
        "created_at": NOW + timedelta(seconds=1),
    }
    values.update(overrides)
    return WorkflowStepAttemptEvidenceResponse.model_validate(values)


def _fallback(**overrides: object) -> WorkflowFallbackDecisionEvidenceResponse:
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "workspace_id": uuid.uuid4(),
        "project_id": uuid.uuid4(),
        "workflow_plan_id": uuid.uuid4(),
        "workflow_version_id": uuid.uuid4(),
        "workflow_run_id": uuid.uuid4(),
        "step_run_id": uuid.uuid4(),
        "created_by_user_id": uuid.uuid4(),
        "step_ref": "step.reddit.search",
        "requirement_ref": "requirement.reddit.posts",
        "contract_version": "workflow_fallback_gate_replay.v1",
        "decision_digest": "sha256:" + "b" * 64,
        "primary_failure_code": "step_rate_limited",
        "primary_assertion_id": "assertion.reddit.search.primary",
        "primary_implementation_id": "fixture.reddit.search.v1",
        "fallback_assertion_id": "assertion.reddit.search.fallback",
        "fallback_implementation_id": "fixture.reddit.search.fallback.v1",
        "outcome": "blocked",
        "gate_snapshot": [
            {
                "gate": gate,
                "status": "blocked" if gate == "approval" else "passed",
                "code": f"fallback_{gate}_recorded",
                "evidence_refs": [],
            }
            for gate in (
                "trigger",
                "policy",
                "credential",
                "budget",
                "fields",
                "evidence",
                "approval",
            )
        ],
        "field_difference": {
            "evidence_status": "verified",
            "required_fields": ["post.id"],
            "missing_required_fields": [],
            "primary_missing_optional_fields": [],
            "fallback_missing_optional_fields": ["author.country"],
        },
        "cost_snapshot": {
            "evidence_status": "verified",
            "currency": "USD",
            "unit_cost_usd": "0.01",
            "ceiling_usd": "0.02",
            "within_ceiling": True,
        },
        "evidence_refs": ["fixture://reddit/fallback/001"],
        "approval_required": True,
        "approval_status": "pending",
        "switch_executed": False,
        "created_at": NOW,
    }
    values.update(overrides)
    return WorkflowFallbackDecisionEvidenceResponse.model_validate(values)


def test_attempt_and_fallback_evidence_accepts_readonly_owned_sequence() -> None:
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    run_id = uuid.uuid4()
    step_id = uuid.uuid4()
    attempts = [
        _attempt(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            step_run_id=step_id,
            status="retryable_error",
            error_code="step_rate_limited",
            backoff_ms=500,
        ),
        _attempt(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            step_run_id=step_id,
            attempt_number=2,
            attempt_key_hash="sha256:" + "c" * 64,
        ),
    ]
    fallback = _fallback(
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
        step_run_id=step_id,
    )

    response = WorkflowAttemptFallbackEvidenceResponse(
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
        attempts=attempts,
        fallback_decisions=[fallback],
        attempt_total=2,
        fallback_decision_total=1,
    )

    assert response.schema_version == "workflow_attempt_fallback_evidence.v1"
    assert response.database_write is False
    assert response.provider_call is False
    assert response.fallback_decisions[0].switch_executed is False


def test_attempt_evidence_rejects_non_contiguous_numbers_and_side_effect_claims() -> None:
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    run_id = uuid.uuid4()
    step_id = uuid.uuid4()
    invalid = _attempt(
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
        step_run_id=step_id,
        attempt_number=2,
    )
    with pytest.raises(ValidationError, match="workflow_step_attempt_sequence_invalid"):
        WorkflowAttemptFallbackEvidenceResponse(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            attempts=[invalid],
            fallback_decisions=[],
            attempt_total=1,
            fallback_decision_total=0,
        )

    with pytest.raises(ValidationError):
        _attempt(provider_call_attempted=True)


def test_attempt_evidence_sequences_are_contiguous_per_retry_generation() -> None:
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    run_id = uuid.uuid4()
    step_id = uuid.uuid4()
    attempts = [
        _attempt(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            step_run_id=step_id,
            retry_generation=0,
        ),
        _attempt(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            step_run_id=step_id,
            retry_generation=1,
            attempt_key_hash="sha256:" + "c" * 64,
        ),
        _attempt(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            step_run_id=step_id,
            retry_generation=1,
            attempt_number=2,
            attempt_key_hash="sha256:" + "d" * 64,
        ),
    ]

    response = WorkflowAttemptFallbackEvidenceResponse(
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
        attempts=attempts,
        fallback_decisions=[],
        attempt_total=3,
        fallback_decision_total=0,
    )

    assert [item.retry_generation for item in response.attempts] == [0, 1, 1]


def test_fallback_evidence_rejects_gate_order_and_silent_switch() -> None:
    gates = _fallback().model_dump(mode="json")["gates"]
    with pytest.raises(ValidationError, match="workflow_fallback_gate_order_invalid"):
        _fallback(gate_snapshot=list(reversed(gates)))
    with pytest.raises(ValidationError):
        _fallback(switch_executed=True)
