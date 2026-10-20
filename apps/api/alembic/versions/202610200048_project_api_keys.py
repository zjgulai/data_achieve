"""Create the project_api_keys table.

Revision ID: 202610200048
Revises: 202610200047
Create Date: 2026-10-21

This revision is source-only. It must not be applied to a real database without
an exact-target authorization and an explicit backup/rollback plan.

说明：

- 表只存 sha256 摘要，不存明文。
- ``key_hash`` 唯一。同一密钥不能登记两次。
- ``(workspace_id, project_id)`` 建复合索引，用于租户隔离查询。
- 撤销只写 ``revoked_at``，不删除行。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610200048"
down_revision: str | None = "202610200047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_api_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("key_prefix", sa.String(length=32), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("tool_allowlist", sa.JSON(), nullable=False),
        sa.Column("daily_collect_quota", sa.Integer(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_project_api_keys"),
        sa.UniqueConstraint("key_hash", name="uq_project_api_keys_key_hash"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_api_keys_project_id_projects",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_project_api_keys_workspace_id_workspaces",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_project_api_keys_created_by_user_id_users",
        ),
    )
    op.create_index(
        "ix_project_api_keys_workspace_project",
        "project_api_keys",
        ["workspace_id", "project_id"],
    )
    # 每个项目最多一把未撤销的密钥。轮换必须先撤销后签发。
    op.create_index(
        "uq_project_api_keys_active_project",
        "project_api_keys",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
        sqlite_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_project_api_keys_active_project", table_name="project_api_keys")
    op.drop_index("ix_project_api_keys_workspace_project", table_name="project_api_keys")
    op.drop_table("project_api_keys")
