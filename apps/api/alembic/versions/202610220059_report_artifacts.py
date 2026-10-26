"""Create the report_artifacts table.

Revision ID: 202610220059
Revises: 202610220058
Create Date: 2026-10-21

This revision is source-only. It must not be applied to a real database without
an exact-target authorization and an explicit backup/rollback plan.

说明：

- 表名来自契约冻结 v1 §1.1：``report_artifacts``。
- 五个哈希列是 64 位十六进制字符串，且不得为空。
- ``report_html_sha256`` 与 ``sop_html_sha256`` 分别存档两页。
  ``combined_sha256`` 是两页哈希的拼接哈希。
- ``contract_json`` 存规范化后的合同。它不得为空。
- ``report_html`` 与 ``sop_html`` 存内联 HTML。本批不写文件系统，
  所以不建路径列。
- ``version`` 默认 ``1.0.0``。
- ``report_id`` 为 B5 的报告表预留。本批不建外键。
- ``run_id`` 可空。手工报告可以没有 run。
- ``down_revision`` 指向 claims 的 056。056 接在 055 之后。
- downgrade 先删索引，再删表。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610220059"
down_revision: str | None = "202610220058"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("report_id", sa.Uuid(), nullable=True),
        sa.Column("template_id", sa.String(length=40), nullable=False),
        sa.Column(
            "version",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'1.0.0'"),
        ),
        sa.Column("contract_json", sa.JSON(), nullable=False),
        sa.Column("contract_sha256", sa.String(length=64), nullable=False),
        sa.Column("data_sha256", sa.String(length=64), nullable=False),
        sa.Column("report_html_sha256", sa.String(length=64), nullable=False),
        sa.Column("sop_html_sha256", sa.String(length=64), nullable=False),
        sa.Column("combined_sha256", sa.String(length=64), nullable=False),
        sa.Column("report_html", sa.Text(), nullable=True),
        sa.Column("sop_html", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_report_artifacts"),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_report_artifacts_workspace_id_workspaces",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_report_artifacts_project_id_projects",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["runs.id"],
            name="fk_report_artifacts_run_id_runs",
        ),
    )
    op.create_index(
        "ix_report_artifacts_workspace_project",
        "report_artifacts",
        ["workspace_id", "project_id"],
    )
    op.create_index("ix_report_artifacts_run_id", "report_artifacts", ["run_id"])
    op.create_index("ix_report_artifacts_report_id", "report_artifacts", ["report_id"])


def downgrade() -> None:
    op.drop_index("ix_report_artifacts_report_id", table_name="report_artifacts")
    op.drop_index("ix_report_artifacts_run_id", table_name="report_artifacts")
    op.drop_index(
        "ix_report_artifacts_workspace_project",
        table_name="report_artifacts",
    )
    op.drop_table("report_artifacts")
