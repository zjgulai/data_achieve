from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Sequence
from typing import cast

import pytest
import pytest_asyncio
from pydantic import JsonValue
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.capability_governance import (
    CapabilityCandidateAssertionVersion,
    CapabilityCandidateEvidenceLink,
    CapabilityDiscoveryBatch,
    CapabilityDiscoveryBatchSource,
    CapabilityGovernanceMembership,
    CapabilityGovernanceRequest,
    CapabilitySourceSnapshot,
    CapabilityVerificationTask,
    GovernanceCapabilityEvidence,
)
from data_intelligence_hub.models.user import User
from data_intelligence_hub.schemas.capability_discovery import (
    CapabilityDiscoveryPreviewRequest,
    CapabilityDiscoveryPreviewResponse,
)
from data_intelligence_hub.schemas.capability_governance import (
    CapabilityGovernanceImportRequest,
)
from data_intelligence_hub.services.capability_discovery.fingerprint import (
    canonical_json_sha256,
)
from data_intelligence_hub.services.capability_discovery.preview import (
    build_capability_discovery_preview,
)
from data_intelligence_hub.services.capability_governance import intake as intake_module
from data_intelligence_hub.services.capability_governance.authority import (
    CapabilityGovernanceForbiddenError,
)
from data_intelligence_hub.services.capability_governance.identity import (
    compute_candidate_key,
)
from data_intelligence_hub.services.capability_governance.intake import (
    CapabilityGovernanceIdempotencyConflictError,
    CapabilityGovernancePreviewStaleError,
    CapabilityGovernanceTransactionStateError,
    import_capability_candidates,
)

FIXTURE_IDS = ["tikhub-youtube-market-v1"]
HASH_D = "sha256:" + "d" * 64
DOMAIN_MODELS = (
    CapabilityDiscoveryBatch,
    CapabilitySourceSnapshot,
    CapabilityDiscoveryBatchSource,
    GovernanceCapabilityEvidence,
    CapabilityCandidateAssertionVersion,
    CapabilityCandidateEvidenceLink,
    CapabilityVerificationTask,
)


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


def _preview(
    fixture_ids: Sequence[str] = FIXTURE_IDS,
) -> CapabilityDiscoveryPreviewResponse:
    return build_capability_discovery_preview(
        CapabilityDiscoveryPreviewRequest(
            schema_version="capability_discovery_preview_request.v1",
            preview_mode="fixture_replay",
            fixture_ids=list(fixture_ids),
        )
    )


def _request(preview: CapabilityDiscoveryPreviewResponse) -> CapabilityGovernanceImportRequest:
    return CapabilityGovernanceImportRequest(
        schema_version="capability_governance_import_request.v1",
        fixture_ids=[item.fixture_id for item in preview.source_snapshots],
        expected_preview_fingerprint=preview.preview_fingerprint,
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
    refreshed_id = f"{previous.evidence_id}:refresh"
    refreshed = previous.model_copy(update={"evidence_id": refreshed_id}, deep=True)

    def replace(values: list[str]) -> list[str]:
        return [refreshed_id if item == previous.evidence_id else item for item in values]

    proposed = [
        item.model_copy(update={"evidence_refs": replace(item.evidence_refs)}, deep=True)
        for item in preview.proposed_implementations
    ]
    candidates = [
        item.model_copy(update={"evidence_refs": replace(item.evidence_refs)}, deep=True)
        for item in preview.candidate_assertions
    ]
    evidence = [
        refreshed if item.evidence_id == previous.evidence_id else item
        for item in preview.evidence
    ]
    return _refingerprint(
        preview,
        proposed_implementations=proposed,
        candidate_assertions=candidates,
        evidence=evidence,
    )


def _semantic_drift_preview(
    preview: CapabilityDiscoveryPreviewResponse,
) -> CapabilityDiscoveryPreviewResponse:
    first = preview.candidate_assertions[0]
    drifted = first.model_copy(
        update={
            "candidate_fingerprint": HASH_D,
            "claimed_field_contract": {"drifted": True},
        },
        deep=True,
    )
    return _refingerprint(
        preview,
        candidate_assertions=[drifted, *preview.candidate_assertions[1:]],
    )


async def _add_governor(
    session: AsyncSession,
    *,
    name: str,
    can_review: bool = True,
) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"{name}@example.com",
        password_hash="not-a-real-secret",
        name=name,
        status="active",
    )
    session.add_all(
        [
            user,
            CapabilityGovernanceMembership(
                id=uuid.uuid4(),
                user_id=user.id,
                can_read=True,
                can_review=can_review,
                can_publish=False,
                is_active=True,
            ),
        ]
    )
    await session.commit()
    return user


async def _count(session: AsyncSession, model: type[Base]) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)


async def _domain_counts(session: AsyncSession) -> tuple[int, ...]:
    return tuple([await _count(session, model) for model in DOMAIN_MODELS])


@pytest.mark.asyncio
async def test_first_observation_exact_new_key_and_same_key_replay(
    session: AsyncSession,
) -> None:
    governor = await _add_governor(session, name="intake-first")
    governor_id = governor.id
    preview = _preview()
    payload = _request(preview)

    first = await import_capability_candidates(
        session,
        actor_user_id=governor_id,
        payload=payload,
        idempotency_key="intake-first-key-0001",
    )
    first_domain_counts = await _domain_counts(session)

    assert first.database_write is True
    assert first.domain_changed is True
    assert first.idempotent_replay is False
    assert first.batch_id is not None
    assert {item.classification for item in first.candidates} == {"first_observation"}
    assert first.provider_call is False
    assert first.actor_run is False
    assert first.browser_run is False
    assert first.llm_call is False
    assert first.workflow_run_created is False
    assert await _count(session, CapabilityGovernanceRequest) == 1

    exact = await import_capability_candidates(
        session,
        actor_user_id=governor_id,
        payload=payload,
        idempotency_key="intake-exact-key-0002",
    )
    assert exact.database_write is True
    assert exact.domain_changed is False
    assert exact.idempotent_replay is False
    assert exact.batch_id is None
    assert {item.classification for item in exact.candidates} == {
        "semantic_exact_replay"
    }
    assert await _domain_counts(session) == first_domain_counts
    assert await _count(session, CapabilityGovernanceRequest) == 2

    replay = await import_capability_candidates(
        session,
        actor_user_id=governor_id,
        payload=payload,
        idempotency_key="intake-first-key-0001",
    )
    assert replay.database_write is False
    assert replay.domain_changed is False
    assert replay.idempotent_replay is True
    assert replay.request_id == first.request_id
    assert replay.batch_id == first.batch_id
    assert await _domain_counts(session) == first_domain_counts
    assert await _count(session, CapabilityGovernanceRequest) == 2


@pytest.mark.asyncio
async def test_authority_stale_idempotency_conflict_and_dirty_session_fail_closed(
    session: AsyncSession,
) -> None:
    reader = await _add_governor(
        session,
        name="intake-reader",
        can_review=False,
    )
    preview = _preview()
    payload = _request(preview)

    with pytest.raises(CapabilityGovernanceForbiddenError):
        await import_capability_candidates(
            session,
            actor_user_id=reader.id,
            payload=payload,
            idempotency_key="intake-reader-key-0001",
        )
    assert await _domain_counts(session) == (0,) * len(DOMAIN_MODELS)
    assert await _count(session, CapabilityGovernanceRequest) == 0

    governor = await _add_governor(session, name="intake-errors")
    governor_id = governor.id
    stale = payload.model_copy(
        update={"expected_preview_fingerprint": "sha256:" + "f" * 64}
    )
    with pytest.raises(CapabilityGovernancePreviewStaleError):
        await import_capability_candidates(
            session,
            actor_user_id=governor_id,
            payload=stale,
            idempotency_key="intake-stale-key-0001",
        )
    assert await _count(session, CapabilityGovernanceRequest) == 0

    await import_capability_candidates(
        session,
        actor_user_id=governor_id,
        payload=payload,
        idempotency_key="intake-conflict-key-01",
    )
    with pytest.raises(CapabilityGovernanceIdempotencyConflictError):
        await import_capability_candidates(
            session,
            actor_user_id=governor_id,
            payload=stale,
            idempotency_key="intake-conflict-key-01",
        )

    pending = User(
        id=uuid.uuid4(),
        email="pending-intake@example.com",
        password_hash="not-a-real-secret",
        name="pending-intake",
        status="active",
    )
    session.add(pending)
    with pytest.raises(CapabilityGovernanceTransactionStateError):
        await import_capability_candidates(
            session,
            actor_user_id=governor_id,
            payload=payload,
            idempotency_key="intake-dirty-key-0001",
        )
    assert pending in session.new
    await session.rollback()


@pytest.mark.asyncio
async def test_evidence_refresh_reuses_candidate_and_versions_open_task(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    governor = await _add_governor(session, name="intake-evidence")
    governor_id = governor.id
    original = _preview()
    first = await import_capability_candidates(
        session,
        actor_user_id=governor_id,
        payload=_request(original),
        idempotency_key="intake-evidence-key-01",
    )
    candidate_count = await _count(session, CapabilityCandidateAssertionVersion)
    task_count = await _count(session, CapabilityVerificationTask)
    refreshed = _evidence_refresh_preview(original)
    monkeypatch.setattr(
        intake_module,
        "build_capability_discovery_preview",
        lambda _request: refreshed,
    )

    result = await import_capability_candidates(
        session,
        actor_user_id=governor_id,
        payload=_request(refreshed),
        idempotency_key="intake-evidence-key-02",
    )

    assert first.domain_changed is True
    assert result.domain_changed is True
    assert {item.classification for item in result.candidates} == {"evidence_refresh"}
    assert await _count(session, CapabilityCandidateAssertionVersion) == candidate_count
    assert await _count(session, CapabilityVerificationTask) == task_count
    assert await _count(session, GovernanceCapabilityEvidence) == 2
    task_versions = list(
        await session.scalars(select(CapabilityVerificationTask.task_version))
    )
    assert set(task_versions) == {2}


@pytest.mark.asyncio
async def test_unrelated_new_source_does_not_refresh_unchanged_candidates(
    session: AsyncSession,
) -> None:
    governor = await _add_governor(session, name="intake-unrelated-source")
    original = _preview(["tikhub-youtube-market-v1"])
    first = await import_capability_candidates(
        session,
        actor_user_id=governor.id,
        payload=_request(original),
        idempotency_key="intake-unrelated-source-key-0001",
    )
    expanded = _preview(
        ["tikhub-youtube-market-v1", "youtube-data-api-doc-v1"]
    )
    expanded_by_key = {
        compute_candidate_key(candidate): candidate
        for candidate in expanded.candidate_assertions
    }
    unchanged_key = next(
        compute_candidate_key(candidate)
        for candidate in original.candidate_assertions
        if (
            (expanded_candidate := expanded_by_key.get(compute_candidate_key(candidate)))
            is not None
            and expanded_candidate.candidate_fingerprint
            == candidate.candidate_fingerprint
            and expanded_candidate.evidence_refs == candidate.evidence_refs
        )
    )
    first_result = next(
        candidate for candidate in first.candidates if candidate.candidate_key == unchanged_key
    )
    assert first_result.verification_task_id is not None

    result = await import_capability_candidates(
        session,
        actor_user_id=governor.id,
        payload=_request(expanded),
        idempotency_key="intake-unrelated-source-key-0002",
    )

    unchanged = next(
        candidate for candidate in result.candidates if candidate.candidate_key == unchanged_key
    )
    assert unchanged.classification == "semantic_exact_replay"
    assert unchanged.verification_task_id is None
    assert unchanged.evidence_added_count == 0
    task = await session.get(
        CapabilityVerificationTask,
        first_result.verification_task_id,
    )
    assert task is not None
    assert task.task_version == 1


@pytest.mark.asyncio
async def test_semantic_drift_creates_next_version_and_preserves_old_rows(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    governor = await _add_governor(session, name="intake-drift")
    governor_id = governor.id
    original = _preview()
    await import_capability_candidates(
        session,
        actor_user_id=governor_id,
        payload=_request(original),
        idempotency_key="intake-drift-key-0001",
    )
    candidate_count = await _count(session, CapabilityCandidateAssertionVersion)
    task_count = await _count(session, CapabilityVerificationTask)
    drifted = _semantic_drift_preview(original)
    monkeypatch.setattr(
        intake_module,
        "build_capability_discovery_preview",
        lambda _request: drifted,
    )

    result = await import_capability_candidates(
        session,
        actor_user_id=governor_id,
        payload=_request(drifted),
        idempotency_key="intake-drift-key-0002",
    )

    drift_result = next(
        item for item in result.candidates if item.classification == "semantic_drift"
    )
    versions = list(
        await session.scalars(
            select(CapabilityCandidateAssertionVersion)
            .where(
                CapabilityCandidateAssertionVersion.candidate_key
                == drift_result.candidate_key
            )
            .order_by(CapabilityCandidateAssertionVersion.semantic_version)
        )
    )
    assert [item.semantic_version for item in versions] == [1, 2]
    assert versions[1].predecessor_id == versions[0].id
    assert await _count(session, CapabilityCandidateAssertionVersion) == candidate_count + 1
    assert await _count(session, CapabilityVerificationTask) == task_count + 1
    assert await _count(session, CapabilityDiscoveryBatch) == 2


@pytest.mark.asyncio
async def test_injected_failure_rolls_back_every_domain_and_ledger_row(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    governor = await _add_governor(session, name="intake-rollback")
    governor_id = governor.id
    preview = _preview()
    real_add = intake_module._add
    add_count = 0

    async def failing_add(
        record: Base,
        target_session: AsyncSession,
    ) -> None:
        nonlocal add_count
        add_count += 1
        if add_count == 4:
            raise RuntimeError("injected_intake_failure")
        await real_add(record, target_session)

    monkeypatch.setattr(intake_module, "_add", failing_add)

    with pytest.raises(RuntimeError, match="injected_intake_failure"):
        await import_capability_candidates(
            session,
            actor_user_id=governor_id,
            payload=_request(preview),
            idempotency_key="intake-rollback-key-01",
        )

    assert await _domain_counts(session) == (0,) * len(DOMAIN_MODELS)
    assert await _count(session, CapabilityGovernanceRequest) == 0
