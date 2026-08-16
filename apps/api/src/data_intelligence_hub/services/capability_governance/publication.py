from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from pydantic import JsonValue, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.capability_governance import (
    CapabilityCatalogHead,
    CapabilityCatalogSnapshot,
    CapabilityGovernanceRequest,
    CapabilityPublicationRevision,
    CapabilityVerificationDecision,
)
from data_intelligence_hub.repositories.capability_governance import (
    add_governance_record,
    get_candidate_version,
    get_catalog_head_for_update,
    get_catalog_snapshot,
    get_governance_request_for_update,
    get_latest_candidate_version_for_update,
    get_latest_verification_decision_for_candidate_version,
    get_open_verification_task,
    get_publication_revision,
    get_verification_decision,
)
from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityAssertion,
    CapabilityCatalog,
    CapabilityEvidence,
    CapabilityImplementation,
    CapabilityStatus,
)
from data_intelligence_hub.schemas.capability_governance import (
    CapabilityGovernancePermission,
    CapabilityGovernancePublicationCreateRequest,
    CapabilityGovernancePublicationResponse,
    CapabilityGovernancePublicationRollbackRequest,
    CapabilityVerificationAction,
    RemoveAssertionOperation,
    normalize_governance_idempotency_key,
)
from data_intelligence_hub.services.capability_governance.authority import (
    require_governance_permission,
)
from data_intelligence_hub.services.capability_governance.catalog_resolution import (
    CapabilityCatalogResolutionError,
    resolve_capability_catalog_for_head,
)
from data_intelligence_hub.services.capability_governance.identity import (
    compute_governance_request_hash,
    compute_logical_assertion_key,
    hash_governance_idempotency_key,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import (
    compute_catalog_snapshot_id,
)


class CatalogMaterializationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class VerifiedCapabilityBundle:
    verification_decision_id: UUID
    action: CapabilityVerificationAction
    candidate_key: str
    candidate_fingerprint: str
    logical_assertion_key: str
    implementation: CapabilityImplementation
    assertion: CapabilityAssertion
    evidence: tuple[CapabilityEvidence, ...]


@dataclass(frozen=True, slots=True)
class UpsertCatalogAssertion:
    bundle: VerifiedCapabilityBundle


@dataclass(frozen=True, slots=True)
class RemoveCatalogAssertion:
    bundle: VerifiedCapabilityBundle


ResolvedCatalogOperation = UpsertCatalogAssertion | RemoveCatalogAssertion


def _logical_key(assertion: CapabilityAssertion) -> str:
    return compute_logical_assertion_key(
        implementation_id=assertion.implementation_id,
        resource_type=assertion.resource_type,
        operation=assertion.operation,
        source_resource_group=assertion.source_resource_group,
    )


def _validate_bundle(bundle: VerifiedCapabilityBundle) -> None:
    assertion = bundle.assertion
    if bundle.logical_assertion_key != _logical_key(assertion):
        raise CatalogMaterializationError("logical_assertion_key_mismatch")
    if assertion.implementation_id != bundle.implementation.implementation_id:
        raise CatalogMaterializationError("bundle_implementation_mismatch")

    evidence_ids = [item.evidence_id for item in bundle.evidence]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise CatalogMaterializationError("bundle_evidence_duplicate")
    if set(evidence_ids) != set(assertion.evidence_refs):
        raise CatalogMaterializationError("bundle_evidence_mismatch")

    if bundle.action is CapabilityVerificationAction.DEPRECATE:
        if assertion.support_status is not CapabilityStatus.DEPRECATED:
            raise CatalogMaterializationError("deprecate_status_required")
    elif bundle.action is CapabilityVerificationAction.VERIFY:
        if assertion.support_status is CapabilityStatus.DEPRECATED:
            raise CatalogMaterializationError("verify_deprecated_status_forbidden")
    else:
        raise CatalogMaterializationError("rejected_bundle_not_publishable")

    reviewed_at = assertion.last_verified_at
    if reviewed_at.tzinfo is None or reviewed_at.utcoffset() is None:
        raise CatalogMaterializationError("bundle_verified_at_timezone_required")


def _base_assertions_by_key(
    catalog: CapabilityCatalog,
) -> dict[str, CapabilityAssertion]:
    by_key: dict[str, CapabilityAssertion] = {}
    for assertion in catalog.assertions:
        key = _logical_key(assertion)
        if key in by_key:
            raise CatalogMaterializationError("catalog_duplicate_logical_assertion")
        by_key[key] = assertion.model_copy(deep=True)
    return by_key


def materialize_capability_catalog(
    base_catalog: CapabilityCatalog,
    operations: Sequence[ResolvedCatalogOperation],
    *,
    generated_at: datetime,
) -> CapabilityCatalog:
    if not operations:
        return base_catalog.model_copy(deep=True)

    implementations = {
        item.implementation_id: item.model_copy(deep=True) for item in base_catalog.implementations
    }
    evidence = {item.evidence_id: item.model_copy(deep=True) for item in base_catalog.evidence}
    assertions = _base_assertions_by_key(base_catalog)

    operation_keys: set[str] = set()
    for operation in operations:
        bundle = operation.bundle
        _validate_bundle(bundle)
        key = bundle.logical_assertion_key
        if key in operation_keys:
            raise CatalogMaterializationError("duplicate_logical_operation")
        operation_keys.add(key)

        if isinstance(operation, RemoveCatalogAssertion):
            if bundle.action is not CapabilityVerificationAction.DEPRECATE:
                raise CatalogMaterializationError("remove_requires_deprecate")
            if key not in assertions:
                raise CatalogMaterializationError("remove_target_not_found")
            del assertions[key]
            continue

        existing_implementation = implementations.get(bundle.implementation.implementation_id)
        if existing_implementation is not None and existing_implementation != bundle.implementation:
            raise CatalogMaterializationError("implementation_id_content_conflict")
        implementations[bundle.implementation.implementation_id] = bundle.implementation.model_copy(
            deep=True
        )

        for item in bundle.evidence:
            existing_evidence = evidence.get(item.evidence_id)
            if existing_evidence is not None and existing_evidence != item:
                raise CatalogMaterializationError("evidence_id_content_conflict")
            evidence[item.evidence_id] = item.model_copy(deep=True)

        for existing_key, existing_assertion in assertions.items():
            if (
                existing_key != key
                and existing_assertion.assertion_id == bundle.assertion.assertion_id
            ):
                raise CatalogMaterializationError("assertion_id_logical_key_conflict")
        assertions[key] = bundle.assertion.model_copy(deep=True)

    referenced_evidence = {
        evidence_ref
        for assertion in assertions.values()
        for evidence_ref in assertion.evidence_refs
    }
    pruned_evidence = [
        item for evidence_id, item in evidence.items() if evidence_id in referenced_evidence
    ]

    try:
        return CapabilityCatalog(
            schema_version="capability_catalog.v1",
            evidence_level=base_catalog.evidence_level,
            provider_call=False,
            production_write_allowed=False,
            generated_at=generated_at,
            implementations=sorted(
                implementations.values(),
                key=lambda item: item.implementation_id,
            ),
            assertions=sorted(
                assertions.values(),
                key=lambda item: item.assertion_id,
            ),
            evidence=sorted(
                pruned_evidence,
                key=lambda item: item.evidence_id,
            ),
        )
    except ValidationError as exc:
        raise CatalogMaterializationError("catalog_contract_invalid") from exc


class CapabilityGovernancePublicationParentConflictError(Exception):
    code = "publication_parent_conflict"


class CapabilityGovernanceDecisionNotCurrentError(Exception):
    code = "verification_decision_not_current"


class CapabilityGovernancePublicationContractError(Exception):
    code = "publication_contract_invalid"


class CapabilityGovernanceCatalogSnapshotInvalidError(Exception):
    code = "catalog_snapshot_invalid"


class CapabilityGovernancePublicationIdempotencyConflictError(Exception):
    code = "idempotency_conflict"


class CapabilityGovernancePublicationTransactionStateError(Exception):
    code = "persistence_transaction_state_invalid"


async def _prepare_service_transaction(session: AsyncSession) -> None:
    if session.new or session.dirty or session.deleted:
        raise CapabilityGovernancePublicationTransactionStateError
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
) -> CapabilityGovernancePublicationResponse:
    if request.request_hash != request_hash:
        raise CapabilityGovernancePublicationIdempotencyConflictError
    original = CapabilityGovernancePublicationResponse.model_validate(request.response_payload)
    return original.model_copy(
        update={
            "database_write": False,
            "domain_changed": False,
            "idempotent_replay": True,
        },
        deep=True,
    )


def _bundle_from_decision(
    decision: CapabilityVerificationDecision,
) -> VerifiedCapabilityBundle:
    payload = decision.canonical_bundle
    if decision.verification_status != "verified" or payload is None:
        raise CapabilityGovernanceDecisionNotCurrentError
    try:
        decision_id = UUID(str(payload["verification_decision_id"]))
        action = CapabilityVerificationAction(str(payload["action"]))
        candidate_key = str(payload["candidate_key"])
        candidate_fingerprint = str(payload["candidate_fingerprint"])
        logical_key = str(payload["logical_assertion_key"])
        implementation = CapabilityImplementation.model_validate(payload["implementation"])
        assertion = CapabilityAssertion.model_validate(payload["assertion"])
        raw_evidence = payload["evidence"]
        if not isinstance(raw_evidence, list):
            raise ValueError("bundle_evidence_invalid")
        evidence = tuple(CapabilityEvidence.model_validate(item) for item in raw_evidence)
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise CapabilityGovernancePublicationContractError from exc
    if (
        decision_id != decision.id
        or action.value != decision.action
        or action is CapabilityVerificationAction.REJECT
    ):
        raise CapabilityGovernancePublicationContractError
    return VerifiedCapabilityBundle(
        verification_decision_id=decision.id,
        action=action,
        candidate_key=candidate_key,
        candidate_fingerprint=candidate_fingerprint,
        logical_assertion_key=logical_key,
        implementation=implementation,
        assertion=assertion,
        evidence=evidence,
    )


async def _current_bundle(
    session: AsyncSession,
    decision_id: uuid.UUID,
) -> VerifiedCapabilityBundle:
    decision = await get_verification_decision(session, decision_id)
    if decision is None:
        raise CapabilityGovernanceDecisionNotCurrentError
    candidate = await get_candidate_version(session, decision.candidate_version_id)
    if candidate is None:
        raise CapabilityGovernancePublicationContractError
    latest_candidate = await get_latest_candidate_version_for_update(
        session,
        candidate.candidate_key,
    )
    latest_decision = await get_latest_verification_decision_for_candidate_version(
        session,
        candidate.id,
    )
    open_task = await get_open_verification_task(session, candidate.id)
    if (
        latest_candidate is None
        or latest_candidate.id != candidate.id
        or latest_decision is None
        or latest_decision.id != decision.id
        or open_task is not None
    ):
        raise CapabilityGovernanceDecisionNotCurrentError
    bundle = _bundle_from_decision(decision)
    if (
        bundle.candidate_key != candidate.candidate_key
        or bundle.candidate_fingerprint != candidate.candidate_fingerprint
    ):
        raise CapabilityGovernancePublicationContractError
    return bundle


async def _resolved_operations(
    session: AsyncSession,
    payload: CapabilityGovernancePublicationCreateRequest,
) -> list[ResolvedCatalogOperation]:
    resolved: list[ResolvedCatalogOperation] = []
    for operation in payload.operations:
        bundle = await _current_bundle(
            session,
            operation.verification_decision_id,
        )
        if isinstance(operation, RemoveAssertionOperation):
            if operation.logical_assertion_key != bundle.logical_assertion_key:
                raise CapabilityGovernancePublicationContractError
            resolved.append(RemoveCatalogAssertion(bundle=bundle))
        else:
            resolved.append(UpsertCatalogAssertion(bundle=bundle))
    return resolved


def _validated_snapshot(snapshot: CapabilityCatalogSnapshot) -> CapabilityCatalog:
    try:
        catalog = CapabilityCatalog.model_validate(snapshot.catalog_payload)
    except (TypeError, ValueError, ValidationError) as exc:
        raise CapabilityGovernancePublicationContractError from exc
    if compute_catalog_snapshot_id(catalog) != snapshot.catalog_snapshot_id:
        raise CapabilityGovernancePublicationContractError
    return catalog


async def _store_snapshot(
    session: AsyncSession,
    catalog: CapabilityCatalog,
) -> str:
    snapshot_id = compute_catalog_snapshot_id(catalog)
    existing = await get_catalog_snapshot(session, snapshot_id)
    if existing is None:
        await _add(
            CapabilityCatalogSnapshot(
                catalog_snapshot_id=snapshot_id,
                catalog_payload=_as_json_object(catalog.model_dump(mode="json")),
            ),
            session,
        )
    else:
        _validated_snapshot(existing)
    return snapshot_id


def _publication_response(
    *,
    publication_kind: str,
    request_id: uuid.UUID,
    revision: CapabilityPublicationRevision,
    head: CapabilityCatalogHead,
    operation_count: int,
) -> CapabilityGovernancePublicationResponse:
    return CapabilityGovernancePublicationResponse(
        schema_version="capability_governance_publication_response.v1",
        publication_kind=publication_kind,
        request_id=request_id,
        revision_id=revision.id,
        revision_number=revision.revision_number,
        parent_revision_id=revision.parent_revision_id,
        restored_from_revision_id=revision.restored_from_revision_id,
        catalog_snapshot_id=revision.catalog_snapshot_id,
        head_version=head.head_version,
        operation_count=operation_count,
        published_at=revision.published_at,
        database_write=True,
        domain_changed=True,
        idempotent_replay=False,
    )


async def publish_capability_catalog(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    payload: CapabilityGovernancePublicationCreateRequest,
    idempotency_key: str,
) -> CapabilityGovernancePublicationResponse:
    normalized_key = normalize_governance_idempotency_key(idempotency_key)
    key_hash = hash_governance_idempotency_key(normalized_key)
    action_scope = "capability_governance.publish"
    request_hash = compute_governance_request_hash(
        action_scope=action_scope,
        payload=cast(JsonValue, payload.model_dump(mode="json")),
    )
    await _prepare_service_transaction(session)

    async with session.begin():
        await require_governance_permission(
            session,
            actor_user_id,
            CapabilityGovernancePermission.PUBLISH,
        )
        existing_request = await get_governance_request_for_update(
            session,
            actor_user_id,
            action_scope,
            key_hash,
        )
        if existing_request is not None:
            return _replay_response(existing_request, request_hash=request_hash)
        head = await get_catalog_head_for_update(session)
        if head is None:
            raise CapabilityGovernanceCatalogSnapshotInvalidError
        existing_request = await get_governance_request_for_update(
            session,
            actor_user_id,
            action_scope,
            key_hash,
        )
        if existing_request is not None:
            return _replay_response(existing_request, request_hash=request_hash)
        if head.current_revision_id != payload.expected_parent_revision_id:
            raise CapabilityGovernancePublicationParentConflictError
        try:
            base_catalog = await resolve_capability_catalog_for_head(session, head)
            operations = await _resolved_operations(session, payload)
            published_at = datetime.now(UTC)
            materialized = materialize_capability_catalog(
                base_catalog,
                operations,
                generated_at=published_at,
            )
        except CapabilityCatalogResolutionError as exc:
            raise CapabilityGovernanceCatalogSnapshotInvalidError from exc
        except CatalogMaterializationError as exc:
            raise CapabilityGovernancePublicationContractError from exc
        snapshot_id = await _store_snapshot(session, materialized)
        revision = CapabilityPublicationRevision(
            id=uuid.uuid4(),
            revision_number=head.head_version + 1,
            parent_revision_id=head.current_revision_id,
            restored_from_revision_id=None,
            catalog_snapshot_id=snapshot_id,
            publisher_user_id=actor_user_id,
            published_at=published_at,
            reason=payload.reason,
            operations=[item.model_dump(mode="json") for item in payload.operations],
        )
        await _add(revision, session)
        head.current_revision_id = revision.id
        head.head_version = revision.revision_number
        head.updated_at = published_at
        request_id = uuid.uuid4()
        response = _publication_response(
            publication_kind="publish",
            request_id=request_id,
            revision=revision,
            head=head,
            operation_count=len(payload.operations),
        )
        await _add(
            CapabilityGovernanceRequest(
                id=request_id,
                actor_user_id=actor_user_id,
                action_scope=action_scope,
                idempotency_key_hash=key_hash,
                request_hash=request_hash,
                outcome="published",
                response_status=201,
                response_payload=_as_json_object(response.model_dump(mode="json")),
                result_reference=str(revision.id),
            ),
            session,
        )
        return response


async def rollback_capability_catalog(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    payload: CapabilityGovernancePublicationRollbackRequest,
    idempotency_key: str,
) -> CapabilityGovernancePublicationResponse:
    normalized_key = normalize_governance_idempotency_key(idempotency_key)
    key_hash = hash_governance_idempotency_key(normalized_key)
    action_scope = "capability_governance.rollback"
    request_hash = compute_governance_request_hash(
        action_scope=action_scope,
        payload=cast(JsonValue, payload.model_dump(mode="json")),
    )
    await _prepare_service_transaction(session)

    async with session.begin():
        await require_governance_permission(
            session,
            actor_user_id,
            CapabilityGovernancePermission.PUBLISH,
        )
        existing_request = await get_governance_request_for_update(
            session,
            actor_user_id,
            action_scope,
            key_hash,
        )
        if existing_request is not None:
            return _replay_response(existing_request, request_hash=request_hash)
        head = await get_catalog_head_for_update(session)
        if head is None:
            raise CapabilityGovernanceCatalogSnapshotInvalidError
        existing_request = await get_governance_request_for_update(
            session,
            actor_user_id,
            action_scope,
            key_hash,
        )
        if existing_request is not None:
            return _replay_response(existing_request, request_hash=request_hash)
        if head.current_revision_id != payload.expected_current_revision_id:
            raise CapabilityGovernancePublicationParentConflictError
        try:
            await resolve_capability_catalog_for_head(session, head)
        except CapabilityCatalogResolutionError as exc:
            raise CapabilityGovernanceCatalogSnapshotInvalidError from exc
        target = await get_publication_revision(session, payload.target_revision_id)
        if target is None or target.id == head.current_revision_id:
            raise CapabilityGovernancePublicationContractError
        target_snapshot = await get_catalog_snapshot(session, target.catalog_snapshot_id)
        if target_snapshot is None:
            raise CapabilityGovernanceCatalogSnapshotInvalidError
        try:
            _validated_snapshot(target_snapshot)
        except CapabilityGovernancePublicationContractError as exc:
            raise CapabilityGovernanceCatalogSnapshotInvalidError from exc

        published_at = datetime.now(UTC)
        revision = CapabilityPublicationRevision(
            id=uuid.uuid4(),
            revision_number=head.head_version + 1,
            parent_revision_id=head.current_revision_id,
            restored_from_revision_id=target.id,
            catalog_snapshot_id=target.catalog_snapshot_id,
            publisher_user_id=actor_user_id,
            published_at=published_at,
            reason=payload.reason,
            operations=[
                {
                    "operation": "rollback",
                    "target_revision_id": str(target.id),
                }
            ],
        )
        await _add(revision, session)
        head.current_revision_id = revision.id
        head.head_version = revision.revision_number
        head.updated_at = published_at
        request_id = uuid.uuid4()
        response = _publication_response(
            publication_kind="rollback",
            request_id=request_id,
            revision=revision,
            head=head,
            operation_count=1,
        )
        await _add(
            CapabilityGovernanceRequest(
                id=request_id,
                actor_user_id=actor_user_id,
                action_scope=action_scope,
                idempotency_key_hash=key_hash,
                request_hash=request_hash,
                outcome="rolled_back",
                response_status=201,
                response_payload=_as_json_object(response.model_dump(mode="json")),
                result_reference=str(revision.id),
            ),
            session,
        )
        return response
