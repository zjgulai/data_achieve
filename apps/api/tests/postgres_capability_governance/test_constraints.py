from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from data_intelligence_hub.models.capability_governance import (
    CapabilityGovernanceMembership,
)
from data_intelligence_hub.models.user import User
from data_intelligence_hub.schemas.capability_discovery import (
    CapabilityDiscoveryPreviewRequest,
)
from data_intelligence_hub.schemas.capability_governance import (
    CapabilityGovernanceImportRequest,
    CapabilityGovernanceReviewRequest,
    CapabilityVerificationAction,
)
from data_intelligence_hub.services.capability_discovery.preview import (
    build_capability_discovery_preview,
)
from data_intelligence_hub.services.capability_governance.intake import (
    import_capability_candidates,
)
from data_intelligence_hub.services.capability_governance.verification import (
    review_capability_candidate,
)

FIXTURE_IDS = [
    "tikhub-youtube-market-v1",
    "apify-reddit-market-v1",
    "youtube-data-api-doc-v1",
    "reddit-data-api-doc-v1",
]


@dataclass(frozen=True)
class PostgresDatabase:
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]


@dataclass(frozen=True)
class SeededGraph:
    database: PostgresDatabase
    actor_user_id: uuid.UUID
    batch_id: uuid.UUID
    resolved_task_id: uuid.UUID
    open_task_id: uuid.UUID


def _sqlstate(error: DBAPIError) -> str | None:
    return getattr(error.orig, "sqlstate", None) or getattr(error.orig, "pgcode", None)


@pytest_asyncio.fixture()
async def postgres_database(
    postgres_database_url: str,
) -> AsyncIterator[PostgresDatabase]:
    engine = create_async_engine(postgres_database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield PostgresDatabase(engine=engine, sessions=sessions)
    finally:
        await engine.dispose()


async def _seed_graph(database: PostgresDatabase) -> SeededGraph:
    actor_user_id = uuid.uuid4()
    async with database.sessions.begin() as session:
        session.add(
            User(
                id=actor_user_id,
                email=f"governance-pg-{actor_user_id}@example.test",
                password_hash="not-a-real-password",
                name="Governance PostgreSQL Test User",
                status="active",
            )
        )
        await session.flush()
        session.add(
            CapabilityGovernanceMembership(
                id=uuid.uuid4(),
                user_id=actor_user_id,
                can_read=True,
                can_review=True,
                can_publish=True,
                is_active=True,
            )
        )

    preview = build_capability_discovery_preview(
        CapabilityDiscoveryPreviewRequest(
            schema_version="capability_discovery_preview_request.v1",
            preview_mode="fixture_replay",
            fixture_ids=FIXTURE_IDS,
        )
    )
    async with database.sessions() as session:
        imported = await import_capability_candidates(
            session,
            actor_user_id=actor_user_id,
            payload=CapabilityGovernanceImportRequest(
                schema_version="capability_governance_import_request.v1",
                fixture_ids=FIXTURE_IDS,
                expected_preview_fingerprint=preview.preview_fingerprint,
            ),
            idempotency_key="postgres-constraints-import-key-01",
        )
    task_ids = [
        item.verification_task_id
        for item in imported.candidates
        if item.verification_task_id is not None
    ]
    assert imported.batch_id is not None
    assert len(task_ids) >= 2

    async with database.sessions() as session:
        await review_capability_candidate(
            session,
            actor_user_id=actor_user_id,
            task_id=task_ids[0],
            payload=CapabilityGovernanceReviewRequest(
                schema_version="capability_governance_review_request.v1",
                expected_task_version=1,
                action=CapabilityVerificationAction.REJECT,
                reason="Constraint fixture review rejection.",
                canonical_implementation=None,
                canonical_assertion=None,
            ),
            idempotency_key="postgres-constraints-review-key-01",
        )

    snapshot_id = f"sha256:{'f' * 64}"
    async with database.engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO capability_catalog_snapshots (
                    catalog_snapshot_id, catalog_payload
                ) VALUES (:snapshot_id, CAST(:payload AS JSON))
                """
            ),
            {"snapshot_id": snapshot_id, "payload": json.dumps({"fixture": True})},
        )
        await connection.execute(
            text(
                """
                INSERT INTO capability_publication_revisions (
                    id, revision_number, parent_revision_id,
                    restored_from_revision_id, catalog_snapshot_id,
                    publisher_user_id, published_at, reason, operations
                ) VALUES (
                    :id, 1, NULL, NULL, :snapshot_id,
                    :publisher_user_id, now(), 'Constraint fixture publication',
                    CAST('[]' AS JSON)
                )
                """
            ),
            {
                "id": uuid.uuid4(),
                "snapshot_id": snapshot_id,
                "publisher_user_id": actor_user_id,
            },
        )

    return SeededGraph(
        database=database,
        actor_user_id=actor_user_id,
        batch_id=imported.batch_id,
        resolved_task_id=task_ids[0],
        open_task_id=task_ids[1],
    )


@pytest_asyncio.fixture()
async def seeded_graph(postgres_database: PostgresDatabase) -> SeededGraph:
    return await _seed_graph(postgres_database)


@pytest.mark.asyncio
async def test_all_immutable_tables_reject_updates_and_deletes(
    seeded_graph: SeededGraph,
) -> None:
    mutations = {
        "capability_discovery_batches": "preview_fingerprint = preview_fingerprint",
        "capability_source_snapshots": "source_name = source_name",
        "capability_discovery_batch_sources": "ordinal = ordinal",
        "capability_evidence": "content_hash = content_hash",
        "capability_candidate_versions": "semantic_version = semantic_version",
        "capability_candidate_evidence": "first_seen_batch_id = first_seen_batch_id",
        "capability_verification_decisions": "reason = reason",
        "capability_catalog_snapshots": "catalog_payload = catalog_payload",
        "capability_publication_revisions": "reason = reason",
        "capability_governance_requests": "outcome = outcome",
    }

    for table_name, assignment in mutations.items():
        with pytest.raises(DBAPIError) as update_error:
            async with seeded_graph.database.engine.begin() as connection:
                await connection.execute(text(f"UPDATE {table_name} SET {assignment}"))
        assert _sqlstate(update_error.value) == "55000"

        with pytest.raises(DBAPIError) as delete_error:
            async with seeded_graph.database.engine.begin() as connection:
                await connection.execute(text(f"DELETE FROM {table_name}"))
        assert _sqlstate(delete_error.value) == "55000"


@pytest.mark.asyncio
async def test_open_task_uniqueness_and_state_transition_triggers(
    seeded_graph: SeededGraph,
) -> None:
    with pytest.raises(DBAPIError) as duplicate_open_error:
        async with seeded_graph.database.engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO capability_verification_tasks (
                        id, candidate_version_id, task_type, status, task_version
                    )
                    SELECT :new_id, candidate_version_id, 'evidence_refresh', 'open', 1
                    FROM capability_verification_tasks
                    WHERE id = :task_id
                    """
                ),
                {"new_id": uuid.uuid4(), "task_id": seeded_graph.open_task_id},
            )
    assert _sqlstate(duplicate_open_error.value) == "23505"

    with pytest.raises(DBAPIError) as open_version_error:
        async with seeded_graph.database.engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    UPDATE capability_verification_tasks
                    SET task_version = task_version
                    WHERE id = :task_id
                    """
                ),
                {"task_id": seeded_graph.open_task_id},
            )
    assert _sqlstate(open_version_error.value) == "23514"

    with pytest.raises(DBAPIError) as resolved_error:
        async with seeded_graph.database.engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    UPDATE capability_verification_tasks
                    SET task_version = task_version + 1
                    WHERE id = :task_id
                    """
                ),
                {"task_id": seeded_graph.resolved_task_id},
            )
    assert _sqlstate(resolved_error.value) == "55000"

    with pytest.raises(DBAPIError) as head_transition_error:
        async with seeded_graph.database.engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    UPDATE capability_catalog_head
                    SET head_version = head_version + 1
                    WHERE singleton_key = 'global'
                    """
                )
            )
    assert _sqlstate(head_transition_error.value) == "23514"


@pytest.mark.asyncio
async def test_singleton_candidate_and_evidence_constraints(
    seeded_graph: SeededGraph,
) -> None:
    with pytest.raises(DBAPIError) as singleton_error:
        async with seeded_graph.database.engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO capability_catalog_head (
                        singleton_key, current_revision_id, head_version
                    ) VALUES ('secondary', NULL, 0)
                    """
                )
            )
    assert _sqlstate(singleton_error.value) == "23514"

    async with seeded_graph.database.engine.connect() as connection:
        candidates = (
            (
                await connection.execute(
                    text(
                        """
                    SELECT id, candidate_key, semantic_version,
                           proposed_implementation_payload, candidate_payload,
                           first_seen_batch_id
                    FROM capability_candidate_versions
                    ORDER BY candidate_key
                    LIMIT 2
                    """
                    )
                )
            )
            .mappings()
            .all()
        )
        evidence = (
            (
                await connection.execute(
                    text(
                        """
                    SELECT id, evidence_id, content_hash, evidence_payload
                    FROM capability_evidence
                    ORDER BY evidence_id
                    LIMIT 1
                    """
                    )
                )
            )
            .mappings()
            .one()
        )
    assert len(candidates) == 2
    assert candidates[0]["candidate_key"] != candidates[1]["candidate_key"]

    first = candidates[0]
    second = candidates[1]
    with pytest.raises(DBAPIError) as predecessor_error:
        async with seeded_graph.database.engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO capability_candidate_versions (
                        id, candidate_key, semantic_version, candidate_fingerprint,
                        predecessor_id, proposed_implementation_payload,
                        candidate_payload, first_seen_batch_id
                    ) VALUES (
                        :id, :candidate_key, :semantic_version, :candidate_fingerprint,
                        :predecessor_id, CAST(:proposed AS JSON),
                        CAST(:candidate AS JSON), :batch_id
                    )
                    """
                ),
                {
                    "id": uuid.uuid4(),
                    "candidate_key": first["candidate_key"],
                    "semantic_version": int(first["semantic_version"]) + 1,
                    "candidate_fingerprint": f"sha256:{'e' * 64}",
                    "predecessor_id": second["id"],
                    "proposed": json.dumps(first["proposed_implementation_payload"]),
                    "candidate": json.dumps(first["candidate_payload"]),
                    "batch_id": first["first_seen_batch_id"],
                },
            )
    assert _sqlstate(predecessor_error.value) == "23503"

    with pytest.raises(DBAPIError) as predecessor_required_error:
        async with seeded_graph.database.engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO capability_candidate_versions (
                        id, candidate_key, semantic_version, candidate_fingerprint,
                        predecessor_id, proposed_implementation_payload,
                        candidate_payload, first_seen_batch_id
                    ) VALUES (
                        :id, :candidate_key, 2, :candidate_fingerprint,
                        NULL, CAST(:proposed AS JSON), CAST(:candidate AS JSON), :batch_id
                    )
                    """
                ),
                {
                    "id": uuid.uuid4(),
                    "candidate_key": first["candidate_key"],
                    "candidate_fingerprint": f"sha256:{'d' * 64}",
                    "proposed": json.dumps(first["proposed_implementation_payload"]),
                    "candidate": json.dumps(first["candidate_payload"]),
                    "batch_id": first["first_seen_batch_id"],
                },
            )
    assert _sqlstate(predecessor_required_error.value) == "23514"

    with pytest.raises(DBAPIError) as evidence_unique_error:
        async with seeded_graph.database.engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO capability_evidence (
                        id, evidence_id, content_hash, evidence_payload
                    ) VALUES (
                        :id, :evidence_id, :content_hash, CAST(:payload AS JSON)
                    )
                    """
                ),
                {
                    "id": uuid.uuid4(),
                    "evidence_id": evidence["evidence_id"],
                    "content_hash": evidence["content_hash"],
                    "payload": json.dumps(evidence["evidence_payload"]),
                },
            )
    assert _sqlstate(evidence_unique_error.value) == "23505"

    with pytest.raises(DBAPIError) as evidence_fk_error:
        async with seeded_graph.database.engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO capability_candidate_evidence (
                        candidate_version_id, evidence_id, first_seen_batch_id
                    ) VALUES (:candidate_id, :evidence_id, :batch_id)
                    """
                ),
                {
                    "candidate_id": first["id"],
                    "evidence_id": uuid.uuid4(),
                    "batch_id": seeded_graph.batch_id,
                },
            )
    assert _sqlstate(evidence_fk_error.value) == "23503"
