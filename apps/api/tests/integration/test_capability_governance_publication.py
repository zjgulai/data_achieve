from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.capability_governance import (
    CapabilityCatalogHead,
    CapabilityCatalogSnapshot,
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
    CapabilityGovernancePublicationCreateRequest,
    CapabilityGovernancePublicationRollbackRequest,
    CapabilityGovernanceReviewRequest,
    CapabilityVerificationAction,
    RemoveAssertionOperation,
    UpsertVerifiedAssertionOperation,
)
from data_intelligence_hub.services.capability_catalog import get_capability_catalog
from data_intelligence_hub.services.capability_discovery.preview import (
    build_capability_discovery_preview,
)
from data_intelligence_hub.services.capability_governance import (
    publication as publication_module,
)
from data_intelligence_hub.services.capability_governance.catalog_resolution import (
    resolve_current_capability_catalog,
)
from data_intelligence_hub.services.capability_governance.identity import (
    compute_candidate_key,
    compute_logical_assertion_key,
)
from data_intelligence_hub.services.capability_governance.intake import (
    import_capability_candidates,
)
from data_intelligence_hub.services.capability_governance.publication import (
    CapabilityGovernanceCatalogSnapshotInvalidError,
    CapabilityGovernanceDecisionNotCurrentError,
    CapabilityGovernancePublicationContractError,
    CapabilityGovernancePublicationParentConflictError,
    publish_capability_catalog,
    rollback_capability_catalog,
)
from data_intelligence_hub.services.capability_governance.verification import (
    review_capability_candidate,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import (
    compute_catalog_snapshot_id,
)

FIXTURE_IDS = [
    "tikhub-youtube-market-v1",
    "apify-reddit-market-v1",
    "youtube-data-api-doc-v1",
    "reddit-data-api-doc-v1",
]


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


async def _add_governor(session: AsyncSession, *, name: str) -> uuid.UUID:
    user_id = uuid.uuid4()
    session.add_all(
        [
            User(
                id=user_id,
                email=f"{name}@example.com",
                password_hash="not-a-real-secret",
                name=name,
                status="active",
            ),
            CapabilityGovernanceMembership(
                id=uuid.uuid4(),
                user_id=user_id,
                can_read=True,
                can_review=True,
                can_publish=True,
                is_active=True,
            ),
            CapabilityCatalogHead(
                singleton_key="global",
                current_revision_id=None,
                head_version=0,
                updated_at=datetime.now(UTC),
            ),
        ]
    )
    await session.commit()
    return user_id


def _preview() -> CapabilityDiscoveryPreviewResponse:
    return build_capability_discovery_preview(
        CapabilityDiscoveryPreviewRequest(
            schema_version="capability_discovery_preview_request.v1",
            preview_mode="fixture_replay",
            fixture_ids=FIXTURE_IDS,
        )
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
    *,
    action: CapabilityVerificationAction,
) -> CapabilityGovernanceReviewRequest:
    matched = _base_match(candidate)
    assert matched is not None
    implementation, source = matched
    assertion = CapabilityGovernanceCanonicalAssertionInput(
        assertion_id=source.assertion_id,
        implementation_id=implementation.implementation_id,
        resource_type=source.resource_type,
        operation=source.operation,
        support_status=(
            CapabilityStatus.DEPRECATED
            if action is CapabilityVerificationAction.DEPRECATE
            else CapabilityStatus.VERIFIED
        ),
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
        action=action,
        reason="Publication candidate was reviewed.",
        canonical_implementation=implementation,
        canonical_assertion=assertion,
    )


async def _reviewed_decisions(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    count: int,
    action: CapabilityVerificationAction = CapabilityVerificationAction.VERIFY,
) -> list[tuple[uuid.UUID, CapabilityCandidateAssertionPreview, str]]:
    preview = _preview()
    intake = await import_capability_candidates(
        session,
        actor_user_id=actor_user_id,
        payload=CapabilityGovernanceImportRequest(
            schema_version="capability_governance_import_request.v1",
            fixture_ids=FIXTURE_IDS,
            expected_preview_fingerprint=preview.preview_fingerprint,
        ),
        idempotency_key=f"publication-intake-{action.value}-key-01",
    )
    tasks = {
        item.candidate_key: item.verification_task_id
        for item in intake.candidates
        if item.verification_task_id is not None
    }
    candidates = [item for item in preview.candidate_assertions if _base_match(item)]
    assert len(candidates) >= count
    reviewed: list[tuple[uuid.UUID, CapabilityCandidateAssertionPreview, str]] = []
    for index, candidate in enumerate(candidates[:count], start=1):
        task_id = tasks[compute_candidate_key(candidate)]
        result = await review_capability_candidate(
            session,
            actor_user_id=actor_user_id,
            task_id=task_id,
            payload=_review_request(candidate, action=action),
            idempotency_key=(
                f"publication-review-{action.value}-key-{index:02d}"
            ),
        )
        assertion = _review_request(candidate, action=action).canonical_assertion
        assert assertion is not None
        logical_key = compute_logical_assertion_key(
            implementation_id=assertion.implementation_id,
            resource_type=assertion.resource_type,
            operation=assertion.operation,
            source_resource_group=assertion.source_resource_group,
        )
        reviewed.append((result.decision_id, candidate, logical_key))
    return reviewed


async def _count(session: AsyncSession, model: type[Base]) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)


@pytest.mark.asyncio
async def test_null_head_publish_snapshot_reuse_and_rollback_history(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publisher_id = await _add_governor(session, name="publication-history")
    base = get_capability_catalog()
    resolved_base = await resolve_current_capability_catalog(session)
    assert resolved_base.model_dump_json() == base.model_dump_json()
    assert compute_catalog_snapshot_id(resolved_base) == compute_catalog_snapshot_id(base)
    decisions = await _reviewed_decisions(
        session,
        actor_user_id=publisher_id,
        count=2,
    )

    first = await publish_capability_catalog(
        session,
        actor_user_id=publisher_id,
        payload=CapabilityGovernancePublicationCreateRequest(
            schema_version="capability_governance_publication_request.v1",
            expected_parent_revision_id=None,
            reason="Publish first verified fact.",
            operations=[
                UpsertVerifiedAssertionOperation(
                    operation="upsert_verified_assertion",
                    verification_decision_id=decisions[0][0],
                )
            ],
        ),
        idempotency_key="publication-create-key-0001",
    )
    replay = await publish_capability_catalog(
        session,
        actor_user_id=publisher_id,
        payload=CapabilityGovernancePublicationCreateRequest(
            schema_version="capability_governance_publication_request.v1",
            expected_parent_revision_id=None,
            reason="Publish first verified fact.",
            operations=[
                UpsertVerifiedAssertionOperation(
                    operation="upsert_verified_assertion",
                    verification_decision_id=decisions[0][0],
                )
            ],
        ),
        idempotency_key="publication-create-key-0001",
    )
    assert first.revision_number == 1
    assert first.parent_revision_id is None
    assert first.database_write is True
    assert replay.idempotent_replay is True
    assert replay.database_write is False
    assert replay.revision_id == first.revision_id
    assert await _count(session, CapabilityPublicationRevision) == 1

    with pytest.raises(CapabilityGovernancePublicationParentConflictError):
        await publish_capability_catalog(
            session,
            actor_user_id=publisher_id,
            payload=CapabilityGovernancePublicationCreateRequest(
                schema_version="capability_governance_publication_request.v1",
                expected_parent_revision_id=None,
                reason="Stale parent.",
                operations=[
                    UpsertVerifiedAssertionOperation(
                        operation="upsert_verified_assertion",
                        verification_decision_id=decisions[1][0],
                    )
                ],
            ),
            idempotency_key="publication-stale-key-0001",
        )

    second = await publish_capability_catalog(
        session,
        actor_user_id=publisher_id,
        payload=CapabilityGovernancePublicationCreateRequest(
            schema_version="capability_governance_publication_request.v1",
            expected_parent_revision_id=first.revision_id,
            reason="Publish second verified fact.",
            operations=[
                UpsertVerifiedAssertionOperation(
                    operation="upsert_verified_assertion",
                    verification_decision_id=decisions[1][0],
                )
            ],
        ),
        idempotency_key="publication-create-key-0002",
    )
    first_row = await session.get(CapabilityPublicationRevision, first.revision_id)
    assert first_row is not None
    first_frozen = (
        first_row.parent_revision_id,
        first_row.catalog_snapshot_id,
        first_row.reason,
        list(first_row.operations),
    )
    assert second.revision_number == 2
    assert second.parent_revision_id == first.revision_id
    assert second.catalog_snapshot_id != first.catalog_snapshot_id
    assert await _count(session, CapabilityCatalogSnapshot) == 2

    def raise_invalid_snapshot(snapshot: CapabilityCatalogSnapshot) -> None:
        del snapshot
        raise CapabilityGovernancePublicationContractError

    with monkeypatch.context() as patch:
        patch.setattr(publication_module, "_validated_snapshot", raise_invalid_snapshot)
        with pytest.raises(CapabilityGovernanceCatalogSnapshotInvalidError):
            await rollback_capability_catalog(
                session,
                actor_user_id=publisher_id,
                payload=CapabilityGovernancePublicationRollbackRequest(
                    schema_version="capability_governance_rollback_request.v1",
                    expected_current_revision_id=second.revision_id,
                    target_revision_id=first.revision_id,
                    reason="Reject an invalid target snapshot.",
                ),
                idempotency_key="publication-invalid-target-01",
            )

    rollback = await rollback_capability_catalog(
        session,
        actor_user_id=publisher_id,
        payload=CapabilityGovernancePublicationRollbackRequest(
            schema_version="capability_governance_rollback_request.v1",
            expected_current_revision_id=second.revision_id,
            target_revision_id=first.revision_id,
            reason="Restore the first publication.",
        ),
        idempotency_key="publication-rollback-key-01",
    )
    rollback_replay = await rollback_capability_catalog(
        session,
        actor_user_id=publisher_id,
        payload=CapabilityGovernancePublicationRollbackRequest(
            schema_version="capability_governance_rollback_request.v1",
            expected_current_revision_id=second.revision_id,
            target_revision_id=first.revision_id,
            reason="Restore the first publication.",
        ),
        idempotency_key="publication-rollback-key-01",
    )
    assert rollback.revision_number == 3
    assert rollback.parent_revision_id == second.revision_id
    assert rollback.restored_from_revision_id == first.revision_id
    assert rollback.catalog_snapshot_id == first.catalog_snapshot_id
    assert rollback_replay.idempotent_replay is True
    assert await _count(session, CapabilityCatalogSnapshot) == 2
    assert await _count(session, CapabilityPublicationRevision) == 3

    restored = await resolve_current_capability_catalog(session)
    assert compute_catalog_snapshot_id(restored) == first.catalog_snapshot_id
    first_row_after = await session.get(
        CapabilityPublicationRevision,
        first.revision_id,
        populate_existing=True,
    )
    assert first_row_after is not None
    assert (
        first_row_after.parent_revision_id,
        first_row_after.catalog_snapshot_id,
        first_row_after.reason,
        list(first_row_after.operations),
    ) == first_frozen

    same_content = await publish_capability_catalog(
        session,
        actor_user_id=publisher_id,
        payload=CapabilityGovernancePublicationCreateRequest(
            schema_version="capability_governance_publication_request.v1",
            expected_parent_revision_id=rollback.revision_id,
            reason="Reaffirm the restored verified fact.",
            operations=[
                UpsertVerifiedAssertionOperation(
                    operation="upsert_verified_assertion",
                    verification_decision_id=decisions[0][0],
                )
            ],
        ),
        idempotency_key="publication-same-content-01",
    )
    assert same_content.revision_number == 4
    assert same_content.catalog_snapshot_id == first.catalog_snapshot_id
    assert await _count(session, CapabilityCatalogSnapshot) == 2
    assert await _count(session, CapabilityPublicationRevision) == 4


@pytest.mark.asyncio
async def test_remove_requires_current_deprecate_decision_and_exact_key(
    session: AsyncSession,
) -> None:
    publisher_id = await _add_governor(session, name="publication-remove")
    decision_id, _, logical_key = (
        await _reviewed_decisions(
            session,
            actor_user_id=publisher_id,
            count=1,
            action=CapabilityVerificationAction.DEPRECATE,
        )
    )[0]

    with pytest.raises(CapabilityGovernancePublicationContractError):
        await publish_capability_catalog(
            session,
            actor_user_id=publisher_id,
            payload=CapabilityGovernancePublicationCreateRequest(
                schema_version="capability_governance_publication_request.v1",
                expected_parent_revision_id=None,
                reason="Wrong remove key.",
                operations=[
                    RemoveAssertionOperation(
                        operation="remove_assertion",
                        verification_decision_id=decision_id,
                        logical_assertion_key="sha256:" + "f" * 64,
                    )
                ],
            ),
            idempotency_key="publication-remove-wrong-01",
        )
    assert await _count(session, CapabilityPublicationRevision) == 0

    result = await publish_capability_catalog(
        session,
        actor_user_id=publisher_id,
        payload=CapabilityGovernancePublicationCreateRequest(
            schema_version="capability_governance_publication_request.v1",
            expected_parent_revision_id=None,
            reason="Remove deprecated fact.",
            operations=[
                RemoveAssertionOperation(
                    operation="remove_assertion",
                    verification_decision_id=decision_id,
                    logical_assertion_key=logical_key,
                )
            ],
        ),
        idempotency_key="publication-remove-valid-01",
    )
    catalog = await resolve_current_capability_catalog(session)
    remaining_keys = {
        compute_logical_assertion_key(
            implementation_id=item.implementation_id,
            resource_type=item.resource_type,
            operation=item.operation,
            source_resource_group=item.source_resource_group,
        )
        for item in catalog.assertions
    }
    assert result.revision_number == 1
    assert logical_key not in remaining_keys


@pytest.mark.asyncio
async def test_stale_decision_and_injected_failure_never_advance_head(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publisher_id = await _add_governor(session, name="publication-failure")
    decisions = await _reviewed_decisions(
        session,
        actor_user_id=publisher_id,
        count=2,
    )
    stale_decision = await session.get(
        CapabilityVerificationDecision,
        decisions[0][0],
    )
    assert stale_decision is not None
    session.add(
        CapabilityVerificationTask(
            id=uuid.uuid4(),
            candidate_version_id=stale_decision.candidate_version_id,
            task_type="evidence_refresh",
            status="open",
            task_version=1,
            opened_at=datetime.now(UTC),
            resolved_at=None,
            decision_id=None,
        )
    )
    await session.commit()

    with pytest.raises(CapabilityGovernanceDecisionNotCurrentError):
        await publish_capability_catalog(
            session,
            actor_user_id=publisher_id,
            payload=CapabilityGovernancePublicationCreateRequest(
                schema_version="capability_governance_publication_request.v1",
                expected_parent_revision_id=None,
                reason="Stale verified decision.",
                operations=[
                    UpsertVerifiedAssertionOperation(
                        operation="upsert_verified_assertion",
                        verification_decision_id=decisions[0][0],
                    )
                ],
            ),
            idempotency_key="publication-stale-decision-01",
        )

    request_count = await _count(session, CapabilityGovernanceRequest)
    real_add = publication_module._add

    async def fail_after_head_flush(record: Base, target_session: AsyncSession) -> None:
        await real_add(record, target_session)
        if isinstance(record, CapabilityGovernanceRequest):
            raise RuntimeError("injected_publication_failure")

    monkeypatch.setattr(publication_module, "_add", fail_after_head_flush)
    with pytest.raises(RuntimeError, match="injected_publication_failure"):
        await publish_capability_catalog(
            session,
            actor_user_id=publisher_id,
            payload=CapabilityGovernancePublicationCreateRequest(
                schema_version="capability_governance_publication_request.v1",
                expected_parent_revision_id=None,
                reason="Injected failure after head mutation.",
                operations=[
                    UpsertVerifiedAssertionOperation(
                        operation="upsert_verified_assertion",
                        verification_decision_id=decisions[1][0],
                    )
                ],
            ),
            idempotency_key="publication-injected-failure-01",
        )

    head = await session.get(CapabilityCatalogHead, "global")
    assert head is not None
    assert head.current_revision_id is None
    assert head.head_version == 0
    assert await _count(session, CapabilityCatalogSnapshot) == 0
    assert await _count(session, CapabilityPublicationRevision) == 0
    assert await _count(session, CapabilityGovernanceRequest) == request_count
