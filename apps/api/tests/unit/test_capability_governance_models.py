from __future__ import annotations

from typing import cast

from sqlalchemy import JSON, CheckConstraint, Constraint, Index, Table, UniqueConstraint

from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.capability_governance import (
    CapabilityCandidateAssertionVersion,
    CapabilityCandidateEvidenceLink,
    CapabilityCatalogHead,
    CapabilityCatalogSnapshot,
    CapabilityDiscoveryBatch,
    CapabilityDiscoveryBatchSource,
    CapabilityGovernanceMembership,
    CapabilityGovernanceRequest,
    CapabilityPublicationRevision,
    CapabilitySourceSnapshot,
    CapabilityVerificationDecision,
    CapabilityVerificationTask,
    GovernanceCapabilityEvidence,
)

MODEL_TABLES: dict[type[Base], str] = {
    CapabilityGovernanceMembership: "capability_governance_memberships",
    CapabilityDiscoveryBatch: "capability_discovery_batches",
    CapabilitySourceSnapshot: "capability_source_snapshots",
    CapabilityDiscoveryBatchSource: "capability_discovery_batch_sources",
    GovernanceCapabilityEvidence: "capability_evidence",
    CapabilityCandidateAssertionVersion: "capability_candidate_versions",
    CapabilityCandidateEvidenceLink: "capability_candidate_evidence",
    CapabilityVerificationTask: "capability_verification_tasks",
    CapabilityVerificationDecision: "capability_verification_decisions",
    CapabilityCatalogSnapshot: "capability_catalog_snapshots",
    CapabilityPublicationRevision: "capability_publication_revisions",
    CapabilityCatalogHead: "capability_catalog_head",
    CapabilityGovernanceRequest: "capability_governance_requests",
}


def _table(model: type[Base]) -> Table:
    return cast(Table, model.__table__)


def _constraint_names(
    model: type[Base],
    constraint_type: type[Constraint],
) -> set[str]:
    return {
        cast(str, item.name)
        for item in _table(model).constraints
        if isinstance(item, constraint_type) and item.name is not None
    }


def test_governance_model_set_is_global_and_bounded() -> None:
    assert {_table(model).name for model in MODEL_TABLES} == set(MODEL_TABLES.values())
    for model in MODEL_TABLES:
        assert "workspace_id" not in _table(model).c
        assert "project_id" not in _table(model).c


def test_membership_has_explicit_separate_permissions_and_no_role_column() -> None:
    columns = CapabilityGovernanceMembership.__table__.c
    assert {"user_id", "can_read", "can_review", "can_publish", "is_active"} <= set(
        columns.keys()
    )
    assert "role" not in columns
    assert "uq_cap_gov_membership_user" in _constraint_names(
        CapabilityGovernanceMembership,
        UniqueConstraint,
    )


def test_candidate_versions_and_evidence_links_are_immutable_shapes() -> None:
    candidate_columns = CapabilityCandidateAssertionVersion.__table__.c
    assert {
        "candidate_key",
        "semantic_version",
        "candidate_fingerprint",
        "predecessor_id",
        "proposed_implementation_payload",
        "candidate_payload",
        "first_seen_batch_id",
    } <= set(candidate_columns.keys())
    assert "updated_at" not in candidate_columns
    assert {
        "uq_cap_candidate_key_version",
        "uq_cap_candidate_key_fingerprint",
        "uq_cap_candidate_key_id",
    } <= _constraint_names(CapabilityCandidateAssertionVersion, UniqueConstraint)
    assert "updated_at" not in CapabilityCandidateEvidenceLink.__table__.c


def test_verification_task_has_partial_open_uniqueness_and_checked_state() -> None:
    indexes = {
        str(item.name): item
        for item in _table(CapabilityVerificationTask).indexes
        if item.name is not None
    }
    assert "uq_cap_verification_task_open" in indexes
    open_index = indexes["uq_cap_verification_task_open"]
    assert isinstance(open_index, Index)
    assert open_index.unique is True
    assert open_index.dialect_options["postgresql"]["where"] is not None
    assert {
        "ck_capability_verification_tasks_type",
        "ck_capability_verification_tasks_status",
        "ck_capability_verification_tasks_version",
        "ck_capability_verification_tasks_resolution",
    } <= _constraint_names(CapabilityVerificationTask, CheckConstraint)


def test_decision_revision_snapshot_and_request_are_append_only_shapes() -> None:
    for model in (
        CapabilityVerificationDecision,
        CapabilityCatalogSnapshot,
        CapabilityPublicationRevision,
        CapabilityGovernanceRequest,
    ):
        assert "updated_at" not in _table(model).c

    assert "uq_cap_verification_decision_task" in _constraint_names(
        CapabilityVerificationDecision,
        UniqueConstraint,
    )
    bundle_type = cast(
        JSON,
        CapabilityVerificationDecision.__table__.c.canonical_bundle.type,
    )
    assert bundle_type.none_as_null is True
    assert "uq_cap_publication_revision_number" in _constraint_names(
        CapabilityPublicationRevision,
        UniqueConstraint,
    )
    assert "uq_cap_gov_request_idempotency" in _constraint_names(
        CapabilityGovernanceRequest,
        UniqueConstraint,
    )


def test_catalog_head_is_one_mutable_global_pointer() -> None:
    columns = CapabilityCatalogHead.__table__.c
    assert set(columns.keys()) == {
        "singleton_key",
        "current_revision_id",
        "head_version",
        "updated_at",
    }
    assert columns.singleton_key.primary_key is True
    assert {
        "ck_capability_catalog_head_singleton",
        "ck_capability_catalog_head_version",
    } <= _constraint_names(CapabilityCatalogHead, CheckConstraint)
