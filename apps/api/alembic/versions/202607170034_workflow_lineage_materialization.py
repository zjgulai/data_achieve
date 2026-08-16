"""Add payload-bound Workflow lineage materialization ledger.

Revision ID: 202607170034
Revises: 202607160033
Create Date: 2026-07-17

This revision is source-only until a new exact-target PostgreSQL authorization
is granted.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202607170034"
down_revision: str | None = "202607160033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_datasets_tenant_id",
        "datasets",
        ["workspace_id", "project_id", "id"],
    )
    op.create_unique_constraint(
        "uq_dataset_versions_tenant_dataset_id",
        "dataset_versions",
        ["workspace_id", "project_id", "dataset_id", "id"],
    )
    op.create_unique_constraint(
        "uq_dataset_versions_source_workflow_run",
        "dataset_versions",
        ["source_workflow_run_id"],
    )
    op.create_table(
        "workflow_lineage_materialization_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_scope", sa.String(length=500), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=71), nullable=False),
        sa.Column("request_hash", sa.String(length=71), nullable=False),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_lineage_materialization_requests"),
        sa.UniqueConstraint(
            "workspace_id",
            "created_by_user_id",
            "idempotency_scope",
            "idempotency_key_hash",
            name="uq_workflow_lineage_materializations_idempotency",
        ),
        sa.UniqueConstraint(
            "workflow_run_id",
            name="uq_workflow_lineage_materializations_run",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_run_id"],
            ["workflow_runs.workspace_id", "workflow_runs.project_id", "workflow_runs.id"],
            name="fk_workflow_lineage_materializations_run_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "dataset_id"],
            ["datasets.workspace_id", "datasets.project_id", "datasets.id"],
            name="fk_workflow_lineage_materializations_dataset_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "dataset_id", "dataset_version_id"],
            [
                "dataset_versions.workspace_id",
                "dataset_versions.project_id",
                "dataset_versions.dataset_id",
                "dataset_versions.id",
            ],
            name="fk_workflow_lineage_materializations_version_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_workflow_lineage_materializations_created_by_user",
        ),
        sa.CheckConstraint(
            "outcome = 'completed'",
            name="ck_workflow_lineage_materialization_requests_outcome",
        ),
        sa.CheckConstraint(
            "response_status BETWEEN 200 AND 599",
            name="ck_workflow_lineage_materialization_requests_response_status",
        ),
    )
    op.create_index(
        "ix_workflow_lineage_materializations_dataset",
        "workflow_lineage_materialization_requests",
        ["workspace_id", "project_id", "dataset_id", "dataset_version_id"],
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM workflow_lineage_materialization_requests) THEN
                RAISE EXCEPTION
                    '202607170034 downgrade refused: workflow lineage materialization data exists';
            END IF;
        END $$;
        """
    )
    op.drop_index(
        "ix_workflow_lineage_materializations_dataset",
        table_name="workflow_lineage_materialization_requests",
    )
    op.drop_table("workflow_lineage_materialization_requests")
    op.drop_constraint(
        "uq_dataset_versions_source_workflow_run",
        "dataset_versions",
        type_="unique",
    )
    op.drop_constraint(
        "uq_dataset_versions_tenant_dataset_id",
        "dataset_versions",
        type_="unique",
    )
    op.drop_constraint("uq_datasets_tenant_id", "datasets", type_="unique")
