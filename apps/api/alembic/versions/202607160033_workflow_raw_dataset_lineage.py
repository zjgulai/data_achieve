"""Add tenant-safe V2 WorkflowRun/StepRun RawRecord and Dataset lineage.

Revision ID: 202607160033
Revises: 202607160032
Create Date: 2026-07-16

The revision is source-only in the current checkpoint. It extends the existing
canonical RawRecord/DatasetVersion tables without creating synthetic legacy
TaskRun or Source rows. PostgreSQL execution requires a separate target-pinned
authorization.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202607160033"
down_revision: str | None = "202607160032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "raw_records",
        "source_id",
        existing_type=sa.Uuid(),
        existing_nullable=False,
        nullable=True,
    )
    op.alter_column(
        "raw_records",
        "task_run_id",
        existing_type=sa.Uuid(),
        existing_nullable=False,
        nullable=True,
    )
    op.add_column("raw_records", sa.Column("workflow_run_id", sa.Uuid(), nullable=True))
    op.add_column("raw_records", sa.Column("workflow_step_run_id", sa.Uuid(), nullable=True))
    op.add_column(
        "raw_records",
        sa.Column("workflow_lineage_contract_version", sa.String(length=100), nullable=True),
    )
    op.create_unique_constraint(
        "uq_step_runs_tenant_run_id",
        "step_runs",
        ["workspace_id", "project_id", "workflow_run_id", "id"],
    )
    op.create_unique_constraint(
        "uq_raw_records_workflow_step_content_hash",
        "raw_records",
        ["workflow_step_run_id", "content_hash"],
    )
    op.create_foreign_key(
        "fk_raw_records_workflow_run_tenant",
        "raw_records",
        "workflow_runs",
        ["workspace_id", "project_id", "workflow_run_id"],
        ["workspace_id", "project_id", "id"],
    )
    op.create_foreign_key(
        "fk_raw_records_workflow_step_tenant",
        "raw_records",
        "step_runs",
        ["workspace_id", "project_id", "workflow_run_id", "workflow_step_run_id"],
        ["workspace_id", "project_id", "workflow_run_id", "id"],
    )
    op.create_check_constraint(
        "ck_raw_records_source_provenance",
        "raw_records",
        "(task_run_id IS NOT NULL AND source_id IS NOT NULL "
        "AND workflow_run_id IS NULL AND workflow_step_run_id IS NULL) "
        "OR (task_run_id IS NULL AND source_id IS NULL "
        "AND workflow_run_id IS NOT NULL AND workflow_step_run_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_raw_records_workflow_lineage_contract",
        "raw_records",
        "(workflow_run_id IS NULL AND workflow_step_run_id IS NULL "
        "AND workflow_lineage_contract_version IS NULL) "
        "OR (workflow_run_id IS NOT NULL AND workflow_step_run_id IS NOT NULL "
        "AND workflow_lineage_contract_version IS NOT NULL "
        "AND workflow_lineage_contract_version = 'workflow_raw_record.v1')",
    )
    op.create_index(
        "ix_raw_records_workflow_run",
        "raw_records",
        ["workspace_id", "project_id", "workflow_run_id"],
    )
    op.create_index(
        "ix_raw_records_workflow_step",
        "raw_records",
        ["workspace_id", "project_id", "workflow_step_run_id"],
    )

    op.add_column("dataset_versions", sa.Column("source_workflow_run_id", sa.Uuid(), nullable=True))
    op.add_column(
        "dataset_versions",
        sa.Column("source_workflow_step_run_ids", sa.JSON(), nullable=True),
    )
    op.add_column(
        "dataset_versions",
        sa.Column("source_raw_record_ids", sa.JSON(), nullable=True),
    )
    op.add_column(
        "dataset_versions",
        sa.Column("lineage_contract_version", sa.String(length=100), nullable=True),
    )
    op.create_foreign_key(
        "fk_dataset_versions_workflow_run_tenant",
        "dataset_versions",
        "workflow_runs",
        ["workspace_id", "project_id", "source_workflow_run_id"],
        ["workspace_id", "project_id", "id"],
    )
    op.create_check_constraint(
        "ck_dataset_versions_workflow_lineage_contract",
        "dataset_versions",
        "(source_workflow_run_id IS NULL "
        "AND source_workflow_step_run_ids IS NULL "
        "AND source_raw_record_ids IS NULL "
        "AND lineage_contract_version IS NULL) "
        "OR (source_workflow_run_id IS NOT NULL "
        "AND source_workflow_step_run_ids IS NOT NULL "
        "AND source_raw_record_ids IS NOT NULL "
        "AND lineage_contract_version IS NOT NULL "
        "AND lineage_contract_version = 'workflow_dataset_version.v1')",
    )
    op.create_index(
        "ix_dataset_versions_workflow_run",
        "dataset_versions",
        ["workspace_id", "project_id", "source_workflow_run_id"],
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM raw_records
                WHERE workflow_run_id IS NOT NULL
                   OR workflow_step_run_id IS NOT NULL
                   OR workflow_lineage_contract_version IS NOT NULL
            ) OR EXISTS (
                SELECT 1 FROM dataset_versions
                WHERE source_workflow_run_id IS NOT NULL
                   OR source_workflow_step_run_ids IS NOT NULL
                   OR source_raw_record_ids IS NOT NULL
                   OR lineage_contract_version IS NOT NULL
            ) THEN
                RAISE EXCEPTION
                    '202607160033 downgrade refused: V2 workflow lineage data exists';
            END IF;
        END $$;
        """
    )
    op.drop_index("ix_dataset_versions_workflow_run", table_name="dataset_versions")
    op.drop_constraint(
        "ck_dataset_versions_workflow_lineage_contract",
        "dataset_versions",
        type_="check",
    )
    op.drop_constraint(
        "fk_dataset_versions_workflow_run_tenant",
        "dataset_versions",
        type_="foreignkey",
    )
    for column_name in (
        "lineage_contract_version",
        "source_raw_record_ids",
        "source_workflow_step_run_ids",
        "source_workflow_run_id",
    ):
        op.drop_column("dataset_versions", column_name)

    op.drop_index("ix_raw_records_workflow_step", table_name="raw_records")
    op.drop_index("ix_raw_records_workflow_run", table_name="raw_records")
    op.drop_constraint(
        "ck_raw_records_workflow_lineage_contract",
        "raw_records",
        type_="check",
    )
    op.drop_constraint(
        "ck_raw_records_source_provenance",
        "raw_records",
        type_="check",
    )
    op.drop_constraint(
        "fk_raw_records_workflow_step_tenant",
        "raw_records",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_raw_records_workflow_run_tenant",
        "raw_records",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_raw_records_workflow_step_content_hash",
        "raw_records",
        type_="unique",
    )
    for column_name in (
        "workflow_lineage_contract_version",
        "workflow_step_run_id",
        "workflow_run_id",
    ):
        op.drop_column("raw_records", column_name)
    op.drop_constraint("uq_step_runs_tenant_run_id", "step_runs", type_="unique")
    op.alter_column(
        "raw_records",
        "task_run_id",
        existing_type=sa.Uuid(),
        existing_nullable=True,
        nullable=False,
    )
    op.alter_column(
        "raw_records",
        "source_id",
        existing_type=sa.Uuid(),
        existing_nullable=True,
        nullable=False,
    )
