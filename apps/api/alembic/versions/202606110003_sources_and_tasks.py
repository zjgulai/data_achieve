"""Create source and collection task tables.

Revision ID: 202606110003
Revises: 202606110002
Create Date: 2026-06-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606110003"
down_revision: str | None = "202606110002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_column(name: str) -> sa.Column[sa.DateTime]:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "collectors",
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("config_schema", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("type"),
    )
    op.create_index(op.f("ix_collectors_type"), "collectors", ["type"], unique=False)

    collectors = sa.table(
        "collectors",
        sa.column("id", sa.Uuid()),
        sa.column("type", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("config_schema", sa.JSON()),
        sa.column("enabled", sa.Boolean()),
    )
    op.bulk_insert(
        collectors,
        [
            {
                "id": "11111111-1111-4111-8111-111111111111",
                "type": "github_repo",
                "name": "GitHub Repo",
                "description": "Monitor a public GitHub repository.",
                "config_schema": {
                    "required": ["owner", "repo"],
                    "properties": {"owner": "string", "repo": "string"},
                },
                "enabled": True,
            },
            {
                "id": "22222222-2222-4222-8222-222222222222",
                "type": "github_topic",
                "name": "GitHub Topic",
                "description": "Discover public repositories by GitHub topic.",
                "config_schema": {
                    "required": ["topic"],
                    "properties": {"topic": "string", "max_results": "integer"},
                },
                "enabled": True,
            },
            {
                "id": "33333333-3333-4333-8333-333333333333",
                "type": "generic_web",
                "name": "Generic Web Page",
                "description": "Monitor a single public web page.",
                "config_schema": {
                    "required": ["url"],
                    "properties": {"url": "string", "extract_mode": "string"},
                },
                "enabled": True,
            },
            {
                "id": "44444444-4444-4444-8444-444444444444",
                "type": "manual_json",
                "name": "Manual JSON",
                "description": "Import structured JSON payloads manually.",
                "config_schema": {
                    "required": ["entity_type", "json_data"],
                    "properties": {"entity_type": "string", "json_data": "object"},
                },
                "enabled": True,
            },
        ],
    )

    op.create_table(
        "sources",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("schedule_cron", sa.String(length=50), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sources_workspace_project", "sources", ["workspace_id", "project_id"])
    op.create_index("ix_sources_type_enabled", "sources", ["type", "enabled"])

    op.create_table(
        "collection_tasks",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("collector_type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("schedule_cron", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("success_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failure_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id"),
    )
    op.create_index(
        "ix_collection_tasks_workspace_status",
        "collection_tasks",
        ["workspace_id", "status"],
    )

    op.create_table(
        "task_runs",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("entities_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_traceback", sa.Text(), nullable=True),
        sa.Column("logs", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["collection_tasks.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_runs_task_created", "task_runs", ["task_id", "created_at"])

    for table in ("collectors", "sources", "collection_tasks"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION set_updated_at();
            """
        )


def downgrade() -> None:
    for table in ("collection_tasks", "sources", "collectors"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")

    op.drop_index("ix_task_runs_task_created", table_name="task_runs")
    op.drop_table("task_runs")
    op.drop_index("ix_collection_tasks_workspace_status", table_name="collection_tasks")
    op.drop_table("collection_tasks")
    op.drop_index("ix_sources_type_enabled", table_name="sources")
    op.drop_index("ix_sources_workspace_project", table_name="sources")
    op.drop_table("sources")
    op.drop_index(op.f("ix_collectors_type"), table_name="collectors")
    op.drop_table("collectors")
