"""Add workflow planner persistence tables and PostgreSQL invariants.

Revision ID: 202606110027
Revises: 202606110026
Create Date: 2026-07-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606110027"
down_revision: str | None = "202606110026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


COMPOSITE_FOREIGN_KEYS: tuple[tuple[str, str], ...] = (
    ("fk_workflow_plans_project_tenant", "workflow_plans"),
    ("fk_monitoring_scopes_project_tenant", "monitoring_scopes"),
    ("fk_workflow_versions_plan_tenant", "workflow_versions"),
    ("fk_workflow_version_scopes_version_tenant", "workflow_version_scopes"),
    ("fk_workflow_version_scopes_scope_tenant", "workflow_version_scopes"),
    ("fk_query_terms_version_scope_tenant", "query_terms"),
    ("fk_workflow_plan_save_requests_plan_tenant", "workflow_plan_save_requests"),
    ("fk_workflow_plan_save_requests_version_tenant", "workflow_plan_save_requests"),
)

TENANT_INDEXES: tuple[tuple[str, str], ...] = (
    ("ix_monitoring_scopes_project_created_at", "monitoring_scopes"),
    ("ix_workflow_plans_project_updated_at", "workflow_plans"),
    ("ix_workflow_versions_plan_created_at", "workflow_versions"),
    ("ix_workflow_plan_save_requests_plan_created_at", "workflow_plan_save_requests"),
)

IMMUTABLE_TABLES: tuple[str, ...] = (
    "workflow_versions",
    "monitoring_scopes",
    "workflow_version_scopes",
    "query_terms",
    "workflow_plan_save_requests",
)


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_projects_workspace_id",
        "projects",
        ["workspace_id", "id"],
    )

    op.create_table(
        "monitoring_scopes",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
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
            name="ck_monitoring_scopes_scope_type_valid",
        ),
        sa.CheckConstraint(
            "match_mode IN ('exact', 'phrase', 'semantic', 'hybrid')",
            name="ck_monitoring_scopes_match_mode_valid",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "scope_key",
            name="uq_monitoring_scopes_project_key",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_monitoring_scopes_tenant_id",
        ),
    )

    op.create_table(
        "workflow_plans",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("flow_mode", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("current_version_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "flow_mode IN ('periodic_monitoring', 'batch_research')",
            name="ck_workflow_plans_flow_mode_valid",
        ),
        sa.CheckConstraint(
            "status = 'previewed'",
            name="ck_workflow_plans_status_previewed",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_workflow_plans_tenant_id",
        ),
    )

    op.create_table(
        "workflow_versions",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_plan_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("planning_status", sa.String(length=30), nullable=False),
        sa.Column("planner_contract_version", sa.String(length=100), nullable=False),
        sa.Column("catalog_snapshot_id", sa.String(length=100), nullable=False),
        sa.Column("policy_version", sa.String(length=100), nullable=False),
        sa.Column("mode_template_version", sa.String(length=100), nullable=False),
        sa.Column("query_versions", sa.JSON(), nullable=False),
        sa.Column("fingerprint_payload", sa.JSON(), nullable=False),
        sa.Column("normalized_input", sa.JSON(), nullable=False),
        sa.Column("plan_payload", sa.JSON(), nullable=False),
        sa.Column("preview_fingerprint", sa.String(length=71), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "version_number >= 1",
            name="ck_workflow_versions_version_number_positive",
        ),
        sa.CheckConstraint(
            "planning_status IN ('resolved', 'partially_resolved', 'held')",
            name="ck_workflow_versions_planning_status_valid",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workflow_plan_id",
            "version_number",
            name="uq_workflow_versions_plan_number",
        ),
        sa.UniqueConstraint(
            "workflow_plan_id",
            "id",
            name="uq_workflow_versions_plan_id",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_workflow_versions_tenant_id",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "workflow_plan_id",
            "id",
            name="uq_workflow_versions_tenant_plan_id",
        ),
    )

    op.create_table(
        "workflow_version_scopes",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_version_id", sa.Uuid(), nullable=False),
        sa.Column("monitoring_scope_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "ordinal >= 0",
            name="ck_workflow_version_scopes_ordinal_non_negative",
        ),
        sa.PrimaryKeyConstraint("workflow_version_id", "monitoring_scope_id"),
        sa.UniqueConstraint(
            "workflow_version_id",
            "ordinal",
            name="uq_workflow_version_scopes_version_ordinal",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "workflow_version_id",
            "monitoring_scope_id",
            name="uq_workflow_version_scopes_tenant_pair",
        ),
    )

    op.create_table(
        "query_terms",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_version_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("term", sa.Text(), nullable=False),
        sa.Column("normalized_term", sa.Text(), nullable=False),
        sa.Column("origin", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("conflict_codes", sa.JSON(), nullable=False),
        sa.Column("matched_scope_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "ordinal >= 0",
            name="ck_query_terms_ordinal_non_negative",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'candidate', 'rejected')",
            name="ck_query_terms_status_valid",
        ),
        sa.CheckConstraint(
            "origin IN ("
            "'canonical', 'alias', 'include', 'official_account', 'seed_url', "
            "'fixture_candidate_expansion'"
            ")",
            name="ck_query_terms_origin_valid",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workflow_version_id",
            "ordinal",
            name="uq_query_terms_version_ordinal",
        ),
    )

    op.create_table(
        "workflow_plan_save_requests",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_scope", sa.String(length=500), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=71), nullable=False),
        sa.Column("request_hash", sa.String(length=71), nullable=False),
        sa.Column("workflow_plan_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_version_id", sa.Uuid(), nullable=False),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('created', 'semantic_no_op')",
            name="ck_workflow_plan_save_requests_outcome_valid",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "created_by_user_id",
            "idempotency_scope",
            "idempotency_key_hash",
            name="uq_workflow_plan_save_requests_idempotency",
        ),
    )

    op.create_index(
        "ix_monitoring_scopes_project_created_at",
        "monitoring_scopes",
        ["workspace_id", "project_id", "created_at"],
    )
    op.create_index(
        "ix_workflow_plans_project_updated_at",
        "workflow_plans",
        ["workspace_id", "project_id", "updated_at"],
    )
    op.create_index(
        "ix_workflow_versions_plan_created_at",
        "workflow_versions",
        ["workspace_id", "project_id", "workflow_plan_id", "created_at"],
    )
    op.create_index(
        "ix_workflow_plan_save_requests_plan_created_at",
        "workflow_plan_save_requests",
        ["workspace_id", "project_id", "workflow_plan_id", "created_at"],
    )

    op.create_foreign_key(
        "fk_workflow_plans_project_tenant",
        "workflow_plans",
        "projects",
        ["workspace_id", "project_id"],
        ["workspace_id", "id"],
    )
    op.create_foreign_key(
        "fk_monitoring_scopes_project_tenant",
        "monitoring_scopes",
        "projects",
        ["workspace_id", "project_id"],
        ["workspace_id", "id"],
    )
    op.create_foreign_key(
        "fk_workflow_versions_plan_tenant",
        "workflow_versions",
        "workflow_plans",
        ["workspace_id", "project_id", "workflow_plan_id"],
        ["workspace_id", "project_id", "id"],
    )
    op.create_foreign_key(
        "fk_workflow_version_scopes_version_tenant",
        "workflow_version_scopes",
        "workflow_versions",
        ["workspace_id", "project_id", "workflow_version_id"],
        ["workspace_id", "project_id", "id"],
    )
    op.create_foreign_key(
        "fk_workflow_version_scopes_scope_tenant",
        "workflow_version_scopes",
        "monitoring_scopes",
        ["workspace_id", "project_id", "monitoring_scope_id"],
        ["workspace_id", "project_id", "id"],
    )
    op.create_foreign_key(
        "fk_query_terms_version_scope_tenant",
        "query_terms",
        "workflow_version_scopes",
        ["workspace_id", "project_id", "workflow_version_id", "matched_scope_id"],
        [
            "workspace_id",
            "project_id",
            "workflow_version_id",
            "monitoring_scope_id",
        ],
    )
    op.create_foreign_key(
        "fk_workflow_plan_save_requests_plan_tenant",
        "workflow_plan_save_requests",
        "workflow_plans",
        ["workspace_id", "project_id", "workflow_plan_id"],
        ["workspace_id", "project_id", "id"],
    )
    op.create_foreign_key(
        "fk_workflow_plan_save_requests_version_tenant",
        "workflow_plan_save_requests",
        "workflow_versions",
        ["workspace_id", "project_id", "workflow_plan_id", "workflow_version_id"],
        ["workspace_id", "project_id", "workflow_plan_id", "id"],
    )

    op.create_foreign_key(
        "fk_workflow_plans_current_version_owner",
        "workflow_plans",
        "workflow_versions",
        ["workspace_id", "project_id", "id", "current_version_id"],
        ["workspace_id", "project_id", "workflow_plan_id", "id"],
    )

    op.execute(
        """
        CREATE FUNCTION enforce_workflow_plan_current_version()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            final_current_version_id uuid;
        BEGIN
            SELECT current_version_id
            INTO final_current_version_id
            FROM workflow_plans
            WHERE id = NEW.id;

            IF NOT FOUND THEN
                RETURN NULL;
            END IF;

            IF final_current_version_id IS NULL THEN
                RAISE EXCEPTION
                    'workflow_plans.current_version_id must be set before commit'
                    USING ERRCODE = '23514';
            END IF;

            RETURN NULL;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_workflow_plans_current_version_required
        AFTER INSERT OR UPDATE OF current_version_id ON workflow_plans
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION enforce_workflow_plan_current_version();
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_workflow_plans_updated_at
        BEFORE UPDATE ON workflow_plans
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
        """
    )
    op.execute(
        """
        CREATE FUNCTION reject_workflow_plan_history_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION '% is immutable', TG_TABLE_NAME
                USING ERRCODE = '55000';
        END;
        $$;
        """
    )
    for table_name in IMMUTABLE_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER trg_{table_name}_immutable
            BEFORE UPDATE OR DELETE ON {table_name}
            FOR EACH ROW
            EXECUTE FUNCTION reject_workflow_plan_history_mutation();
            """
        )


def downgrade() -> None:
    for table_name in reversed(IMMUTABLE_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_immutable ON {table_name}")
    op.execute("DROP FUNCTION IF EXISTS reject_workflow_plan_history_mutation()")
    op.execute("DROP TRIGGER IF EXISTS trg_workflow_plans_updated_at ON workflow_plans")

    op.execute(
        "DROP TRIGGER IF EXISTS trg_workflow_plans_current_version_required ON workflow_plans"
    )
    op.execute("DROP FUNCTION IF EXISTS enforce_workflow_plan_current_version()")
    op.drop_constraint(
        "fk_workflow_plans_current_version_owner",
        "workflow_plans",
        type_="foreignkey",
    )

    for constraint_name, table_name in reversed(COMPOSITE_FOREIGN_KEYS):
        op.drop_constraint(constraint_name, table_name, type_="foreignkey")
    for index_name, table_name in reversed(TENANT_INDEXES):
        op.drop_index(index_name, table_name=table_name)

    op.drop_table("workflow_plan_save_requests")
    op.drop_table("query_terms")
    op.drop_table("workflow_version_scopes")
    op.drop_table("workflow_versions")
    op.drop_table("workflow_plans")
    op.drop_table("monitoring_scopes")
    op.drop_constraint(
        "uq_projects_workspace_id",
        "projects",
        type_="unique",
    )
