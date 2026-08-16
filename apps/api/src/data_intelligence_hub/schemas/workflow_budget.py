from __future__ import annotations

import re
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from data_intelligence_hub.schemas.workflow_execution import (
    Sha256Digest,
    WorkflowExecutionContract,
    WorkflowFixtureBoundary,
)
from data_intelligence_hub.schemas.workflow_resume import WorkflowStepResumeResult

WorkflowBudgetBlockerCode = Literal[
    "workflow_request_budget_exceeded",
    "workflow_item_budget_exceeded",
    "workflow_quota_budget_exceeded",
    "workflow_cost_budget_exceeded",
    "workflow_time_budget_exceeded",
]
WorkflowBudgetEntryStatus = Literal["reserved", "blocked"]
WorkflowBudgetExecutionStatus = Literal["completed", "in_progress", "held"]

_BUDGET_KEY = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,99}$")


def _validate_quota_map(value: dict[str, int], *, allow_zero: bool) -> dict[str, int]:
    if not value or len(value) > 64:
        raise ValueError("workflow_budget_quota_map_invalid")
    for key, amount in value.items():
        if _BUDGET_KEY.fullmatch(key) is None or isinstance(amount, bool):
            raise ValueError("workflow_budget_quota_map_invalid")
        if amount < 0 or (not allow_zero and amount == 0):
            raise ValueError("workflow_budget_quota_map_invalid")
    return dict(sorted(value.items()))


class WorkflowBudgetPolicy(WorkflowExecutionContract):
    max_requests: int = Field(ge=1, le=1_000_000)
    max_items: int = Field(ge=0, le=100_000_000)
    quota_ceilings: dict[str, int]
    max_cost_usd: Decimal = Field(ge=0, max_digits=20, decimal_places=8)
    max_time_ms: int = Field(ge=1, le=31_536_000_000)
    evidence_refs: list[str] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        self.quota_ceilings = _validate_quota_map(self.quota_ceilings, allow_zero=True)
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("workflow_budget_evidence_refs_duplicate")
        return self


class WorkflowBudgetCharge(WorkflowExecutionContract):
    request_count: int = Field(ge=1, le=1_000_000)
    item_count: int = Field(ge=0, le=100_000_000)
    quota_units: dict[str, int]
    estimated_cost_usd: Decimal = Field(ge=0, max_digits=20, decimal_places=8)
    reserved_time_ms: int = Field(ge=1, le=31_536_000_000)

    @model_validator(mode="after")
    def validate_charge(self) -> Self:
        self.quota_units = _validate_quota_map(self.quota_units, allow_zero=True)
        return self


class WorkflowBudgetAccountResponse(WorkflowExecutionContract):
    id: UUID
    execution_session_id: UUID
    workspace_id: UUID
    project_id: UUID
    workflow_plan_id: UUID
    workflow_version_id: UUID
    contract_version: Literal["workflow_budget_account.v1"]
    policy_digest: Sha256Digest
    max_requests: int = Field(ge=1)
    max_items: int = Field(ge=0)
    quota_ceilings: dict[str, int]
    max_cost_usd: Decimal = Field(ge=0)
    max_time_ms: int = Field(ge=1)
    evidence_refs: list[str] = Field(min_length=1, max_length=64)
    provider_call_attempted: Literal[False] = False
    credential_read_attempted: Literal[False] = False
    actor_run: Literal[False] = False
    browser_run: Literal[False] = False
    llm_call: Literal[False] = False
    raw_record_write: Literal[False] = False
    dataset_write: Literal[False] = False
    production_write_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        self.quota_ceilings = _validate_quota_map(self.quota_ceilings, allow_zero=True)
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("workflow_budget_evidence_refs_duplicate")
        return self


class WorkflowBudgetLedgerEntryResponse(WorkflowExecutionContract):
    id: UUID
    budget_account_id: UUID
    execution_session_id: UUID
    workspace_id: UUID
    project_id: UUID
    contract_version: Literal["workflow_budget_ledger.v1"]
    policy_digest: Sha256Digest
    entry_number: int = Field(ge=1)
    step_ref: str = Field(min_length=1, max_length=500)
    page_number: int = Field(ge=1)
    side_effect_key_hash: Sha256Digest
    status: WorkflowBudgetEntryStatus
    blocker_code: WorkflowBudgetBlockerCode | None = None
    request_count: int = Field(ge=1)
    item_count: int = Field(ge=0)
    quota_units: dict[str, int]
    estimated_cost_usd: Decimal = Field(ge=0)
    reserved_time_ms: int = Field(ge=1)
    cumulative_request_count: int = Field(ge=0)
    cumulative_item_count: int = Field(ge=0)
    cumulative_quota_units: dict[str, int]
    cumulative_cost_usd: Decimal = Field(ge=0)
    cumulative_time_ms: int = Field(ge=0)
    previous_ledger_digest: Sha256Digest | None = None
    ledger_digest: Sha256Digest
    provider_call_attempted: Literal[False] = False
    credential_read_attempted: Literal[False] = False
    actor_run: Literal[False] = False
    browser_run: Literal[False] = False
    llm_call: Literal[False] = False
    raw_record_write: Literal[False] = False
    dataset_write: Literal[False] = False
    production_write_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if (self.status == "reserved") != (self.blocker_code is None):
            raise ValueError("workflow_budget_ledger_outcome_invalid")
        self.quota_units = _validate_quota_map(self.quota_units, allow_zero=True)
        self.cumulative_quota_units = _validate_quota_map(
            self.cumulative_quota_units,
            allow_zero=True,
        )
        return self


class WorkflowBudgetedStepResult(WorkflowFixtureBoundary):
    budget_contract_version: Literal["workflow_budget_ledger.v1"] = "workflow_budget_ledger.v1"
    execution_session_id: UUID
    step_ref: str = Field(min_length=1, max_length=500)
    status: WorkflowBudgetExecutionStatus
    held_reason_code: WorkflowBudgetBlockerCode | None = None
    next_page_number: int = Field(ge=1)
    next_cursor: str | None = Field(default=None, max_length=1000)
    confirmed_pages: int = Field(ge=0)
    account_created: bool
    budget_entries_written: int = Field(ge=0)
    reservation_replays: int = Field(ge=0)
    executor_calls: int = Field(ge=0)
    held_before_executor: bool
    account: WorkflowBudgetAccountResponse
    entries: list[WorkflowBudgetLedgerEntryResponse]
    checkpoint_result: WorkflowStepResumeResult | None = None

    @model_validator(mode="after")
    def validate_execution_state(self) -> Self:
        if self.status == "held":
            if self.held_reason_code is None or not self.held_before_executor:
                raise ValueError("workflow_budget_held_state_invalid")
        elif self.held_reason_code is not None or self.held_before_executor:
            raise ValueError("workflow_budget_nonheld_state_invalid")
        if self.status == "completed" and (
            self.checkpoint_result is None or not self.checkpoint_result.terminal
        ):
            raise ValueError("workflow_budget_completed_checkpoint_required")
        if self.status == "in_progress" and (
            self.checkpoint_result is None or self.checkpoint_result.terminal
        ):
            raise ValueError("workflow_budget_in_progress_checkpoint_invalid")
        if self.status == "held" and self.checkpoint_result is not None:
            raise ValueError("workflow_budget_held_checkpoint_result_forbidden")
        return self


__all__ = [
    "WorkflowBudgetAccountResponse",
    "WorkflowBudgetBlockerCode",
    "WorkflowBudgetCharge",
    "WorkflowBudgetExecutionStatus",
    "WorkflowBudgetLedgerEntryResponse",
    "WorkflowBudgetPolicy",
    "WorkflowBudgetedStepResult",
]
