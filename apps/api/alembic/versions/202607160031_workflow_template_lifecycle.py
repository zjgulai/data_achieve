"""Add WorkflowTemplate persistence and the six-state Plan lifecycle check.

Revision ID: 202607160031
Revises: 202607160030
Create Date: 2026-07-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202607160031"
down_revision: str | None = "202607160030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PLAN_STATUS_CHECK = (
    "status IN ('draft', 'previewed', 'approved', 'active', 'paused', 'archived')"
)


def upgrade() -> None:
    op.drop_constraint(
        "ck_workflow_plans_status_previewed",
        "workflow_plans",
        type_="check",
    )
    op.create_check_constraint(
        "ck_workflow_plans_status",
        "workflow_plans",
        _PLAN_STATUS_CHECK,
    )
    op.create_table(
        "workflow_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("template_key", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
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
        sa.CheckConstraint(
            _PLAN_STATUS_CHECK,
            name="ck_workflow_templates_status",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_workflow_templates_created_by_user",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id"],
            ["projects.workspace_id", "projects.id"],
            name="fk_workflow_templates_project_tenant",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_templates"),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "id",
            name="uq_workflow_templates_tenant_id",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "template_key",
            name="uq_workflow_templates_tenant_key",
        ),
    )
    op.create_index(
        "ix_workflow_templates_project_updated_at",
        "workflow_templates",
        ["workspace_id", "project_id", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workflow_templates_project_updated_at",
        table_name="workflow_templates",
    )
    op.drop_table("workflow_templates")
    op.drop_constraint("ck_workflow_plans_status", "workflow_plans", type_="check")
    op.create_check_constraint(
        "ck_workflow_plans_status_previewed",
        "workflow_plans",
        "status = 'previewed'",
    )
