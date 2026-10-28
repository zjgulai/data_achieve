"""Create the ABI catalog, query, upload, and export tables.

Revision ID: 202610280063
Revises: 202610280062
Create Date: 2026-10-28

This revision is source-only. It must not be applied to a real database without
an exact-target authorization and an explicit backup/rollback plan.

说明：

- 本文件建 ``abi`` schema 的目录层、上传层、导出层与字段策略。
- 表名用 ``catalog_dataset`` 而不是 ``dataset``：仓库已有 ``datasets`` /
  ``dataset_versions`` / ``dataset_export_jobs``，同名不同义会让 ORM、
  迁移与搜索全部混淆。
- 每张对外表都带 ``workspace_id``。现有业务表都有租户键，ABI 不能例外，
  否则一旦开启多租户就是旁路。
- ``field_policy`` 是 PII 遮罩的唯一依据。没有策略行的字段默认拒绝导出，
  这与「未知即遮罩」一致。``pii_class`` 默认 ``unknown`` 而不是 ``none``：
  默认 ``none`` 是 fail-open。
- ``upload_batch`` 的唯一键是 ``(dataset_id, file_sha256)``，用于幂等重传。
  ``upload_error`` 只存定位信息，不存原始值。
- ``export_job`` 记录 ``filters_hmac`` 而不是裸哈希：邮箱、handle 这类
  低熵值可被字典反查。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610280063"
down_revision: str | None = "202610280062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---------------------------------------------------------- 目录层
    op.create_table(
        "catalog_dataset",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("source_table", sa.Text(), nullable=True),
        sa.Column("platform", sa.Text(), nullable=True),
        sa.Column("object_type", sa.Text(), nullable=True),
        sa.Column("origin", sa.Text(), nullable=True),
        sa.Column("row_count", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_loaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("pii_scanned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("quality_status", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_catalog_dataset"),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_catalog_dataset_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name="fk_catalog_dataset_owner_id_users",
        ),
        sa.UniqueConstraint("workspace_id", "slug", name="uq_catalog_dataset_workspace_slug"),
        sa.CheckConstraint(
            "source_kind IN ('apify_platform', 'local_table', 'upload')",
            name="source_kind",
        ),
        schema="abi",
    )
    op.create_index(
        "ix_catalog_dataset_platform",
        "catalog_dataset",
        ["workspace_id", "platform"],
        schema="abi",
    )

    op.create_table(
        "dataset_column",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("column_name", sa.Text(), nullable=False),
        sa.Column("data_type", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("nullable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("filterable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sortable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id", name="pk_dataset_column"),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["abi.catalog_dataset.id"],
            name="fk_dataset_column_dataset_id_catalog_dataset",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "dataset_id", "column_name", name="uq_dataset_column_dataset_name"
        ),
        schema="abi",
    )

    # ---------------------------------------------------------- PII 策略
    op.create_table(
        "field_policy",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("field_path", sa.Text(), nullable=False),
        sa.Column(
            "pii_class",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'unknown'"),
        ),
        sa.Column("mask_rule", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.Text(), nullable=False, server_default=sa.text("'system'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_field_policy"),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["abi.catalog_dataset.id"],
            name="fk_field_policy_dataset_id_catalog_dataset",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "dataset_id", "field_path", name="uq_field_policy_dataset_field"
        ),
        sa.CheckConstraint(
            "pii_class IN ('unknown', 'none', 'quasi', 'direct', 'secret')",
            name="pii_class",
        ),
        schema="abi",
    )

    # ---------------------------------------------------------- 授权
    op.create_table(
        "access_grant",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default=sa.text("'viewer'")),
        sa.Column("granted_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_access_grant"),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["abi.catalog_dataset.id"],
            name="fk_access_grant_dataset_id_catalog_dataset",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_access_grant_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_access_grant_user_id_users",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("dataset_id", "user_id", name="uq_access_grant_dataset_user"),
        sa.CheckConstraint(
            "role IN ('viewer', 'editor', 'publisher', 'admin')",
            name="role",
        ),
        schema="abi",
    )
    op.create_index(
        "ix_access_grant_user",
        "access_grant",
        ["user_id", "workspace_id"],
        schema="abi",
    )

    # ---------------------------------------------------------- 上传
    op.create_table(
        "upload_batch",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("expected_sha256", sa.LargeBinary(length=32), nullable=True),
        sa.Column("actual_sha256", sa.LargeBinary(length=32), nullable=True),
        sa.Column("expected_rows", sa.BigInteger(), nullable=True),
        sa.Column("actual_rows", sa.BigInteger(), nullable=True),
        sa.Column("bytes_total", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("storage_path", sa.Text(), nullable=True),
        sa.Column("upload_token_hash", sa.LargeBinary(length=32), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows_loaded", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("rows_rejected", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_upload_batch"),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["abi.catalog_dataset.id"],
            name="fk_upload_batch_dataset_id_catalog_dataset",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_upload_batch_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "dataset_id", "actual_sha256", name="uq_upload_batch_dataset_sha256"
        ),
        sa.CheckConstraint(
            "mode IN ('append', 'upsert', 'replace')",
            name="mode",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'uploaded', 'validating', 'committed', 'failed', 'expired')",
            name="status",
        ),
        schema="abi",
    )

    op.create_table(
        "upload_error",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("column_name", sa.Text(), nullable=True),
        sa.Column("rule_id", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_upload_error"),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["abi.upload_batch.id"],
            name="fk_upload_error_batch_id_upload_batch",
            ondelete="CASCADE",
        ),
        schema="abi",
    )
    op.create_index(
        "ix_upload_error_batch_row",
        "upload_error",
        ["batch_id", "row_number"],
        schema="abi",
    )

    # ---------------------------------------------------------- 导出
    op.create_table(
        "export_policy",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=True),
        sa.Column("max_rows_masked", sa.BigInteger(), nullable=True),
        sa.Column(
            "require_dual_approval",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("allowed_formats", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_export_policy"),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_export_policy_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["abi.catalog_dataset.id"],
            name="fk_export_policy_dataset_id_catalog_dataset",
            ondelete="CASCADE",
        ),
        schema="abi",
    )

    op.create_table(
        "export_job",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("format", sa.Text(), nullable=False),
        sa.Column("mask_pii", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("filters", sa.JSON(), nullable=True),
        # HMAC 而非裸 sha256：低熵值可被字典反查
        sa.Column("filters_hmac", sa.LargeBinary(length=32), nullable=True),
        sa.Column("columns", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("artifact_path", sa.Text(), nullable=True),
        sa.Column("filename", sa.Text(), nullable=True),
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column("bytes_total", sa.BigInteger(), nullable=True),
        sa.Column("rows_total", sa.BigInteger(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_export_job"),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_export_job_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["abi.catalog_dataset.id"],
            name="fk_export_job_dataset_id_catalog_dataset",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "format IN ('csv', 'xlsx', 'jsonl')", name="format"
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'awaiting_approval', 'running', 'succeeded', "
            "'failed', 'expired', 'rejected')",
            name="status",
        ),
        schema="abi",
    )
    op.create_index(
        "ix_export_job_workspace_created",
        "export_job",
        ["workspace_id", "created_at"],
        schema="abi",
    )
    op.create_index(
        "ix_export_job_expires",
        "export_job",
        ["expires_at"],
        schema="abi",
        postgresql_where=sa.text("status = 'succeeded'"),
    )

    # ---------------------------------------------------------- 其它
    op.create_table(
        "saved_query",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        # 只存结构化过滤，不存 SQL 片段
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_saved_query"),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["abi.catalog_dataset.id"],
            name="fk_saved_query_dataset_id_catalog_dataset",
            ondelete="CASCADE",
        ),
        schema="abi",
    )

    op.create_table(
        "dataset_daily_stat",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("stat_date", sa.Date(), nullable=False),
        sa.Column("row_count", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("bytes_total", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("null_rate", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_dataset_daily_stat"),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["abi.catalog_dataset.id"],
            name="fk_dataset_daily_stat_dataset_id_catalog_dataset",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "dataset_id", "stat_date", name="uq_dataset_daily_stat_dataset_date"
        ),
        schema="abi",
    )

    # 类型转换错误集中记录，避免一页查询因坏行 500
    op.create_table(
        "cast_error",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=True),
        sa.Column("row_key", sa.Text(), nullable=True),
        sa.Column("column_name", sa.Text(), nullable=True),
        sa.Column("raw_value", sa.Text(), nullable=True),
        sa.Column("target_type", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_cast_error"),
        schema="abi",
    )

    # 跨源实体：同一视频在不同来源里 id 不同，视图靠它 join
    op.create_table(
        "platform_object",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("object_type", sa.Text(), nullable=False),
        sa.Column("canonical_id", sa.Text(), nullable=False),
        sa.Column("row_key", sa.Text(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_platform_object"),
        sa.UniqueConstraint("row_key", name="uq_platform_object_row_key"),
        schema="abi",
    )
    op.create_index(
        "ix_platform_object_canonical",
        "platform_object",
        ["platform", "object_type", "canonical_id"],
        schema="abi",
    )


def downgrade() -> None:
    op.drop_index("ix_platform_object_canonical", table_name="platform_object", schema="abi")
    op.drop_table("platform_object", schema="abi")
    op.drop_table("cast_error", schema="abi")
    op.drop_table("dataset_daily_stat", schema="abi")
    op.drop_table("saved_query", schema="abi")
    op.drop_index("ix_export_job_expires", table_name="export_job", schema="abi")
    op.drop_index("ix_export_job_workspace_created", table_name="export_job", schema="abi")
    op.drop_table("export_job", schema="abi")
    op.drop_table("export_policy", schema="abi")
    op.drop_index("ix_upload_error_batch_row", table_name="upload_error", schema="abi")
    op.drop_table("upload_error", schema="abi")
    op.drop_table("upload_batch", schema="abi")
    op.drop_index("ix_access_grant_user", table_name="access_grant", schema="abi")
    op.drop_table("access_grant", schema="abi")
    op.drop_table("field_policy", schema="abi")
    op.drop_table("dataset_column", schema="abi")
    op.drop_index("ix_catalog_dataset_platform", table_name="catalog_dataset", schema="abi")
    op.drop_table("catalog_dataset", schema="abi")
