"""Create entity and entity snapshot tables.

Revision ID: 202606110005
Revises: 202606110004
Create Date: 2026-06-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606110005"
down_revision: str | None = "202606110004"
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
        "entities",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("external_id", sa.String(length=500), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("domain", sa.String(length=30), nullable=False),
        sa.Column("latest_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "entity_type",
            "external_id",
            name="uq_entities_workspace_type_external",
        ),
    )
    op.create_index("ix_entities_workspace_domain", "entities", ["workspace_id", "domain"])
    op.create_index("ix_entities_project_type", "entities", ["project_id", "entity_type"])

    op.create_table(
        "entity_snapshots",
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("raw_record_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_data", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["raw_record_id"], ["raw_records.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_entity_snapshots_entity_captured",
        "entity_snapshots",
        ["entity_id", "captured_at"],
    )
    op.create_index(
        "ix_entity_snapshots_raw_record",
        "entity_snapshots",
        ["raw_record_id"],
    )
    op.create_foreign_key(
        "fk_entities_latest_snapshot_id_entity_snapshots",
        "entities",
        "entity_snapshots",
        ["latest_snapshot_id"],
        ["id"],
    )

    op.execute(
        """
        CREATE TRIGGER trg_entities_updated_at
        BEFORE UPDATE ON entities
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_entities_updated_at ON entities")
    op.drop_constraint(
        "fk_entities_latest_snapshot_id_entity_snapshots",
        "entities",
        type_="foreignkey",
    )
    op.drop_index("ix_entity_snapshots_raw_record", table_name="entity_snapshots")
    op.drop_index("ix_entity_snapshots_entity_captured", table_name="entity_snapshots")
    op.drop_table("entity_snapshots")
    op.drop_index("ix_entities_project_type", table_name="entities")
    op.drop_index("ix_entities_workspace_domain", table_name="entities")
    op.drop_table("entities")
