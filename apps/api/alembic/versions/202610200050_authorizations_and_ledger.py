"""Create authorizations, run_ledger_entries and run_evidence_grades.

Revision ID: 202610200050
Revises: 202610200049
Create Date: 2026-10-21

This revision is source-only. It must not be applied to a real database without
an exact-target authorization and an explicit backup/rollback plan.

说明：

- 表名来自契约冻结 v1 §1.1：``authorizations``、``run_ledger_entries``、
  ``run_evidence_grades``。不得使用 ``automation_*`` 或 ``cost_ledger_entries``。
- 账本列集按契约 §2.7.1 固定为八列。金额用 ``Numeric(12, 6)``。
- ``task_runs`` 按契约 §1.3 补列。全部可空，存量行不受影响。
- downgrade 先删外键与索引，再删列，最后删表。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610200050"
down_revision: str | None = "202610200049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "authorizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=True),
        sa.Column("plan_version_id", sa.Uuid(), nullable=True),
        sa.Column("gate_id", sa.String(length=20), nullable=False),
        sa.Column("gate_status", sa.String(length=20), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("allowed_risk_levels", sa.JSON(), nullable=True),
        sa.Column("max_cost_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("approver", sa.Uuid(), nullable=False),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_authorizations"),
        sa.UniqueConstraint(
            "workspace_id",
            "approver",
            "idempotency_key_hash",
            name="uq_authorizations_workspace_approver_idempotency",
        ),
        sa.CheckConstraint(
            "gate_status IN ('pending', 'pass', 'fail', 'blocked', 'expired')",
            name="ck_authorizations_gate_status",
        ),
        sa.CheckConstraint(
            "max_cost_usd >= 0",
            name="ck_authorizations_max_cost_usd_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_authorizations_workspace_id_workspaces",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_authorizations_project_id_projects",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["workflow_plans.id"],
            name="fk_authorizations_plan_id_workflow_plans",
        ),
        sa.ForeignKeyConstraint(
            ["plan_version_id"],
            ["workflow_versions.id"],
            name="fk_authorizations_plan_version_id_workflow_versions",
        ),
        sa.ForeignKeyConstraint(
            ["approver"],
            ["users.id"],
            name="fk_authorizations_approver_users",
        ),
    )
    op.create_index(
        "ix_authorizations_workspace_project",
        "authorizations",
        ["workspace_id", "project_id"],
    )

    op.create_table(
        "run_ledger_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("step_id", sa.Uuid(), nullable=True),
        sa.Column("entry_kind", sa.String(length=30), nullable=False),
        sa.Column("amount_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("balance_after_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_run_ledger_entries"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_run_ledger_entries_idempotency_key",
        ),
        sa.CheckConstraint(
            "entry_kind IN ('estimate', 'reserve', 'accrued', 'settle', 'release', 'block')",
            name="ck_run_ledger_entries_entry_kind",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["runs.id"],
            name="fk_run_ledger_entries_run_id_runs",
        ),
        sa.ForeignKeyConstraint(
            ["step_id"],
            ["run_steps.id"],
            name="fk_run_ledger_entries_step_id_run_steps",
        ),
    )
    op.create_index(
        "ix_run_ledger_entries_run_id",
        "run_ledger_entries",
        ["run_id"],
    )

    op.create_table(
        "run_evidence_grades",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("live_call", sa.Boolean(), nullable=False),
        sa.Column("authorization_id", sa.Uuid(), nullable=True),
        sa.Column("sample_n", sa.Integer(), nullable=False),
        sa.Column("required_n", sa.Integer(), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("required_window_days", sa.Integer(), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("required_source_count", sa.Integer(), nullable=False),
        sa.Column("entity_count", sa.Integer(), nullable=False),
        sa.Column("required_entity_count", sa.Integer(), nullable=False),
        sa.Column("grade", sa.String(length=30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_run_evidence_grades"),
        sa.UniqueConstraint("run_id", name="uq_run_evidence_grades_run_id"),
        sa.CheckConstraint(
            "grade IN ('L0_unverified', 'L1_contract', 'L2_fixture_local', "
            "'L3_live_single', 'L4_authorized_live')",
            name="ck_run_evidence_grades_grade",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["runs.id"],
            name="fk_run_evidence_grades_run_id_runs",
        ),
        sa.ForeignKeyConstraint(
            ["authorization_id"],
            ["authorizations.id"],
            name="fk_run_evidence_grades_authorization_id_authorizations",
        ),
    )

    # 契约冻结 v1 §1.3 的其余扩展列。全部可空。
    op.add_column("task_runs", sa.Column("project_id", sa.Uuid(), nullable=True))
    op.add_column("task_runs", sa.Column("run_id", sa.Uuid(), nullable=True))
    op.add_column("task_runs", sa.Column("step_index", sa.Integer(), nullable=True))
    op.add_column("task_runs", sa.Column("unit", sa.String(length=20), nullable=True))
    op.add_column("task_runs", sa.Column("quantity", sa.Numeric(12, 3), nullable=True))
    op.add_column("task_runs", sa.Column("unit_price", sa.Numeric(12, 6), nullable=True))
    op.add_column(
        "task_runs",
        sa.Column("total_cost_usd", sa.Numeric(12, 6), nullable=True),
    )
    op.add_column(
        "task_runs",
        sa.Column("remaining_budget", sa.Numeric(12, 6), nullable=True),
    )
    op.add_column("task_runs", sa.Column("provider", sa.String(length=40), nullable=True))
    op.add_column(
        "task_runs",
        sa.Column("provider_run_id", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "task_runs",
        sa.Column("endpoint_type", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "task_runs",
        sa.Column("evidence_grade", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "task_runs",
        sa.Column("schema_version", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "task_runs",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_task_runs_project_id_projects",
        "task_runs",
        "projects",
        ["project_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_task_runs_run_id_runs",
        "task_runs",
        "runs",
        ["run_id"],
        ["id"],
    )
    op.create_index("ix_task_runs_run_id", "task_runs", ["run_id"])


def downgrade() -> None:
    # 先删 task_runs 的索引、外键与列。
    op.drop_index("ix_task_runs_run_id", table_name="task_runs")
    op.drop_constraint("fk_task_runs_run_id_runs", "task_runs", type_="foreignkey")
    op.drop_constraint("fk_task_runs_project_id_projects", "task_runs", type_="foreignkey")
    op.drop_column("task_runs", "updated_at")
    op.drop_column("task_runs", "schema_version")
    op.drop_column("task_runs", "evidence_grade")
    op.drop_column("task_runs", "endpoint_type")
    op.drop_column("task_runs", "provider_run_id")
    op.drop_column("task_runs", "provider")
    op.drop_column("task_runs", "remaining_budget")
    op.drop_column("task_runs", "total_cost_usd")
    op.drop_column("task_runs", "unit_price")
    op.drop_column("task_runs", "quantity")
    op.drop_column("task_runs", "unit")
    op.drop_column("task_runs", "step_index")
    op.drop_column("task_runs", "run_id")
    op.drop_column("task_runs", "project_id")

    op.drop_table("run_evidence_grades")
    op.drop_index("ix_run_ledger_entries_run_id", table_name="run_ledger_entries")
    op.drop_table("run_ledger_entries")
    op.drop_index("ix_authorizations_workspace_project", table_name="authorizations")
    op.drop_table("authorizations")
