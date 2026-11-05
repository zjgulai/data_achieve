"""创建数说 Bot 请求日志表(bot_request_log)。

Revision ID: 202610310069
Revises: 202610310068
Create Date: 2026-11-10

设计:Plan C 冲刺 D5(docs/plans/source-plan-c-sprint-2026-11-05.md §2 D5)。

Stage 3 自进化的统计基座:记录 @数说 的每条消息请求(channel/chat_id/
trigger/command),供后续「高频请求 ≥10 次/周 → 固化为常驻任务」的
周聚合统计。最小 schema,不做 PII 扩展:

- 不存消息原文,只存命令名与参数摘要(command/argument 截断)。
- chat_id/open_id 是飞书标识符,非个人身份字段;保留 90 天由运维清理。
- 写点在 webhook 后台任务,失败不阻断回执(见 router.py)。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610310069"
down_revision: str | None = "202610310068"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bot_request_log",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("bot", sa.String(length=30), nullable=False, server_default="shusuo"),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("chat_id", sa.String(length=80), nullable=False),
        sa.Column("open_id", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("trigger", sa.String(length=30), nullable=False),
        sa.Column("command", sa.String(length=40), nullable=False),
        sa.Column("argument", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("message_type", sa.String(length=30), nullable=False, server_default="text"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_bot_request_log_created_at", "bot_request_log", ["created_at"])
    op.create_index("ix_bot_request_log_command", "bot_request_log", ["command"])


def downgrade() -> None:
    op.drop_index("ix_bot_request_log_command", table_name="bot_request_log")
    op.drop_index("ix_bot_request_log_created_at", table_name="bot_request_log")
    op.drop_table("bot_request_log")
