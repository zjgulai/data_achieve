"""Create the ABI raw Apify tables and the partition provisioning function.

Revision ID: 202610280061
Revises: 202610280060
Create Date: 2026-10-28

This revision is source-only. It must not be applied to a real database without
an exact-target authorization and an explicit backup/rollback plan.

说明：

- ``raw.apify_dataset`` 是清单：账号内每个 dataset 一行，含保留期估算。
- ``raw.apify_run`` 是运行记录。``usage_total_usd`` 只对终态 run 取值，
  RUNNING 的 run 费用仍在变化。
- ``raw.apify_item`` 是原始条目，按月 RANGE 分区，只追加。
- **分区键是 dataset 的 createdAt 月首，不是入仓日。**
  这是本设计的核心决定。同一 dataset 在任何日期重抓都落同一分区，
  主键天然去重；若用入仓日，跨天重跑会在两个分区各留一行。
- 主键含分区键是 PostgreSQL 声明式分区的硬约束，不是风格选择。
- ``dataset_id`` 不是主键前导列，因此必须单独建 ``(dataset_id, item_index)``
  索引。生产是 PG16，没有 B-tree skip scan（PG18 才有）。
- 不建 GIN ``jsonb_path_ops``：查询层用 ``->>`` 做等值与范围，
  该 opclass 只服务 ``@>`` / ``@?`` / ``@@``，建了用不上还增加写成本。
- ``item`` 剔除 ``\\u0000`` 后才能写入，PostgreSQL jsonb 拒绝 NUL 字节。
- ``ensure_partitions`` 从给定起点补到终点，**不是只建未来**。
  首日回填 2026-09 的数据时，只建未来会让 INSERT 报
  ``no partition of relation found`` 并整批回滚。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610280061"
down_revision: str | None = "202610280060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 预建分区范围：覆盖实测最早数据（2026-09-25）到 2027-01
PARTITION_MONTHS = [
    "2026-09-01", "2026-10-01", "2026-11-01", "2026-12-01", "2027-01-01",
]


def upgrade() -> None:
    op.create_table(
        "apify_dataset",
        sa.Column("dataset_id", sa.Text(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=True),
        sa.Column("act_id", sa.Text(), nullable=True),
        sa.Column("actor_name", sa.Text(), nullable=True),
        sa.Column("platform", sa.Text(), nullable=False, server_default=sa.text("'other'")),
        sa.Column("object_type", sa.Text(), nullable=False, server_default=sa.text("'unknown'")),
        # endpoint_type 与 endpoint_source 是两件事：
        # endpoint_type 是归因出的业务端点（apify_tiktok_scraper 等），可为空
        #   ——歧义 actor 无法按首条字段判定时写 NULL，不猜；
        # endpoint_source 是这条归因从哪来（catalog / run_input / manual 等），非空。
        sa.Column("endpoint_type", sa.Text(), nullable=True),
        sa.Column(
            "endpoint_source",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'unknown'"),
        ),
        sa.Column("confidence", sa.Text(), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("dataset_name", sa.Text(), nullable=True),
        sa.Column("named", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accessed_at", sa.DateTime(timezone=True), nullable=True),
        # 保留期只是估算：API 没有 expiresAt 字段，命名 dataset 永久保留
        sa.Column("retention_deadline", sa.Date(), nullable=True),
        sa.Column(
            "retention_estimated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("item_count_head", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("item_count_local", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("schema_hash", sa.LargeBinary(length=32), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_batch", sa.Uuid(), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_row_at",
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
        sa.PrimaryKeyConstraint("dataset_id", name="pk_apify_dataset"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["meta.apify_account.id"],
            name="fk_apify_dataset_account_id_apify_account",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'complete', 'expired', 'missing', 'partial', 'error')",
            name="status",
        ),
        schema="raw",
    )
    op.create_index(
        "ix_apify_dataset_account_created",
        "apify_dataset",
        ["account_id", "created_at"],
        schema="raw",
    )
    op.create_index(
        "ix_apify_dataset_platform_type",
        "apify_dataset",
        ["platform", "object_type"],
        schema="raw",
    )
    op.create_index(
        "ix_apify_dataset_retention",
        "apify_dataset",
        ["retention_deadline"],
        schema="raw",
        # 谓词只排除终态：complete 的 dataset 同样会过期，用 status='active'
        # 会把已入仓但面临删除的数据集排除在风险查询之外（实测 8,465 行全是
        # complete，索引命中 0 行）。
        postgresql_where=sa.text("status NOT IN ('expired', 'missing')"),
    )

    op.create_table(
        "apify_run",
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("act_id", sa.Text(), nullable=True),
        sa.Column("actor_name", sa.Text(), nullable=True),
        sa.Column("build_id", sa.Text(), nullable=True),
        sa.Column("build_number", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("default_dataset_id", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        # RUNNING 时该值仍在变，只有 finished_at 非空才可信
        sa.Column("usage_total_usd", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("usage_final", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("input_sha256", sa.LargeBinary(length=32), nullable=True),
        sa.Column("input_available", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("run_id", name="pk_apify_run"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["meta.apify_account.id"],
            name="fk_apify_run_account_id_apify_account",
        ),
        schema="raw",
    )
    op.create_index(
        "ix_apify_run_act_started",
        "apify_run",
        ["act_id", "started_at"],
        schema="raw",
    )

    # ---- 分区主表 ----
    # collected_month 由应用写入 dataset.createdAt 的月首，不是入仓日
    op.execute(
        sa.text(
            """
            CREATE TABLE raw.apify_item (
                collected_month date NOT NULL,
                dataset_id text NOT NULL,
                item_index integer NOT NULL,
                account_id uuid NOT NULL,
                platform text NOT NULL DEFAULT 'other',
                object_type text NOT NULL DEFAULT 'unknown',
                item jsonb NOT NULL,
                content_hash bytea NOT NULL,
                pii_class text NOT NULL DEFAULT 'unknown',
                item_status text NOT NULL DEFAULT 'content',
                fetched_at timestamptz NOT NULL DEFAULT clock_timestamp(),
                fetch_batch_id uuid NOT NULL,
                PRIMARY KEY (collected_month, dataset_id, item_index),
                CONSTRAINT ck_apify_item_index CHECK (item_index >= 0),
                CONSTRAINT ck_apify_item_pii CHECK (
                    pii_class IN ('unknown', 'none', 'quasi', 'direct', 'secret')
                ),
                CONSTRAINT ck_apify_item_status CHECK (
                    item_status IN ('content', 'empty', 'error')
                )
            ) PARTITION BY RANGE (collected_month)
            """
        )
    )
    op.execute(sa.text(
        "CREATE INDEX ix_apify_item_dataset ON raw.apify_item (dataset_id, item_index)"
    ))
    op.execute(sa.text(
        "CREATE INDEX ix_apify_item_platform_month ON raw.apify_item (platform, collected_month)"
    ))
    op.execute(sa.text(
        "CREATE INDEX ix_apify_item_content_hash ON raw.apify_item (content_hash)"
    ))

    for month_start in PARTITION_MONTHS:
        _create_item_partition(month_start)

    # ---- 分区供给函数 ----
    # 从 p_from 到 p_to 逐月补齐。首日回填前必须调用，不能只建未来。
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION meta.ensure_partitions(
                p_from date, p_to date
            ) RETURNS integer
            LANGUAGE plpgsql AS $$
            DECLARE
                cur date := date_trunc('month', p_from)::date;
                stop date := date_trunc('month', p_to)::date;
                part text;
                created integer := 0;
            BEGIN
                -- advisory lock 防并发重复建
                PERFORM pg_advisory_xact_lock(hashtext('meta.ensure_partitions'));
                WHILE cur <= stop LOOP
                    part := 'apify_item_' || to_char(cur, 'YYYYMM');
                    IF to_regclass('raw.' || part) IS NULL THEN
                        EXECUTE format(
                            'CREATE TABLE raw.%I PARTITION OF raw.apify_item '
                            'FOR VALUES FROM (%L) TO (%L)',
                            part, cur, (cur + interval '1 month')::date
                        );
                        INSERT INTO meta.partition_registry
                            (id, parent_table, partition_name, range_start, range_end)
                        VALUES (gen_random_uuid(), 'raw.apify_item', part,
                                cur, (cur + interval '1 month')::date)
                        ON CONFLICT DO NOTHING;
                        created := created + 1;
                    END IF;
                    cur := (cur + interval '1 month')::date;
                END LOOP;
                RETURN created;
            END;
            $$;
            """
        )
    )

    # 登记已预建的分区
    for month_start in PARTITION_MONTHS:
        start = month_start
        op.execute(
            sa.text(
                f"INSERT INTO meta.partition_registry "
                f"(id, parent_table, partition_name, range_start, range_end) "
                f"VALUES (gen_random_uuid(), 'raw.apify_item', "
                f"'apify_item_{start[0:7].replace('-', '')}', "
                f"'{start}'::date, ('{start}'::date + interval '1 month')::date) "
                f"ON CONFLICT DO NOTHING"
            )
        )


def _create_item_partition(month_start: str) -> None:
    suffix = month_start[0:7].replace("-", "")
    op.execute(
        sa.text(
            f"CREATE TABLE IF NOT EXISTS raw.apify_item_{suffix} "
            f"PARTITION OF raw.apify_item "
            f"FOR VALUES FROM ('{month_start}') "
            f"TO (('{month_start}'::date + interval '1 month')::date)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP FUNCTION IF EXISTS meta.ensure_partitions(date, date)"))
    op.execute(sa.text("DROP TABLE IF EXISTS raw.apify_item CASCADE"))
    op.drop_index("ix_apify_run_act_started", table_name="apify_run", schema="raw")
    op.drop_table("apify_run", schema="raw")
    op.drop_index("ix_apify_dataset_retention", table_name="apify_dataset", schema="raw")
    op.drop_index("ix_apify_dataset_platform_type", table_name="apify_dataset", schema="raw")
    op.drop_index("ix_apify_dataset_account_created", table_name="apify_dataset", schema="raw")
    op.drop_table("apify_dataset", schema="raw")
