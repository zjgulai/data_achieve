"""Add evidence reference metadata.

Revision ID: 202606110013
Revises: 202606110012
Create Date: 2026-06-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202606110013"
down_revision: str | None = "202606110012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "evidences",
        sa.Column("reference_metadata", sa.JSON(), nullable=True),
    )
    op.execute(
        """
        UPDATE evidences AS e
        SET reference_metadata = json_build_object(
            'claim_type', e.evidence_type,
            'source_layer',
                CASE
                    WHEN e.evidence_type = 'raw_record' THEN 'raw_record'
                    WHEN e.evidence_type = 'snapshot' THEN 'entity_snapshot'
                    WHEN e.evidence_type = 'signal' THEN 'signal'
                    ELSE 'source'
                END,
            'raw_record_id', e.raw_record_id::text,
            'content_hash', r.content_hash,
            'json_paths',
                CASE
                    WHEN e.evidence_type = 'raw_record' THEN json_build_array('$.content')
                    WHEN e.evidence_type = 'snapshot' THEN json_build_array('$.metrics')
                    WHEN e.evidence_type = 'signal' THEN json_build_array('$.signal')
                    ELSE json_build_array('$.url')
                END,
            'snapshot_strategy',
                CASE
                    WHEN r.content::jsonb ? 'html_content' THEN
                        json_build_object(
                            'storage', 'raw_records.content.html_content',
                            'text_path', '$.content.text_content',
                            'html_path', '$.content.html_content',
                            'html_available', true
                        )
                    ELSE json_build_object(
                        'storage', 'raw_records.content',
                        'html_available', false
                    )
                END
        )
        FROM raw_records AS r
        WHERE e.raw_record_id = r.id
          AND e.reference_metadata IS NULL;
        """
    )
    op.execute(
        """
        UPDATE evidences
        SET reference_metadata = json_build_object(
            'claim_type', evidence_type,
            'source_layer',
                CASE
                    WHEN evidence_type = 'snapshot' THEN 'entity_snapshot'
                    WHEN evidence_type = 'signal' THEN 'signal'
                    ELSE 'source'
                END,
            'json_paths',
                CASE
                    WHEN evidence_type = 'snapshot' THEN json_build_array('$.metrics')
                    WHEN evidence_type = 'signal' THEN json_build_array('$.signal')
                    ELSE json_build_array('$.url')
                END
        )
        WHERE reference_metadata IS NULL;
        """
    )


def downgrade() -> None:
    op.drop_column("evidences", "reference_metadata")
