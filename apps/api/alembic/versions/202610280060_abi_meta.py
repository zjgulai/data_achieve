"""Create the ABI external data center meta schema.

Revision ID: 202610280060
Revises: 202610220059
Create Date: 2026-10-28

This revision is source-only. It must not be applied to a real database without
an exact-target authorization and an explicit backup/rollback plan.

说明：

- 新建 ``meta`` / ``raw`` / ``abi`` 三个 schema，本文件只建 ``meta``。
- ``apify_account`` 一行一个 Apify 账号。实测 5 个 token 只对应 2 个账号，
  限流按账号计算，因此 token 不能当限流主体。
- ``apify_token`` 只存密文、指纹与前四位。明文不落库。
- ``token_fingerprint`` 用 ``bytea`` 存 sha256 原值，不用 ``char(64)``：
  固定长度字符串在 B-tree 上比 32 字节 binary 多一倍空间。
- ``status`` 只有 active / invalid / retired。没有 ``cooldown``：Apify 限流
  按账号计算，429 换 token 无效，把 token 打进冷却只会制造抖动。
- ``ingest_job.lease_version`` 是 fencing 令牌。租约过期后两个 worker
  可能同时持锁，写入方必须带 ``WHERE lease_version = :mine``。
- ``schedule_state`` 按账号一行，不是全局一行。
- ``audit_log`` 按月分区，与 ``raw.apify_item`` 同一套分区维护函数。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610280060"
down_revision: str | None = "202610220059"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMAS = ("meta", "raw", "abi")


def upgrade() -> None:
    for schema in SCHEMAS:
        op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))

    op.create_table(
        "apify_account",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("apify_user_id", sa.Text(), nullable=False),
        sa.Column("plan", sa.Text(), nullable=True),
        sa.Column(
            "data_retention_days",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("31"),
        ),
        sa.Column(
            "max_concurrency",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("8"),
        ),
        sa.Column(
            "max_rps",
            sa.Numeric(precision=6, scale=2),
            nullable=False,
            server_default=sa.text("8.0"),
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
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
        sa.PrimaryKeyConstraint("id", name="pk_apify_account"),
        sa.UniqueConstraint("label", name="uq_apify_account_label"),
        sa.UniqueConstraint("apify_user_id", name="uq_apify_account_apify_user_id"),
        schema="meta",
    )

    op.create_table(
        "apify_token",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("token_fingerprint", sa.LargeBinary(length=32), nullable=False),
        sa.Column("token_last4", sa.String(length=4), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column(
            "key_version",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'abi.fernet.v1'"),
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column("last_error_code", sa.Integer(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_apify_token"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["meta.apify_account.id"],
            name="fk_apify_token_account_id_apify_account",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "token_fingerprint", name="uq_apify_token_token_fingerprint"
        ),
        sa.UniqueConstraint(
            "account_id", "label", name="uq_apify_token_account_id_label"
        ),
        sa.CheckConstraint(
            "status IN ('active', 'invalid', 'retired')",
            name="status",
        ),
        schema="meta",
    )
    op.create_index(
        "ix_apify_token_account_status",
        "apify_token",
        ["account_id", "status"],
        schema="meta",
    )

    op.create_table(
        "apify_token_daily",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column(
            "requests", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "rate_limited", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "items_fetched", sa.BigInteger(), nullable=False, server_default=sa.text("0")
        ),
        sa.PrimaryKeyConstraint("id", name="pk_apify_token_daily"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["meta.apify_account.id"],
            name="fk_apify_token_daily_account_id_apify_account",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "account_id", "usage_date", name="uq_apify_token_daily_account_usage_date"
        ),
        schema="meta",
    )

    op.create_table(
        "actor_registry",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("actor_name", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("object_type", sa.Text(), nullable=False),
        sa.Column("endpoint_type", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Text(), nullable=False),
        sa.Column("license", sa.Text(), nullable=True),
        sa.Column("terms_url", sa.Text(), nullable=True),
        sa.Column("deprecated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_actor_registry"),
        sa.UniqueConstraint("actor_id", name="uq_actor_registry_actor_id"),
        sa.CheckConstraint(
            "source IN ('catalog', 'run_input', 'task_log', 'field_signature', 'manual')",
            name="source",
        ),
        sa.CheckConstraint(
            "confidence IN ('high', 'medium', 'low', 'unknown')",
            name="confidence",
        ),
        schema="meta",
    )

    op.create_table(
        "actor_schema_version",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("endpoint_type", sa.Text(), nullable=True),
        sa.Column("input_sha256", sa.LargeBinary(length=32), nullable=True),
        sa.Column("schema_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("field_names", sa.ARRAY(sa.Text()), nullable=False),
        sa.Column("field_types", sa.JSON(), nullable=False),
        sa.Column("field_count", sa.Integer(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sample_dataset_id", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_actor_schema_version"),
        sa.UniqueConstraint(
            "actor_id",
            "schema_hash",
            name="uq_actor_schema_version_actor_id_schema_hash",
        ),
        schema="meta",
    )

    op.create_table(
        "ingest_job",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("dataset_id", sa.Text(), nullable=True),
        sa.Column(
            "state",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default=sa.text("6")),
        sa.Column("not_before", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.Text(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "lease_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("last_error_code", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_ingest_job"),
        sa.UniqueConstraint("idempotency_key", name="uq_ingest_job_idempotency_key"),
        sa.CheckConstraint(
            "state IN ('queued', 'running', 'succeeded', 'failed', 'dead', 'skipped')",
            name="state",
        ),
        schema="meta",
    )
    # claim 查询的主路径：按状态 + 不早于时间取待跑作业
    op.create_index(
        "ix_ingest_job_state_not_before",
        "ingest_job",
        ["state", "not_before"],
        schema="meta",
    )
    op.create_index(
        "ix_ingest_job_account_state",
        "ingest_job",
        ["account_id", "state"],
        schema="meta",
    )

    op.create_table(
        "ingest_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sweep_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("datasets_total", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("datasets_done", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("items_total", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("bytes_total", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'running'")),
        sa.Column("tool_version", sa.Text(), nullable=True),
        sa.Column("config_sha256", sa.LargeBinary(length=32), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_ingest_run"),
        sa.CheckConstraint(
            "mode IN ('sweep', 'incremental', 'backfill', 'repair')",
            name="mode",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'aborted')",
            name="status",
        ),
        schema="meta",
    )

    op.create_table(
        "schedule_state",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("last_target_date", sa.Date(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sweep_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_schedule_state"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["meta.apify_account.id"],
            name="fk_schedule_state_account_id_apify_account",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("account_id", name="uq_schedule_state_account_id"),
        schema="meta",
    )

    op.create_table(
        "partition_registry",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("parent_table", sa.Text(), nullable=False),
        sa.Column("partition_name", sa.Text(), nullable=False),
        sa.Column("range_start", sa.Date(), nullable=False),
        sa.Column("range_end", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("detached_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_partition_registry"),
        sa.UniqueConstraint(
            "parent_table", "partition_name", name="uq_partition_registry_parent_name"
        ),
        schema="meta",
    )

    op.create_table(
        "worker_heartbeat",
        sa.Column("worker_id", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("beat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_job_id", sa.Uuid(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("worker_id", name="pk_worker_heartbeat"),
        schema="meta",
    )

    # audit_log 按月分区。分区键必须在主键里，这是声明式分区的硬约束。
    op.execute(
        sa.text(
            """
            CREATE TABLE meta.audit_log (
                occurred_month date NOT NULL,
                id uuid NOT NULL DEFAULT gen_random_uuid(),
                occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
                actor text NOT NULL,
                action text NOT NULL,
                object_type text NOT NULL,
                object_id text,
                workspace_id uuid,
                detail jsonb,
                PRIMARY KEY (occurred_month, id)
            ) PARTITION BY RANGE (occurred_month)
            """
        )
    )
    op.create_index(
        "ix_audit_log_occurred_at",
        "audit_log",
        ["occurred_at"],
        schema="meta",
    )
    # 审计表也需要当前月分区，否则第一条审计写入就报 no partition found
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS meta.audit_log_202610
            PARTITION OF meta.audit_log
            FOR VALUES FROM ('2026-10-01') TO ('2026-11-01')
            """
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO meta.partition_registry "
            "(id, parent_table, partition_name, range_start, range_end) "
            "VALUES (gen_random_uuid(), 'meta.audit_log', 'audit_log_202610', "
            "'2026-10-01', '2026-11-01') ON CONFLICT DO NOTHING"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS meta.audit_log CASCADE"))
    op.drop_table("worker_heartbeat", schema="meta")
    op.drop_table("partition_registry", schema="meta")
    op.drop_table("schedule_state", schema="meta")
    op.drop_table("ingest_run", schema="meta")
    op.drop_index("ix_ingest_job_account_state", table_name="ingest_job", schema="meta")
    op.drop_index("ix_ingest_job_state_not_before", table_name="ingest_job", schema="meta")
    op.drop_table("ingest_job", schema="meta")
    op.drop_table("actor_schema_version", schema="meta")
    op.drop_table("actor_registry", schema="meta")
    op.drop_table("apify_token_daily", schema="meta")
    op.drop_index("ix_apify_token_account_status", table_name="apify_token", schema="meta")
    op.drop_table("apify_token", schema="meta")
    op.drop_table("apify_account", schema="meta")
    # 三个 schema 不在这里 DROP：下一个迁移还要用，降级顺序由调用方控制
