from __future__ import annotations

import uuid

from sqlalchemy import Select, desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.capability_governance import (
    CapabilityCandidateAssertionVersion,
    CapabilityCandidateEvidenceLink,
    CapabilityCatalogHead,
    CapabilityCatalogSnapshot,
    CapabilityGovernanceMembership,
    CapabilityGovernanceRequest,
    CapabilityPublicationRevision,
    CapabilitySourceSnapshot,
    CapabilityVerificationDecision,
    CapabilityVerificationTask,
    GovernanceCapabilityEvidence,
)

MAX_GOVERNANCE_PAGE_SIZE = 100
CAPABILITY_GOVERNANCE_IMPORT_LOCK_SCOPE = "data_scrapy.capability_governance.import.v1"


def _validate_pagination(*, limit: int, offset: int) -> None:
    if not 1 <= limit <= MAX_GOVERNANCE_PAGE_SIZE or offset < 0:
        raise ValueError("governance_pagination_invalid")


async def acquire_governance_import_lock(session: AsyncSession) -> None:
    if session.get_bind().dialect.name != "postgresql":
        return
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_scope, 0))"),
        {"lock_scope": CAPABILITY_GOVERNANCE_IMPORT_LOCK_SCOPE},
    )


async def get_active_governance_membership(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> CapabilityGovernanceMembership | None:
    result = await session.execute(
        select(CapabilityGovernanceMembership).where(
            CapabilityGovernanceMembership.user_id == user_id,
            CapabilityGovernanceMembership.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def get_candidate_version(
    session: AsyncSession,
    candidate_version_id: uuid.UUID,
) -> CapabilityCandidateAssertionVersion | None:
    result = await session.execute(
        select(CapabilityCandidateAssertionVersion).where(
            CapabilityCandidateAssertionVersion.id == candidate_version_id
        )
    )
    return result.scalar_one_or_none()


async def get_candidate_version_by_fingerprint(
    session: AsyncSession,
    candidate_key: str,
    candidate_fingerprint: str,
) -> CapabilityCandidateAssertionVersion | None:
    result = await session.execute(
        select(CapabilityCandidateAssertionVersion).where(
            CapabilityCandidateAssertionVersion.candidate_key == candidate_key,
            CapabilityCandidateAssertionVersion.candidate_fingerprint == candidate_fingerprint,
        )
    )
    return result.scalar_one_or_none()


def candidate_version_lock_statement(
    candidate_key: str,
) -> Select[tuple[CapabilityCandidateAssertionVersion]]:
    return (
        select(CapabilityCandidateAssertionVersion)
        .where(CapabilityCandidateAssertionVersion.candidate_key == candidate_key)
        .order_by(
            desc(CapabilityCandidateAssertionVersion.semantic_version),
            desc(CapabilityCandidateAssertionVersion.id),
        )
        .limit(1)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def get_latest_candidate_version(
    session: AsyncSession,
    candidate_key: str,
) -> CapabilityCandidateAssertionVersion | None:
    result = await session.execute(
        select(CapabilityCandidateAssertionVersion)
        .where(CapabilityCandidateAssertionVersion.candidate_key == candidate_key)
        .order_by(
            desc(CapabilityCandidateAssertionVersion.semantic_version),
            desc(CapabilityCandidateAssertionVersion.id),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_latest_candidate_version_for_update(
    session: AsyncSession,
    candidate_key: str,
) -> CapabilityCandidateAssertionVersion | None:
    result = await session.execute(candidate_version_lock_statement(candidate_key))
    return result.scalar_one_or_none()


async def list_candidate_versions(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
) -> list[CapabilityCandidateAssertionVersion]:
    _validate_pagination(limit=limit, offset=offset)
    result = await session.execute(
        select(CapabilityCandidateAssertionVersion)
        .order_by(
            desc(CapabilityCandidateAssertionVersion.created_at),
            desc(CapabilityCandidateAssertionVersion.semantic_version),
            desc(CapabilityCandidateAssertionVersion.id),
        )
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


def verification_task_lock_statement(
    task_id: uuid.UUID,
) -> Select[tuple[CapabilityVerificationTask]]:
    return (
        select(CapabilityVerificationTask)
        .where(CapabilityVerificationTask.id == task_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def get_verification_task(
    session: AsyncSession,
    task_id: uuid.UUID,
) -> CapabilityVerificationTask | None:
    result = await session.execute(
        select(CapabilityVerificationTask).where(CapabilityVerificationTask.id == task_id)
    )
    return result.scalar_one_or_none()


async def get_verification_task_for_update(
    session: AsyncSession,
    task_id: uuid.UUID,
) -> CapabilityVerificationTask | None:
    result = await session.execute(verification_task_lock_statement(task_id))
    return result.scalar_one_or_none()


async def get_open_verification_task(
    session: AsyncSession,
    candidate_version_id: uuid.UUID,
) -> CapabilityVerificationTask | None:
    result = await session.execute(
        select(CapabilityVerificationTask).where(
            CapabilityVerificationTask.candidate_version_id == candidate_version_id,
            CapabilityVerificationTask.status == "open",
        )
    )
    return result.scalar_one_or_none()


def open_verification_task_lock_statement(
    candidate_version_id: uuid.UUID,
) -> Select[tuple[CapabilityVerificationTask]]:
    return (
        select(CapabilityVerificationTask)
        .where(
            CapabilityVerificationTask.candidate_version_id == candidate_version_id,
            CapabilityVerificationTask.status == "open",
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def get_open_verification_task_for_update(
    session: AsyncSession,
    candidate_version_id: uuid.UUID,
) -> CapabilityVerificationTask | None:
    result = await session.execute(open_verification_task_lock_statement(candidate_version_id))
    return result.scalar_one_or_none()


async def list_verification_tasks(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
    status: str | None = None,
) -> list[CapabilityVerificationTask]:
    _validate_pagination(limit=limit, offset=offset)
    statement = select(CapabilityVerificationTask)
    if status is not None:
        statement = statement.where(CapabilityVerificationTask.status == status)
    result = await session.execute(
        statement.order_by(
            desc(CapabilityVerificationTask.opened_at),
            desc(CapabilityVerificationTask.id),
        )
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_publication_revision(
    session: AsyncSession,
    revision_id: uuid.UUID,
) -> CapabilityPublicationRevision | None:
    result = await session.execute(
        select(CapabilityPublicationRevision).where(CapabilityPublicationRevision.id == revision_id)
    )
    return result.scalar_one_or_none()


async def get_catalog_snapshot(
    session: AsyncSession,
    catalog_snapshot_id: str,
) -> CapabilityCatalogSnapshot | None:
    result = await session.execute(
        select(CapabilityCatalogSnapshot).where(
            CapabilityCatalogSnapshot.catalog_snapshot_id == catalog_snapshot_id
        )
    )
    return result.scalar_one_or_none()


async def get_catalog_head(
    session: AsyncSession,
) -> CapabilityCatalogHead | None:
    result = await session.execute(
        select(CapabilityCatalogHead).where(CapabilityCatalogHead.singleton_key == "global")
    )
    return result.scalar_one_or_none()


async def get_latest_verification_decision_for_candidate_version(
    session: AsyncSession,
    candidate_version_id: uuid.UUID,
) -> CapabilityVerificationDecision | None:
    result = await session.execute(
        select(CapabilityVerificationDecision)
        .where(CapabilityVerificationDecision.candidate_version_id == candidate_version_id)
        .order_by(
            desc(CapabilityVerificationDecision.reviewed_at),
            desc(CapabilityVerificationDecision.id),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_source_snapshot(
    session: AsyncSession,
    fixture_id: str,
    content_hash: str,
) -> CapabilitySourceSnapshot | None:
    result = await session.execute(
        select(CapabilitySourceSnapshot).where(
            CapabilitySourceSnapshot.fixture_id == fixture_id,
            CapabilitySourceSnapshot.content_hash == content_hash,
        )
    )
    return result.scalar_one_or_none()


async def get_governance_evidence(
    session: AsyncSession,
    evidence_id: str,
) -> GovernanceCapabilityEvidence | None:
    result = await session.execute(
        select(GovernanceCapabilityEvidence).where(
            GovernanceCapabilityEvidence.evidence_id == evidence_id
        )
    )
    return result.scalar_one_or_none()


async def list_candidate_evidence_external_ids(
    session: AsyncSession,
    candidate_version_id: uuid.UUID,
) -> set[str]:
    result = await session.execute(
        select(GovernanceCapabilityEvidence.evidence_id)
        .join(
            CapabilityCandidateEvidenceLink,
            CapabilityCandidateEvidenceLink.evidence_id == GovernanceCapabilityEvidence.id,
        )
        .where(CapabilityCandidateEvidenceLink.candidate_version_id == candidate_version_id)
    )
    return set(result.scalars().all())


async def list_candidate_evidence(
    session: AsyncSession,
    candidate_version_id: uuid.UUID,
) -> list[GovernanceCapabilityEvidence]:
    result = await session.execute(
        select(GovernanceCapabilityEvidence)
        .join(
            CapabilityCandidateEvidenceLink,
            CapabilityCandidateEvidenceLink.evidence_id == GovernanceCapabilityEvidence.id,
        )
        .where(CapabilityCandidateEvidenceLink.candidate_version_id == candidate_version_id)
        .order_by(GovernanceCapabilityEvidence.evidence_id)
    )
    return list(result.scalars().all())


async def get_verification_decision(
    session: AsyncSession,
    decision_id: uuid.UUID,
) -> CapabilityVerificationDecision | None:
    result = await session.execute(
        select(CapabilityVerificationDecision).where(
            CapabilityVerificationDecision.id == decision_id
        )
    )
    return result.scalar_one_or_none()


async def list_publication_revisions(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
) -> list[CapabilityPublicationRevision]:
    _validate_pagination(limit=limit, offset=offset)
    result = await session.execute(
        select(CapabilityPublicationRevision)
        .order_by(
            desc(CapabilityPublicationRevision.revision_number),
            desc(CapabilityPublicationRevision.id),
        )
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


def catalog_head_lock_statement() -> Select[tuple[CapabilityCatalogHead]]:
    return (
        select(CapabilityCatalogHead)
        .where(CapabilityCatalogHead.singleton_key == "global")
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def get_catalog_head_for_update(
    session: AsyncSession,
) -> CapabilityCatalogHead | None:
    result = await session.execute(catalog_head_lock_statement())
    return result.scalar_one_or_none()


def governance_request_lock_statement(
    actor_user_id: uuid.UUID,
    action_scope: str,
    idempotency_key_hash: str,
) -> Select[tuple[CapabilityGovernanceRequest]]:
    return (
        select(CapabilityGovernanceRequest)
        .where(
            CapabilityGovernanceRequest.actor_user_id == actor_user_id,
            CapabilityGovernanceRequest.action_scope == action_scope,
            CapabilityGovernanceRequest.idempotency_key_hash == idempotency_key_hash,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def get_governance_request(
    session: AsyncSession,
    actor_user_id: uuid.UUID,
    action_scope: str,
    idempotency_key_hash: str,
) -> CapabilityGovernanceRequest | None:
    result = await session.execute(
        select(CapabilityGovernanceRequest).where(
            CapabilityGovernanceRequest.actor_user_id == actor_user_id,
            CapabilityGovernanceRequest.action_scope == action_scope,
            CapabilityGovernanceRequest.idempotency_key_hash == idempotency_key_hash,
        )
    )
    return result.scalar_one_or_none()


async def get_governance_request_for_update(
    session: AsyncSession,
    actor_user_id: uuid.UUID,
    action_scope: str,
    idempotency_key_hash: str,
) -> CapabilityGovernanceRequest | None:
    result = await session.execute(
        governance_request_lock_statement(
            actor_user_id,
            action_scope,
            idempotency_key_hash,
        )
    )
    return result.scalar_one_or_none()


async def add_governance_record(
    session: AsyncSession,
    record: Base,
) -> Base:
    session.add(record)
    await session.flush()
    return record


__all__ = [
    "CAPABILITY_GOVERNANCE_IMPORT_LOCK_SCOPE",
    "MAX_GOVERNANCE_PAGE_SIZE",
    "acquire_governance_import_lock",
    "add_governance_record",
    "candidate_version_lock_statement",
    "catalog_head_lock_statement",
    "get_active_governance_membership",
    "get_catalog_head",
    "get_catalog_head_for_update",
    "get_catalog_snapshot",
    "get_candidate_version",
    "get_candidate_version_by_fingerprint",
    "get_governance_evidence",
    "get_governance_request",
    "get_governance_request_for_update",
    "get_latest_candidate_version",
    "get_latest_candidate_version_for_update",
    "get_latest_verification_decision_for_candidate_version",
    "get_open_verification_task",
    "get_open_verification_task_for_update",
    "get_publication_revision",
    "get_source_snapshot",
    "get_verification_decision",
    "get_verification_task",
    "get_verification_task_for_update",
    "governance_request_lock_statement",
    "list_candidate_evidence",
    "list_candidate_evidence_external_ids",
    "list_candidate_versions",
    "list_publication_revisions",
    "list_verification_tasks",
    "open_verification_task_lock_statement",
    "verification_task_lock_statement",
]
