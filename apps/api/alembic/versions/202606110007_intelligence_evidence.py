"""Create intelligence and evidence tables.

Revision ID: 202606110007
Revises: 202606110006
Create Date: 2026-06-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606110007"
down_revision: str | None = "202606110006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_column(name: str) -> sa.Column[sa.DateTime]:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "intelligence_items",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("intelligence_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="new"),
        sa.Column("impact_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("novelty_score", sa.Float(), nullable=False),
        sa.Column("urgency_score", sa.Float(), nullable=False),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("generated_by", sa.String(length=10), nullable=False),
        sa.Column("domain", sa.String(length=30), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_intelligence_project_created",
        "intelligence_items",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_intelligence_workspace_domain_created",
        "intelligence_items",
        ["workspace_id", "domain", "created_at"],
    )
    op.create_index(
        "ix_intelligence_final_score",
        "intelligence_items",
        ["final_score"],
    )
    op.execute(
        """
        CREATE TRIGGER trg_intelligence_items_updated_at
        BEFORE UPDATE ON intelligence_items
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
        """
    )

    op.create_table(
        "evidences",
        sa.Column("intelligence_id", sa.Uuid(), nullable=False),
        sa.Column("signal_id", sa.Uuid(), nullable=True),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("raw_record_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_type", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("highlighted_text", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["intelligence_id"], ["intelligence_items.id"]),
        sa.ForeignKeyConstraint(["raw_record_id"], ["raw_records.id"]),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidences_intelligence", "evidences", ["intelligence_id"])

    op.create_table(
        "intelligence_feedback",
        sa.Column("intelligence_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("feedback_type", sa.String(length=30), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["intelligence_id"], ["intelligence_items.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_intelligence_feedback_intelligence",
        "intelligence_feedback",
        ["intelligence_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_intelligence_feedback_intelligence", table_name="intelligence_feedback")
    op.drop_table("intelligence_feedback")
    op.drop_index("ix_evidences_intelligence", table_name="evidences")
    op.drop_table("evidences")
    op.execute("DROP TRIGGER IF EXISTS trg_intelligence_items_updated_at ON intelligence_items")
    op.drop_index("ix_intelligence_final_score", table_name="intelligence_items")
    op.drop_index("ix_intelligence_workspace_domain_created", table_name="intelligence_items")
    op.drop_index("ix_intelligence_project_created", table_name="intelligence_items")
    op.drop_table("intelligence_items")
