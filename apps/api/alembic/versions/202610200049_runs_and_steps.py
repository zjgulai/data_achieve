"""Create the runs and run_steps tables.

Revision ID: 202610200049
Revises: 202610200048
Create Date: 2026-10-21

This revision is source-only. It must not be applied to a real database without
an exact-target authorization and an explicit backup/rollback plan.

说明：

- 表名来自契约冻结 v1 §1.1：``runs`` 与 ``run_steps``。
- ``runs.status``、``run_steps.status``、两处 ``outcome`` 由 CHECK 约束钉死。
- ``(workspace_id, idempotency_key_hash)`` 是部分唯一索引。空值不参与。
- ``(status, lease_expires_at)`` 索引供持久队列扫描。
- ``run_steps`` 的 ``(run_id, step_index)`` 唯一。
- downgrade 先删 ``run_steps``，再删 ``runs``。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610200049"
down_revision: str | None = "202610200048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("workflow_version_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=True),
        sa.Column("execution_mode", sa.String(length=30), nullable=False),
        sa.Column("trigger", sa.String(length=30), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=True),
        sa.Column("evidence_grade", sa.String(length=30), nullable=True),
        sa.Column("records_count", sa.Integer(), nullable=False),
        sa.Column("total_cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_runs"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_runs_status",
        ),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome IN ('success', 'empty', 'config_gated', 'failed')",
            name="ck_runs_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_runs_workspace_id_workspaces",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_runs_project_id_projects",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["collection_tasks.id"],
            name="fk_runs_task_id_collection_tasks",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_version_id"],
            ["workflow_versions.id"],
            name="fk_runs_workflow_version_id_workflow_versions",
        ),
    )
    op.create_index(
        "ix_runs_workspace_project",
        "runs",
        ["workspace_id", "project_id"],
    )
    op.create_index(
        "ix_runs_status_lease",
        "runs",
        ["status", "lease_expires_at"],
    )
    # 同一工作区下，同一个幂等键只能有一行。空值不参与唯一性。
    op.create_index(
        "uq_runs_workspace_idempotency",
        "runs",
        ["workspace_id", "idempotency_key_hash"],
        unique=True,
        postgresql_where=sa.text("idempotency_key_hash IS NOT NULL"),
        sqlite_where=sa.text("idempotency_key_hash IS NOT NULL"),
    )

    op.create_table(
        "run_steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("endpoint_type", sa.String(length=80), nullable=False),
        sa.Column("collector_type", sa.String(length=50), nullable=False),
        sa.Column("task_run_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=True),
        sa.Column("records_count", sa.Integer(), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=True),
        sa.Column("unit_price", sa.Numeric(12, 6), nullable=True),
        sa.Column("total_cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_run_steps"),
        sa.UniqueConstraint(
            "run_id",
            "step_index",
            name="uq_run_steps_run_step_index",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'success', 'empty', "
            "'config_gated', 'failed', 'skipped')",
            name="ck_run_steps_status",
        ),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome IN ('success', 'empty', 'config_gated', 'failed')",
            name="ck_run_steps_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["runs.id"],
            name="fk_run_steps_run_id_runs",
        ),
        sa.ForeignKeyConstraint(
            ["task_run_id"],
            ["task_runs.id"],
            name="fk_run_steps_task_run_id_task_runs",
        ),
    )


def downgrade() -> None:
    # 先删步骤表，再删运行表。步骤表有指向 runs 的外键。
    op.drop_table("run_steps")
    op.drop_index("uq_runs_workspace_idempotency", table_name="runs")
    op.drop_index("ix_runs_status_lease", table_name="runs")
    op.drop_index("ix_runs_workspace_project", table_name="runs")
    op.drop_table("runs")
