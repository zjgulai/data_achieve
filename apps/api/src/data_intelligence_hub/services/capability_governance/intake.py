from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.capability_governance import (
    CapabilityCandidateAssertionVersion,
    CapabilityCandidateEvidenceLink,
    CapabilityDiscoveryBatch,
    CapabilityDiscoveryBatchSource,
    CapabilityGovernanceRequest,
    CapabilitySourceSnapshot,
    CapabilityVerificationTask,
    GovernanceCapabilityEvidence,
)
from data_intelligence_hub.repositories.capability_governance import (
    acquire_governance_import_lock,
    add_governance_record,
    get_candidate_version_by_fingerprint,
    get_governance_evidence,
    get_governance_request_for_update,
    get_latest_candidate_version_for_update,
    get_open_verification_task_for_update,
    get_source_snapshot,
    list_candidate_evidence_external_ids,
)
from data_intelligence_hub.schemas.capability_catalog import CapabilityEvidence
from data_intelligence_hub.schemas.capability_discovery import (
    CapabilityCandidateAssertionPreview,
    CapabilityDiscoveryPreviewRequest,
    CapabilityDiscoveryPreviewResponse,
    CapabilityProposedImplementationPreview,
)
from data_intelligence_hub.schemas.capability_governance import (
    CapabilityCandidateIntakeClassification,
    CapabilityGovernanceCandidateIntakeResult,
    CapabilityGovernanceImportRequest,
    CapabilityGovernanceImportResponse,
    CapabilityGovernancePermission,
    normalize_governance_idempotency_key,
)
from data_intelligence_hub.services.capability_discovery.fingerprint import (
    canonical_json_sha256,
)
from data_intelligence_hub.services.capability_discovery.fixture_loader import (
    LoadedCapabilityDiscoveryFixture,
    load_capability_discovery_fixtures,
)
from data_intelligence_hub.services.capability_discovery.preview import (
    build_capability_discovery_preview,
)
from data_intelligence_hub.services.capability_governance.authority import (
    require_governance_permission,
)
from data_intelligence_hub.services.capability_governance.identity import (
    compute_candidate_key,
    compute_governance_request_hash,
    hash_governance_idempotency_key,
)

IMPORT_ACTION_SCOPE = "capability_governance.import"


class CapabilityGovernancePreviewStaleError(Exception):
    code = "preview_stale"


class CapabilityGovernanceIdempotencyConflictError(Exception):
    code = "idempotency_conflict"


class CapabilityGovernanceTransactionStateError(Exception):
    code = "persistence_transaction_state_invalid"


class CapabilityGovernanceDataConflictError(Exception):
    code = "capability_governance_data_conflict"


@dataclass(slots=True)
class _CandidateState:
    preview: CapabilityCandidateAssertionPreview
    proposed: CapabilityProposedImplementationPreview
    candidate_key: str
    candidate_version: CapabilityCandidateAssertionVersion | None
    latest_version: CapabilityCandidateAssertionVersion | None
    linked_evidence_ids: set[str]
    classification: CapabilityCandidateIntakeClassification


def _as_json_object(value: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], cast(JsonValue, value))


def _candidate_payload(
    candidate: CapabilityCandidateAssertionPreview,
) -> dict[str, Any]:
    return _as_json_object(
        candidate.model_dump(
            mode="json",
            exclude={"evidence_refs", "source_claim_refs"},
        )
    )


def _proposed_payload(
    proposed: CapabilityProposedImplementationPreview,
) -> dict[str, Any]:
    return _as_json_object(proposed.model_dump(mode="json", exclude={"evidence_refs"}))


def _evidence_payload(value: CapabilityEvidence) -> dict[str, Any]:
    return _as_json_object(value.model_dump(mode="json"))


async def _prepare_service_transaction(session: AsyncSession) -> None:
    if session.new or session.dirty or session.deleted:
        raise CapabilityGovernanceTransactionStateError
    if session.in_transaction():
        await session.rollback()


def _replay_response(
    request: CapabilityGovernanceRequest,
    *,
    request_hash: str,
) -> CapabilityGovernanceImportResponse:
    if request.request_hash != request_hash:
        raise CapabilityGovernanceIdempotencyConflictError
    original = CapabilityGovernanceImportResponse.model_validate(request.response_payload)
    return original.model_copy(
        update={
            "database_write": False,
            "domain_changed": False,
            "idempotent_replay": True,
        },
        deep=True,
    )


def _build_preview(
    payload: CapabilityGovernanceImportRequest,
) -> CapabilityDiscoveryPreviewResponse:
    return build_capability_discovery_preview(
        CapabilityDiscoveryPreviewRequest(
            schema_version="capability_discovery_preview_request.v1",
            preview_mode="fixture_replay",
            fixture_ids=payload.fixture_ids,
        )
    )


def _loaded_fixture_map(
    payload: CapabilityGovernanceImportRequest,
    preview: CapabilityDiscoveryPreviewResponse,
) -> dict[str, LoadedCapabilityDiscoveryFixture]:
    loaded = load_capability_discovery_fixtures(sorted(payload.fixture_ids))
    loaded_by_id = {item.snapshot.fixture_id: item for item in loaded}
    preview_by_id = {item.fixture_id: item for item in preview.source_snapshots}
    if set(loaded_by_id) != set(preview_by_id):
        raise CapabilityGovernanceDataConflictError
    for fixture_id, source in preview_by_id.items():
        current = loaded_by_id[fixture_id]
        if (
            current.content_hash != source.content_hash
            or current.snapshot.parser_id != source.parser_id
        ):
            raise CapabilityGovernanceDataConflictError
    return loaded_by_id


def _fixture_set_hash(
    loaded_by_id: dict[str, LoadedCapabilityDiscoveryFixture],
) -> str:
    payload = cast(
        JsonValue,
        [
            {
                "fixture_id": fixture_id,
                "content_hash": loaded_by_id[fixture_id].content_hash,
            }
            for fixture_id in sorted(loaded_by_id)
        ],
    )
    return f"sha256:{canonical_json_sha256(payload)}"


async def _source_states(
    session: AsyncSession,
    preview: CapabilityDiscoveryPreviewResponse,
    loaded_by_id: dict[str, LoadedCapabilityDiscoveryFixture],
) -> dict[str, CapabilitySourceSnapshot | None]:
    states: dict[str, CapabilitySourceSnapshot | None] = {}
    for source in preview.source_snapshots:
        existing = await get_source_snapshot(
            session,
            source.fixture_id,
            source.content_hash,
        )
        if existing is not None:
            expected_payload = loaded_by_id[source.fixture_id].snapshot.model_dump(mode="json")
            if (
                existing.snapshot_payload != expected_payload
                or existing.source_kind != source.source_kind
                or existing.source_url != source.source_url
                or existing.source_version != source.source_version
                or existing.parser_id != source.parser_id.value
            ):
                raise CapabilityGovernanceDataConflictError
        states[source.fixture_id] = existing
    return states


async def _evidence_states(
    session: AsyncSession,
    preview: CapabilityDiscoveryPreviewResponse,
) -> dict[str, GovernanceCapabilityEvidence | None]:
    states: dict[str, GovernanceCapabilityEvidence | None] = {}
    for evidence in preview.evidence:
        existing = await get_governance_evidence(session, evidence.evidence_id)
        payload = _evidence_payload(evidence)
        if existing is not None and (
            existing.content_hash != evidence.content_hash or existing.evidence_payload != payload
        ):
            raise CapabilityGovernanceDataConflictError
        states[evidence.evidence_id] = existing
    return states


async def _candidate_states(
    session: AsyncSession,
    preview: CapabilityDiscoveryPreviewResponse,
) -> list[_CandidateState]:
    proposed_by_id = {
        item.proposed_implementation_id: item for item in preview.proposed_implementations
    }
    states: list[_CandidateState] = []
    for candidate in preview.candidate_assertions:
        candidate_key = compute_candidate_key(candidate)
        latest = await get_latest_candidate_version_for_update(session, candidate_key)
        matching = await get_candidate_version_by_fingerprint(
            session,
            candidate_key,
            candidate.candidate_fingerprint,
        )
        linked_ids: set[str] = set()
        proposed = proposed_by_id[candidate.proposed_implementation_id]
        if matching is None:
            classification = (
                CapabilityCandidateIntakeClassification.FIRST_OBSERVATION
                if latest is None
                else CapabilityCandidateIntakeClassification.SEMANTIC_DRIFT
            )
        else:
            if matching.candidate_payload != _candidate_payload(
                candidate
            ) or matching.proposed_implementation_payload != _proposed_payload(proposed):
                raise CapabilityGovernanceDataConflictError
            linked_ids = await list_candidate_evidence_external_ids(
                session,
                matching.id,
            )
            has_new_link = bool(set(candidate.evidence_refs) - linked_ids)
            classification = (
                CapabilityCandidateIntakeClassification.EVIDENCE_REFRESH
                if has_new_link
                else CapabilityCandidateIntakeClassification.SEMANTIC_EXACT_REPLAY
            )
        states.append(
            _CandidateState(
                preview=candidate,
                proposed=proposed,
                candidate_key=candidate_key,
                candidate_version=matching,
                latest_version=latest,
                linked_evidence_ids=linked_ids,
                classification=classification,
            )
        )
    return states


async def _add(record: Base, session: AsyncSession) -> None:
    await add_governance_record(session, record)


async def _persist_sources(
    session: AsyncSession,
    *,
    batch_id: uuid.UUID,
    preview: CapabilityDiscoveryPreviewResponse,
    loaded_by_id: dict[str, LoadedCapabilityDiscoveryFixture],
    source_states: dict[str, CapabilitySourceSnapshot | None],
) -> None:
    for ordinal, source in enumerate(preview.source_snapshots):
        stored = source_states[source.fixture_id]
        if stored is None:
            loaded = loaded_by_id[source.fixture_id]
            stored = CapabilitySourceSnapshot(
                id=uuid.uuid4(),
                fixture_id=source.fixture_id,
                source_kind=source.source_kind,
                source_name=source.source_name,
                source_url=source.source_url,
                source_version=source.source_version,
                observed_at=source.observed_at,
                parser_id=source.parser_id.value,
                content_hash=source.content_hash,
                snapshot_payload=_as_json_object(loaded.snapshot.model_dump(mode="json")),
            )
            await _add(stored, session)
            source_states[source.fixture_id] = stored
        await _add(
            CapabilityDiscoveryBatchSource(
                batch_id=batch_id,
                source_snapshot_id=stored.id,
                ordinal=ordinal,
            ),
            session,
        )


async def _persist_evidence(
    session: AsyncSession,
    *,
    preview: CapabilityDiscoveryPreviewResponse,
    evidence_states: dict[str, GovernanceCapabilityEvidence | None],
) -> dict[str, GovernanceCapabilityEvidence]:
    persisted: dict[str, GovernanceCapabilityEvidence] = {}
    for evidence in preview.evidence:
        stored = evidence_states[evidence.evidence_id]
        if stored is None:
            stored = GovernanceCapabilityEvidence(
                id=uuid.uuid4(),
                evidence_id=evidence.evidence_id,
                content_hash=evidence.content_hash,
                evidence_payload=_evidence_payload(evidence),
            )
            await _add(stored, session)
            evidence_states[evidence.evidence_id] = stored
        persisted[evidence.evidence_id] = stored
    return persisted


async def _persist_candidate_state(
    session: AsyncSession,
    *,
    state: _CandidateState,
    batch_id: uuid.UUID,
    evidence_by_id: dict[str, GovernanceCapabilityEvidence],
    now: datetime,
) -> CapabilityGovernanceCandidateIntakeResult:
    candidate_version = state.candidate_version
    task: CapabilityVerificationTask | None = None
    evidence_to_add = set(state.preview.evidence_refs) - state.linked_evidence_ids
    if state.classification in {
        CapabilityCandidateIntakeClassification.FIRST_OBSERVATION,
        CapabilityCandidateIntakeClassification.SEMANTIC_DRIFT,
    }:
        semantic_version = (
            1 if state.latest_version is None else state.latest_version.semantic_version + 1
        )
        candidate_version = CapabilityCandidateAssertionVersion(
            id=uuid.uuid4(),
            candidate_key=state.candidate_key,
            semantic_version=semantic_version,
            candidate_fingerprint=state.preview.candidate_fingerprint,
            predecessor_id=(None if state.latest_version is None else state.latest_version.id),
            proposed_implementation_payload=_proposed_payload(state.proposed),
            candidate_payload=_candidate_payload(state.preview),
            first_seen_batch_id=batch_id,
        )
        await _add(candidate_version, session)
        evidence_to_add = set(state.preview.evidence_refs)
        task = CapabilityVerificationTask(
            id=uuid.uuid4(),
            candidate_version_id=candidate_version.id,
            task_type=(
                "initial_review"
                if state.classification is CapabilityCandidateIntakeClassification.FIRST_OBSERVATION
                else "semantic_drift"
            ),
            status="open",
            task_version=1,
            opened_at=now,
            resolved_at=None,
            decision_id=None,
        )
        await _add(task, session)
    elif state.classification is CapabilityCandidateIntakeClassification.EVIDENCE_REFRESH:
        if candidate_version is None:
            raise CapabilityGovernanceDataConflictError
        task = await get_open_verification_task_for_update(
            session,
            candidate_version.id,
        )
        if task is None:
            task = CapabilityVerificationTask(
                id=uuid.uuid4(),
                candidate_version_id=candidate_version.id,
                task_type="evidence_refresh",
                status="open",
                task_version=1,
                opened_at=now,
                resolved_at=None,
                decision_id=None,
            )
            await _add(task, session)
        else:
            task.task_version += 1

    if candidate_version is None:
        raise CapabilityGovernanceDataConflictError
    for evidence_id in sorted(evidence_to_add):
        evidence = evidence_by_id.get(evidence_id)
        if evidence is None:
            raise CapabilityGovernanceDataConflictError
        await _add(
            CapabilityCandidateEvidenceLink(
                candidate_version_id=candidate_version.id,
                evidence_id=evidence.id,
                first_seen_batch_id=batch_id,
            ),
            session,
        )
    return CapabilityGovernanceCandidateIntakeResult(
        candidate_key=state.candidate_key,
        candidate_version_id=candidate_version.id,
        semantic_version=candidate_version.semantic_version,
        classification=state.classification,
        verification_task_id=None if task is None else task.id,
        evidence_added_count=len(evidence_to_add),
    )


def _outcome(
    candidates: list[CapabilityGovernanceCandidateIntakeResult],
) -> str:
    values = {item.classification.value for item in candidates}
    return next(iter(values)) if len(values) == 1 else "mixed"


async def import_capability_candidates(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    payload: CapabilityGovernanceImportRequest,
    idempotency_key: str,
) -> CapabilityGovernanceImportResponse:
    normalized_key = normalize_governance_idempotency_key(idempotency_key)
    key_hash = hash_governance_idempotency_key(normalized_key)
    request_hash = compute_governance_request_hash(
        action_scope=IMPORT_ACTION_SCOPE,
        payload=cast(JsonValue, payload.model_dump(mode="json")),
    )
    await _prepare_service_transaction(session)

    async with session.begin():
        await require_governance_permission(
            session,
            actor_user_id,
            CapabilityGovernancePermission.REVIEW,
        )
        await acquire_governance_import_lock(session)
        existing_request = await get_governance_request_for_update(
            session,
            actor_user_id,
            IMPORT_ACTION_SCOPE,
            key_hash,
        )
        if existing_request is not None:
            return _replay_response(existing_request, request_hash=request_hash)

        preview = _build_preview(payload)
        if preview.preview_fingerprint != payload.expected_preview_fingerprint:
            raise CapabilityGovernancePreviewStaleError
        loaded_by_id = _loaded_fixture_map(payload, preview)
        source_states = await _source_states(
            session,
            preview,
            loaded_by_id,
        )
        evidence_states = await _evidence_states(session, preview)
        new_source_exists = any(item is None for item in source_states.values())
        candidate_states = await _candidate_states(session, preview)
        domain_changed = new_source_exists or any(
            item.classification is not CapabilityCandidateIntakeClassification.SEMANTIC_EXACT_REPLAY
            for item in candidate_states
        )
        now = datetime.now(UTC)
        request_id = uuid.uuid4()
        batch_id = uuid.uuid4() if domain_changed else None
        candidate_results: list[CapabilityGovernanceCandidateIntakeResult] = []

        if batch_id is not None:
            await _add(
                CapabilityDiscoveryBatch(
                    id=batch_id,
                    preview_fingerprint=preview.preview_fingerprint,
                    request_hash=request_hash,
                    fixture_set_hash=_fixture_set_hash(loaded_by_id),
                    imported_by_user_id=actor_user_id,
                    imported_at=now,
                ),
                session,
            )
            await _persist_sources(
                session,
                batch_id=batch_id,
                preview=preview,
                loaded_by_id=loaded_by_id,
                source_states=source_states,
            )
            evidence_by_id = await _persist_evidence(
                session,
                preview=preview,
                evidence_states=evidence_states,
            )
            for state in candidate_states:
                candidate_results.append(
                    await _persist_candidate_state(
                        session,
                        state=state,
                        batch_id=batch_id,
                        evidence_by_id=evidence_by_id,
                        now=now,
                    )
                )
        else:
            for state in candidate_states:
                if state.candidate_version is None:
                    raise CapabilityGovernanceDataConflictError
                candidate_results.append(
                    CapabilityGovernanceCandidateIntakeResult(
                        candidate_key=state.candidate_key,
                        candidate_version_id=state.candidate_version.id,
                        semantic_version=state.candidate_version.semantic_version,
                        classification=state.classification,
                        verification_task_id=None,
                        evidence_added_count=0,
                    )
                )

        response = CapabilityGovernanceImportResponse(
            schema_version="capability_governance_import_response.v1",
            request_id=request_id,
            batch_id=batch_id,
            preview_fingerprint=preview.preview_fingerprint,
            outcome=_outcome(candidate_results),
            candidates=candidate_results,
            database_write=True,
            domain_changed=domain_changed,
            idempotent_replay=False,
        )
        result_reference = (
            str(batch_id)
            if batch_id is not None
            else str(candidate_results[0].candidate_version_id)
        )
        await _add(
            CapabilityGovernanceRequest(
                id=request_id,
                actor_user_id=actor_user_id,
                action_scope=IMPORT_ACTION_SCOPE,
                idempotency_key_hash=key_hash,
                request_hash=request_hash,
                outcome=response.outcome,
                response_status=201 if domain_changed else 200,
                response_payload=_as_json_object(response.model_dump(mode="json")),
                result_reference=result_reference,
            ),
            session,
        )
        return response


__all__ = [
    "CapabilityGovernanceDataConflictError",
    "CapabilityGovernanceIdempotencyConflictError",
    "CapabilityGovernancePreviewStaleError",
    "CapabilityGovernanceTransactionStateError",
    "import_capability_candidates",
]
