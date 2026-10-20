"""Create the tool_catalog table.

Revision ID: 202610200047
Revises: 202610200046
Create Date: 2026-10-20

This revision is source-only. It must not be applied to a real database without
an exact-target authorization and an explicit backup/rollback plan.

说明：

- 表以字符串 ``tool_id`` 为主键。契约规定工具标识稳定，不用 uuid。
- 参数与输出 schema 用 JSON 列保存。Postgres 与 SQLite 都可读写。
- 表不含租户列。目录由种子脚本重放，对所有工作区共享。
- ``updated_at`` 由数据库默认值与更新钩子维护。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610200047"
down_revision: str | None = "202610200046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tool_catalog",
        sa.Column("tool_id", sa.String(length=200), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("platform", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=200), nullable=False),
        sa.Column("provider_group", sa.String(length=100), nullable=False),
        sa.Column("method", sa.String(length=50), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("risk_class", sa.String(length=20), nullable=False),
        sa.Column("output_kind", sa.String(length=20), nullable=False),
        sa.Column("run_mode", sa.String(length=20), nullable=False),
        sa.Column("cancellable", sa.Boolean(), nullable=False),
        sa.Column("executable", sa.Boolean(), nullable=False),
        sa.Column("is_alias_view", sa.Boolean(), nullable=False),
        sa.Column("canonical_tool_id", sa.String(length=200), nullable=False),
        sa.Column("cost_summary", sa.Text(), nullable=True),
        sa.Column("cost_source", sa.String(length=30), nullable=False),
        sa.Column("catalog_status", sa.String(length=50), nullable=False),
        sa.Column("availability", sa.String(length=30), nullable=False),
        sa.Column("contract_version", sa.String(length=50), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("required_parameters", sa.JSON(), nullable=False),
        sa.Column("optional_parameters", sa.JSON(), nullable=False),
        sa.Column("output_schema", sa.JSON(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("tool_id", name="pk_tool_catalog"),
    )


def downgrade() -> None:
    op.drop_table("tool_catalog")
