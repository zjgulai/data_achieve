from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.capability_governance import (
    CapabilityCandidateAssertionVersion,
    CapabilityPublicationRevision,
    CapabilityVerificationDecision,
    CapabilityVerificationTask,
    GovernanceCapabilityEvidence,
)
from data_intelligence_hub.repositories.capability_governance import (
    get_candidate_version,
    get_catalog_head,
    get_latest_candidate_version,
    get_latest_verification_decision_for_candidate_version,
    get_open_verification_task,
    get_publication_revision,
    get_verification_decision,
    get_verification_task,
    list_candidate_evidence,
    list_candidate_versions,
    list_publication_revisions,
    list_verification_tasks,
)
from data_intelligence_hub.schemas.capability_catalog import CapabilityEvidence
from data_intelligence_hub.schemas.capability_governance import (
    CapabilityGovernanceCandidateAssertionResponse,
    CapabilityGovernanceCandidateDetailResponse,
    CapabilityGovernanceCandidateListResponse,
    CapabilityGovernanceCandidateResponse,
    CapabilityGovernanceDecisionResponse,
    CapabilityGovernancePermission,
    CapabilityGovernancePermissionSet,
    CapabilityGovernanceProposedImplementationResponse,
    CapabilityGovernancePublicationDetailResponse,
    CapabilityGovernancePublicationListResponse,
    CapabilityGovernancePublicationRevisionResponse,
    CapabilityGovernanceVerificationTaskDetailResponse,
    CapabilityGovernanceVerificationTaskListResponse,
    CapabilityGovernanceVerificationTaskResponse,
    CapabilityVerificationAction,
    CapabilityVerificationTaskStatus,
    CapabilityVerificationTaskType,
)
from data_intelligence_hub.services.capability_governance.authority import (
    require_governance_permission,
)


class CapabilityGovernanceResourceNotFoundError(Exception):
    code = "governance_resource_not_found"


class CapabilityGovernanceReadContractError(Exception):
    code = "internal_server_error"


def _candidate_response(
    candidate: CapabilityCandidateAssertionVersion,
) -> CapabilityGovernanceCandidateResponse:
    return CapabilityGovernanceCandidateResponse(
        id=candidate.id,
        candidate_key=candidate.candidate_key,
        semantic_version=candidate.semantic_version,
        candidate_fingerprint=candidate.candidate_fingerprint,
        predecessor_id=candidate.predecessor_id,
        proposed_implementation=CapabilityGovernanceProposedImplementationResponse.model_validate(
            candidate.proposed_implementation_payload
        ),
        candidate_assertion=CapabilityGovernanceCandidateAssertionResponse.model_validate(
            candidate.candidate_payload
        ),
        first_seen_batch_id=candidate.first_seen_batch_id,
        created_at=candidate.created_at,
    )


def _evidence_response(
    evidence: GovernanceCapabilityEvidence,
) -> CapabilityEvidence:
    return CapabilityEvidence.model_validate(evidence.evidence_payload)


def _task_response(
    task: CapabilityVerificationTask,
) -> CapabilityGovernanceVerificationTaskResponse:
    return CapabilityGovernanceVerificationTaskResponse(
        id=task.id,
        candidate_version_id=task.candidate_version_id,
        task_type=CapabilityVerificationTaskType(task.task_type),
        status=CapabilityVerificationTaskStatus(task.status),
        task_version=task.task_version,
        opened_at=task.opened_at,
        resolved_at=task.resolved_at,
        decision_id=task.decision_id,
    )


def _decision_response(
    decision: CapabilityVerificationDecision,
) -> CapabilityGovernanceDecisionResponse:
    return CapabilityGovernanceDecisionResponse(
        id=decision.id,
        verification_task_id=decision.verification_task_id,
        candidate_version_id=decision.candidate_version_id,
        action=CapabilityVerificationAction(decision.action),
        verification_status=decision.verification_status,
        reviewer_user_id=decision.reviewer_user_id,
        reviewed_at=decision.reviewed_at,
        reason=decision.reason,
        canonical_bundle=decision.canonical_bundle,
    )


def _revision_response(
    revision: CapabilityPublicationRevision,
    *,
    current_revision_id: uuid.UUID | None,
) -> CapabilityGovernancePublicationRevisionResponse:
    return CapabilityGovernancePublicationRevisionResponse(
        id=revision.id,
        revision_number=revision.revision_number,
        parent_revision_id=revision.parent_revision_id,
        restored_from_revision_id=revision.restored_from_revision_id,
        catalog_snapshot_id=revision.catalog_snapshot_id,
        publisher_user_id=revision.publisher_user_id,
        published_at=revision.published_at,
        reason=revision.reason,
        operations=revision.operations,
        is_current=revision.id == current_revision_id,
    )


async def list_governance_candidates(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    limit: int,
    offset: int,
) -> CapabilityGovernanceCandidateListResponse:
    membership = await require_governance_permission(
        session,
        actor_user_id,
        CapabilityGovernancePermission.READ,
    )
    candidates = await list_candidate_versions(session, limit=limit, offset=offset)
    return CapabilityGovernanceCandidateListResponse(
        schema_version="capability_governance_candidate_list.v1",
        permissions=CapabilityGovernancePermissionSet(
            can_read=membership.can_read,
            can_review=membership.can_review,
            can_publish=membership.can_publish,
        ),
        items=[_candidate_response(item) for item in candidates],
        limit=limit,
        offset=offset,
    )


async def get_governance_candidate_detail(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    candidate_key: str,
) -> CapabilityGovernanceCandidateDetailResponse:
    await require_governance_permission(
        session,
        actor_user_id,
        CapabilityGovernancePermission.READ,
    )
    candidate = await get_latest_candidate_version(session, candidate_key)
    if candidate is None:
        raise CapabilityGovernanceResourceNotFoundError
    evidence = await list_candidate_evidence(session, candidate.id)
    task = await get_open_verification_task(session, candidate.id)
    decision = await get_latest_verification_decision_for_candidate_version(
        session,
        candidate.id,
    )
    return CapabilityGovernanceCandidateDetailResponse(
        schema_version="capability_governance_candidate_detail.v1",
        candidate=_candidate_response(candidate),
        evidence=[_evidence_response(item) for item in evidence],
        open_verification_task=None if task is None else _task_response(task),
        latest_decision=(None if decision is None else _decision_response(decision)),
    )


async def list_governance_verification_tasks(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    limit: int,
    offset: int,
    task_status: CapabilityVerificationTaskStatus | None,
) -> CapabilityGovernanceVerificationTaskListResponse:
    await require_governance_permission(
        session,
        actor_user_id,
        CapabilityGovernancePermission.READ,
    )
    tasks = await list_verification_tasks(
        session,
        limit=limit,
        offset=offset,
        status=None if task_status is None else task_status.value,
    )
    return CapabilityGovernanceVerificationTaskListResponse(
        schema_version="capability_governance_verification_task_list.v1",
        items=[_task_response(item) for item in tasks],
        limit=limit,
        offset=offset,
    )


async def get_governance_verification_task_detail(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    task_id: uuid.UUID,
) -> CapabilityGovernanceVerificationTaskDetailResponse:
    await require_governance_permission(
        session,
        actor_user_id,
        CapabilityGovernancePermission.READ,
    )
    task = await get_verification_task(session, task_id)
    if task is None:
        raise CapabilityGovernanceResourceNotFoundError
    candidate = await get_candidate_version(session, task.candidate_version_id)
    if candidate is None:
        raise CapabilityGovernanceReadContractError
    evidence = await list_candidate_evidence(session, candidate.id)
    decision = (
        None
        if task.decision_id is None
        else await get_verification_decision(session, task.decision_id)
    )
    if task.decision_id is not None and decision is None:
        raise CapabilityGovernanceReadContractError
    return CapabilityGovernanceVerificationTaskDetailResponse(
        schema_version="capability_governance_verification_task_detail.v1",
        task=_task_response(task),
        candidate=_candidate_response(candidate),
        evidence=[_evidence_response(item) for item in evidence],
        decision=None if decision is None else _decision_response(decision),
    )


async def list_governance_publications(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    limit: int,
    offset: int,
) -> CapabilityGovernancePublicationListResponse:
    await require_governance_permission(
        session,
        actor_user_id,
        CapabilityGovernancePermission.READ,
    )
    head = await get_catalog_head(session)
    if head is None:
        raise CapabilityGovernanceReadContractError
    revisions = await list_publication_revisions(session, limit=limit, offset=offset)
    return CapabilityGovernancePublicationListResponse(
        schema_version="capability_governance_publication_list.v1",
        items=[
            _revision_response(item, current_revision_id=head.current_revision_id)
            for item in revisions
        ],
        current_revision_id=head.current_revision_id,
        limit=limit,
        offset=offset,
    )


async def get_governance_publication_detail(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    revision_id: uuid.UUID,
) -> CapabilityGovernancePublicationDetailResponse:
    await require_governance_permission(
        session,
        actor_user_id,
        CapabilityGovernancePermission.READ,
    )
    revision = await get_publication_revision(session, revision_id)
    if revision is None:
        raise CapabilityGovernanceResourceNotFoundError
    head = await get_catalog_head(session)
    if head is None:
        raise CapabilityGovernanceReadContractError
    return CapabilityGovernancePublicationDetailResponse(
        schema_version="capability_governance_publication_detail.v1",
        revision=_revision_response(
            revision,
            current_revision_id=head.current_revision_id,
        ),
        current_revision_id=head.current_revision_id,
    )


__all__ = [
    "CapabilityGovernanceReadContractError",
    "CapabilityGovernanceResourceNotFoundError",
    "get_governance_candidate_detail",
    "get_governance_publication_detail",
    "get_governance_verification_task_detail",
    "list_governance_candidates",
    "list_governance_publications",
    "list_governance_verification_tasks",
]
