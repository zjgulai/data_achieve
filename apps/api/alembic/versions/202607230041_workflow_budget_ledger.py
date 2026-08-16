"""Add durable workflow budget accounts and append-only reservations.

Revision ID: 202607230041
Revises: 202607230040
Create Date: 2026-07-23

This revision is source-only. It must not be applied to a real database without
an exact-target authorization and an explicit backup/rollback plan.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202607230041"
down_revision: str | None = "202607230040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _fixture_boundary_columns() -> tuple[sa.Column[bool], ...]:
    return tuple(
        sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.false())
        for name in (
            "provider_call_attempted",
            "credential_read_attempted",
            "actor_run",
            "browser_run",
            "llm_call",
            "raw_record_write",
            "dataset_write",
            "production_write_allowed",
        )
    )


def upgrade() -> None:
    op.create_table(
        "workflow_budget_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("execution_session_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_plan_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_version_id", sa.Uuid(), nullable=False),
        sa.Column("contract_version", sa.String(length=100), nullable=False),
        sa.Column("policy_digest", sa.String(length=71), nullable=False),
        sa.Column("max_requests", sa.Integer(), nullable=False),
        sa.Column("max_items", sa.Integer(), nullable=False),
        sa.Column("quota_ceilings", sa.JSON(), nullable=False),
        sa.Column("max_cost_usd", sa.Numeric(20, 8), nullable=False),
        sa.Column("max_time_ms", sa.Integer(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        *_fixture_boundary_columns(),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_budget_accounts"),
        sa.UniqueConstraint(
            "execution_session_id",
            name="uq_workflow_budget_accounts_execution_session",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_workflow_budget_accounts_tenant_id",
        ),
        sa.ForeignKeyConstraint(
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
        sa.CheckConstraint(
            "contract_version = 'workflow_budget_account.v1'",
            name="ck_workflow_budget_accounts_contract_version",
        ),
        sa.CheckConstraint(
            "max_requests >= 1 AND max_items >= 0 AND max_cost_usd >= 0 AND max_time_ms >= 1",
            name="ck_workflow_budget_accounts_limits",
        ),
        sa.CheckConstraint(
            "NOT provider_call_attempted AND NOT credential_read_attempted "
            "AND NOT actor_run AND NOT browser_run AND NOT llm_call "
            "AND NOT raw_record_write AND NOT dataset_write "
            "AND NOT production_write_allowed",
            name="ck_workflow_budget_accounts_fixture_boundaries",
        ),
    )
    op.create_table(
        "workflow_budget_ledger_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("budget_account_id", sa.Uuid(), nullable=False),
        sa.Column("execution_session_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("contract_version", sa.String(length=100), nullable=False),
        sa.Column("policy_digest", sa.String(length=71), nullable=False),
        sa.Column("entry_number", sa.Integer(), nullable=False),
        sa.Column("step_ref", sa.String(length=500), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("side_effect_key_hash", sa.String(length=71), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("blocker_code", sa.String(length=100), nullable=True),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("quota_units", sa.JSON(), nullable=False),
        sa.Column("estimated_cost_usd", sa.Numeric(20, 8), nullable=False),
        sa.Column("reserved_time_ms", sa.Integer(), nullable=False),
        sa.Column("cumulative_request_count", sa.Integer(), nullable=False),
        sa.Column("cumulative_item_count", sa.Integer(), nullable=False),
        sa.Column("cumulative_quota_units", sa.JSON(), nullable=False),
        sa.Column("cumulative_cost_usd", sa.Numeric(20, 8), nullable=False),
        sa.Column("cumulative_time_ms", sa.Integer(), nullable=False),
        sa.Column("previous_ledger_digest", sa.String(length=71), nullable=True),
        sa.Column("ledger_digest", sa.String(length=71), nullable=False),
        *_fixture_boundary_columns(),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_budget_ledger_entries"),
        sa.UniqueConstraint(
            "budget_account_id",
            "entry_number",
            name="uq_workflow_budget_ledger_entries_account_number",
        ),
        sa.UniqueConstraint(
            "budget_account_id",
            "step_ref",
            "page_number",
            name="uq_workflow_budget_ledger_entries_account_step_page",
        ),
        sa.UniqueConstraint(
            "budget_account_id",
            "side_effect_key_hash",
            name="uq_workflow_budget_ledger_entries_account_side_effect_key",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "budget_account_id"],
            [
                "workflow_budget_accounts.workspace_id",
                "workflow_budget_accounts.project_id",
                "workflow_budget_accounts.id",
            ],
            name="fk_workflow_budget_ledger_entries_account_tenant",
        ),
        sa.CheckConstraint(
            "contract_version = 'workflow_budget_ledger.v1'",
            name="ck_workflow_budget_ledger_entries_contract_version",
        ),
        sa.CheckConstraint(
            "entry_number >= 1 AND page_number >= 1",
            name="ck_workflow_budget_ledger_entries_sequence",
        ),
        sa.CheckConstraint(
            "status IN ('reserved', 'blocked')",
            name="ck_workflow_budget_ledger_entries_status",
        ),
        sa.CheckConstraint(
            "(status = 'reserved' AND blocker_code IS NULL) OR "
            "(status = 'blocked' AND blocker_code IS NOT NULL)",
            name="ck_workflow_budget_ledger_entries_outcome",
        ),
        sa.CheckConstraint(
            "request_count >= 1 AND item_count >= 0 AND estimated_cost_usd >= 0 "
            "AND reserved_time_ms >= 1 AND cumulative_request_count >= 0 "
            "AND cumulative_item_count >= 0 AND cumulative_cost_usd >= 0 "
            "AND cumulative_time_ms >= 0",
            name="ck_workflow_budget_ledger_entries_usage",
        ),
        sa.CheckConstraint(
            "NOT provider_call_attempted AND NOT credential_read_attempted "
            "AND NOT actor_run AND NOT browser_run AND NOT llm_call "
            "AND NOT raw_record_write AND NOT dataset_write "
            "AND NOT production_write_allowed",
            name="ck_workflow_budget_ledger_entries_fixture_boundaries",
        ),
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM workflow_budget_ledger_entries)
               OR EXISTS (SELECT 1 FROM workflow_budget_accounts) THEN
                RAISE EXCEPTION
                    '202607230041 downgrade refused: budget evidence exists';
            END IF;
        END $$;
        """
    )
    op.drop_table("workflow_budget_ledger_entries")
    op.drop_table("workflow_budget_accounts")
