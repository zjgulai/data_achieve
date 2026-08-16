from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from data_intelligence_hub.schemas.capability_catalog import CapabilityStatus
from data_intelligence_hub.schemas.capability_governance import (
    CapabilityGovernanceCanonicalAssertionInput,
    CapabilityGovernanceImportRequest,
    CapabilityGovernancePermissionSet,
    CapabilityGovernancePublicationCreateRequest,
    CapabilityGovernancePublicationRollbackRequest,
    CapabilityGovernanceReviewRequest,
    CapabilityGovernanceWriteAttempt,
    RemoveAssertionOperation,
    UpsertVerifiedAssertionOperation,
    normalize_governance_idempotency_key,
)
from data_intelligence_hub.services.capability_catalog import get_capability_catalog

FINGERPRINT = "sha256:" + "a" * 64
LOGICAL_KEY = "sha256:" + "b" * 64


def _implementation_payload() -> dict[str, object]:
    implementation = get_capability_catalog().implementations[0]
    return implementation.model_dump(mode="python")


def _assertion_input(
    support_status: CapabilityStatus = CapabilityStatus.VERIFIED,
) -> CapabilityGovernanceCanonicalAssertionInput:
    assertion = get_capability_catalog().assertions[0]
    return CapabilityGovernanceCanonicalAssertionInput(
        assertion_id=assertion.assertion_id,
        implementation_id=assertion.implementation_id,
        resource_type=assertion.resource_type,
        operation=assertion.operation,
        support_status=support_status,
        source_resource_group=assertion.source_resource_group,
        region_scope=assertion.region_scope,
        purpose_scope=assertion.purpose_scope,
        auth_scope=assertion.auth_scope,
        field_contract=assertion.field_contract,
        constraints=assertion.constraints,
        score_profile=assertion.score_profile,
        evidence_refs=assertion.evidence_refs,
    )


def test_import_request_is_strict_bounded_unique_and_fingerprint_checked() -> None:
    request = CapabilityGovernanceImportRequest(
        schema_version="capability_governance_import_request.v1",
        fixture_ids=["tikhub-youtube-market-v1"],
        expected_preview_fingerprint=FINGERPRINT,
    )
    assert request.fixture_ids == ["tikhub-youtube-market-v1"]

    invalid_payloads = [
        {**request.model_dump(mode="json"), "fixture_ids": []},
        {**request.model_dump(mode="json"), "fixture_ids": ["same", "same"]},
        {
            **request.model_dump(mode="json"),
            "fixture_ids": ["one", "two", "three", "four", "five"],
        },
        {**request.model_dump(mode="json"), "fixture_ids": ["../secret"]},
        {**request.model_dump(mode="json"), "expected_preview_fingerprint": "sha256:ABC"},
        {**request.model_dump(mode="json"), "candidate_body": {}},
    ]
    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            CapabilityGovernanceImportRequest.model_validate(payload)


def test_permission_set_keeps_read_review_and_publish_explicit() -> None:
    permissions = CapabilityGovernancePermissionSet(
        can_read=True,
        can_review=True,
        can_publish=False,
    )
    assert permissions.can_review is True
    assert permissions.can_publish is False

    for invalid in (
        {"can_read": False, "can_review": True, "can_publish": False},
        {"can_read": False, "can_review": False, "can_publish": True},
        {"can_read": True, "can_review": False, "can_publish": False, "role": "owner"},
    ):
        with pytest.raises(ValidationError):
            CapabilityGovernancePermissionSet.model_validate(invalid)


def test_review_request_requires_action_specific_canonical_bundle() -> None:
    implementation = _implementation_payload()
    verified = CapabilityGovernanceReviewRequest(
        schema_version="capability_governance_review_request.v1",
        expected_task_version=1,
        action="verify",
        reason="  Evidence and contract reviewed.  ",
        canonical_implementation=implementation,
        canonical_assertion=_assertion_input(),
    )
    assert verified.reason == "Evidence and contract reviewed."

    rejected = CapabilityGovernanceReviewRequest(
        schema_version="capability_governance_review_request.v1",
        expected_task_version=2,
        action="reject",
        reason="Source claim is not supported by the evidence.",
    )
    assert rejected.canonical_assertion is None

    deprecated = CapabilityGovernanceReviewRequest(
        schema_version="capability_governance_review_request.v1",
        expected_task_version=3,
        action="deprecate",
        reason="The documented endpoint is retired.",
        canonical_implementation=implementation,
        canonical_assertion=_assertion_input(CapabilityStatus.DEPRECATED),
    )
    assert deprecated.canonical_assertion is not None
    assert deprecated.canonical_assertion.support_status is CapabilityStatus.DEPRECATED

    invalid_payloads = [
        {**verified.model_dump(mode="python"), "canonical_assertion": None},
        {
            **verified.model_dump(mode="python"),
            "canonical_assertion": _assertion_input(CapabilityStatus.DEPRECATED),
        },
        {
            **rejected.model_dump(mode="python"),
            "canonical_implementation": implementation,
        },
        {
            **deprecated.model_dump(mode="python"),
            "canonical_assertion": _assertion_input(CapabilityStatus.VERIFIED),
        },
        {**verified.model_dump(mode="python"), "expected_task_version": 0},
    ]
    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            CapabilityGovernanceReviewRequest.model_validate(payload)


def test_canonical_assertion_input_excludes_server_owned_review_time() -> None:
    assertion = _assertion_input()
    assert "last_verified_at" not in CapabilityGovernanceCanonicalAssertionInput.model_fields

    payload = assertion.model_dump(mode="python")
    payload["last_verified_at"] = "2026-07-14T00:00:00Z"
    with pytest.raises(ValidationError):
        CapabilityGovernanceCanonicalAssertionInput.model_validate(payload)


def test_publication_request_uses_bounded_typed_operations() -> None:
    upsert_id = uuid.uuid4()
    remove_id = uuid.uuid4()
    request = CapabilityGovernancePublicationCreateRequest(
        schema_version="capability_governance_publication_request.v1",
        expected_parent_revision_id=None,
        reason="Publish the reviewed capability facts.",
        operations=[
            UpsertVerifiedAssertionOperation(
                operation="upsert_verified_assertion",
                verification_decision_id=upsert_id,
            ),
            RemoveAssertionOperation(
                operation="remove_assertion",
                verification_decision_id=remove_id,
                logical_assertion_key=LOGICAL_KEY,
            ),
        ],
    )
    assert request.operations[0].operation == "upsert_verified_assertion"
    assert request.operations[1].operation == "remove_assertion"

    duplicate = request.model_dump(mode="python")
    duplicate["operations"] = [
        {
            "operation": "upsert_verified_assertion",
            "verification_decision_id": upsert_id,
        },
        {
            "operation": "upsert_verified_assertion",
            "verification_decision_id": upsert_id,
        },
    ]
    with pytest.raises(ValidationError, match="duplicate_verification_decision"):
        CapabilityGovernancePublicationCreateRequest.model_validate(duplicate)

    with pytest.raises(ValidationError):
        CapabilityGovernancePublicationCreateRequest(
            schema_version="capability_governance_publication_request.v1",
            expected_parent_revision_id=None,
            reason="No operations.",
            operations=[],
        )


def test_rollback_requires_distinct_current_and_target_revision() -> None:
    current = uuid.uuid4()
    request = CapabilityGovernancePublicationRollbackRequest(
        schema_version="capability_governance_rollback_request.v1",
        expected_current_revision_id=current,
        target_revision_id=uuid.uuid4(),
        reason="Restore the earlier verified Catalog snapshot.",
    )
    assert request.target_revision_id != request.expected_current_revision_id

    with pytest.raises(ValidationError, match="rollback_target_must_differ"):
        CapabilityGovernancePublicationRollbackRequest(
            schema_version="capability_governance_rollback_request.v1",
            expected_current_revision_id=current,
            target_revision_id=current,
            reason="Invalid self rollback.",
        )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  governance-key-0001  ", "governance-key-0001"),
        ("x" * 12, "x" * 12),
        ("x" * 200, "x" * 200),
    ],
)
def test_governance_idempotency_key_is_trimmed_and_bounded(
    raw: str,
    expected: str,
) -> None:
    assert normalize_governance_idempotency_key(raw) == expected


@pytest.mark.parametrize("raw", ["", " " * 20, "x" * 11, "x" * 201])
def test_governance_idempotency_key_rejects_invalid_values(raw: str) -> None:
    with pytest.raises(ValueError, match="idempotency_key_invalid"):
        normalize_governance_idempotency_key(raw)


def test_write_attempt_flags_distinguish_domain_noop_and_idempotent_replay() -> None:
    changed = CapabilityGovernanceWriteAttempt(
        database_write=True,
        domain_changed=True,
        idempotent_replay=False,
    )
    semantic_noop = CapabilityGovernanceWriteAttempt(
        database_write=True,
        domain_changed=False,
        idempotent_replay=False,
    )
    replay = CapabilityGovernanceWriteAttempt(
        database_write=False,
        domain_changed=False,
        idempotent_replay=True,
    )

    assert changed.provider_call is False
    assert semantic_noop.domain_changed is False
    assert replay.database_write is False

    for invalid in (
        {"database_write": False, "domain_changed": True, "idempotent_replay": False},
        {"database_write": True, "domain_changed": False, "idempotent_replay": True},
        {"database_write": False, "domain_changed": False, "idempotent_replay": False},
    ):
        with pytest.raises(ValidationError, match="write_attempt_flags_invalid"):
            CapabilityGovernanceWriteAttempt.model_validate(invalid)
