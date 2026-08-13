"""Add capability governance persistence and append-only Catalog revisions.

Revision ID: 202606110028
Revises: 202606110027
Create Date: 2026-07-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606110028"
down_revision: str | None = "202606110027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GOVERNANCE_TABLES: tuple[str, ...] = (
    "capability_governance_memberships",
    "capability_discovery_batches",
    "capability_source_snapshots",
    "capability_discovery_batch_sources",
    "capability_evidence",
    "capability_candidate_versions",
    "capability_candidate_evidence",
    "capability_verification_tasks",
    "capability_verification_decisions",
    "capability_catalog_snapshots",
    "capability_publication_revisions",
    "capability_catalog_head",
    "capability_governance_requests",
)

IMMUTABLE_TABLES: tuple[str, ...] = (
    "capability_discovery_batches",
    "capability_source_snapshots",
    "capability_discovery_batch_sources",
    "capability_evidence",
    "capability_candidate_versions",
    "capability_candidate_evidence",
    "capability_verification_decisions",
    "capability_catalog_snapshots",
    "capability_publication_revisions",
    "capability_governance_requests",
)


def _uuid_primary_key() -> sa.Column[object]:
    return sa.Column("id", sa.Uuid(), nullable=False)


def _created_at() -> sa.Column[object]:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "capability_governance_memberships",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("can_read", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("can_review", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("can_publish", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        _uuid_primary_key(),
        _created_at(),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "NOT (can_review OR can_publish) OR can_read",
            name="ck_capability_governance_memberships_permission_implication",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_cap_gov_membership_user",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_cap_gov_membership_user"),
    )

    op.create_table(
        "capability_discovery_batches",
        sa.Column("preview_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("request_hash", sa.String(length=71), nullable=False),
        sa.Column("fixture_set_hash", sa.String(length=71), nullable=False),
        sa.Column("imported_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        _uuid_primary_key(),
        sa.ForeignKeyConstraint(
            ["imported_by_user_id"],
            ["users.id"],
            name="fk_cap_discovery_batch_user",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "preview_fingerprint",
            name="uq_cap_discovery_batch_preview",
        ),
    )

    op.create_table(
        "capability_source_snapshots",
        sa.Column("fixture_id", sa.String(length=100), nullable=False),
        sa.Column("source_kind", sa.String(length=30), nullable=False),
        sa.Column("source_name", sa.String(length=500), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_version", sa.String(length=500), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("parser_id", sa.String(length=100), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("snapshot_payload", sa.JSON(), nullable=False),
        _created_at(),
        _uuid_primary_key(),
        sa.CheckConstraint(
            "source_kind IN ('public_market', 'official_doc')",
            name="ck_capability_source_snapshots_source_kind",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "fixture_id",
            "content_hash",
            name="uq_cap_source_fixture_content",
        ),
    )

    op.create_table(
        "capability_discovery_batch_sources",
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("source_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        _created_at(),
        sa.CheckConstraint(
            "ordinal >= 0",
            name="ck_capability_discovery_batch_sources_ordinal",
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["capability_discovery_batches.id"],
            name="fk_cap_batch_source_batch",
        ),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"],
            ["capability_source_snapshots.id"],
            name="fk_cap_batch_source_snapshot",
        ),
        sa.PrimaryKeyConstraint("batch_id", "source_snapshot_id"),
        sa.UniqueConstraint(
            "batch_id",
            "ordinal",
            name="uq_cap_batch_source_ordinal",
        ),
    )

    op.create_table(
        "capability_evidence",
        sa.Column("evidence_id", sa.String(length=500), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("evidence_payload", sa.JSON(), nullable=False),
        _created_at(),
        _uuid_primary_key(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evidence_id", name="uq_cap_evidence_external_id"),
    )

    op.create_table(
        "capability_candidate_versions",
        sa.Column("candidate_key", sa.String(length=71), nullable=False),
        sa.Column("semantic_version", sa.Integer(), nullable=False),
        sa.Column("candidate_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("predecessor_id", sa.Uuid(), nullable=True),
        sa.Column("proposed_implementation_payload", sa.JSON(), nullable=False),
        sa.Column("candidate_payload", sa.JSON(), nullable=False),
        sa.Column("first_seen_batch_id", sa.Uuid(), nullable=False),
        _created_at(),
        _uuid_primary_key(),
        sa.CheckConstraint(
            "semantic_version >= 1",
            name="ck_capability_candidate_versions_semantic_version",
        ),
        sa.CheckConstraint(
            "predecessor_id IS NOT NULL OR semantic_version = 1",
            name="ck_capability_candidate_versions_predecessor_version",
        ),
        sa.ForeignKeyConstraint(
            ["first_seen_batch_id"],
            ["capability_discovery_batches.id"],
            name="fk_cap_candidate_first_batch",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_key", "predecessor_id"],
            [
                "capability_candidate_versions.candidate_key",
                "capability_candidate_versions.id",
            ],
            name="fk_cap_candidate_predecessor_key",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "candidate_key",
            "semantic_version",
            name="uq_cap_candidate_key_version",
        ),
        sa.UniqueConstraint(
            "candidate_key",
            "candidate_fingerprint",
            name="uq_cap_candidate_key_fingerprint",
        ),
        sa.UniqueConstraint(
            "candidate_key",
            "id",
            name="uq_cap_candidate_key_id",
        ),
    )

    op.create_table(
        "capability_candidate_evidence",
        sa.Column("candidate_version_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("first_seen_batch_id", sa.Uuid(), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["candidate_version_id"],
            ["capability_candidate_versions.id"],
            name="fk_cap_candidate_evidence_candidate",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["capability_evidence.id"],
            name="fk_cap_candidate_evidence_evidence",
        ),
        sa.ForeignKeyConstraint(
            ["first_seen_batch_id"],
            ["capability_discovery_batches.id"],
            name="fk_cap_candidate_evidence_batch",
        ),
        sa.PrimaryKeyConstraint("candidate_version_id", "evidence_id"),
    )

    op.create_table(
        "capability_verification_tasks",
        sa.Column("candidate_version_id", sa.Uuid(), nullable=False),
        sa.Column("task_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("task_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "opened_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_id", sa.Uuid(), nullable=True),
        _uuid_primary_key(),
        sa.CheckConstraint(
            "task_type IN ('initial_review', 'evidence_refresh', 'semantic_drift')",
            name="ck_capability_verification_tasks_type",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'resolved')",
            name="ck_capability_verification_tasks_status",
        ),
        sa.CheckConstraint(
            "task_version >= 1",
            name="ck_capability_verification_tasks_version",
        ),
        sa.CheckConstraint(
            "(status = 'open' AND resolved_at IS NULL AND decision_id IS NULL) OR "
            "(status = 'resolved' AND resolved_at IS NOT NULL AND decision_id IS NOT NULL)",
            name="ck_capability_verification_tasks_resolution",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_version_id"],
            ["capability_candidate_versions.id"],
            name="fk_cap_verification_task_candidate",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "candidate_version_id",
            name="uq_cap_verification_task_candidate",
        ),
    )
    op.create_index(
        "uq_cap_verification_task_open",
        "capability_verification_tasks",
        ["candidate_version_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )

    op.create_table(
        "capability_verification_decisions",
        sa.Column("verification_task_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_version_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("verification_status", sa.String(length=20), nullable=False),
        sa.Column("reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("canonical_bundle", sa.JSON(none_as_null=True), nullable=True),
        _uuid_primary_key(),
        sa.CheckConstraint(
            "action IN ('verify', 'reject', 'deprecate')",
            name="ck_capability_verification_decisions_action",
        ),
        sa.CheckConstraint(
            "verification_status IN ('verified', 'rejected')",
            name="ck_capability_verification_decisions_status",
        ),
        sa.CheckConstraint(
            "(action = 'reject' AND verification_status = 'rejected' "
            "AND canonical_bundle IS NULL) OR "
            "(action IN ('verify', 'deprecate') AND verification_status = 'verified' "
            "AND canonical_bundle IS NOT NULL)",
            name="ck_capability_verification_decisions_bundle",
        ),
        sa.ForeignKeyConstraint(
            ["verification_task_id", "candidate_version_id"],
            [
                "capability_verification_tasks.id",
                "capability_verification_tasks.candidate_version_id",
            ],
            name="fk_cap_verification_decision_task_candidate",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_user_id"],
            ["users.id"],
            name="fk_cap_verification_decision_reviewer",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "verification_task_id",
            name="uq_cap_verification_decision_task",
        ),
    )
    op.create_foreign_key(
        "fk_cap_verification_task_decision",
        "capability_verification_tasks",
        "capability_verification_decisions",
        ["decision_id"],
        ["id"],
    )

    op.create_table(
        "capability_catalog_snapshots",
        sa.Column("catalog_snapshot_id", sa.String(length=71), nullable=False),
        sa.Column("catalog_payload", sa.JSON(), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("catalog_snapshot_id"),
    )

    op.create_table(
        "capability_publication_revisions",
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("parent_revision_id", sa.Uuid(), nullable=True),
        sa.Column("restored_from_revision_id", sa.Uuid(), nullable=True),
        sa.Column("catalog_snapshot_id", sa.String(length=71), nullable=False),
        sa.Column("publisher_user_id", sa.Uuid(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("operations", sa.JSON(), nullable=False),
        _uuid_primary_key(),
        sa.CheckConstraint(
            "revision_number >= 1",
            name="ck_capability_publication_revisions_number",
        ),
        sa.CheckConstraint(
            "restored_from_revision_id IS NULL OR restored_from_revision_id <> id",
            name="ck_capability_publication_revisions_restore_not_self",
        ),
        sa.ForeignKeyConstraint(
            ["parent_revision_id"],
            ["capability_publication_revisions.id"],
            name="fk_cap_publication_revision_parent",
        ),
        sa.ForeignKeyConstraint(
            ["restored_from_revision_id"],
            ["capability_publication_revisions.id"],
            name="fk_cap_publication_revision_restore",
        ),
        sa.ForeignKeyConstraint(
            ["catalog_snapshot_id"],
            ["capability_catalog_snapshots.catalog_snapshot_id"],
            name="fk_cap_publication_revision_snapshot",
        ),
        sa.ForeignKeyConstraint(
            ["publisher_user_id"],
            ["users.id"],
            name="fk_cap_publication_revision_publisher",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "revision_number",
            name="uq_cap_publication_revision_number",
        ),
    )

    op.create_table(
        "capability_catalog_head",
        sa.Column("singleton_key", sa.String(length=20), nullable=False),
        sa.Column("current_revision_id", sa.Uuid(), nullable=True),
        sa.Column("head_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "singleton_key = 'global'",
            name="ck_capability_catalog_head_singleton",
        ),
        sa.CheckConstraint(
            "head_version >= 0",
            name="ck_capability_catalog_head_version",
        ),
        sa.ForeignKeyConstraint(
            ["current_revision_id"],
            ["capability_publication_revisions.id"],
            name="fk_cap_catalog_head_revision",
        ),
        sa.PrimaryKeyConstraint("singleton_key"),
    )

    head_table = sa.table(
        "capability_catalog_head",
        sa.column("singleton_key", sa.String()),
        sa.column("current_revision_id", sa.Uuid()),
        sa.column("head_version", sa.Integer()),
    )
    op.bulk_insert(
        head_table,
        [
            {
                "singleton_key": "global",
                "current_revision_id": None,
                "head_version": 0,
            }
        ],
    )

    op.create_table(
        "capability_governance_requests",
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("action_scope", sa.String(length=500), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=71), nullable=False),
        sa.Column("request_hash", sa.String(length=71), nullable=False),
        sa.Column("outcome", sa.String(length=50), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=False),
        sa.Column("result_reference", sa.String(length=500), nullable=True),
        _created_at(),
        _uuid_primary_key(),
        sa.CheckConstraint(
            "response_status >= 200 AND response_status <= 299",
            name="ck_capability_governance_requests_response_status",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_cap_gov_request_actor",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "actor_user_id",
            "action_scope",
            "idempotency_key_hash",
            name="uq_cap_gov_request_idempotency",
        ),
    )

    op.create_index(
        "ix_cap_candidate_key_created",
        "capability_candidate_versions",
        ["candidate_key", "created_at"],
    )
    op.create_index(
        "ix_cap_verification_status_opened",
        "capability_verification_tasks",
        ["status", "opened_at"],
    )
    op.create_index(
        "ix_cap_publication_published",
        "capability_publication_revisions",
        ["published_at", "revision_number"],
    )
    op.create_index(
        "ix_cap_gov_request_actor_created",
        "capability_governance_requests",
        ["actor_user_id", "created_at"],
    )

    op.execute(
        """
        CREATE FUNCTION reject_capability_governance_mutation()
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
            EXECUTE FUNCTION reject_capability_governance_mutation();
            """
        )

    op.execute(
        """
        CREATE FUNCTION enforce_capability_verification_task_transition()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.status = 'resolved' THEN
                RAISE EXCEPTION 'resolved capability verification task is immutable'
                    USING ERRCODE = '55000';
            END IF;
            IF NEW.id <> OLD.id
                OR NEW.candidate_version_id <> OLD.candidate_version_id
                OR NEW.task_type <> OLD.task_type
                OR NEW.opened_at <> OLD.opened_at THEN
                RAISE EXCEPTION 'capability verification task identity is immutable'
                    USING ERRCODE = '55000';
            END IF;
            IF NEW.status = 'open' AND NEW.task_version <= OLD.task_version THEN
                RAISE EXCEPTION 'open task evidence refresh must increment task_version'
                    USING ERRCODE = '23514';
            END IF;
            IF NEW.status = 'resolved' AND NEW.task_version < OLD.task_version THEN
                RAISE EXCEPTION 'resolved task version cannot decrease'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_capability_verification_task_transition
        BEFORE UPDATE ON capability_verification_tasks
        FOR EACH ROW
        EXECUTE FUNCTION enforce_capability_verification_task_transition();
        """
    )
    op.execute(
        """
        CREATE FUNCTION enforce_capability_catalog_head_transition()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.singleton_key <> OLD.singleton_key
                OR NEW.head_version <> OLD.head_version + 1
                OR NEW.current_revision_id IS NULL THEN
                RAISE EXCEPTION 'invalid capability Catalog head transition'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_capability_catalog_head_transition
        BEFORE UPDATE ON capability_catalog_head
        FOR EACH ROW
        EXECUTE FUNCTION enforce_capability_catalog_head_transition();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_cap_gov_membership_updated_at
        BEFORE UPDATE ON capability_governance_memberships
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_cap_catalog_head_updated_at
        BEFORE UPDATE ON capability_catalog_head
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_cap_catalog_head_updated_at "
        "ON capability_catalog_head"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_cap_gov_membership_updated_at "
        "ON capability_governance_memberships"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_capability_catalog_head_transition "
        "ON capability_catalog_head"
    )
    op.execute("DROP FUNCTION IF EXISTS enforce_capability_catalog_head_transition()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_capability_verification_task_transition "
        "ON capability_verification_tasks"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS enforce_capability_verification_task_transition()"
    )
    for table_name in reversed(IMMUTABLE_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_immutable ON {table_name}")
    op.execute("DROP FUNCTION IF EXISTS reject_capability_governance_mutation()")

    op.drop_constraint(
        "fk_cap_verification_task_decision",
        "capability_verification_tasks",
        type_="foreignkey",
    )
    for table_name in reversed(GOVERNANCE_TABLES):
        op.drop_table(table_name)
