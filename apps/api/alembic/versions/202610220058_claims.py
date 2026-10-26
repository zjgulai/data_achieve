"""Create claims and claim_evidence.

Revision ID: 202610220058
Revises: 202610210055
Create Date: 2026-10-21

This revision is source-only. It must not be applied to a real database without
an exact-target authorization and an explicit backup/rollback plan.

说明：

- 表名来自契约冻结 v1 §1.1：``claims`` 与 ``claim_evidence``。
- ``claim_evidence`` 的主键只有 ``claim_id`` 与 ``evidence_id``。
  ``role`` 是普通列，不进主键。
- claim 状态只有契约 §2.6 的五个取值。
- 报告合同需要的五列全部可空。存量行保持 None：
  ``owner``、``scope_market``、``scope_window_days``、``scope_sample_n``、
  ``counterevidence_text``。
- 表内 ``state`` 与 ``claim_text`` 保持不变。它们分别对应 PRD 与报告合同的
  ``claim_status`` 与 ``text``。
- 反证完整性由服务层保证。数据库约束无法表达「至少一行关联」。
- 只有 gap 或 context 时状态受限。这条规则也由服务层保证。
- downgrade 先删 ``claim_evidence``，再删 ``claims``。
- CHECK 约束名与模型逐字一致。模型用 ``conv`` 屏蔽命名约定的前缀。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202610220058"
down_revision: str | None = "202610220057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "claims",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("evidence_grade", sa.String(length=30), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("owner", sa.Uuid(), nullable=True),
        sa.Column("scope_market", sa.String(length=40), nullable=True),
        sa.Column("scope_window_days", sa.Integer(), nullable=True),
        sa.Column("scope_sample_n", sa.Integer(), nullable=True),
        sa.Column("counterevidence_text", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_claims"),
        sa.CheckConstraint(
            "state IN ('confirmed', 'directional', 'hypothesis', 'evidence_gap', 'blocked')",
            name="ck_claims_state",
        ),
        sa.CheckConstraint(
            "evidence_grade IS NULL OR evidence_grade IN ('L0_unverified', 'L1_contract', "
            "'L2_fixture_local', 'L3_live_single', 'L4_authorized_live')",
            name="ck_claims_evidence_grade",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_claims_confidence_range",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_claims_workspace_id_workspaces",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_claims_project_id_projects",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["runs.id"],
            name="fk_claims_run_id_runs",
        ),
    )
    op.create_index("ix_claims_workspace_project", "claims", ["workspace_id", "project_id"])
    op.create_index("ix_claims_run_id", "claims", ["run_id"])

    op.create_table(
        "claim_evidence",
        sa.Column("claim_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("claim_id", "evidence_id", name="pk_claim_evidence"),
        sa.CheckConstraint(
            "role IN ('support', 'counter', 'context', 'gap')",
            name="ck_claim_evidence_role",
        ),
        sa.ForeignKeyConstraint(
            ["claim_id"],
            ["claims.id"],
            name="fk_claim_evidence_claim_id_claims",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["evidences.id"],
            name="fk_claim_evidence_evidence_id_evidences",
        ),
    )
    op.create_index(
        "ix_claim_evidence_evidence_id",
        "claim_evidence",
        ["evidence_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_claim_evidence_evidence_id", table_name="claim_evidence")
    op.drop_table("claim_evidence")
    op.drop_index("ix_claims_run_id", table_name="claims")
    op.drop_index("ix_claims_workspace_project", table_name="claims")
    op.drop_table("claims")
