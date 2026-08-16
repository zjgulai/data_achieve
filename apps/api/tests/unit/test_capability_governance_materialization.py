from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityEvidence,
    CapabilityStatus,
)
from data_intelligence_hub.schemas.capability_governance import (
    CapabilityVerificationAction,
)
from data_intelligence_hub.services.capability_catalog import get_capability_catalog
from data_intelligence_hub.services.capability_governance.identity import (
    compute_logical_assertion_key,
)
from data_intelligence_hub.services.capability_governance.publication import (
    CatalogMaterializationError,
    RemoveCatalogAssertion,
    UpsertCatalogAssertion,
    VerifiedCapabilityBundle,
    materialize_capability_catalog,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import (
    compute_catalog_snapshot_id,
)

NOW = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)


def _bundle(
    assertion_index: int = 0,
    *,
    action: CapabilityVerificationAction = CapabilityVerificationAction.VERIFY,
) -> VerifiedCapabilityBundle:
    catalog = get_capability_catalog()
    source = catalog.assertions[assertion_index]
    implementation = next(
        item
        for item in catalog.implementations
        if item.implementation_id == source.implementation_id
    )
    support_status = (
        CapabilityStatus.DEPRECATED
        if action is CapabilityVerificationAction.DEPRECATE
        else CapabilityStatus.VERIFIED
    )
    assertion = source.model_copy(
        update={
            "support_status": support_status,
            "last_verified_at": NOW,
        }
    )
    evidence_by_id = {item.evidence_id: item for item in catalog.evidence}
    evidence = tuple(evidence_by_id[item] for item in assertion.evidence_refs)
    logical_key = compute_logical_assertion_key(
        implementation_id=assertion.implementation_id,
        resource_type=assertion.resource_type,
        operation=assertion.operation,
        source_resource_group=assertion.source_resource_group,
    )
    return VerifiedCapabilityBundle(
        verification_decision_id=uuid.uuid4(),
        action=action,
        candidate_key="sha256:" + "c" * 64,
        candidate_fingerprint="sha256:" + "d" * 64,
        logical_assertion_key=logical_key,
        implementation=implementation,
        assertion=assertion,
        evidence=evidence,
    )


def test_packaged_catalog_has_unique_four_field_logical_assertion_keys() -> None:
    catalog = get_capability_catalog()
    keys = {
        compute_logical_assertion_key(
            implementation_id=item.implementation_id,
            resource_type=item.resource_type,
            operation=item.operation,
            source_resource_group=item.source_resource_group,
        )
        for item in catalog.assertions
    }
    assert len(keys) == len(catalog.assertions) == 35


def test_empty_materialization_preserves_packaged_catalog_and_snapshot_id() -> None:
    catalog = get_capability_catalog()
    materialized = materialize_capability_catalog(catalog, [], generated_at=catalog.generated_at)

    assert materialized == catalog
    assert compute_catalog_snapshot_id(materialized) == compute_catalog_snapshot_id(catalog)
    assert materialized is not catalog


def test_verified_upsert_replaces_one_logical_assertion_and_changes_snapshot() -> None:
    catalog = get_capability_catalog()
    bundle = _bundle()
    materialized = materialize_capability_catalog(
        catalog,
        [UpsertCatalogAssertion(bundle=bundle)],
        generated_at=NOW,
    )

    target = next(
        item
        for item in materialized.assertions
        if item.assertion_id == bundle.assertion.assertion_id
    )
    assert target.support_status is CapabilityStatus.VERIFIED
    assert len(materialized.assertions) == len(catalog.assertions)
    assert compute_catalog_snapshot_id(materialized) != compute_catalog_snapshot_id(catalog)


def test_same_effective_content_has_same_snapshot_id_despite_event_time() -> None:
    catalog = get_capability_catalog()
    operation = UpsertCatalogAssertion(bundle=_bundle())
    first = materialize_capability_catalog(catalog, [operation], generated_at=NOW)
    second = materialize_capability_catalog(
        catalog,
        [operation],
        generated_at=datetime(2026, 7, 14, 13, 0, tzinfo=UTC),
    )

    assert first.generated_at != second.generated_at
    assert compute_catalog_snapshot_id(first) == compute_catalog_snapshot_id(second)


def test_remove_requires_deprecate_decision_and_removes_only_target_assertion() -> None:
    catalog = get_capability_catalog()
    bundle = _bundle(action=CapabilityVerificationAction.DEPRECATE)
    materialized = materialize_capability_catalog(
        catalog,
        [RemoveCatalogAssertion(bundle=bundle)],
        generated_at=NOW,
    )

    assert len(materialized.assertions) == len(catalog.assertions) - 1
    assert bundle.assertion.assertion_id not in {
        item.assertion_id for item in materialized.assertions
    }

    with pytest.raises(CatalogMaterializationError, match="remove_requires_deprecate"):
        materialize_capability_catalog(
            catalog,
            [RemoveCatalogAssertion(bundle=_bundle())],
            generated_at=NOW,
        )


def test_duplicate_operation_for_one_logical_key_fails_closed() -> None:
    catalog = get_capability_catalog()
    bundle = _bundle()

    with pytest.raises(CatalogMaterializationError, match="duplicate_logical_operation"):
        materialize_capability_catalog(
            catalog,
            [
                UpsertCatalogAssertion(bundle=bundle),
                UpsertCatalogAssertion(bundle=bundle),
            ],
            generated_at=NOW,
        )


def test_bundle_logical_key_and_references_are_validated() -> None:
    catalog = get_capability_catalog()
    bundle = _bundle()
    mismatched_key = replace(
        bundle,
        logical_assertion_key="sha256:" + "e" * 64,
    )
    with pytest.raises(CatalogMaterializationError, match="logical_assertion_key_mismatch"):
        materialize_capability_catalog(
            catalog,
            [UpsertCatalogAssertion(bundle=mismatched_key)],
            generated_at=NOW,
        )

    missing_evidence = replace(bundle, evidence=())
    with pytest.raises(CatalogMaterializationError, match="bundle_evidence_mismatch"):
        materialize_capability_catalog(
            catalog,
            [UpsertCatalogAssertion(bundle=missing_evidence)],
            generated_at=NOW,
        )


def test_existing_implementation_or_evidence_id_with_different_content_fails() -> None:
    catalog = get_capability_catalog()
    bundle = _bundle()
    conflicting_implementation = bundle.implementation.model_copy(
        update={"provider_id": "different-provider"}
    )
    conflict = replace(bundle, implementation=conflicting_implementation)
    with pytest.raises(CatalogMaterializationError, match="implementation_id_content_conflict"):
        materialize_capability_catalog(
            catalog,
            [UpsertCatalogAssertion(bundle=conflict)],
            generated_at=NOW,
        )

    evidence = bundle.evidence[0]
    conflicting_evidence = evidence.model_copy(update={"source_version": "different"})
    evidence_conflict = replace(
        bundle,
        evidence=(conflicting_evidence, *bundle.evidence[1:]),
    )
    with pytest.raises(CatalogMaterializationError, match="evidence_id_content_conflict"):
        materialize_capability_catalog(
            catalog,
            [UpsertCatalogAssertion(bundle=evidence_conflict)],
            generated_at=NOW,
        )


def test_materialization_prunes_unreferenced_evidence_after_an_operation() -> None:
    catalog = get_capability_catalog()
    extra = CapabilityEvidence(
        **{
            **catalog.evidence[0].model_dump(mode="python"),
            "evidence_id": "evidence:unreferenced",
            "content_hash": "f" * 64,
        }
    )
    with_orphan = catalog.model_copy(update={"evidence": [*catalog.evidence, extra]})
    materialized = materialize_capability_catalog(
        with_orphan,
        [UpsertCatalogAssertion(bundle=_bundle())],
        generated_at=NOW,
    )

    assert "evidence:unreferenced" not in {
        item.evidence_id for item in materialized.evidence
    }
