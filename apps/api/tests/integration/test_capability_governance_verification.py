from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import cast

import pytest
import pytest_asyncio
from pydantic import JsonValue
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
from data_intelligence_hub.schemas.capability_catalog import CapabilityStatus
from data_intelligence_hub.schemas.capability_discovery import (
    CapabilityCandidateAssertionPreview,
    CapabilityDiscoveryPreviewRequest,
    CapabilityDiscoveryPreviewResponse,
)
from data_intelligence_hub.schemas.capability_governance import (
    CapabilityGovernanceCanonicalAssertionInput,
    CapabilityGovernanceImportRequest,
    CapabilityGovernanceReviewRequest,
    CapabilityVerificationAction,
)
from data_intelligence_hub.services.capability_catalog import get_capability_catalog
from data_intelligence_hub.services.capability_discovery.fingerprint import (
    canonical_json_sha256,
)
from data_intelligence_hub.services.capability_discovery.preview import (
    build_capability_discovery_preview,
)
from data_intelligence_hub.services.capability_governance import (
    intake as intake_module,
)
from data_intelligence_hub.services.capability_governance import (
    verification as verification_module,
)
from data_intelligence_hub.services.capability_governance.authority import (
    CapabilityGovernanceForbiddenError,
)
from data_intelligence_hub.services.capability_governance.identity import (
    compute_candidate_key,
)
from data_intelligence_hub.services.capability_governance.intake import (
    import_capability_candidates,
)
from data_intelligence_hub.services.capability_governance.verification import (
    CapabilityGovernanceReviewContractError,
    CapabilityGovernanceReviewIdempotencyConflictError,
    CapabilityGovernanceReviewTransactionStateError,
    CapabilityGovernanceVerificationTaskConflictError,
    review_capability_candidate,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import (
    compute_catalog_snapshot_id,
)

FIXTURE_IDS = ["tikhub-youtube-market-v1"]


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


async def _add_governor(
    session: AsyncSession,
    *,
    name: str,
    can_review: bool = True,
) -> uuid.UUID:
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
                can_review=can_review,
                can_publish=False,
                is_active=True,
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


def _refingerprint(
    preview: CapabilityDiscoveryPreviewResponse,
    **updates: object,
) -> CapabilityDiscoveryPreviewResponse:
    draft = preview.model_copy(update=updates, deep=True)
    payload = draft.model_dump(mode="json")
    payload.pop("preview_fingerprint")
    fingerprint = canonical_json_sha256(cast(JsonValue, payload))
    complete = draft.model_dump(mode="json")
    complete["preview_fingerprint"] = f"sha256:{fingerprint}"
    return CapabilityDiscoveryPreviewResponse.model_validate(complete)


def _evidence_refresh_preview(
    preview: CapabilityDiscoveryPreviewResponse,
) -> CapabilityDiscoveryPreviewResponse:
    previous = preview.evidence[0]
    refreshed_id = f"{previous.evidence_id}:review-refresh"
    refreshed = previous.model_copy(update={"evidence_id": refreshed_id}, deep=True)

    def replace(values: list[str]) -> list[str]:
        return [refreshed_id if item == previous.evidence_id else item for item in values]

    return _refingerprint(
        preview,
        proposed_implementations=[
            item.model_copy(
                update={"evidence_refs": replace(item.evidence_refs)},
                deep=True,
            )
            for item in preview.proposed_implementations
        ],
        candidate_assertions=[
            item.model_copy(
                update={"evidence_refs": replace(item.evidence_refs)},
                deep=True,
            )
            for item in preview.candidate_assertions
        ],
        evidence=[
            refreshed if item.evidence_id == previous.evidence_id else item
            for item in preview.evidence
        ],
    )


async def _intake(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    preview: CapabilityDiscoveryPreviewResponse,
    key: str,
) -> dict[str, uuid.UUID]:
    result = await import_capability_candidates(
        session,
        actor_user_id=actor_user_id,
        payload=CapabilityGovernanceImportRequest(
            schema_version="capability_governance_import_request.v1",
            fixture_ids=FIXTURE_IDS,
            expected_preview_fingerprint=preview.preview_fingerprint,
        ),
        idempotency_key=key,
    )
    return {
        item.candidate_key: item.verification_task_id
        for item in result.candidates
        if item.verification_task_id is not None
    }


def _review_request(
    preview: CapabilityDiscoveryPreviewResponse,
    candidate: CapabilityCandidateAssertionPreview,
    *,
    action: CapabilityVerificationAction,
    expected_task_version: int = 1,
    evidence_refs: list[str] | None = None,
) -> CapabilityGovernanceReviewRequest:
    if action is CapabilityVerificationAction.REJECT:
        return CapabilityGovernanceReviewRequest(
            schema_version="capability_governance_review_request.v1",
            expected_task_version=expected_task_version,
            action=action,
            reason="Candidate contract is not sufficiently supported.",
            canonical_implementation=None,
            canonical_assertion=None,
        )

    proposed = next(
        item
        for item in preview.proposed_implementations
        if item.proposed_implementation_id == candidate.proposed_implementation_id
    )
    template = get_capability_catalog().implementations[0]
    implementation = template.model_copy(
        update={
            "implementation_id": f"implementation:{proposed.provider_id}:reviewed",
            "provider_id": proposed.provider_id,
            "platform": candidate.platform,
            "access_channel": candidate.access_channel,
            "delivery_form": proposed.delivery_form,
            "deployment_mode": proposed.deployment_mode,
            "auth_mode": proposed.claimed_auth_mode,
            "required_credentials": proposed.claimed_required_credentials,
        },
        deep=True,
    )
    assertion = CapabilityGovernanceCanonicalAssertionInput(
        assertion_id=f"assertion:{candidate.candidate_id}:reviewed",
        implementation_id=implementation.implementation_id,
        resource_type=candidate.resource_type,
        operation=candidate.operation,
        support_status=(
            CapabilityStatus.DEPRECATED
            if action is CapabilityVerificationAction.DEPRECATE
            else CapabilityStatus.VERIFIED
        ),
        source_resource_group=candidate.resource_type.value,
        region_scope=candidate.region_scope,
        purpose_scope=candidate.purpose_scope,
        auth_scope=candidate.auth_scope,
        field_contract=candidate.claimed_field_contract,
        constraints=candidate.claimed_constraints,
        score_profile=get_capability_catalog().assertions[0].score_profile,
        evidence_refs=(
            list(candidate.evidence_refs) if evidence_refs is None else evidence_refs
        ),
    )
    return CapabilityGovernanceReviewRequest(
        schema_version="capability_governance_review_request.v1",
        expected_task_version=expected_task_version,
        action=action,
        reason="Evidence and canonical contract were reviewed.",
        canonical_implementation=implementation,
        canonical_assertion=assertion,
    )


async def _count(session: AsyncSession, model: type[Base]) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)


@pytest.mark.asyncio
async def test_verify_freezes_server_timed_bundle_and_same_key_replays(
    session: AsyncSession,
) -> None:
    reviewer_id = await _add_governor(session, name="verification-verify")
    session.add(
        CapabilityCatalogHead(
            singleton_key="global",
            current_revision_id=None,
            head_version=0,
        )
    )
    await session.commit()
    preview = _preview()
    tasks = await _intake(
        session,
        actor_user_id=reviewer_id,
        preview=preview,
        key="verification-intake-key-01",
    )
    candidate = preview.candidate_assertions[0]
    task_id = tasks[compute_candidate_key(candidate)]
    payload = _review_request(
        preview,
        candidate,
        action=CapabilityVerificationAction.VERIFY,
    )
    open_task = await session.get(CapabilityVerificationTask, task_id)
    head_before_review = await session.get(CapabilityCatalogHead, "global")
    assert open_task is not None
    assert open_task.status == "open"
    assert open_task.decision_id is None
    assert await _count(session, CapabilityVerificationDecision) == 0
    assert head_before_review is not None
    assert head_before_review.current_revision_id is None
    assert head_before_review.head_version == 0

    first = await review_capability_candidate(
        session,
        actor_user_id=reviewer_id,
        task_id=task_id,
        payload=payload,
        idempotency_key="verification-review-key-01",
    )
    replay = await review_capability_candidate(
        session,
        actor_user_id=reviewer_id,
        task_id=task_id,
        payload=payload,
        idempotency_key="verification-review-key-01",
    )

    assert first.action is CapabilityVerificationAction.VERIFY
    assert first.verification_status == "verified"
    assert first.reviewed_at.tzinfo is not None
    assert first.reviewed_at.utcoffset() is not None
    assert first.database_write is True
    assert first.domain_changed is True
    assert replay.database_write is False
    assert replay.domain_changed is False
    assert replay.idempotent_replay is True
    assert replay.decision_id == first.decision_id
    assert await _count(session, CapabilityVerificationDecision) == 1

    decision = await session.get(CapabilityVerificationDecision, first.decision_id)
    task = await session.get(CapabilityVerificationTask, task_id)
    assert decision is not None
    assert task is not None
    assert task.status == "resolved"
    assert task.decision_id == decision.id
    assert decision.reviewer_user_id == reviewer_id
    assert decision.reason == payload.reason
    assert decision.canonical_bundle is not None
    assertion = decision.canonical_bundle["assertion"]
    assert assertion["last_verified_at"].endswith("Z")
    assert set(assertion["evidence_refs"]) == set(candidate.evidence_refs)
    assert decision.canonical_bundle["candidate_fingerprint"] == (
        candidate.candidate_fingerprint
    )
    head_after_review = await session.get(CapabilityCatalogHead, "global")
    assert head_after_review is not None
    assert head_after_review.current_revision_id is None
    assert head_after_review.head_version == 0

    conflicting = payload.model_copy(update={"reason": "Different request body"})
    with pytest.raises(CapabilityGovernanceReviewIdempotencyConflictError):
        await review_capability_candidate(
            session,
            actor_user_id=reviewer_id,
            task_id=task_id,
            payload=conflicting,
            idempotency_key="verification-review-key-01",
        )


@pytest.mark.asyncio
async def test_reject_and_deprecate_keep_verification_and_support_axes_separate(
    session: AsyncSession,
) -> None:
    reviewer_id = await _add_governor(session, name="verification-actions")
    preview = _preview()
    tasks = await _intake(
        session,
        actor_user_id=reviewer_id,
        preview=preview,
        key="verification-actions-intake-01",
    )
    assert len(preview.candidate_assertions) >= 2
    rejected_candidate, deprecated_candidate = preview.candidate_assertions[:2]

    rejected = await review_capability_candidate(
        session,
        actor_user_id=reviewer_id,
        task_id=tasks[compute_candidate_key(rejected_candidate)],
        payload=_review_request(
            preview,
            rejected_candidate,
            action=CapabilityVerificationAction.REJECT,
        ),
        idempotency_key="verification-reject-key-01",
    )
    deprecated = await review_capability_candidate(
        session,
        actor_user_id=reviewer_id,
        task_id=tasks[compute_candidate_key(deprecated_candidate)],
        payload=_review_request(
            preview,
            deprecated_candidate,
            action=CapabilityVerificationAction.DEPRECATE,
        ),
        idempotency_key="verification-deprecate-key-01",
    )

    reject_decision = await session.get(
        CapabilityVerificationDecision,
        rejected.decision_id,
    )
    deprecate_decision = await session.get(
        CapabilityVerificationDecision,
        deprecated.decision_id,
    )
    assert reject_decision is not None
    assert deprecate_decision is not None
    assert rejected.verification_status == "rejected"
    assert reject_decision.canonical_bundle is None
    assert deprecated.verification_status == "verified"
    assert deprecate_decision.canonical_bundle is not None
    assert (
        deprecate_decision.canonical_bundle["assertion"]["support_status"]
        == "deprecated"
    )


@pytest.mark.asyncio
async def test_permission_version_lineage_and_resolution_conflicts_fail_closed(
    session: AsyncSession,
) -> None:
    reader_id = await _add_governor(
        session,
        name="verification-reader",
        can_review=False,
    )
    reviewer_id = await _add_governor(session, name="verification-conflicts")
    preview = _preview()
    tasks = await _intake(
        session,
        actor_user_id=reviewer_id,
        preview=preview,
        key="verification-conflict-intake-01",
    )
    candidate = preview.candidate_assertions[0]
    task_id = tasks[compute_candidate_key(candidate)]
    valid = _review_request(
        preview,
        candidate,
        action=CapabilityVerificationAction.VERIFY,
    )

    with pytest.raises(CapabilityGovernanceForbiddenError):
        await review_capability_candidate(
            session,
            actor_user_id=reader_id,
            task_id=task_id,
            payload=valid,
            idempotency_key="verification-reader-key-01",
        )
    with pytest.raises(CapabilityGovernanceVerificationTaskConflictError):
        await review_capability_candidate(
            session,
            actor_user_id=reviewer_id,
            task_id=task_id,
            payload=valid.model_copy(update={"expected_task_version": 2}),
            idempotency_key="verification-version-key-01",
        )
    with pytest.raises(CapabilityGovernanceReviewContractError):
        await review_capability_candidate(
            session,
            actor_user_id=reviewer_id,
            task_id=task_id,
            payload=_review_request(
                preview,
                candidate,
                action=CapabilityVerificationAction.VERIFY,
                evidence_refs=["evidence:not-linked"],
            ),
            idempotency_key="verification-lineage-key-01",
        )

    await review_capability_candidate(
        session,
        actor_user_id=reviewer_id,
        task_id=task_id,
        payload=valid,
        idempotency_key="verification-valid-key-001",
    )
    with pytest.raises(CapabilityGovernanceVerificationTaskConflictError):
        await review_capability_candidate(
            session,
            actor_user_id=reviewer_id,
            task_id=task_id,
            payload=valid,
            idempotency_key="verification-second-key-01",
        )


@pytest.mark.asyncio
async def test_dirty_session_and_injected_failure_leave_task_open(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviewer_id = await _add_governor(session, name="verification-rollback")
    preview = _preview()
    tasks = await _intake(
        session,
        actor_user_id=reviewer_id,
        preview=preview,
        key="verification-rollback-intake-01",
    )
    candidate = preview.candidate_assertions[0]
    task_id = tasks[compute_candidate_key(candidate)]
    payload = _review_request(
        preview,
        candidate,
        action=CapabilityVerificationAction.VERIFY,
    )
    pending = User(
        id=uuid.uuid4(),
        email="verification-pending@example.com",
        password_hash="not-a-real-secret",
        name="verification-pending",
        status="active",
    )
    session.add(pending)
    with pytest.raises(CapabilityGovernanceReviewTransactionStateError):
        await review_capability_candidate(
            session,
            actor_user_id=reviewer_id,
            task_id=task_id,
            payload=payload,
            idempotency_key="verification-dirty-key-01",
        )
    assert pending in session.new
    await session.rollback()

    real_add = verification_module._add
    add_count = 0

    async def failing_add(record: Base, target_session: AsyncSession) -> None:
        nonlocal add_count
        add_count += 1
        await real_add(record, target_session)
        if add_count == 1:
            raise RuntimeError("injected_review_failure")

    monkeypatch.setattr(verification_module, "_add", failing_add)
    with pytest.raises(RuntimeError, match="injected_review_failure"):
        await review_capability_candidate(
            session,
            actor_user_id=reviewer_id,
            task_id=task_id,
            payload=payload,
            idempotency_key="verification-rollback-key-01",
        )

    task = await session.get(CapabilityVerificationTask, task_id)
    assert task is not None
    assert task.status == "open"
    assert task.decision_id is None
    assert await _count(session, CapabilityVerificationDecision) == 0
    assert await _count(session, CapabilityGovernanceRequest) == 1


@pytest.mark.asyncio
async def test_evidence_refresh_review_does_not_advance_existing_catalog_head(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviewer_id = await _add_governor(session, name="verification-head")
    original = _preview()
    tasks = await _intake(
        session,
        actor_user_id=reviewer_id,
        preview=original,
        key="verification-head-intake-01",
    )
    candidate = original.candidate_assertions[0]
    await review_capability_candidate(
        session,
        actor_user_id=reviewer_id,
        task_id=tasks[compute_candidate_key(candidate)],
        payload=_review_request(
            original,
            candidate,
            action=CapabilityVerificationAction.VERIFY,
        ),
        idempotency_key="verification-head-review-01",
    )

    catalog = get_capability_catalog()
    snapshot_id = compute_catalog_snapshot_id(catalog)
    revision_id = uuid.uuid4()
    session.add_all(
        [
            CapabilityCatalogSnapshot(
                catalog_snapshot_id=snapshot_id,
                catalog_payload=cast(
                    dict[str, object],
                    catalog.model_dump(mode="json"),
                ),
                created_at=datetime.now(UTC),
            ),
            CapabilityPublicationRevision(
                id=revision_id,
                revision_number=1,
                parent_revision_id=None,
                restored_from_revision_id=None,
                catalog_snapshot_id=snapshot_id,
                publisher_user_id=reviewer_id,
                published_at=datetime.now(UTC),
                reason="existing publication",
                operations=[],
            ),
            CapabilityCatalogHead(
                singleton_key="global",
                current_revision_id=revision_id,
                head_version=1,
                updated_at=datetime.now(UTC),
            ),
        ]
    )
    await session.commit()

    refreshed = _evidence_refresh_preview(original)
    monkeypatch.setattr(
        intake_module,
        "build_capability_discovery_preview",
        lambda _request: refreshed,
    )
    refreshed_tasks = await _intake(
        session,
        actor_user_id=reviewer_id,
        preview=refreshed,
        key="verification-head-intake-02",
    )
    refreshed_candidate = refreshed.candidate_assertions[0]
    refreshed_task_id = refreshed_tasks[compute_candidate_key(refreshed_candidate)]
    revision_count = await _count(session, CapabilityPublicationRevision)

    await review_capability_candidate(
        session,
        actor_user_id=reviewer_id,
        task_id=refreshed_task_id,
        payload=_review_request(
            refreshed,
            refreshed_candidate,
            action=CapabilityVerificationAction.VERIFY,
        ),
        idempotency_key="verification-head-review-02",
    )

    head = await session.get(CapabilityCatalogHead, "global")
    assert head is not None
    assert head.current_revision_id == revision_id
    assert head.head_version == 1
    assert await _count(session, CapabilityPublicationRevision) == revision_count
