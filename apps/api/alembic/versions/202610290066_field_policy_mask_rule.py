"""field_policy.mask_rule 加取值白名单。

Revision ID: 202610290066
Revises: 202610290065
Create Date: 2026-10-29

背景：``mask_rule`` 原本是自由文本（API 侧 max_length=200，DB 侧 Text 无
约束）。遮罩实现遇到未知规则会退回 ``***``——那是 fail-closed，可以接受。
真正的问题是反方向：``last4`` / ``partial`` 会保留尾部或首尾字符，而规则
拼写没有任何校验，意味着放宽遮罩不需要任何审批。

允许值：``redact`` / ``null`` / ``hash`` / ``last4`` / ``partial``。

``NULL`` 仍然合法：它表示「未指定规则」，遮罩时按 ``redact`` 处理。
历史行不受影响——旧代码只会写 ``NULL``，因为没有任何路径写入过规则。
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "202610290066"
down_revision: str | None = "202610290065"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ALLOWED = "('redact', 'null', 'hash', 'last4', 'partial')"


def upgrade() -> None:
    op.create_check_constraint(
        "ck_field_policy_mask_rule",
        "field_policy",
        f"mask_rule IS NULL OR mask_rule IN {_ALLOWED}",
        schema="abi",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_field_policy_mask_rule", "field_policy", schema="abi", type_="check"
    )
