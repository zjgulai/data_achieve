from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import Select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.capability_governance import (
    CapabilityCandidateAssertionVersion,
    CapabilityCatalogHead,
    CapabilityCatalogSnapshot,
    CapabilityDiscoveryBatch,
    CapabilityGovernanceMembership,
    CapabilityGovernanceRequest,
    CapabilityPublicationRevision,
    CapabilityVerificationTask,
)
from data_intelligence_hub.models.user import User
from data_intelligence_hub.repositories.capability_governance import (
    acquire_governance_import_lock,
    add_governance_record,
    candidate_version_lock_statement,
    catalog_head_lock_statement,
    get_active_governance_membership,
    get_catalog_head_for_update,
    get_governance_request,
    get_governance_request_for_update,
    get_latest_candidate_version,
    get_latest_candidate_version_for_update,
    get_publication_revision,
    get_verification_task,
    get_verification_task_for_update,
    governance_request_lock_statement,
    list_candidate_versions,
    list_publication_revisions,
    list_verification_tasks,
    verification_task_lock_statement,
)

NOW = datetime(2026, 7, 14, tzinfo=UTC)
HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
HASH_C = "sha256:" + "c" * 64


@pytest_asyncio.fixture()
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as value:
        yield value
    await engine.dispose()


async def _seed_graph(session: AsyncSession) -> dict[str, object]:
    user = User(
        id=uuid.uuid4(),
        email="governance-repository@example.com",
        password_hash="not-a-real-secret",
        name="governance-repository",
        status="active",
    )
    membership = CapabilityGovernanceMembership(
        id=uuid.uuid4(),
        user_id=user.id,
        can_read=True,
        can_review=True,
        can_publish=True,
        is_active=True,
    )
    batch = CapabilityDiscoveryBatch(
        id=uuid.uuid4(),
        preview_fingerprint=HASH_A,
        request_hash=HASH_B,
        fixture_set_hash=HASH_C,
        imported_by_user_id=user.id,
        imported_at=NOW,
    )
    candidate_v1 = CapabilityCandidateAssertionVersion(
        id=uuid.uuid4(),
        candidate_key=HASH_A,
        semantic_version=1,
        candidate_fingerprint=HASH_B,
        predecessor_id=None,
        proposed_implementation_payload={"implementation_id": "example.v1"},
        candidate_payload={"support_status": "candidate"},
        first_seen_batch_id=batch.id,
        created_at=NOW,
    )
    candidate_v2 = CapabilityCandidateAssertionVersion(
        id=uuid.uuid4(),
        candidate_key=HASH_A,
        semantic_version=2,
        candidate_fingerprint=HASH_C,
        predecessor_id=candidate_v1.id,
        proposed_implementation_payload={"implementation_id": "example.v1"},
        candidate_payload={"support_status": "candidate"},
        first_seen_batch_id=batch.id,
        created_at=NOW + timedelta(minutes=1),
    )
    task = CapabilityVerificationTask(
        id=uuid.uuid4(),
        candidate_version_id=candidate_v2.id,
        task_type="semantic_drift",
        status="open",
        task_version=1,
        opened_at=NOW + timedelta(minutes=2),
        resolved_at=None,
        decision_id=None,
    )
    snapshot = CapabilityCatalogSnapshot(
        catalog_snapshot_id=HASH_A,
        catalog_payload={"schema_version": "capability_catalog.v2"},
        created_at=NOW,
    )
    revision = CapabilityPublicationRevision(
        id=uuid.uuid4(),
        revision_number=1,
        parent_revision_id=None,
        restored_from_revision_id=None,
        catalog_snapshot_id=snapshot.catalog_snapshot_id,
        publisher_user_id=user.id,
        published_at=NOW + timedelta(minutes=3),
        reason="initial publication",
        operations=[],
    )
    head = CapabilityCatalogHead(
        singleton_key="global",
        current_revision_id=revision.id,
        head_version=1,
        updated_at=NOW + timedelta(minutes=3),
    )
    request = CapabilityGovernanceRequest(
        id=uuid.uuid4(),
        actor_user_id=user.id,
        action_scope="publication:create",
        idempotency_key_hash=HASH_B,
        request_hash=HASH_C,
        outcome="created",
        response_status=201,
        response_payload={"revision_id": str(revision.id)},
        result_reference=str(revision.id),
        created_at=NOW + timedelta(minutes=3),
    )
    session.add_all(
        [
            user,
            membership,
            batch,
            candidate_v1,
            candidate_v2,
            task,
            snapshot,
            revision,
            head,
            request,
        ]
    )
    await session.commit()
    return {
        "user": user,
        "membership": membership,
        "candidate_v1": candidate_v1,
        "candidate_v2": candidate_v2,
        "task": task,
        "revision": revision,
        "head": head,
        "request": request,
    }


@pytest.mark.asyncio
async def test_governance_import_lock_is_a_sqlite_noop(
    session: AsyncSession,
) -> None:
    await acquire_governance_import_lock(session)

    assert session.in_transaction() is False


@pytest.mark.asyncio
async def test_global_reads_and_bounded_pagination_are_stable(
    session: AsyncSession,
) -> None:
    graph = await _seed_graph(session)
    user = graph["user"]
    candidate_v1 = graph["candidate_v1"]
    candidate_v2 = graph["candidate_v2"]
    task = graph["task"]
    revision = graph["revision"]
    request = graph["request"]
    assert isinstance(user, User)
    assert isinstance(candidate_v1, CapabilityCandidateAssertionVersion)
    assert isinstance(candidate_v2, CapabilityCandidateAssertionVersion)
    assert isinstance(task, CapabilityVerificationTask)
    assert isinstance(revision, CapabilityPublicationRevision)
    assert isinstance(request, CapabilityGovernanceRequest)

    membership = await get_active_governance_membership(session, user.id)
    assert membership is graph["membership"]
    assert await get_latest_candidate_version(session, HASH_A) is candidate_v2
    assert await get_verification_task(session, task.id) is task
    assert await get_publication_revision(session, revision.id) is revision
    assert (
        await get_governance_request(
            session,
            user.id,
            "publication:create",
            HASH_B,
        )
        is request
    )

    assert await list_candidate_versions(session, limit=1, offset=0) == [candidate_v2]
    assert await list_candidate_versions(session, limit=1, offset=1) == [candidate_v1]
    assert await list_verification_tasks(session, limit=50, offset=0) == [task]
    assert await list_publication_revisions(session, limit=50, offset=0) == [revision]

    with pytest.raises(ValueError, match="governance_pagination_invalid"):
        await list_candidate_versions(session, limit=0, offset=0)
    with pytest.raises(ValueError, match="governance_pagination_invalid"):
        await list_verification_tasks(session, limit=101, offset=0)
    with pytest.raises(ValueError, match="governance_pagination_invalid"):
        await list_publication_revisions(session, limit=50, offset=-1)


def test_governance_lock_statements_compile_with_refresh_semantics() -> None:
    user_id = uuid.uuid4()
    task_id = uuid.uuid4()
    dialect = postgresql.dialect()  # type: ignore[no-untyped-call]
    statements: list[Select[Any]] = [
        candidate_version_lock_statement(HASH_A),
        verification_task_lock_statement(task_id),
        catalog_head_lock_statement(),
        governance_request_lock_statement(
            user_id,
            "publication:create",
            HASH_B,
        ),
    ]

    for statement in statements:
        assert "FOR UPDATE" in str(statement.compile(dialect=dialect))
        assert statement.get_execution_options()["populate_existing"] is True


@pytest.mark.asyncio
async def test_lock_queries_return_rows_without_claiming_sqlite_lock_behavior(
    session: AsyncSession,
) -> None:
    graph = await _seed_graph(session)
    user = graph["user"]
    candidate_v2 = graph["candidate_v2"]
    task = graph["task"]
    head = graph["head"]
    request = graph["request"]
    assert isinstance(user, User)
    assert isinstance(candidate_v2, CapabilityCandidateAssertionVersion)
    assert isinstance(task, CapabilityVerificationTask)
    assert isinstance(head, CapabilityCatalogHead)
    assert isinstance(request, CapabilityGovernanceRequest)

    assert await get_latest_candidate_version_for_update(session, HASH_A) is candidate_v2
    assert await get_verification_task_for_update(session, task.id) is task
    assert await get_catalog_head_for_update(session) is head
    assert (
        await get_governance_request_for_update(
            session,
            user.id,
            "publication:create",
            HASH_B,
        )
        is request
    )


@pytest.mark.asyncio
async def test_add_record_flushes_without_commit_and_rollback_removes_it(
    session: AsyncSession,
) -> None:
    user = User(
        id=uuid.uuid4(),
        email="governance-rollback@example.com",
        password_hash="not-a-real-secret",
        name="governance-rollback",
        status="active",
    )
    session.add(user)
    await session.flush()
    membership = CapabilityGovernanceMembership(
        id=uuid.uuid4(),
        user_id=user.id,
        can_read=True,
        can_review=False,
        can_publish=False,
        is_active=True,
    )

    assert await add_governance_record(session, membership) is membership
    assert await get_active_governance_membership(session, user.id) is membership

    await session.rollback()
    assert await get_active_governance_membership(session, user.id) is None
