from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast

from pydantic import JsonValue, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.capability_governance import (
    CapabilityCandidateAssertionVersion,
    CapabilityGovernanceRequest,
    CapabilityVerificationDecision,
    GovernanceCapabilityEvidence,
)
from data_intelligence_hub.repositories.capability_governance import (
    add_governance_record,
    get_candidate_version,
    get_governance_request_for_update,
    get_verification_task_for_update,
    list_candidate_evidence,
)
from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityAssertion,
    CapabilityEvidence,
)
from data_intelligence_hub.schemas.capability_governance import (
    CapabilityGovernancePermission,
    CapabilityGovernanceReviewRequest,
    CapabilityGovernanceReviewResponse,
    CapabilityVerificationAction,
    normalize_governance_idempotency_key,
)
from data_intelligence_hub.services.capability_governance.authority import (
    require_governance_permission,
)
from data_intelligence_hub.services.capability_governance.identity import (
    compute_governance_request_hash,
    compute_logical_assertion_key,
    hash_governance_idempotency_key,
)


class CapabilityGovernanceVerificationTaskConflictError(Exception):
    code = "verification_task_conflict"


class CapabilityGovernanceReviewIdempotencyConflictError(Exception):
    code = "idempotency_conflict"


class CapabilityGovernanceReviewTransactionStateError(Exception):
    code = "persistence_transaction_state_invalid"


class CapabilityGovernanceReviewContractError(Exception):
    code = "verification_contract_invalid"


async def _prepare_service_transaction(session: AsyncSession) -> None:
    if session.new or session.dirty or session.deleted:
        raise CapabilityGovernanceReviewTransactionStateError
    if session.in_transaction():
        await session.rollback()


async def _add(record: Base, session: AsyncSession) -> None:
    await add_governance_record(session, record)


def _as_json_object(value: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], cast(JsonValue, value))


def _replay_response(
    request: CapabilityGovernanceRequest,
    *,
    request_hash: str,
) -> CapabilityGovernanceReviewResponse:
    if request.request_hash != request_hash:
        raise CapabilityGovernanceReviewIdempotencyConflictError
    original = CapabilityGovernanceReviewResponse.model_validate(
        request.response_payload
    )
    return original.model_copy(
        update={
            "database_write": False,
            "domain_changed": False,
            "idempotent_replay": True,
        },
        deep=True,
    )


def _candidate_field(
    candidate: CapabilityCandidateAssertionVersion,
    field: str,
) -> str:
    value = candidate.candidate_payload.get(field)
    if not isinstance(value, str):
        raise CapabilityGovernanceReviewContractError
    return value


def _validated_evidence(
    candidate: CapabilityCandidateAssertionVersion,
    payload: CapabilityGovernanceReviewRequest,
    persisted_evidence: Sequence[GovernanceCapabilityEvidence],
) -> tuple[CapabilityEvidence, ...]:
    canonical = payload.canonical_assertion
    if canonical is None:
        raise CapabilityGovernanceReviewContractError
    parsed: dict[str, CapabilityEvidence] = {}
    try:
        for stored in persisted_evidence:
            evidence = CapabilityEvidence.model_validate(stored.evidence_payload)
            parsed[evidence.evidence_id] = evidence
    except (TypeError, ValueError, ValidationError) as exc:
        raise CapabilityGovernanceReviewContractError from exc

    requested_ids = set(canonical.evidence_refs)
    if not requested_ids or not requested_ids <= set(parsed):
        raise CapabilityGovernanceReviewContractError
    selected = tuple(parsed[evidence_id] for evidence_id in canonical.evidence_refs)
    if not any(item.hash_scope == "retrieved_content" for item in selected):
        raise CapabilityGovernanceReviewContractError
    if any(
        item.provider_call_attempted
        or item.credential_read_attempted
        or item.live_client_created
        or item.production_write_attempted
        for item in selected
    ):
        raise CapabilityGovernanceReviewContractError
    if candidate.id is None:
        raise CapabilityGovernanceReviewContractError
    return selected


def _canonical_bundle(
    *,
    decision_id: uuid.UUID,
    candidate: CapabilityCandidateAssertionVersion,
    payload: CapabilityGovernanceReviewRequest,
    evidence: tuple[CapabilityEvidence, ...],
    reviewed_at: datetime,
) -> dict[str, Any]:
    implementation = payload.canonical_implementation
    assertion_input = payload.canonical_assertion
    if implementation is None or assertion_input is None:
        raise CapabilityGovernanceReviewContractError
    if (
        implementation.platform.value != _candidate_field(candidate, "platform")
        or implementation.access_channel.value
        != _candidate_field(candidate, "access_channel")
        or assertion_input.resource_type.value
        != _candidate_field(candidate, "resource_type")
        or assertion_input.operation.value != _candidate_field(candidate, "operation")
    ):
        raise CapabilityGovernanceReviewContractError
    try:
        assertion = CapabilityAssertion(
            **assertion_input.model_dump(mode="python"),
            schema_version="capability_assertion.v1",
            last_verified_at=reviewed_at,
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise CapabilityGovernanceReviewContractError from exc
    logical_key = compute_logical_assertion_key(
        implementation_id=assertion.implementation_id,
        resource_type=assertion.resource_type,
        operation=assertion.operation,
        source_resource_group=assertion.source_resource_group,
    )
    return _as_json_object(
        {
            "schema_version": "verified_capability_bundle.v1",
            "verification_decision_id": str(decision_id),
            "action": payload.action.value,
            "candidate_key": candidate.candidate_key,
            "candidate_fingerprint": candidate.candidate_fingerprint,
            "logical_assertion_key": logical_key,
            "implementation": implementation.model_dump(mode="json"),
            "assertion": assertion.model_dump(mode="json"),
            "evidence": [item.model_dump(mode="json") for item in evidence],
        }
    )


async def review_capability_candidate(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    task_id: uuid.UUID,
    payload: CapabilityGovernanceReviewRequest,
    idempotency_key: str,
) -> CapabilityGovernanceReviewResponse:
    normalized_key = normalize_governance_idempotency_key(idempotency_key)
    key_hash = hash_governance_idempotency_key(normalized_key)
    action_scope = f"capability_governance.review:{task_id}"
    request_hash = compute_governance_request_hash(
        action_scope=action_scope,
        payload=cast(JsonValue, payload.model_dump(mode="json")),
    )
    await _prepare_service_transaction(session)

    async with session.begin():
        await require_governance_permission(
            session,
            actor_user_id,
            CapabilityGovernancePermission.REVIEW,
        )
        existing_request = await get_governance_request_for_update(
            session,
            actor_user_id,
            action_scope,
            key_hash,
        )
        if existing_request is not None:
            return _replay_response(existing_request, request_hash=request_hash)

        task = await get_verification_task_for_update(session, task_id)
        existing_request = await get_governance_request_for_update(
            session,
            actor_user_id,
            action_scope,
            key_hash,
        )
        if existing_request is not None:
            return _replay_response(existing_request, request_hash=request_hash)
        if (
            task is None
            or task.status != "open"
            or task.task_version != payload.expected_task_version
            or task.decision_id is not None
        ):
            raise CapabilityGovernanceVerificationTaskConflictError
        candidate = await get_candidate_version(session, task.candidate_version_id)
        if candidate is None:
            raise CapabilityGovernanceReviewContractError

        reviewed_at = datetime.now(UTC)
        decision_id = uuid.uuid4()
        canonical_bundle: dict[str, Any] | None = None
        verification_status = "rejected"
        if payload.action is not CapabilityVerificationAction.REJECT:
            persisted_evidence = await list_candidate_evidence(
                session,
                candidate.id,
            )
            evidence = _validated_evidence(candidate, payload, persisted_evidence)
            canonical_bundle = _canonical_bundle(
                decision_id=decision_id,
                candidate=candidate,
                payload=payload,
                evidence=evidence,
                reviewed_at=reviewed_at,
            )
            verification_status = "verified"

        decision = CapabilityVerificationDecision(
            id=decision_id,
            verification_task_id=task.id,
            candidate_version_id=candidate.id,
            action=payload.action.value,
            verification_status=verification_status,
            reviewer_user_id=actor_user_id,
            reviewed_at=reviewed_at,
            reason=payload.reason,
            canonical_bundle=canonical_bundle,
        )
        await _add(decision, session)
        task.status = "resolved"
        task.resolved_at = reviewed_at
        task.decision_id = decision_id

        request_id = uuid.uuid4()
        response = CapabilityGovernanceReviewResponse(
            schema_version="capability_governance_review_response.v1",
            request_id=request_id,
            decision_id=decision_id,
            task_id=task.id,
            candidate_version_id=candidate.id,
            task_version=task.task_version,
            action=payload.action,
            verification_status=verification_status,
            reviewed_at=reviewed_at,
            database_write=True,
            domain_changed=True,
            idempotent_replay=False,
        )
        await _add(
            CapabilityGovernanceRequest(
                id=request_id,
                actor_user_id=actor_user_id,
                action_scope=action_scope,
                idempotency_key_hash=key_hash,
                request_hash=request_hash,
                outcome=payload.action.value,
                response_status=200,
                response_payload=_as_json_object(response.model_dump(mode="json")),
                result_reference=str(decision_id),
            ),
            session,
        )
        return response


__all__ = [
    "CapabilityGovernanceReviewContractError",
    "CapabilityGovernanceReviewIdempotencyConflictError",
    "CapabilityGovernanceReviewTransactionStateError",
    "CapabilityGovernanceVerificationTaskConflictError",
    "review_capability_candidate",
]
