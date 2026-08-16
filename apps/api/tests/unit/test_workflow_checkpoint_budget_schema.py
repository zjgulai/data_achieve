from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from data_intelligence_hub.schemas.workflow_budget import (
    WorkflowBudgetAccountResponse,
    WorkflowBudgetLedgerEntryResponse,
)
from data_intelligence_hub.schemas.workflow_checkpoint_budget import (
    WorkflowBudgetUsageEvidenceResponse,
    WorkflowCheckpointBudgetEvidenceResponse,
    WorkflowCheckpointStepEvidenceResponse,
)
from data_intelligence_hub.schemas.workflow_resume import WorkflowStepCheckpointResponse

NOW = datetime(2026, 7, 24, 10, 0, tzinfo=UTC)
WORKSPACE_ID = uuid.UUID("10000000-0000-4000-8000-000000000001")
PROJECT_ID = uuid.UUID("20000000-0000-4000-8000-000000000002")
PLAN_ID = uuid.UUID("30000000-0000-4000-8000-000000000003")
VERSION_ID = uuid.UUID("40000000-0000-4000-8000-000000000004")
RUN_ID = uuid.UUID("50000000-0000-4000-8000-000000000005")
STEP_RUN_ID = uuid.UUID("60000000-0000-4000-8000-000000000006")
ACCOUNT_ID = uuid.UUID("70000000-0000-4000-8000-000000000007")


def _hash(character: str) -> str:
    return "sha256:" + character * 64


def _checkpoint(**overrides: object) -> WorkflowStepCheckpointResponse:
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "execution_session_id": RUN_ID,
        "workspace_id": WORKSPACE_ID,
        "project_id": PROJECT_ID,
        "workflow_plan_id": PLAN_ID,
        "workflow_version_id": VERSION_ID,
        "step_ref": "step://youtube/search",
        "requirement_ref": "requirement://youtube/search",
        "implementation_id": "fixture.youtube.search.v1",
        "contract_version": "workflow_step_checkpoint.v1",
        "fixture_profile_id": "fixture-payload-v2",
        "fixture_profile_hash": _hash("a"),
        "step_input_digest": _hash("b"),
        "page_number": 1,
        "cursor_before": None,
        "cursor_before_digest": _hash("c"),
        "cursor_after": "cursor-1",
        "cursor_after_digest": _hash("d"),
        "side_effect_key_hash": _hash("e"),
        "page_output_digest": _hash("f"),
        "checkpoint_digest": _hash("1"),
        "records_count": 2,
        "terminal": False,
        "evidence_refs": ["fixture://youtube/search/page/1"],
        "confirmed_at": NOW,
        "created_at": NOW,
    }
    values.update(overrides)
    return WorkflowStepCheckpointResponse.model_validate(values)


def _checkpoint_step(
    checkpoints: list[WorkflowStepCheckpointResponse] | None = None,
) -> WorkflowCheckpointStepEvidenceResponse:
    items = checkpoints or [_checkpoint()]
    final = items[-1]
    return WorkflowCheckpointStepEvidenceResponse(
        step_run_id=STEP_RUN_ID,
        execution_session_id=RUN_ID,
        step_ref="step://youtube/search",
        requirement_ref="requirement://youtube/search",
        implementation_id="fixture.youtube.search.v1",
        checkpoints=items,
        confirmed_pages=len(items),
        confirmed_records=sum(item.records_count for item in items),
        terminal=final.terminal,
        next_page_number=len(items) + 1,
        next_cursor=final.cursor_after,
    )


def _account() -> WorkflowBudgetAccountResponse:
    return WorkflowBudgetAccountResponse(
        id=ACCOUNT_ID,
        execution_session_id=RUN_ID,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_plan_id=PLAN_ID,
        workflow_version_id=VERSION_ID,
        contract_version="workflow_budget_account.v1",
        policy_digest=_hash("2"),
        max_requests=1,
        max_items=10,
        quota_ceilings={"youtube.search": 10},
        max_cost_usd=Decimal("1.00"),
        max_time_ms=1000,
        evidence_refs=["policy://fixture-budget/v1"],
    )


def _entry(
    *,
    entry_number: int,
    status: str,
    previous_digest: str | None,
    ledger_digest: str,
) -> WorkflowBudgetLedgerEntryResponse:
    blocked = status == "blocked"
    return WorkflowBudgetLedgerEntryResponse.model_validate(
        {
            "id": uuid.uuid4(),
            "budget_account_id": ACCOUNT_ID,
            "execution_session_id": RUN_ID,
            "workspace_id": WORKSPACE_ID,
            "project_id": PROJECT_ID,
            "contract_version": "workflow_budget_ledger.v1",
            "policy_digest": _hash("2"),
            "entry_number": entry_number,
            "step_ref": "step://youtube/search",
            "page_number": entry_number,
            "side_effect_key_hash": _hash("9" if blocked else "e"),
            "status": status,
            "blocker_code": "workflow_request_budget_exceeded" if blocked else None,
            "request_count": 1,
            "item_count": 2,
            "quota_units": {"youtube.search": 2},
            "estimated_cost_usd": Decimal("0.10"),
            "reserved_time_ms": 100,
            "cumulative_request_count": 1,
            "cumulative_item_count": 2,
            "cumulative_quota_units": {"youtube.search": 2},
            "cumulative_cost_usd": Decimal("0.10"),
            "cumulative_time_ms": 100,
            "previous_ledger_digest": previous_digest,
            "ledger_digest": ledger_digest,
        }
    )


def _usage() -> WorkflowBudgetUsageEvidenceResponse:
    return WorkflowBudgetUsageEvidenceResponse(
        request_count=1,
        request_limit=1,
        item_count=2,
        item_limit=10,
        quota_units={"youtube.search": 2},
        quota_ceilings={"youtube.search": 10},
        cost_usd=Decimal("0.10"),
        cost_limit_usd=Decimal("1.00"),
        time_ms=100,
        time_limit_ms=1000,
    )


def test_checkpoint_budget_evidence_accepts_owned_held_read_model() -> None:
    reserved = _entry(
        entry_number=1,
        status="reserved",
        previous_digest=None,
        ledger_digest=_hash("3"),
    )
    blocked = _entry(
        entry_number=2,
        status="blocked",
        previous_digest=reserved.ledger_digest,
        ledger_digest=_hash("4"),
    )

    response = WorkflowCheckpointBudgetEvidenceResponse(
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_plan_id=PLAN_ID,
        workflow_version_id=VERSION_ID,
        workflow_run_id=RUN_ID,
        execution_session_id=RUN_ID,
        checkpoint_steps=[_checkpoint_step()],
        checkpoint_step_total=1,
        checkpoint_page_total=1,
        budget_status="held",
        budget_account=_account(),
        budget_entries=[reserved, blocked],
        budget_entry_total=2,
        usage=_usage(),
        held_reason_code="workflow_request_budget_exceeded",
    )

    assert response.schema_version == "workflow_checkpoint_budget_evidence.v1"
    assert response.database_write is False
    assert response.resume_action_available is False
    assert response.budget_override_available is False


def test_checkpoint_budget_evidence_accepts_explicit_empty_state() -> None:
    response = WorkflowCheckpointBudgetEvidenceResponse(
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        workflow_plan_id=PLAN_ID,
        workflow_version_id=VERSION_ID,
        workflow_run_id=RUN_ID,
        execution_session_id=RUN_ID,
        checkpoint_steps=[],
        checkpoint_step_total=0,
        checkpoint_page_total=0,
        budget_status="not_configured",
        budget_account=None,
        budget_entries=[],
        budget_entry_total=0,
        usage=None,
        held_reason_code=None,
    )

    assert response.budget_status == "not_configured"


def test_checkpoint_chain_and_budget_coverage_fail_closed() -> None:
    second = _checkpoint(
        page_number=2,
        cursor_before="unexpected-cursor",
        cursor_before_digest=_hash("8"),
        cursor_after=None,
        cursor_after_digest=None,
        terminal=True,
    )
    with pytest.raises(
        ValidationError,
        match="workflow_checkpoint_evidence_cursor_chain_invalid",
    ):
        _checkpoint_step([_checkpoint(), second])

    with pytest.raises(
        ValidationError,
        match="workflow_checkpoint_budget_reservation_missing",
    ):
        WorkflowCheckpointBudgetEvidenceResponse(
            workspace_id=WORKSPACE_ID,
            project_id=PROJECT_ID,
            workflow_plan_id=PLAN_ID,
            workflow_version_id=VERSION_ID,
            workflow_run_id=RUN_ID,
            execution_session_id=RUN_ID,
            checkpoint_steps=[_checkpoint_step()],
            checkpoint_step_total=1,
            checkpoint_page_total=1,
            budget_status="configured",
            budget_account=_account(),
            budget_entries=[],
            budget_entry_total=0,
            usage=WorkflowBudgetUsageEvidenceResponse(
                request_count=0,
                request_limit=1,
                item_count=0,
                item_limit=10,
                quota_units={"youtube.search": 0},
                quota_ceilings={"youtube.search": 10},
                cost_usd=0,
                cost_limit_usd=1,
                time_ms=0,
                time_limit_ms=1000,
            ),
        )
