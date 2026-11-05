"""补 meta.audit_log 的 2026-11 分区。

Revision ID: 202610310070
Revises: 202610310069
Create Date: 2026-11-11

背景:迁移 060 只预建了 audit_log_202610 一个分区。11 月起任何
INSERT 都会报「no partition of relation found for row」——D2 生产
冒烟已确认 meta.audit_log 0 行正是这个原因的前兆(写入者当时也缺,
D6 一并补上,见 abi_service.delete_abi_dataset)。

本迁移用 DO 块动态建「当前月与下一个月」的分区,幂等(IF NOT EXISTS),
以后每月的分区由运维脚本或下一迁移续建(阶段 1 的例行化在 NB)。
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "202610310070"
down_revision: str | None = "202610310069"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 与 060 的 meta.audit_log 同构:RANGE(occurred_month),月粒度。
_CREATE_PARTITION = """
DO $$
DECLARE
    cur date;
    part_name text;
    start_ts text;
    end_ts text;
BEGIN
    -- 当前月与其后两个月(覆盖发布窗口与下月运维间隔)。
    FOR i IN 0..2 LOOP
        cur := date_trunc('month', CURRENT_DATE) + make_interval(months => i);
        part_name := 'audit_log_' || to_char(cur, 'YYYYMM');
        IF NOT EXISTS (
            SELECT 1 FROM pg_tables
            WHERE schemaname = 'meta' AND tablename = part_name
        ) THEN
            start_ts := format('%s', cur);
            end_ts := format('%s', cur + make_interval(months => 1));
            EXECUTE format(
                'CREATE TABLE meta.%I PARTITION OF meta.audit_log '
                'FOR VALUES FROM (%L) TO (%L)',
                part_name, start_ts, end_ts
            );
        END IF;
    END LOOP;
END $$;
"""


def upgrade() -> None:
    op.execute(_CREATE_PARTITION)


def downgrade() -> None:
    # 分区里可能有已写入的审计行:downgrade 只删空分区,非空报错即停。
    op.execute(
        """
        DO $$
        DECLARE
            cur date;
            part_name text;
        BEGIN
            FOR i IN 0..2 LOOP
                cur := date_trunc('month', CURRENT_DATE) + make_interval(months => i);
                part_name := 'audit_log_' || to_char(cur, 'YYYYMM');
                IF EXISTS (
                    SELECT 1 FROM pg_tables
                    WHERE schemaname = 'meta' AND tablename = part_name
                ) THEN
                    EXECUTE format('DROP TABLE IF EXISTS meta.%I', part_name);
                END IF;
            END LOOP;
        END $$;
        """
    )
