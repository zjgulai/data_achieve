from __future__ import annotations

import uuid

from data_intelligence_hub.schemas.capability_catalog import (
    AccessChannel,
    CapabilityOperation,
    PlatformId,
    ResourceType,
)
from data_intelligence_hub.schemas.capability_discovery import (
    CapabilityCandidateAssertionPreview,
    CapabilityDiscoveryPreviewRequest,
)
from data_intelligence_hub.services.capability_discovery.preview import (
    build_capability_discovery_preview,
)
from data_intelligence_hub.services.capability_governance.identity import (
    compute_candidate_key,
    compute_governance_request_hash,
    compute_logical_assertion_key,
    hash_governance_idempotency_key,
)

FIXTURE_IDS = [
    "tikhub-youtube-market-v1",
    "apify-reddit-market-v1",
    "youtube-data-api-doc-v1",
    "reddit-data-api-doc-v1",
]


def _candidate() -> CapabilityCandidateAssertionPreview:
    preview = build_capability_discovery_preview(
        CapabilityDiscoveryPreviewRequest(
            schema_version="capability_discovery_preview_request.v1",
            preview_mode="fixture_replay",
            fixture_ids=FIXTURE_IDS,
        )
    )
    return preview.candidate_assertions[0]


def test_candidate_key_uses_logical_identity_not_semantic_or_evidence_fields() -> None:
    candidate = _candidate()
    original = compute_candidate_key(candidate)
    changed_semantics = candidate.model_copy(
        update={
            "claimed_field_contract": {"changed": True},
            "region_scope": ["different-region"],
            "evidence_refs": ["different-evidence"],
            "source_claim_refs": ["different-claim"],
            "candidate_fingerprint": "sha256:" + "f" * 64,
        }
    )

    assert compute_candidate_key(changed_semantics) == original
    assert original.startswith("sha256:")
    assert len(original) == 71


def test_candidate_key_changes_when_logical_identity_changes() -> None:
    candidate = _candidate()
    original = compute_candidate_key(candidate)

    assert (
        compute_candidate_key(
            candidate.model_copy(update={"operation": CapabilityOperation.BATCH_PARSE})
        )
        != original
    )
    assert (
        compute_candidate_key(
            candidate.model_copy(update={"access_channel": AccessChannel.PUBLIC_WEB_FEED})
        )
        != original
    )


def test_logical_assertion_key_is_stable_and_field_specific() -> None:
    key = compute_logical_assertion_key(
        implementation_id="implementation:youtube:v1",
        resource_type=ResourceType.CONTENT,
        operation=CapabilityOperation.RESOLVE_DETAIL,
        source_resource_group="video_detail",
    )
    same = compute_logical_assertion_key(
        implementation_id="implementation:youtube:v1",
        resource_type=ResourceType.CONTENT,
        operation=CapabilityOperation.RESOLVE_DETAIL,
        source_resource_group="video_detail",
    )
    changed = compute_logical_assertion_key(
        implementation_id="implementation:youtube:v1",
        resource_type=ResourceType.CONTENT,
        operation=CapabilityOperation.SEARCH_DISCOVER,
        source_resource_group="video_detail",
    )
    changed_group = compute_logical_assertion_key(
        implementation_id="implementation:youtube:v1",
        resource_type=ResourceType.CONTENT,
        operation=CapabilityOperation.RESOLVE_DETAIL,
        source_resource_group="content_search",
    )

    assert key == same
    assert key != changed
    assert key != changed_group
    assert len(key) == 71


def test_request_hash_is_canonical_and_action_scoped() -> None:
    first = compute_governance_request_hash(
        action_scope="capability_governance.import",
        payload={"b": [2, 1], "a": {"z": True, "y": None}},
    )
    reordered = compute_governance_request_hash(
        action_scope="capability_governance.import",
        payload={"a": {"y": None, "z": True}, "b": [2, 1]},
    )
    changed_scope = compute_governance_request_hash(
        action_scope="capability_governance.publish",
        payload={"a": {"y": None, "z": True}, "b": [2, 1]},
    )

    assert first == reordered
    assert first != changed_scope


def test_idempotency_hash_never_contains_raw_key_or_actor_identity() -> None:
    raw_key = "governance-private-key-0001"
    actor_id = uuid.uuid4()
    hashed = hash_governance_idempotency_key(raw_key)

    assert hashed.startswith("sha256:")
    assert raw_key not in hashed
    assert str(actor_id) not in hashed


def test_candidate_key_accepts_all_catalog_identity_enums() -> None:
    candidate = _candidate().model_copy(
        update={
            "platform": PlatformId.REDDIT,
            "access_channel": AccessChannel.OFFICIAL_AUTHORIZED_API,
            "resource_type": ResourceType.CONVERSATION,
            "operation": CapabilityOperation.LIST_ENUMERATE,
        }
    )
    assert compute_candidate_key(candidate).startswith("sha256:")
