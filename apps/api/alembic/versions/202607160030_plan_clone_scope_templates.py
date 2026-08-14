"""Add Plan clone provenance and editable ScopeTemplate copies.

Revision ID: 202607160030
Revises: 202606110029
Create Date: 2026-07-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202607160030"
down_revision: str | None = "202606110029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workflow_plans",
        sa.Column("source_workflow_plan_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "workflow_plans",
        sa.Column("source_workflow_version_id", sa.Uuid(), nullable=True),
    )
    op.create_check_constraint(
        "ck_workflow_plans_source_version_pair",
        "workflow_plans",
        "(source_workflow_plan_id IS NULL AND source_workflow_version_id IS NULL) "
        "OR (source_workflow_plan_id IS NOT NULL AND source_workflow_version_id IS NOT NULL)",
    )
    op.create_foreign_key(
        "fk_workflow_plans_source_version_owner",
        "workflow_plans",
        "workflow_versions",
        [
            "workspace_id",
            "project_id",
            "source_workflow_plan_id",
            "source_workflow_version_id",
        ],
        [
            "workspace_id",
            "project_id",
            "workflow_plan_id",
            "id",
        ],
    )

    op.create_table(
        "monitoring_scope_templates",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("source_scope_id", sa.Uuid(), nullable=False),
        sa.Column("source_workflow_plan_id", sa.Uuid(), nullable=False),
        sa.Column("source_workflow_version_id", sa.Uuid(), nullable=False),
        sa.Column("scope_key", sa.String(length=71), nullable=False),
        sa.Column("scope_type", sa.String(length=30), nullable=False),
        sa.Column("canonical_term", sa.Text(), nullable=True),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("include_terms", sa.JSON(), nullable=False),
        sa.Column("exclude_terms", sa.JSON(), nullable=False),
        sa.Column("official_accounts", sa.JSON(), nullable=False),
        sa.Column("seed_urls", sa.JSON(), nullable=False),
        sa.Column("effective_languages", sa.JSON(), nullable=False),
        sa.Column("effective_regions", sa.JSON(), nullable=False),
        sa.Column("effective_platforms", sa.JSON(), nullable=False),
        sa.Column("match_mode", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "scope_type IN ('brand', 'category', 'competitor', 'topic', 'campaign')",
            name="ck_monitoring_scope_templates_scope_type",
        ),
        sa.CheckConstraint(
            "match_mode IN ('exact', 'phrase', 'semantic', 'hybrid')",
            name="ck_monitoring_scope_templates_match_mode",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_monitoring_scope_templates_created_by_user",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_monitoring_scope_templates"),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_monitoring_scope_templates_tenant_id",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_monitoring_scope_templates_project_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "source_scope_id"],
            [
                "monitoring_scopes.workspace_id",
                "monitoring_scopes.project_id",
                "monitoring_scopes.id",
            ],
            name="fk_monitoring_scope_templates_source_scope_tenant",
        ),
        sa.ForeignKeyConstraint(
            [
                "workspace_id",
                "project_id",
                "source_workflow_plan_id",
                "source_workflow_version_id",
            ],
            [
                "workflow_versions.workspace_id",
                "workflow_versions.project_id",
                "workflow_versions.workflow_plan_id",
                "workflow_versions.id",
            ],
            name="fk_monitoring_scope_templates_source_version_tenant",
        ),
        sa.ForeignKeyConstraint(
            [
                "workspace_id",
                "project_id",
                "source_workflow_version_id",
                "source_scope_id",
            ],
            [
                "workflow_version_scopes.workspace_id",
                "workflow_version_scopes.project_id",
                "workflow_version_scopes.workflow_version_id",
                "workflow_version_scopes.monitoring_scope_id",
            ],
            name="fk_monitoring_scope_templates_source_association_tenant",
        ),
    )
    op.create_index(
        "ix_monitoring_scope_templates_project_created_at",
        "monitoring_scope_templates",
        ["workspace_id", "project_id", "created_at"],
    )
    op.execute(
        """
        CREATE TRIGGER trg_monitoring_scope_templates_immutable
        BEFORE UPDATE OR DELETE ON monitoring_scope_templates
        FOR EACH ROW
        EXECUTE FUNCTION reject_workflow_plan_history_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_monitoring_scope_templates_immutable "
        "ON monitoring_scope_templates"
    )
    op.drop_index(
        "ix_monitoring_scope_templates_project_created_at",
        table_name="monitoring_scope_templates",
    )
    op.drop_table("monitoring_scope_templates")
    op.drop_constraint(
        "fk_workflow_plans_source_version_owner",
        "workflow_plans",
        type_="foreignkey",
    )
    op.drop_constraint(
        "ck_workflow_plans_source_version_pair",
        "workflow_plans",
        type_="check",
    )
    op.drop_column("workflow_plans", "source_workflow_version_id")
    op.drop_column("workflow_plans", "source_workflow_plan_id")

