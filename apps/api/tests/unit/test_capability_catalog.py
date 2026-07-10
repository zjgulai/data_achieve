from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from data_intelligence_hub.schemas.capability_catalog import (
    AccessChannel,
    CapabilityAssertion,
    CapabilityCatalog,
    CapabilityEvidence,
    CapabilityImplementation,
    CapabilityOperation,
    CapabilityScoreProfile,
    CapabilityStatus,
    DeliveryForm,
    DeploymentMode,
    EvidenceType,
    PlatformId,
    ResourceType,
)


def build_catalog() -> CapabilityCatalog:
    observed_at = datetime(2026, 7, 10, tzinfo=UTC)
    implementation = CapabilityImplementation(
        schema_version="capability_implementation.v1",
        implementation_id="youtube.v3",
        provider_id="youtube.v3",
        platform=PlatformId.YOUTUBE,
        access_channel=AccessChannel.OFFICIAL_AUTHORIZED_API,
        delivery_form=DeliveryForm.SDK,
        deployment_mode=DeploymentMode.OFFICIAL_CLOUD,
        data_domains=["video_detail"],
        resource_groups=["video_detail"],
        official_docs=["https://developers.google.com/youtube/v3/docs"],
        sdk_selection=None,
        live_adapter_strategy="manual_review",
        auth_mode="API key",
        quota_hint={},
        cost_hint={},
        policy_flags=["no_login_state"],
        blocked_actions=["private_message"],
        stability="high",
        self_host_priority="p0",
        api_version="v3",
        required_credentials=["api_key"],
        supported_endpoints=["videos.list"],
        lifecycle_status="active",
    )
    evidence = CapabilityEvidence(
        schema_version="capability_evidence.v1",
        evidence_id="evidence:youtube-docs",
        evidence_type=EvidenceType.OFFICIAL_DOC,
        source_url="https://developers.google.com/youtube/v3/docs",
        source_version="v3",
        observed_at=observed_at,
        content_hash="a" * 64,
        hash_scope="source_reference_only",
        evidence_grade="L1-public-or-runtime",
        provider_call_attempted=False,
        credential_read_attempted=False,
        live_client_created=False,
        production_write_attempted=False,
    )
    assertion = CapabilityAssertion(
        schema_version="capability_assertion.v1",
        assertion_id="youtube.v3:content:resolve_detail:video_detail",
        implementation_id="youtube.v3",
        resource_type=ResourceType.CONTENT,
        operation=CapabilityOperation.RESOLVE_DETAIL,
        support_status=CapabilityStatus.CANDIDATE,
        source_resource_group="video_detail",
        region_scope=["manual_review"],
        purpose_scope=["commercial_review_required"],
        auth_scope=["api_key"],
        field_contract={"required": [], "optional": [], "status": "manual_review"},
        constraints=[],
        score_profile=CapabilityScoreProfile(
            coverage=3,
            freshness=3,
            history=2,
            reliability=5,
            schema_stability=5,
            cost_efficiency=3,
            maintainability=4,
            evidence_confidence=3,
        ),
        evidence_refs=["evidence:youtube-docs"],
        last_verified_at=observed_at,
    )
    return CapabilityCatalog(
        schema_version="capability_catalog.v1",
        evidence_level="L1-public-or-runtime",
        provider_call=False,
        production_write_allowed=False,
        generated_at=observed_at,
        implementations=[implementation],
        assertions=[assertion],
        evidence=[evidence],
    )


def test_capability_taxonomy_is_locked_to_prd_v2() -> None:
    assert {item.value for item in PlatformId} == {
        "youtube", "reddit", "x", "instagram", "threads", "tiktok", "linkedin"
    }
    assert {item.value for item in ResourceType} == {
        "content",
        "conversation",
        "creator",
        "topic",
        "metrics",
        "media_live",
        "commerce_ads",
        "relationship_graph",
    }
    assert {item.value for item in CapabilityOperation} == {
        "resolve_detail",
        "search_discover",
        "list_enumerate",
        "monitor_incremental",
        "backfill_history",
        "batch_parse",
        "export_download",
    }
    assert {item.value for item in CapabilityStatus} == {
        "unknown",
        "candidate",
        "verified",
        "partial",
        "blocked",
        "unsupported",
        "deprecated",
    }
    assert {item.value for item in AccessChannel} == {
        "official_authorized_api",
        "licensed_partner_data_service",
        "public_web_feed",
        "authorized_browser",
        "managed_opaque_collector",
        "authorized_export_import",
    }


def test_capability_catalog_accepts_valid_references() -> None:
    catalog = build_catalog()
    assert catalog.provider_call is False
    assert catalog.production_write_allowed is False
    assert catalog.assertions[0].evidence_refs == ["evidence:youtube-docs"]

    for field_name in ("provider_call", "production_write_allowed"):
        payload = catalog.model_dump(mode="json")
        payload[field_name] = True
        with pytest.raises(ValidationError, match=field_name):
            CapabilityCatalog.model_validate(payload)


def test_capability_catalog_rejects_unknown_implementation_reference() -> None:
    payload = build_catalog().model_dump(mode="json")
    payload["assertions"][0]["implementation_id"] = "missing.provider"
    with pytest.raises(ValidationError, match="unknown implementation_id"):
        CapabilityCatalog.model_validate(payload)


def test_capability_catalog_rejects_unknown_evidence_reference() -> None:
    payload = build_catalog().model_dump(mode="json")
    payload["assertions"][0]["evidence_refs"] = ["evidence:missing"]
    with pytest.raises(ValidationError, match="unknown evidence_ref"):
        CapabilityCatalog.model_validate(payload)


def test_capability_catalog_rejects_duplicate_assertion_id() -> None:
    duplicate_cases = (
        ("implementations", "duplicate implementation_id"),
        ("assertions", "duplicate assertion_id"),
        ("evidence", "duplicate evidence_id"),
    )
    for collection_name, error_message in duplicate_cases:
        payload = build_catalog().model_dump(mode="json")
        payload[collection_name].append(payload[collection_name][0])
        with pytest.raises(ValidationError, match=error_message):
            CapabilityCatalog.model_validate(payload)
