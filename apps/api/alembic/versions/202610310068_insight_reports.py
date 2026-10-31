"""创建洞察分析报告表。

Revision ID: 202610310068
Revises: 202610290067
Create Date: 2026-10-31

设计：``docs/design/insight-new-integration.md`` §2。

- 新表是纯增量，不改任何既有表。
- ``insight_reports`` 只放元数据与数据范围；HTML 正文放
  ``insight_report_contents``，列表和详情在结构上就不会读到正文。
- ``data_scope`` 用 JSONB：不同分析类型的范围字段不同，内层形状由
  Pydantic 在导入时校验，数据库不约束。
- ``(workspace_id, analysis_type, version)`` 唯一：同一版本只导入一次，
  正文变更必须换版本。
- 正文的 SHA-256 与字节数入库，读取正文时每次校验，失败即 fail-closed。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "202610310068"
down_revision: str | None = "202610290067"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "insight_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("analysis_type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'ready'"),
            nullable=False,
        ),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column(
            "data_scope",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "source_status",
            sa.String(length=20),
            server_default=sa.text("'snapshot_only'"),
            nullable=False,
        ),
        sa.Column("source_note", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_insight_reports"),
        sa.UniqueConstraint(
            "workspace_id",
            "analysis_type",
            "version",
            name="uq_insight_reports_workspace_type_version",
        ),
        sa.CheckConstraint(
            "status IN ('ready', 'withdrawn')",
            name="status",
        ),
        sa.CheckConstraint(
            "source_status IN ('snapshot_only', 'connected', 'unavailable')",
            name="source_status",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_insight_reports_workspace_id_workspaces",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_insight_reports_project_id_projects",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_insight_reports_created_by_users",
        ),
    )
    op.create_index(
        "ix_insight_reports_workspace_type_generated",
        "insight_reports",
        ["workspace_id", "analysis_type", sa.text("generated_at DESC")],
    )
    op.create_index(
        "ix_insight_reports_project",
        "insight_reports",
        ["project_id"],
    )

    op.create_table(
        "insight_report_contents",
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column(
            "content_format",
            sa.String(length=10),
            server_default=sa.text("'html'"),
            nullable=False,
        ),
        sa.Column("content_html", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("content_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("report_id", name="pk_insight_report_contents"),
        sa.CheckConstraint(
            "content_format IN ('html')",
            name="format",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["insight_reports.id"],
            name="fk_insight_report_contents_report_id_insight_reports",
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    op.drop_table("insight_report_contents")
    op.drop_index("ix_insight_reports_project", table_name="insight_reports")
    op.drop_index(
        "ix_insight_reports_workspace_type_generated",
        table_name="insight_reports",
    )
    op.drop_table("insight_reports")
