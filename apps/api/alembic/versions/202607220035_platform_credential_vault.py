"""Add workspace-scoped encrypted platform credential bundles.

Revision ID: 202607220035
Revises: 202607170034
Create Date: 2026-07-22

This revision is source-only until a new exact-target PostgreSQL authorization
is granted. The table stores ciphertext and configured field names only.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202607220035"
down_revision: str | None = "202607170034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platform_credential_bundles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.String(length=120), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column("configured_fields", sa.JSON(), nullable=False),
        sa.Column("key_version", sa.String(length=30), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_platform_credential_bundles"),
        sa.UniqueConstraint(
            "workspace_id",
            "provider_id",
            name="uq_platform_credential_bundles_workspace_provider",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_platform_credential_bundles_workspace",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_platform_credential_bundles_created_by_user",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name="fk_platform_credential_bundles_updated_by_user",
        ),
    )
    op.create_index(
        "ix_platform_credential_bundles_workspace_id",
        "platform_credential_bundles",
        ["workspace_id"],
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM platform_credential_bundles) THEN
                RAISE EXCEPTION
                    '202607220035 downgrade refused: platform credential data exists';
            END IF;
        END $$;
        """
    )
    op.drop_index(
        "ix_platform_credential_bundles_workspace_id",
        table_name="platform_credential_bundles",
    )
    op.drop_table("platform_credential_bundles")
