"""Enable auto freshness policy for curated collection sources.

Revision ID: 202606110014
Revises: 202606110013
Create Date: 2026-06-14 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "202606110014"
down_revision = "202606110013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _set_curated_schedule_policy("auto_freshness", "manual_refresh_only")


def downgrade() -> None:
    _set_curated_schedule_policy("manual_refresh_only", "auto_freshness")


def _set_curated_schedule_policy(next_policy: str, previous_policy: str) -> None:
    for table_name in ("sources", "collection_tasks"):
        op.execute(
            f"""
            UPDATE {table_name}
            SET config = jsonb_set(
                config::jsonb,
                '{{schedule_policy}}',
                '"{next_policy}"',
                true
            )::json
            WHERE config->>'schedule_policy' = '{previous_policy}'
              AND config->'provenance'->>'dataset' = 'curated_demo'
            """
        )
