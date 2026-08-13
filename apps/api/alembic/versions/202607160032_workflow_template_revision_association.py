"""Move WorkflowTemplate definitions into immutable revisions and bind Plans.

Revision ID: 202607160032
Revises: 202607160031
Create Date: 2026-07-16

This migration is intentionally fail-closed.  Revision 031 was authored before
the immutable revision contract existed, so a non-empty legacy template table
cannot be converted without an explicit, separately reviewed backfill.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202607160032"
down_revision: str | None = "202607160031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PLAN_TEMPLATE_PAIR = (
    "(workflow_template_id IS NULL AND workflow_template_revision_id IS NULL) "
    "OR (workflow_template_id IS NOT NULL AND workflow_template_revision_id IS NOT NULL)"
)


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM workflow_templates) THEN
                RAISE EXCEPTION
                    '202607160032 requires an empty workflow_templates table; '
                    'legacy definitions need an explicit backfill';
            END IF;
        END $$;
        """
    )

    op.create_table(
        "workflow_template_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_template_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("definition_fingerprint", sa.String(length=71), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "revision_number >= 1",
            name="ck_workflow_template_revisions_revision_number",
        ),
        sa.CheckConstraint(
            "definition_fingerprint LIKE 'sha256:%'",
            name="ck_workflow_template_revisions_definition_fingerprint",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_template_id"],
            [
                "workflow_templates.workspace_id",
                "workflow_templates.project_id",
                "workflow_templates.id",
            ],
            name="fk_workflow_template_revisions_template_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_workflow_template_revisions_created_by_user",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_template_revisions"),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_workflow_template_revisions_tenant_id",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "workflow_template_id",
            "id",
            name="uq_workflow_template_revisions_template_tenant_id",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "workflow_template_id",
            "revision_number",
            name="uq_workflow_template_revisions_tenant_number",
        ),
    )
    op.execute(
        """
        CREATE TRIGGER trg_workflow_template_revisions_immutable
        BEFORE UPDATE OR DELETE ON workflow_template_revisions
        FOR EACH ROW
        EXECUTE FUNCTION reject_workflow_plan_history_mutation();
        """
    )
    op.create_table(
        "workflow_template_mutation_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_scope", sa.String(length=500), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=71), nullable=False),
        sa.Column("request_hash", sa.String(length=71), nullable=False),
        sa.Column("workflow_template_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_template_revision_id", sa.Uuid(), nullable=True),
        sa.Column("operation", sa.String(length=30), nullable=False),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "operation IN ('create', 'metadata', 'revision')",
            name="ck_workflow_template_mutation_requests_operation",
        ),
        sa.CheckConstraint(
            "outcome IN ('created', 'updated')",
            name="ck_workflow_template_mutation_requests_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_workflow_template_mutation_requests_created_by_user",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "workflow_template_id"],
            [
                "workflow_templates.workspace_id",
                "workflow_templates.project_id",
                "workflow_templates.id",
            ],
            name="fk_workflow_template_mutation_requests_template_tenant",
        ),
        sa.ForeignKeyConstraint(
            [
                "workspace_id",
                "project_id",
                "workflow_template_id",
                "workflow_template_revision_id",
            ],
            [
                "workflow_template_revisions.workspace_id",
                "workflow_template_revisions.project_id",
                "workflow_template_revisions.workflow_template_id",
                "workflow_template_revisions.id",
            ],
            name="fk_workflow_template_mutation_requests_revision_tenant",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_template_mutation_requests"),
        sa.UniqueConstraint(
            "workspace_id",
            "created_by_user_id",
            "idempotency_scope",
            "idempotency_key_hash",
            name="uq_workflow_template_mutation_requests_idempotency",
        ),
    )
    op.add_column(
        "workflow_templates",
        sa.Column("current_revision_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_workflow_templates_current_revision_tenant",
        "workflow_templates",
        "workflow_template_revisions",
        ["workspace_id", "project_id", "id", "current_revision_id"],
        [
            "workspace_id",
            "project_id",
            "workflow_template_id",
            "id",
        ],
    )
    op.drop_column("workflow_templates", "definition")

    for table_name in ("workflow_plans", "workflow_versions"):
        op.add_column(
            table_name,
            sa.Column("workflow_template_id", sa.Uuid(), nullable=True),
        )
        op.add_column(
            table_name,
            sa.Column("workflow_template_revision_id", sa.Uuid(), nullable=True),
        )
        op.create_check_constraint(
            f"ck_{table_name}_template_revision_pair",
            table_name,
            _PLAN_TEMPLATE_PAIR,
        )
        op.create_foreign_key(
            f"fk_{table_name}_template_revision_tenant",
            table_name,
            "workflow_template_revisions",
            [
                "workspace_id",
                "project_id",
                "workflow_template_id",
                "workflow_template_revision_id",
            ],
            [
                "workspace_id",
                "project_id",
                "workflow_template_id",
                "id",
            ],
        )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM workflow_templates)
               OR EXISTS (SELECT 1 FROM workflow_template_revisions)
               OR EXISTS (
                   SELECT 1 FROM workflow_plans
                   WHERE workflow_template_id IS NOT NULL
                      OR workflow_template_revision_id IS NOT NULL
               )
               OR EXISTS (
                   SELECT 1 FROM workflow_versions
                   WHERE workflow_template_id IS NOT NULL
                      OR workflow_template_revision_id IS NOT NULL
               ) THEN
                RAISE EXCEPTION
                    '202607160032 downgrade refused: template revision data exists';
            END IF;
        END $$;
        """
    )
    for table_name in ("workflow_versions", "workflow_plans"):
        op.drop_constraint(
            f"fk_{table_name}_template_revision_tenant",
            table_name,
            type_="foreignkey",
        )
        op.drop_constraint(
            f"ck_{table_name}_template_revision_pair",
            table_name,
            type_="check",
        )
        op.drop_column(table_name, "workflow_template_revision_id")
        op.drop_column(table_name, "workflow_template_id")
    op.drop_constraint(
        "fk_workflow_templates_current_revision_tenant",
        "workflow_templates",
        type_="foreignkey",
    )
    op.drop_column("workflow_templates", "current_revision_id")
    op.drop_table("workflow_template_mutation_requests")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_workflow_template_revisions_immutable "
        "ON workflow_template_revisions"
    )
    op.drop_table("workflow_template_revisions")
    op.add_column(
        "workflow_templates",
        sa.Column("definition", sa.JSON(), nullable=False),
    )
