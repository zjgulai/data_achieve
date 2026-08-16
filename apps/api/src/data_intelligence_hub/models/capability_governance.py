from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class _CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class CapabilityGovernanceMembership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "capability_governance_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_cap_gov_membership_user"),
        CheckConstraint(
            "NOT (can_review OR can_publish) OR can_read",
            name="permission_implication",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    can_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_publish: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CapabilityDiscoveryBatch(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "capability_discovery_batches"
    __table_args__ = (
        UniqueConstraint(
            "preview_fingerprint",
            name="uq_cap_discovery_batch_preview",
        ),
    )

    preview_fingerprint: Mapped[str] = mapped_column(String(71), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    fixture_set_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    imported_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class CapabilitySourceSnapshot(UUIDPrimaryKeyMixin, _CreatedAtMixin, Base):
    __tablename__ = "capability_source_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "fixture_id",
            "content_hash",
            name="uq_cap_source_fixture_content",
        ),
        CheckConstraint(
            "source_kind IN ('public_market', 'official_doc')",
            name="source_kind",
        ),
    )

    fixture_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    source_name: Mapped[str] = mapped_column(String(500), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_version: Mapped[str] = mapped_column(String(500), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    parser_id: Mapped[str] = mapped_column(String(100), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class CapabilityDiscoveryBatchSource(_CreatedAtMixin, Base):
    __tablename__ = "capability_discovery_batch_sources"
    __table_args__ = (
        UniqueConstraint(
            "batch_id",
            "ordinal",
            name="uq_cap_batch_source_ordinal",
        ),
        CheckConstraint("ordinal >= 0", name="ordinal"),
    )

    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("capability_discovery_batches.id"),
        primary_key=True,
    )
    source_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("capability_source_snapshots.id"),
        primary_key=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)


class GovernanceCapabilityEvidence(UUIDPrimaryKeyMixin, _CreatedAtMixin, Base):
    __tablename__ = "capability_evidence"
    __table_args__ = (
        UniqueConstraint("evidence_id", name="uq_cap_evidence_external_id"),
    )

    evidence_id: Mapped[str] = mapped_column(String(500), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class CapabilityCandidateAssertionVersion(UUIDPrimaryKeyMixin, _CreatedAtMixin, Base):
    __tablename__ = "capability_candidate_versions"
    __table_args__ = (
        UniqueConstraint(
            "candidate_key",
            "semantic_version",
            name="uq_cap_candidate_key_version",
        ),
        UniqueConstraint(
            "candidate_key",
            "candidate_fingerprint",
            name="uq_cap_candidate_key_fingerprint",
        ),
        UniqueConstraint(
            "candidate_key",
            "id",
            name="uq_cap_candidate_key_id",
        ),
        ForeignKeyConstraint(
            ["candidate_key", "predecessor_id"],
            ["capability_candidate_versions.candidate_key", "capability_candidate_versions.id"],
            name="fk_cap_candidate_predecessor_key",
        ),
        CheckConstraint("semantic_version >= 1", name="semantic_version"),
        CheckConstraint(
            "predecessor_id IS NOT NULL OR semantic_version = 1",
            name="predecessor_version",
        ),
    )

    candidate_key: Mapped[str] = mapped_column(String(71), nullable=False)
    semantic_version: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_fingerprint: Mapped[str] = mapped_column(String(71), nullable=False)
    predecessor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    proposed_implementation_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    candidate_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    first_seen_batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("capability_discovery_batches.id"),
        nullable=False,
    )


class CapabilityCandidateEvidenceLink(_CreatedAtMixin, Base):
    __tablename__ = "capability_candidate_evidence"

    candidate_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("capability_candidate_versions.id"),
        primary_key=True,
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("capability_evidence.id"),
        primary_key=True,
    )
    first_seen_batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("capability_discovery_batches.id"),
        nullable=False,
    )


class CapabilityVerificationTask(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "capability_verification_tasks"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "candidate_version_id",
            name="uq_cap_verification_task_candidate",
        ),
        ForeignKeyConstraint(
            ["decision_id"],
            ["capability_verification_decisions.id"],
            name="fk_cap_verification_task_decision",
            use_alter=True,
        ),
        CheckConstraint(
            "task_type IN ('initial_review', 'evidence_refresh', 'semantic_drift')",
            name="type",
        ),
        CheckConstraint("status IN ('open', 'resolved')", name="status"),
        CheckConstraint("task_version >= 1", name="version"),
        CheckConstraint(
            "(status = 'open' AND resolved_at IS NULL AND decision_id IS NULL) OR "
            "(status = 'resolved' AND resolved_at IS NOT NULL AND decision_id IS NOT NULL)",
            name="resolution",
        ),
        Index(
            "uq_cap_verification_task_open",
            "candidate_version_id",
            unique=True,
            postgresql_where=text("status = 'open'"),
            sqlite_where=text("status = 'open'"),
        ),
    )

    candidate_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("capability_candidate_versions.id"),
        nullable=False,
    )
    task_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    task_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))


class CapabilityVerificationDecision(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "capability_verification_decisions"
    __table_args__ = (
        UniqueConstraint(
            "verification_task_id",
            name="uq_cap_verification_decision_task",
        ),
        ForeignKeyConstraint(
            ["verification_task_id", "candidate_version_id"],
            [
                "capability_verification_tasks.id",
                "capability_verification_tasks.candidate_version_id",
            ],
            name="fk_cap_verification_decision_task_candidate",
        ),
        CheckConstraint(
            "action IN ('verify', 'reject', 'deprecate')",
            name="action",
        ),
        CheckConstraint(
            "verification_status IN ('verified', 'rejected')",
            name="status",
        ),
        CheckConstraint(
            "(action = 'reject' AND verification_status = 'rejected' "
            "AND canonical_bundle IS NULL) OR "
            "(action IN ('verify', 'deprecate') AND verification_status = 'verified' "
            "AND canonical_bundle IS NOT NULL)",
            name="bundle",
        ),
    )

    verification_task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    candidate_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(20), nullable=False)
    reviewer_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_bundle: Mapped[dict[str, Any] | None] = mapped_column(
        JSON(none_as_null=True)
    )


class CapabilityCatalogSnapshot(Base):
    __tablename__ = "capability_catalog_snapshots"

    catalog_snapshot_id: Mapped[str] = mapped_column(
        String(71),
        primary_key=True,
    )
    catalog_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class CapabilityPublicationRevision(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "capability_publication_revisions"
    __table_args__ = (
        UniqueConstraint(
            "revision_number",
            name="uq_cap_publication_revision_number",
        ),
        CheckConstraint("revision_number >= 1", name="number"),
        CheckConstraint(
            "restored_from_revision_id IS NULL OR restored_from_revision_id <> id",
            name="restore_not_self",
        ),
    )

    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("capability_publication_revisions.id"),
    )
    restored_from_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("capability_publication_revisions.id"),
    )
    catalog_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("capability_catalog_snapshots.catalog_snapshot_id"),
        nullable=False,
    )
    publisher_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    operations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)


class CapabilityCatalogHead(Base):
    __tablename__ = "capability_catalog_head"
    __table_args__ = (
        CheckConstraint("singleton_key = 'global'", name="singleton"),
        CheckConstraint("head_version >= 0", name="version"),
    )

    singleton_key: Mapped[str] = mapped_column(String(20), primary_key=True)
    current_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("capability_publication_revisions.id"),
    )
    head_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class CapabilityGovernanceRequest(UUIDPrimaryKeyMixin, _CreatedAtMixin, Base):
    __tablename__ = "capability_governance_requests"
    __table_args__ = (
        UniqueConstraint(
            "actor_user_id",
            "action_scope",
            "idempotency_key_hash",
            name="uq_cap_gov_request_idempotency",
        ),
        CheckConstraint(
            "response_status >= 200 AND response_status <= 299",
            name="response_status",
        ),
    )

    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    action_scope: Mapped[str] = mapped_column(String(500), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    outcome: Mapped[str] = mapped_column(String(50), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    result_reference: Mapped[str | None] = mapped_column(String(500))
