from __future__ import annotations

from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from data_intelligence_hub.schemas.workflow_budget import (
    WorkflowBudgetAccountResponse,
    WorkflowBudgetBlockerCode,
    WorkflowBudgetLedgerEntryResponse,
)
from data_intelligence_hub.schemas.workflow_execution import (
    WorkflowExecutionContract,
    WorkflowFixtureReadBoundary,
)
from data_intelligence_hub.schemas.workflow_resume import (
    CheckpointCursor,
    CheckpointReference,
    WorkflowStepCheckpointResponse,
)

WorkflowBudgetEvidenceStatus = Literal[
    "not_configured",
    "configured",
    "within_limit",
    "held",
]


class WorkflowCheckpointStepEvidenceResponse(WorkflowExecutionContract):
    step_run_id: UUID
    execution_session_id: UUID
    step_ref: CheckpointReference
    requirement_ref: CheckpointReference
    implementation_id: CheckpointReference
    checkpoints: list[WorkflowStepCheckpointResponse] = Field(min_length=1)
    confirmed_pages: int = Field(ge=1)
    confirmed_records: int = Field(ge=0)
    terminal: bool
    next_page_number: int = Field(ge=1)
    next_cursor: CheckpointCursor | None = None
    resume_action_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_checkpoint_chain(self) -> Self:
        if self.confirmed_pages != len(self.checkpoints):
            raise ValueError("workflow_checkpoint_evidence_count_invalid")
        if self.confirmed_records != sum(item.records_count for item in self.checkpoints):
            raise ValueError("workflow_checkpoint_evidence_records_invalid")
        if self.next_page_number != self.confirmed_pages + 1:
            raise ValueError("workflow_checkpoint_evidence_next_page_invalid")

        previous: WorkflowStepCheckpointResponse | None = None
        for expected_page, checkpoint in enumerate(self.checkpoints, start=1):
            if (
                checkpoint.execution_session_id != self.execution_session_id
                or checkpoint.step_ref != self.step_ref
                or checkpoint.requirement_ref != self.requirement_ref
                or checkpoint.implementation_id != self.implementation_id
                or checkpoint.page_number != expected_page
            ):
                raise ValueError("workflow_checkpoint_evidence_identity_invalid")
            if previous is not None and (
                checkpoint.cursor_before != previous.cursor_after
                or checkpoint.cursor_before_digest != previous.cursor_after_digest
            ):
                raise ValueError("workflow_checkpoint_evidence_cursor_chain_invalid")
            if previous is not None and previous.terminal:
                raise ValueError("workflow_checkpoint_evidence_after_terminal")
            previous = checkpoint

        final = self.checkpoints[-1]
        if self.terminal != final.terminal or self.next_cursor != final.cursor_after:
            raise ValueError("workflow_checkpoint_evidence_terminal_state_invalid")
        return self


class WorkflowBudgetUsageEvidenceResponse(WorkflowExecutionContract):
    request_count: int = Field(ge=0)
    request_limit: int = Field(ge=1)
    item_count: int = Field(ge=0)
    item_limit: int = Field(ge=0)
    quota_units: dict[str, int]
    quota_ceilings: dict[str, int]
    cost_usd: Decimal = Field(ge=0)
    cost_limit_usd: Decimal = Field(ge=0)
    time_ms: int = Field(ge=0)
    time_limit_ms: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_usage_dimensions(self) -> Self:
        if set(self.quota_units) != set(self.quota_ceilings):
            raise ValueError("workflow_budget_usage_quota_keys_invalid")
        if any(value < 0 for value in self.quota_units.values()) or any(
            value < 0 for value in self.quota_ceilings.values()
        ):
            raise ValueError("workflow_budget_usage_quota_values_invalid")
        return self


class WorkflowCheckpointBudgetEvidenceResponse(WorkflowFixtureReadBoundary):
    schema_version: Literal["workflow_checkpoint_budget_evidence.v1"] = (
        "workflow_checkpoint_budget_evidence.v1"
    )
    workspace_id: UUID
    project_id: UUID
    workflow_plan_id: UUID
    workflow_version_id: UUID
    workflow_run_id: UUID
    execution_session_id: UUID
    checkpoint_steps: list[WorkflowCheckpointStepEvidenceResponse]
    checkpoint_step_total: int = Field(ge=0)
    checkpoint_page_total: int = Field(ge=0)
    budget_status: WorkflowBudgetEvidenceStatus
    budget_account: WorkflowBudgetAccountResponse | None = None
    budget_entries: list[WorkflowBudgetLedgerEntryResponse]
    budget_entry_total: int = Field(ge=0)
    usage: WorkflowBudgetUsageEvidenceResponse | None = None
    held_reason_code: WorkflowBudgetBlockerCode | None = None
    resume_action_available: Literal[False] = False
    budget_override_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_checkpoint_budget_evidence(self) -> Self:
        if self.execution_session_id != self.workflow_run_id:
            raise ValueError("workflow_execution_session_run_binding_invalid")
        if self.checkpoint_step_total != len(self.checkpoint_steps):
            raise ValueError("workflow_checkpoint_step_total_invalid")
        if self.checkpoint_page_total != sum(
            item.confirmed_pages for item in self.checkpoint_steps
        ):
            raise ValueError("workflow_checkpoint_page_total_invalid")
        if len({item.step_run_id for item in self.checkpoint_steps}) != len(
            self.checkpoint_steps
        ):
            raise ValueError("workflow_checkpoint_step_duplicate")

        checkpoints = []
        for item in self.checkpoint_steps:
            if item.execution_session_id != self.execution_session_id:
                raise ValueError("workflow_checkpoint_session_invalid")
            for checkpoint in item.checkpoints:
                if (
                    checkpoint.workspace_id != self.workspace_id
                    or checkpoint.project_id != self.project_id
                    or checkpoint.workflow_plan_id != self.workflow_plan_id
                    or checkpoint.workflow_version_id != self.workflow_version_id
                ):
                    raise ValueError("workflow_checkpoint_owner_invalid")
                checkpoints.append(checkpoint)

        if self.budget_entry_total != len(self.budget_entries):
            raise ValueError("workflow_budget_entry_total_invalid")
        if self.budget_account is None:
            if (
                self.budget_status != "not_configured"
                or self.budget_entries
                or self.usage is not None
                or self.held_reason_code is not None
            ):
                raise ValueError("workflow_budget_not_configured_state_invalid")
            return self

        account = self.budget_account
        if (
            account.execution_session_id != self.execution_session_id
            or account.workspace_id != self.workspace_id
            or account.project_id != self.project_id
            or account.workflow_plan_id != self.workflow_plan_id
            or account.workflow_version_id != self.workflow_version_id
            or self.usage is None
        ):
            raise ValueError("workflow_budget_account_owner_invalid")
        if self.budget_status == "not_configured":
            raise ValueError("workflow_budget_configured_state_invalid")

        previous: WorkflowBudgetLedgerEntryResponse | None = None
        requests = 0
        items = 0
        quotas = {key: 0 for key in account.quota_ceilings}
        cost = Decimal("0")
        time_ms = 0
        for expected_number, entry in enumerate(self.budget_entries, start=1):
            if (
                entry.budget_account_id != account.id
                or entry.execution_session_id != self.execution_session_id
                or entry.workspace_id != self.workspace_id
                or entry.project_id != self.project_id
                or entry.policy_digest != account.policy_digest
                or entry.entry_number != expected_number
                or entry.previous_ledger_digest
                != (previous.ledger_digest if previous is not None else None)
                or not set(entry.quota_units).issubset(quotas)
            ):
                raise ValueError("workflow_budget_ledger_chain_invalid")
            if previous is not None and previous.status == "blocked":
                raise ValueError("workflow_budget_entry_after_hold")
            if entry.status == "reserved":
                requests += entry.request_count
                items += entry.item_count
                for key, value in entry.quota_units.items():
                    quotas[key] += value
                cost += entry.estimated_cost_usd
                time_ms += entry.reserved_time_ms
            if (
                entry.cumulative_request_count != requests
                or entry.cumulative_item_count != items
                or entry.cumulative_quota_units != quotas
                or entry.cumulative_cost_usd != cost
                or entry.cumulative_time_ms != time_ms
            ):
                raise ValueError("workflow_budget_ledger_cumulative_invalid")
            previous = entry

        expected_status: WorkflowBudgetEvidenceStatus
        expected_reason: WorkflowBudgetBlockerCode | None
        if previous is None:
            expected_status = "configured"
            expected_reason = None
        elif previous.status == "blocked":
            expected_status = "held"
            expected_reason = previous.blocker_code
        else:
            expected_status = "within_limit"
            expected_reason = None
        if self.budget_status != expected_status or self.held_reason_code != expected_reason:
            raise ValueError("workflow_budget_evidence_status_invalid")

        usage = self.usage
        if (
            usage.request_count != requests
            or usage.request_limit != account.max_requests
            or usage.item_count != items
            or usage.item_limit != account.max_items
            or usage.quota_units != quotas
            or usage.quota_ceilings != account.quota_ceilings
            or usage.cost_usd != cost
            or usage.cost_limit_usd != account.max_cost_usd
            or usage.time_ms != time_ms
            or usage.time_limit_ms != account.max_time_ms
        ):
            raise ValueError("workflow_budget_usage_invalid")

        reservations = {
            (entry.step_ref, entry.page_number, entry.side_effect_key_hash)
            for entry in self.budget_entries
            if entry.status == "reserved"
        }
        if any(
            (item.step_ref, item.page_number, item.side_effect_key_hash)
            not in reservations
            for item in checkpoints
        ):
            raise ValueError("workflow_checkpoint_budget_reservation_missing")
        return self


__all__ = [
    "WorkflowBudgetEvidenceStatus",
    "WorkflowBudgetUsageEvidenceResponse",
    "WorkflowCheckpointBudgetEvidenceResponse",
    "WorkflowCheckpointStepEvidenceResponse",
]
