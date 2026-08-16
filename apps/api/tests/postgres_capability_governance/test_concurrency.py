from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from data_intelligence_hub.models.capability_governance import (
    CapabilityCatalogHead,
    CapabilityDiscoveryBatch,
    CapabilityGovernanceMembership,
    CapabilityGovernanceRequest,
    CapabilityPublicationRevision,
    CapabilityVerificationDecision,
    CapabilityVerificationTask,
)
from data_intelligence_hub.models.user import User
from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityAssertion,
    CapabilityImplementation,
    CapabilityStatus,
)
from data_intelligence_hub.schemas.capability_discovery import (
    CapabilityCandidateAssertionPreview,
    CapabilityDiscoveryPreviewRequest,
    CapabilityDiscoveryPreviewResponse,
)
from data_intelligence_hub.schemas.capability_governance import (
    CapabilityGovernanceCanonicalAssertionInput,
    CapabilityGovernanceImportRequest,
    CapabilityGovernanceImportResponse,
    CapabilityGovernancePublicationCreateRequest,
    CapabilityGovernancePublicationResponse,
    CapabilityGovernancePublicationRollbackRequest,
    CapabilityGovernanceReviewRequest,
    CapabilityGovernanceReviewResponse,
    CapabilityVerificationAction,
    UpsertVerifiedAssertionOperation,
)
from data_intelligence_hub.services.capability_catalog import get_capability_catalog
from data_intelligence_hub.services.capability_discovery.preview import (
    build_capability_discovery_preview,
)
from data_intelligence_hub.services.capability_governance.identity import (
    compute_candidate_key,
)
from data_intelligence_hub.services.capability_governance.intake import (
    import_capability_candidates,
)
from data_intelligence_hub.services.capability_governance.publication import (
    publish_capability_catalog,
    rollback_capability_catalog,
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


def _preview() -> CapabilityDiscoveryPreviewResponse:
    return build_capability_discovery_preview(
        CapabilityDiscoveryPreviewRequest(
            schema_version="capability_discovery_preview_request.v1",
            preview_mode="fixture_replay",
            fixture_ids=FIXTURE_IDS,
        )
    )


def _import_request(
    preview: CapabilityDiscoveryPreviewResponse,
) -> CapabilityGovernanceImportRequest:
    return CapabilityGovernanceImportRequest(
        schema_version="capability_governance_import_request.v1",
        fixture_ids=FIXTURE_IDS,
        expected_preview_fingerprint=preview.preview_fingerprint,
    )


async def _seed_governor(database: PostgresDatabase, *, label: str) -> uuid.UUID:
    actor_user_id = uuid.uuid4()
    async with database.sessions.begin() as session:
        session.add(
            User(
                id=actor_user_id,
                email=f"governance-concurrency-{label}-{actor_user_id}@example.test",
                password_hash="not-a-real-password",
                name=f"Governance Concurrency {label}",
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
    return actor_user_id


async def _import(
    database: PostgresDatabase,
    *,
    actor_user_id: uuid.UUID,
    preview: CapabilityDiscoveryPreviewResponse,
    idempotency_key: str,
) -> CapabilityGovernanceImportResponse:
    async with database.sessions() as session:
        return await import_capability_candidates(
            session,
            actor_user_id=actor_user_id,
            payload=_import_request(preview),
            idempotency_key=idempotency_key,
        )


def _base_match(
    candidate: CapabilityCandidateAssertionPreview,
) -> tuple[CapabilityImplementation, CapabilityAssertion] | None:
    catalog = get_capability_catalog()
    for implementation in catalog.implementations:
        if (
            implementation.platform != candidate.platform
            or implementation.access_channel != candidate.access_channel
        ):
            continue
        for assertion in catalog.assertions:
            if (
                assertion.implementation_id == implementation.implementation_id
                and assertion.resource_type == candidate.resource_type
                and assertion.operation == candidate.operation
            ):
                return implementation, assertion
    return None


def _review_request(
    candidate: CapabilityCandidateAssertionPreview,
) -> CapabilityGovernanceReviewRequest:
    matched = _base_match(candidate)
    assert matched is not None
    implementation, source = matched
    assertion = CapabilityGovernanceCanonicalAssertionInput(
        assertion_id=source.assertion_id,
        implementation_id=implementation.implementation_id,
        resource_type=source.resource_type,
        operation=source.operation,
        support_status=CapabilityStatus.VERIFIED,
        source_resource_group=source.source_resource_group,
        region_scope=source.region_scope,
        purpose_scope=source.purpose_scope,
        auth_scope=source.auth_scope,
        field_contract=source.field_contract,
        constraints=source.constraints,
        score_profile=source.score_profile,
        evidence_refs=candidate.evidence_refs,
    )
    return CapabilityGovernanceReviewRequest(
        schema_version="capability_governance_review_request.v1",
        expected_task_version=1,
        action=CapabilityVerificationAction.VERIFY,
        reason="PostgreSQL concurrent verification.",
        canonical_implementation=implementation,
        canonical_assertion=assertion,
    )


async def _prepare_open_review(
    database: PostgresDatabase,
    *,
    actor_user_id: uuid.UUID,
    import_key: str,
) -> tuple[uuid.UUID, CapabilityGovernanceReviewRequest]:
    preview = _preview()
    imported = await _import(
        database,
        actor_user_id=actor_user_id,
        preview=preview,
        idempotency_key=import_key,
    )
    tasks = {
        item.candidate_key: item.verification_task_id
        for item in imported.candidates
        if item.verification_task_id is not None
    }
    candidate = next(item for item in preview.candidate_assertions if _base_match(item))
    task_id = tasks[compute_candidate_key(candidate)]
    assert task_id is not None
    return task_id, _review_request(candidate)


async def _prepare_verified_decision(
    database: PostgresDatabase,
    *,
    actor_user_id: uuid.UUID,
    label: str,
) -> uuid.UUID:
    task_id, payload = await _prepare_open_review(
        database,
        actor_user_id=actor_user_id,
        import_key=f"postgres-{label}-intake-key-01",
    )
    async with database.sessions() as session:
        reviewed = await review_capability_candidate(
            session,
            actor_user_id=actor_user_id,
            task_id=task_id,
            payload=payload,
            idempotency_key=f"postgres-{label}-review-key-01",
        )
    return reviewed.decision_id


async def _count(database: PostgresDatabase, model: type[object]) -> int:
    async with database.sessions() as session:
        return int(await session.scalar(select(func.count()).select_from(model)) or 0)


@pytest.mark.asyncio
async def test_concurrent_same_import_key_has_one_write_and_one_replay(
    postgres_database: PostgresDatabase,
) -> None:
    actor_user_id = await _seed_governor(postgres_database, label="same-import")
    preview = _preview()
    start = asyncio.Event()

    async def run() -> CapabilityGovernanceImportResponse:
        await start.wait()
        return await _import(
            postgres_database,
            actor_user_id=actor_user_id,
            preview=preview,
            idempotency_key="postgres-concurrent-same-import-key-01",
        )

    tasks = [asyncio.create_task(run()) for _ in range(2)]
    start.set()
    results = await asyncio.gather(*tasks, return_exceptions=True)

    responses = [item for item in results if isinstance(item, CapabilityGovernanceImportResponse)]
    assert len(responses) == 2, results
    assert sum(item.idempotent_replay for item in responses) == 1
    assert sum(item.database_write for item in responses) == 1
    assert await _count(postgres_database, CapabilityDiscoveryBatch) == 1
    assert await _count(postgres_database, CapabilityGovernanceRequest) == 1


@pytest.mark.asyncio
async def test_concurrent_distinct_import_keys_have_one_domain_change(
    postgres_database: PostgresDatabase,
) -> None:
    actor_user_id = await _seed_governor(postgres_database, label="distinct-import")
    preview = _preview()
    start = asyncio.Event()

    async def run(key: str) -> CapabilityGovernanceImportResponse:
        await start.wait()
        return await _import(
            postgres_database,
            actor_user_id=actor_user_id,
            preview=preview,
            idempotency_key=key,
        )

    tasks = [
        asyncio.create_task(run("postgres-concurrent-import-key-01")),
        asyncio.create_task(run("postgres-concurrent-import-key-02")),
    ]
    start.set()
    results = await asyncio.gather(*tasks, return_exceptions=True)

    responses = [item for item in results if isinstance(item, CapabilityGovernanceImportResponse)]
    assert len(responses) == 2, results
    assert sum(item.domain_changed for item in responses) == 1
    assert all(item.database_write for item in responses)
    assert await _count(postgres_database, CapabilityDiscoveryBatch) == 1
    assert await _count(postgres_database, CapabilityGovernanceRequest) == 2


@pytest.mark.asyncio
async def test_concurrent_same_review_key_has_one_write_and_one_replay(
    postgres_database: PostgresDatabase,
) -> None:
    actor_user_id = await _seed_governor(postgres_database, label="review")
    task_id, payload = await _prepare_open_review(
        postgres_database,
        actor_user_id=actor_user_id,
        import_key="postgres-concurrent-review-intake-key-01",
    )
    start = asyncio.Event()

    async def run() -> CapabilityGovernanceReviewResponse:
        await start.wait()
        async with postgres_database.sessions() as session:
            return await review_capability_candidate(
                session,
                actor_user_id=actor_user_id,
                task_id=task_id,
                payload=payload,
                idempotency_key="postgres-concurrent-same-review-key-01",
            )

    tasks = [
        asyncio.create_task(run()),
        asyncio.create_task(run()),
    ]
    start.set()
    results = await asyncio.gather(*tasks, return_exceptions=True)

    responses = [item for item in results if isinstance(item, CapabilityGovernanceReviewResponse)]
    assert len(responses) == 2, results
    assert sum(item.idempotent_replay for item in responses) == 1
    assert sum(item.database_write for item in responses) == 1
    assert await _count(postgres_database, CapabilityVerificationDecision) == 1
    async with postgres_database.sessions() as session:
        task = await session.get(CapabilityVerificationTask, task_id)
    assert task is not None
    assert task.status == "resolved"
    assert {item.decision_id for item in responses} == {task.decision_id}


@pytest.mark.asyncio
async def test_concurrent_same_publish_key_has_one_write_and_one_replay(
    postgres_database: PostgresDatabase,
) -> None:
    actor_user_id = await _seed_governor(postgres_database, label="publish")
    decision_id = await _prepare_verified_decision(
        postgres_database,
        actor_user_id=actor_user_id,
        label="concurrent-publish",
    )
    payload = CapabilityGovernancePublicationCreateRequest(
        schema_version="capability_governance_publication_request.v1",
        expected_parent_revision_id=None,
        reason="Concurrent PostgreSQL publication.",
        operations=[
            UpsertVerifiedAssertionOperation(
                operation="upsert_verified_assertion",
                verification_decision_id=decision_id,
            )
        ],
    )
    start = asyncio.Event()

    async def run() -> CapabilityGovernancePublicationResponse:
        await start.wait()
        async with postgres_database.sessions() as session:
            return await publish_capability_catalog(
                session,
                actor_user_id=actor_user_id,
                payload=payload,
                idempotency_key="postgres-concurrent-same-publish-key-01",
            )

    tasks = [
        asyncio.create_task(run()),
        asyncio.create_task(run()),
    ]
    start.set()
    results = await asyncio.gather(*tasks, return_exceptions=True)

    responses = [
        item for item in results if isinstance(item, CapabilityGovernancePublicationResponse)
    ]
    assert len(responses) == 2, results
    assert sum(item.idempotent_replay for item in responses) == 1
    assert sum(item.database_write for item in responses) == 1
    assert await _count(postgres_database, CapabilityPublicationRevision) == 1
    async with postgres_database.sessions() as session:
        head = await session.get(CapabilityCatalogHead, "global")
    assert head is not None
    assert {item.revision_id for item in responses} == {head.current_revision_id}
    assert head.head_version == 1


@pytest.mark.asyncio
async def test_concurrent_same_rollback_key_has_one_write_and_one_replay(
    postgres_database: PostgresDatabase,
) -> None:
    actor_user_id = await _seed_governor(postgres_database, label="rollback")
    decision_id = await _prepare_verified_decision(
        postgres_database,
        actor_user_id=actor_user_id,
        label="concurrent-rollback",
    )

    async def publish(
        parent_id: uuid.UUID | None, key: str
    ) -> CapabilityGovernancePublicationResponse:
        async with postgres_database.sessions() as session:
            return await publish_capability_catalog(
                session,
                actor_user_id=actor_user_id,
                payload=CapabilityGovernancePublicationCreateRequest(
                    schema_version="capability_governance_publication_request.v1",
                    expected_parent_revision_id=parent_id,
                    reason="Prepare PostgreSQL rollback history.",
                    operations=[
                        UpsertVerifiedAssertionOperation(
                            operation="upsert_verified_assertion",
                            verification_decision_id=decision_id,
                        )
                    ],
                ),
                idempotency_key=key,
            )

    first = await publish(None, "postgres-rollback-publish-key-01")
    second = await publish(first.revision_id, "postgres-rollback-publish-key-02")
    payload = CapabilityGovernancePublicationRollbackRequest(
        schema_version="capability_governance_rollback_request.v1",
        expected_current_revision_id=second.revision_id,
        target_revision_id=first.revision_id,
        reason="Concurrent PostgreSQL rollback.",
    )
    start = asyncio.Event()

    async def run() -> CapabilityGovernancePublicationResponse:
        await start.wait()
        async with postgres_database.sessions() as session:
            return await rollback_capability_catalog(
                session,
                actor_user_id=actor_user_id,
                payload=payload,
                idempotency_key="postgres-concurrent-same-rollback-key-01",
            )

    tasks = [
        asyncio.create_task(run()),
        asyncio.create_task(run()),
    ]
    start.set()
    results = await asyncio.gather(*tasks, return_exceptions=True)

    responses = [
        item for item in results if isinstance(item, CapabilityGovernancePublicationResponse)
    ]
    assert len(responses) == 2, results
    assert sum(item.idempotent_replay for item in responses) == 1
    assert sum(item.database_write for item in responses) == 1
    assert responses[0].restored_from_revision_id == first.revision_id
    assert await _count(postgres_database, CapabilityPublicationRevision) == 3
    async with postgres_database.sessions() as session:
        head = await session.get(CapabilityCatalogHead, "global")
    assert head is not None
    assert head.current_revision_id == responses[0].revision_id
    assert head.head_version == 3
