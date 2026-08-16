from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin


class _CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class WorkflowRun(UUIDPrimaryKeyMixin, _CreatedAtMixin, Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_workflow_runs_tenant_id",
        ),
        ForeignKeyConstraint(
            [
                "workspace_id",
                "project_id",
                "workflow_plan_id",
                "workflow_version_id",
            ],
            [
                "workflow_versions.workspace_id",
                "workflow_versions.project_id",
                "workflow_versions.workflow_plan_id",
                "workflow_versions.id",
            ],
            name="fk_workflow_runs_version_tenant",
        ),
        ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_workflow_runs_created_by_user",
        ),
        CheckConstraint(
            "execution_contract_version = 'workflow_execution_fixture.v1'",
            name="execution_contract",
        ),
        CheckConstraint("execution_mode = 'fixture'", name="execution_mode"),
        CheckConstraint(
            "status IN ('draft', 'ready', 'running', 'completed', 'degraded', "
            "'held', 'cancelled', 'empty_valid')",
            name="status",
        ),
        CheckConstraint(
            "total_steps >= 1 AND completed_steps >= 0 "
            "AND completed_steps <= total_steps AND records_count >= 0",
            name="counts",
        ),
        CheckConstraint(
            "(status IN ('draft', 'ready', 'running') "
            "AND status_reason_code IS NULL AND impact_code IS NULL "
            "AND json_array_length(missing_fields) = 0 "
            "AND json_array_length(recovery_action_codes) = 0 "
            "AND finished_at IS NULL) OR "
            "(status = 'completed' AND completed_steps = total_steps "
            "AND records_count >= 1 AND status_reason_code IS NULL "
            "AND impact_code IS NULL AND json_array_length(missing_fields) = 0 "
            "AND json_array_length(recovery_action_codes) = 0 "
            "AND finished_at >= started_at) OR "
            "(status = 'empty_valid' AND completed_steps = total_steps "
            "AND records_count = 0 AND status_reason_code IS NOT NULL "
            "AND impact_code IS NOT NULL AND json_array_length(missing_fields) = 0 "
            "AND json_array_length(recovery_action_codes) = 0 "
            "AND finished_at >= started_at) OR "
            "(status = 'degraded' AND completed_steps = total_steps "
            "AND status_reason_code IS NOT NULL AND impact_code IS NOT NULL "
            "AND json_array_length(missing_fields) > 0 "
            "AND json_array_length(recovery_action_codes) > 0 "
            "AND finished_at >= started_at) OR "
            "(status = 'held' AND completed_steps < total_steps "
            "AND status_reason_code IS NOT NULL AND impact_code IS NOT NULL "
            "AND json_array_length(recovery_action_codes) > 0 "
            "AND finished_at IS NULL) OR "
            "(status = 'cancelled' AND status_reason_code IS NOT NULL "
            "AND impact_code IS NOT NULL "
            "AND json_array_length(recovery_action_codes) = 0 "
            "AND finished_at >= started_at)",
            name="state_snapshot",
        ),
        CheckConstraint(
            "NOT provider_call_attempted AND NOT credential_read_attempted "
            "AND NOT actor_run AND NOT browser_run AND NOT llm_call "
            "AND NOT production_write_allowed",
            name="fixture_boundaries",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workflow_plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    workflow_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    execution_contract_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    execution_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    planner_contract_version: Mapped[str] = mapped_column(String(100), nullable=False)
    preview_fingerprint: Mapped[str] = mapped_column(String(71), nullable=False)
    catalog_snapshot_id: Mapped[str] = mapped_column(String(100), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    mode_template_version: Mapped[str] = mapped_column(String(100), nullable=False)
    query_versions: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    fixture_profile_id: Mapped[str] = mapped_column(String(100), nullable=False)
    fixture_profile_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    total_steps: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_steps: Mapped[int] = mapped_column(Integer, nullable=False)
    records_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status_reason_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    impact_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    missing_fields: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    recovery_action_codes: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    provider_call_attempted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    credential_read_attempted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    actor_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    browser_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    llm_call: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    production_write_allowed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class StepRun(UUIDPrimaryKeyMixin, _CreatedAtMixin, Base):
    __tablename__ = "step_runs"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_step_runs_tenant_id",
        ),
        UniqueConstraint(
            "workflow_run_id",
            "step_ref",
            name="uq_step_runs_run_step_ref",
        ),
        UniqueConstraint(
            "workflow_run_id",
            "requirement_ref",
            "implementation_id",
            name="uq_step_runs_run_requirement_implementation",
        ),
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "workflow_run_id",
            "id",
            name="uq_step_runs_tenant_run_id",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_run_id"],
            [
                "workflow_runs.workspace_id",
                "workflow_runs.project_id",
                "workflow_runs.id",
            ],
            name="fk_step_runs_run_tenant",
        ),
        CheckConstraint("sequence >= 1", name="sequence"),
        CheckConstraint("retry_generation >= 0", name="retry_generation"),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="status",
        ),
        CheckConstraint("records_count >= 0", name="records_count"),
        CheckConstraint(
            "(status IN ('pending', 'running') "
            "AND fixture_case_id IS NULL AND fixture_content_hash IS NULL "
            "AND output_digest IS NULL AND finished_at IS NULL) OR "
            "(status = 'completed' AND fixture_case_id IS NOT NULL "
            "AND fixture_content_hash IS NOT NULL AND output_digest IS NOT NULL "
            "AND finished_at >= started_at) OR "
            "(status IN ('failed', 'cancelled') AND records_count = 0 "
            "AND fixture_case_id IS NULL AND fixture_content_hash IS NULL "
            "AND output_digest IS NULL AND finished_at >= started_at)",
            name="state_snapshot",
        ),
        CheckConstraint(
            "NOT provider_call_attempted AND NOT credential_read_attempted "
            "AND NOT actor_run AND NOT browser_run AND NOT llm_call "
            "AND NOT production_write_allowed",
            name="fixture_boundaries",
        ),
    )

    workflow_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    step_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    requirement_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    retry_generation: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    assertion_id: Mapped[str] = mapped_column(String(500), nullable=False)
    implementation_id: Mapped[str] = mapped_column(String(500), nullable=False)
    route_plan_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    fixture_case_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    fixture_content_hash: Mapped[str | None] = mapped_column(String(71), nullable=True)
    input_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    output_digest: Mapped[str | None] = mapped_column(String(71), nullable=True)
    idempotency_scope: Mapped[str] = mapped_column(String(500), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    records_count: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_call_attempted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    credential_read_attempted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    actor_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    browser_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    llm_call: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    production_write_allowed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class StepRunAttempt(UUIDPrimaryKeyMixin, _CreatedAtMixin, Base):
    __tablename__ = "step_run_attempts"
    __table_args__ = (
        UniqueConstraint(
            "step_run_id",
            "retry_generation",
            "attempt_number",
            name="uq_step_run_attempts_step_number",
        ),
        UniqueConstraint(
            "step_run_id",
            "attempt_key_hash",
            name="uq_step_run_attempts_step_key",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_run_id", "step_run_id"],
            [
                "step_runs.workspace_id",
                "step_runs.project_id",
                "step_runs.workflow_run_id",
                "step_runs.id",
            ],
            name="fk_step_run_attempts_step_tenant",
        ),
        CheckConstraint("attempt_number >= 1", name="attempt_number"),
        CheckConstraint("retry_generation >= 0", name="retry_generation"),
        CheckConstraint(
            "status IN ('succeeded', 'retryable_error', 'timeout', 'terminal_error')",
            name="status",
        ),
        CheckConstraint(
            "(status = 'succeeded' AND error_code IS NULL AND backoff_ms = 0) "
            "OR (status <> 'succeeded' AND error_code IS NOT NULL)",
            name="outcome",
        ),
        CheckConstraint("finished_at >= started_at", name="time_order"),
        CheckConstraint(
            "NOT provider_call_attempted AND NOT credential_read_attempted "
            "AND NOT actor_run AND NOT browser_run AND NOT llm_call "
            "AND NOT production_write_allowed",
            name="fixture_boundaries",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    step_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    retry_generation: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_key_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    backoff_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_call_attempted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    credential_read_attempted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    actor_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    browser_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    llm_call: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    production_write_allowed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    finished_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class WorkflowStepCheckpoint(UUIDPrimaryKeyMixin, _CreatedAtMixin, Base):
    __tablename__ = "workflow_step_checkpoints"
    __table_args__ = (
        UniqueConstraint(
            "execution_session_id",
            "step_ref",
            "page_number",
            name="uq_workflow_step_checkpoints_session_step_page",
        ),
        UniqueConstraint(
            "execution_session_id",
            "step_ref",
            "cursor_before_digest",
            name="uq_workflow_step_checkpoints_session_step_cursor",
        ),
        UniqueConstraint(
            "execution_session_id",
            "side_effect_key_hash",
            name="uq_workflow_step_checkpoints_session_side_effect_key",
        ),
        ForeignKeyConstraint(
            [
                "workspace_id",
                "project_id",
                "workflow_plan_id",
                "workflow_version_id",
            ],
            [
                "workflow_versions.workspace_id",
                "workflow_versions.project_id",
                "workflow_versions.workflow_plan_id",
                "workflow_versions.id",
            ],
            name="fk_workflow_step_checkpoints_version_tenant",
        ),
        CheckConstraint(
            "contract_version = 'workflow_step_checkpoint.v1'",
            name="contract_version",
        ),
        CheckConstraint("page_number >= 1", name="page_number"),
        CheckConstraint("records_count >= 0", name="records_count"),
        CheckConstraint(
            "(page_number = 1 AND cursor_before IS NULL) OR "
            "(page_number > 1 AND cursor_before IS NOT NULL)",
            name="cursor_before",
        ),
        CheckConstraint(
            "(terminal AND cursor_after IS NULL AND cursor_after_digest IS NULL) OR "
            "(NOT terminal AND cursor_after IS NOT NULL "
            "AND cursor_after_digest IS NOT NULL)",
            name="cursor_after",
        ),
        CheckConstraint(
            "NOT provider_call_attempted AND NOT credential_read_attempted "
            "AND NOT actor_run AND NOT browser_run AND NOT llm_call "
            "AND NOT raw_record_write AND NOT dataset_write "
            "AND NOT production_write_allowed",
            name="fixture_boundaries",
        ),
    )

    execution_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workflow_plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    workflow_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    step_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    requirement_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    implementation_id: Mapped[str] = mapped_column(String(500), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(100), nullable=False)
    fixture_profile_id: Mapped[str] = mapped_column(String(100), nullable=False)
    fixture_profile_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    step_input_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    cursor_before: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    cursor_before_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    cursor_after: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    cursor_after_digest: Mapped[str | None] = mapped_column(String(71), nullable=True)
    side_effect_key_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    page_output_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    checkpoint_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    records_count: Mapped[int] = mapped_column(Integer, nullable=False)
    terminal: Mapped[bool] = mapped_column(Boolean, nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    provider_call_attempted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    credential_read_attempted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    actor_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    browser_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    llm_call: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raw_record_write: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dataset_write: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    production_write_allowed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class WorkflowBudgetAccount(UUIDPrimaryKeyMixin, _CreatedAtMixin, Base):
    __tablename__ = "workflow_budget_accounts"
    __table_args__ = (
        UniqueConstraint(
            "execution_session_id",
            name="uq_workflow_budget_accounts_execution_session",
        ),
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_workflow_budget_accounts_tenant_id",
        ),
        ForeignKeyConstraint(
            [
                "workspace_id",
                "project_id",
                "workflow_plan_id",
                "workflow_version_id",
            ],
            [
                "workflow_versions.workspace_id",
                "workflow_versions.project_id",
                "workflow_versions.workflow_plan_id",
                "workflow_versions.id",
            ],
            name="fk_workflow_budget_accounts_version_tenant",
        ),
        CheckConstraint(
            "contract_version = 'workflow_budget_account.v1'",
            name="contract_version",
        ),
        CheckConstraint(
            "max_requests >= 1 AND max_items >= 0 AND max_cost_usd >= 0 AND max_time_ms >= 1",
            name="limits",
        ),
        CheckConstraint(
            "NOT provider_call_attempted AND NOT credential_read_attempted "
            "AND NOT actor_run AND NOT browser_run AND NOT llm_call "
            "AND NOT raw_record_write AND NOT dataset_write "
            "AND NOT production_write_allowed",
            name="fixture_boundaries",
        ),
    )

    execution_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workflow_plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    workflow_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    contract_version: Mapped[str] = mapped_column(String(100), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    max_requests: Mapped[int] = mapped_column(Integer, nullable=False)
    max_items: Mapped[int] = mapped_column(Integer, nullable=False)
    quota_ceilings: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False)
    max_cost_usd: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    max_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    provider_call_attempted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    credential_read_attempted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    actor_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    browser_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    llm_call: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raw_record_write: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dataset_write: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    production_write_allowed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )


class WorkflowBudgetLedgerEntry(UUIDPrimaryKeyMixin, _CreatedAtMixin, Base):
    __tablename__ = "workflow_budget_ledger_entries"
    __table_args__ = (
        UniqueConstraint(
            "budget_account_id",
            "entry_number",
            name="uq_workflow_budget_ledger_entries_account_number",
        ),
        UniqueConstraint(
            "budget_account_id",
            "step_ref",
            "page_number",
            name="uq_workflow_budget_ledger_entries_account_step_page",
        ),
        UniqueConstraint(
            "budget_account_id",
            "side_effect_key_hash",
            name="uq_workflow_budget_ledger_entries_account_side_effect_key",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "budget_account_id"],
            [
                "workflow_budget_accounts.workspace_id",
                "workflow_budget_accounts.project_id",
                "workflow_budget_accounts.id",
            ],
            name="fk_workflow_budget_ledger_entries_account_tenant",
        ),
        CheckConstraint(
            "contract_version = 'workflow_budget_ledger.v1'",
            name="contract_version",
        ),
        CheckConstraint("entry_number >= 1 AND page_number >= 1", name="sequence"),
        CheckConstraint(
            "status IN ('reserved', 'blocked')",
            name="status",
        ),
        CheckConstraint(
            "(status = 'reserved' AND blocker_code IS NULL) OR "
            "(status = 'blocked' AND blocker_code IS NOT NULL)",
            name="outcome",
        ),
        CheckConstraint(
            "request_count >= 1 AND item_count >= 0 AND estimated_cost_usd >= 0 "
            "AND reserved_time_ms >= 1 AND cumulative_request_count >= 0 "
            "AND cumulative_item_count >= 0 AND cumulative_cost_usd >= 0 "
            "AND cumulative_time_ms >= 0",
            name="usage",
        ),
        CheckConstraint(
            "NOT provider_call_attempted AND NOT credential_read_attempted "
            "AND NOT actor_run AND NOT browser_run AND NOT llm_call "
            "AND NOT raw_record_write AND NOT dataset_write "
            "AND NOT production_write_allowed",
            name="fixture_boundaries",
        ),
    )

    budget_account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    execution_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(100), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    entry_number: Mapped[int] = mapped_column(Integer, nullable=False)
    step_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    side_effect_key_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    blocker_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    quota_units: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    reserved_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    cumulative_request_count: Mapped[int] = mapped_column(Integer, nullable=False)
    cumulative_item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    cumulative_quota_units: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False)
    cumulative_cost_usd: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    cumulative_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_ledger_digest: Mapped[str | None] = mapped_column(String(71), nullable=True)
    ledger_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    provider_call_attempted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    credential_read_attempted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    actor_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    browser_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    llm_call: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raw_record_write: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dataset_write: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    production_write_allowed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )


class WorkflowFallbackDecision(UUIDPrimaryKeyMixin, _CreatedAtMixin, Base):
    __tablename__ = "workflow_fallback_decisions"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "created_by_user_id",
            "idempotency_scope",
            "idempotency_key_hash",
            "step_ref",
            name="uq_workflow_fallback_decisions_request_step",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_plan_id", "workflow_version_id"],
            [
                "workflow_versions.workspace_id",
                "workflow_versions.project_id",
                "workflow_versions.workflow_plan_id",
                "workflow_versions.id",
            ],
            name="fk_workflow_fallback_decisions_version_tenant",
        ),
        ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_workflow_fallback_decisions_created_by_user",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_run_id"],
            [
                "workflow_runs.workspace_id",
                "workflow_runs.project_id",
                "workflow_runs.id",
            ],
            name="fk_workflow_fallback_decisions_run_tenant",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_run_id", "step_run_id"],
            [
                "step_runs.workspace_id",
                "step_runs.project_id",
                "step_runs.workflow_run_id",
                "step_runs.id",
            ],
            name="fk_workflow_fallback_decisions_step_tenant",
        ),
        CheckConstraint(
            "contract_version = 'workflow_fallback_gate_replay.v1'",
            name="contract_version",
        ),
        CheckConstraint("outcome IN ('eligible', 'blocked')", name="outcome"),
        CheckConstraint(
            "((fallback_assertion_id IS NULL AND fallback_implementation_id IS NULL) "
            "OR (fallback_assertion_id IS NOT NULL "
            "AND fallback_implementation_id IS NOT NULL)) "
            "AND (outcome <> 'eligible' OR fallback_implementation_id IS NOT NULL)",
            name="candidate_identity",
        ),
        CheckConstraint("NOT switch_executed", name="no_silent_switch"),
        CheckConstraint(
            "(workflow_run_id IS NULL AND step_run_id IS NULL) OR "
            "(workflow_run_id IS NOT NULL AND step_run_id IS NOT NULL)",
            name="run_step_pair",
        ),
        CheckConstraint(
            "NOT provider_call_attempted AND NOT credential_read_attempted "
            "AND NOT actor_run AND NOT browser_run AND NOT llm_call "
            "AND NOT production_write_allowed",
            name="fixture_boundaries",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workflow_plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    workflow_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    workflow_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    step_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    idempotency_scope: Mapped[str] = mapped_column(String(500), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    step_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    requirement_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(100), nullable=False)
    decision_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    primary_failure_code: Mapped[str] = mapped_column(String(100), nullable=False)
    primary_assertion_id: Mapped[str] = mapped_column(String(500), nullable=False)
    primary_implementation_id: Mapped[str] = mapped_column(String(500), nullable=False)
    fallback_assertion_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fallback_implementation_id: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    gate_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    field_difference: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    cost_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    approval_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    approval_status: Mapped[str] = mapped_column(String(30), nullable=False)
    switch_executed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    provider_call_attempted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    credential_read_attempted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    actor_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    browser_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    llm_call: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    production_write_allowed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )


class WorkflowShadowComparison(UUIDPrimaryKeyMixin, _CreatedAtMixin, Base):
    __tablename__ = "workflow_shadow_comparisons"
    __table_args__ = (
        UniqueConstraint(
            "workflow_run_id",
            "step_run_id",
            name="uq_workflow_shadow_comparisons_run_step",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_run_id"],
            [
                "workflow_runs.workspace_id",
                "workflow_runs.project_id",
                "workflow_runs.id",
            ],
            name="fk_workflow_shadow_comparisons_run_tenant",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_run_id", "step_run_id"],
            [
                "step_runs.workspace_id",
                "step_runs.project_id",
                "step_runs.workflow_run_id",
                "step_runs.id",
            ],
            name="fk_workflow_shadow_comparisons_step_tenant",
        ),
        CheckConstraint(
            "contract_version = 'workflow_shadow_comparison.v1'",
            name="contract_version",
        ),
        CheckConstraint(
            "sample_rate > 0 AND sample_rate <= 1 "
            "AND max_items >= 1 AND max_items <= 100 "
            "AND sampled_items >= 1 AND sampled_items <= max_items",
            name="sample_budget",
        ),
        CheckConstraint(
            "matched_items >= 0 AND mismatched_items >= 0 "
            "AND primary_only_items >= 0 AND shadow_only_items >= 0 "
            "AND matched_items + mismatched_items + primary_only_items "
            "+ shadow_only_items = sampled_items",
            name="comparison_counts",
        ),
        CheckConstraint(
            "equivalence_status IN ('equivalent', 'different')",
            name="equivalence_status",
        ),
        CheckConstraint(
            "(equivalence_status = 'equivalent' AND matched_items = sampled_items "
            "AND routing_recommendation = 'eligible_for_governance_review') OR "
            "(equivalence_status = 'different' AND matched_items < sampled_items "
            "AND routing_recommendation = 'keep_primary_investigate_shadow')",
            name="recommendation",
        ),
        CheckConstraint(
            "NOT catalog_mutation_applied AND NOT route_ranking_mutation_applied",
            name="no_automatic_governance_mutation",
        ),
        CheckConstraint(
            "NOT provider_call_attempted AND NOT credential_read_attempted "
            "AND NOT actor_run AND NOT browser_run AND NOT llm_call "
            "AND NOT production_write_allowed",
            name="fixture_boundaries",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    step_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    requirement_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(100), nullable=False)
    comparison_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    primary_implementation_id: Mapped[str] = mapped_column(String(500), nullable=False)
    shadow_implementation_id: Mapped[str] = mapped_column(String(500), nullable=False)
    fixture_profile_id: Mapped[str] = mapped_column(String(100), nullable=False)
    fixture_profile_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    primary_fixture_case_id: Mapped[str] = mapped_column(String(200), nullable=False)
    primary_fixture_content_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    shadow_fixture_case_id: Mapped[str] = mapped_column(String(200), nullable=False)
    shadow_fixture_content_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    sample_rate: Mapped[float] = mapped_column(Float, nullable=False)
    max_items: Mapped[int] = mapped_column(Integer, nullable=False)
    sampled_items: Mapped[int] = mapped_column(Integer, nullable=False)
    matched_items: Mapped[int] = mapped_column(Integer, nullable=False)
    mismatched_items: Mapped[int] = mapped_column(Integer, nullable=False)
    primary_only_items: Mapped[int] = mapped_column(Integer, nullable=False)
    shadow_only_items: Mapped[int] = mapped_column(Integer, nullable=False)
    equivalence_status: Mapped[str] = mapped_column(String(20), nullable=False)
    difference_evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    routing_recommendation: Mapped[str] = mapped_column(String(50), nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    catalog_mutation_applied: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    route_ranking_mutation_applied: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    provider_call_attempted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    credential_read_attempted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    actor_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    browser_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    llm_call: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    production_write_allowed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )


class WorkflowRunRequest(UUIDPrimaryKeyMixin, _CreatedAtMixin, Base):
    __tablename__ = "workflow_run_requests"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "created_by_user_id",
            "idempotency_scope",
            "idempotency_key_hash",
            name="uq_workflow_run_requests_idempotency",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_run_id"],
            [
                "workflow_runs.workspace_id",
                "workflow_runs.project_id",
                "workflow_runs.id",
            ],
            name="fk_workflow_run_requests_run_tenant",
        ),
        ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_workflow_run_requests_created_by_user",
        ),
        CheckConstraint("outcome IN ('completed', 'held')", name="outcome"),
        CheckConstraint(
            "response_status BETWEEN 200 AND 599",
            name="response_status",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    idempotency_scope: Mapped[str] = mapped_column(String(500), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class WorkflowLineageMaterializationRequest(UUIDPrimaryKeyMixin, _CreatedAtMixin, Base):
    __tablename__ = "workflow_lineage_materialization_requests"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "created_by_user_id",
            "idempotency_scope",
            "idempotency_key_hash",
            name="uq_workflow_lineage_materializations_idempotency",
        ),
        UniqueConstraint(
            "workflow_run_id",
            name="uq_workflow_lineage_materializations_run",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_run_id"],
            ["workflow_runs.workspace_id", "workflow_runs.project_id", "workflow_runs.id"],
            name="fk_workflow_lineage_materializations_run_tenant",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "dataset_id"],
            ["datasets.workspace_id", "datasets.project_id", "datasets.id"],
            name="fk_workflow_lineage_materializations_dataset_tenant",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "project_id", "dataset_id", "dataset_version_id"],
            [
                "dataset_versions.workspace_id",
                "dataset_versions.project_id",
                "dataset_versions.dataset_id",
                "dataset_versions.id",
            ],
            name="fk_workflow_lineage_materializations_version_tenant",
        ),
        ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_workflow_lineage_materializations_created_by_user",
        ),
        CheckConstraint("outcome = 'completed'", name="outcome"),
        CheckConstraint("response_status BETWEEN 200 AND 599", name="response_status"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    dataset_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    idempotency_scope: Mapped[str] = mapped_column(String(500), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


__all__ = [
    "StepRun",
    "StepRunAttempt",
    "WorkflowBudgetAccount",
    "WorkflowBudgetLedgerEntry",
    "WorkflowStepCheckpoint",
    "WorkflowFallbackDecision",
    "WorkflowLineageMaterializationRequest",
    "WorkflowRun",
    "WorkflowRunRequest",
    "WorkflowShadowComparison",
]
