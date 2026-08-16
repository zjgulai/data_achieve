from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from data_intelligence_hub.schemas.capability_catalog import (
    AccessChannel,
    CapabilityEvidence,
    CapabilityOperation,
    DeliveryForm,
    DeploymentMode,
    EvidenceType,
    PlatformId,
    ResourceType,
)
from data_intelligence_hub.schemas.capability_discovery import (
    CapabilityCandidateAssertionPreview,
    CapabilityDiscoveryDiagnostic,
    CapabilityDiscoveryFixtureManifest,
    CapabilityDiscoveryFixtureManifestEntry,
    CapabilityDiscoveryParserId,
    CapabilityDiscoveryParserOutput,
    CapabilityDiscoveryPreviewRequest,
    CapabilityDiscoveryPreviewResponse,
    CapabilityDiscoverySummary,
    CapabilityProposedImplementationPreview,
    CapabilitySourceSnapshotFixture,
    CapabilitySourceSnapshotPreview,
)
from data_intelligence_hub.services.exceptions import (
    CapabilityDiscoveryContractInvalidError,
    CapabilityDiscoveryFixtureInvalidError,
    CapabilityDiscoveryFixtureUnknownError,
)

OBSERVED_AT = datetime(2026, 7, 14, 8, 0, tzinfo=UTC)
CONTENT_HASH = "a" * 64
FINGERPRINT = f"sha256:{'b' * 64}"


def build_source_fixture() -> CapabilitySourceSnapshotFixture:
    return CapabilitySourceSnapshotFixture(
        schema_version="capability_source_snapshot_fixture.v1",
        fixture_id="tikhub-youtube-market-v1",
        source_kind="public_market",
        source_name="TikHub public market",
        source_url="https://www.tikhub.io/api-market",
        source_version="public-page-2026-07-14",
        observed_at=OBSERVED_AT,
        parser_id=CapabilityDiscoveryParserId.TIKHUB_PUBLIC_MARKET_V1,
        payload={
            "provider_id": "tikhub.youtube.v1",
            "claims": [{"claim_ref": "claim:video-detail"}],
        },
    )


def build_source_preview() -> CapabilitySourceSnapshotPreview:
    source = build_source_fixture()
    return CapabilitySourceSnapshotPreview(
        schema_version="capability_source_snapshot_preview.v1",
        fixture_id=source.fixture_id,
        source_kind=source.source_kind,
        source_name=source.source_name,
        source_url=source.source_url,
        source_version=source.source_version,
        observed_at=source.observed_at,
        parser_id=source.parser_id,
        content_hash=CONTENT_HASH,
    )


def build_evidence() -> CapabilityEvidence:
    return CapabilityEvidence(
        schema_version="capability_evidence.v1",
        evidence_id="evidence:tikhub-youtube-market-v1",
        evidence_type=EvidenceType.PUBLIC_MARKET,
        source_url="https://www.tikhub.io/api-market",
        source_version="public-page-2026-07-14",
        observed_at=OBSERVED_AT,
        content_hash=CONTENT_HASH,
        hash_scope="retrieved_content",
        evidence_grade="L2-fixture-or-dry-run",
        provider_call_attempted=False,
        credential_read_attempted=False,
        live_client_created=False,
        production_write_attempted=False,
    )


def build_proposed_implementation() -> CapabilityProposedImplementationPreview:
    return CapabilityProposedImplementationPreview(
        schema_version="capability_proposed_implementation_preview.v1",
        proposed_implementation_id="proposed:tikhub.youtube.v1",
        provider_id="tikhub.youtube.v1",
        platform=PlatformId.YOUTUBE,
        access_channel=AccessChannel.MANAGED_OPAQUE_COLLECTOR,
        delivery_form=DeliveryForm.ENDPOINT,
        deployment_mode=DeploymentMode.MANAGED_SAAS,
        source_label="TikHub public market",
        claimed_auth_mode="api_key",
        claimed_required_credentials=["api_key"],
        claimed_limitations=["public_market_claim_unverified"],
        evidence_refs=["evidence:tikhub-youtube-market-v1"],
    )


def build_candidate() -> CapabilityCandidateAssertionPreview:
    return CapabilityCandidateAssertionPreview(
        schema_version="capability_candidate_assertion_preview.v1",
        candidate_id="candidate:tikhub.youtube.v1:content:resolve_detail",
        proposed_implementation_id="proposed:tikhub.youtube.v1",
        platform=PlatformId.YOUTUBE,
        access_channel=AccessChannel.MANAGED_OPAQUE_COLLECTOR,
        resource_type=ResourceType.CONTENT,
        operation=CapabilityOperation.RESOLVE_DETAIL,
        support_status="candidate",
        verification_status="unverified",
        executable=False,
        publishable=False,
        claimed_field_contract={"required": ["video_id"]},
        claimed_constraints=[],
        region_scope=["source_claim_only"],
        purpose_scope=["manual_review_required"],
        auth_scope=["api_key_claimed"],
        source_claim_refs=["claim:video-detail"],
        evidence_refs=["evidence:tikhub-youtube-market-v1"],
        parser_id=CapabilityDiscoveryParserId.TIKHUB_PUBLIC_MARKET_V1,
        candidate_fingerprint=FINGERPRINT,
    )


def build_response() -> CapabilityDiscoveryPreviewResponse:
    return CapabilityDiscoveryPreviewResponse(
        schema_version="capability_discovery_preview.v1",
        evidence_grade="L2-fixture-or-dry-run",
        preview_mode="fixture_replay",
        preview_fingerprint=FINGERPRINT,
        generated_from_observed_at=OBSERVED_AT,
        source_snapshots=[build_source_preview()],
        proposed_implementations=[build_proposed_implementation()],
        candidate_assertions=[build_candidate()],
        evidence=[build_evidence()],
        diagnostics=[
            CapabilityDiscoveryDiagnostic(
                schema_version="capability_discovery_diagnostic.v1",
                fixture_id="tikhub-youtube-market-v1",
                severity="warning",
                code="source_claim_unverified",
                message="Source claim requires verification.",
                source_claim_ref="claim:video-detail",
            )
        ],
        summary=CapabilityDiscoverySummary(
            source_count=1,
            market_source_count=1,
            official_doc_source_count=0,
            proposed_implementation_count=1,
            candidate_assertion_count=1,
            evidence_count=1,
            warning_count=1,
            error_count=0,
        ),
    )


def test_preview_request_is_strict_bounded_and_unique() -> None:
    request = CapabilityDiscoveryPreviewRequest(
        schema_version="capability_discovery_preview_request.v1",
        preview_mode="fixture_replay",
        fixture_ids=["tikhub-youtube-market-v1"],
    )
    assert request.fixture_ids == ["tikhub-youtube-market-v1"]

    invalid_payloads = [
        {**request.model_dump(mode="json"), "fixture_ids": []},
        {
            **request.model_dump(mode="json"),
            "fixture_ids": ["same", "same"],
        },
        {
            **request.model_dump(mode="json"),
            "fixture_ids": ["one", "two", "three", "four", "five"],
        },
        {**request.model_dump(mode="json"), "raw_url": "https://example.com"},
    ]
    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            CapabilityDiscoveryPreviewRequest.model_validate(payload)


def test_source_fixture_requires_https_timezone_and_known_parser() -> None:
    source = build_source_fixture()
    assert source.observed_at.tzinfo is not None
    assert source.source_url.startswith("https://")

    invalid_cases = [
        {**source.model_dump(mode="json"), "source_url": "http://example.com"},
        {**source.model_dump(mode="json"), "observed_at": "2026-07-14T08:00:00"},
        {**source.model_dump(mode="json"), "source_version": ""},
        {**source.model_dump(mode="json"), "parser_id": "unknown.v1"},
        {**source.model_dump(mode="json"), "unexpected": True},
    ]
    for payload in invalid_cases:
        with pytest.raises(ValidationError):
            CapabilitySourceSnapshotFixture.model_validate(payload)


def test_manifest_requires_four_unique_entries_and_lowercase_hashes() -> None:
    parser_ids = list(CapabilityDiscoveryParserId)
    entries = [
        CapabilityDiscoveryFixtureManifestEntry(
            fixture_id=f"fixture-{index}",
            relative_path=f"fixture-{index}.json",
            parser_id=parser_id,
            expected_sha256=chr(ord("a") + index) * 64,
        )
        for index, parser_id in enumerate(parser_ids)
    ]
    manifest = CapabilityDiscoveryFixtureManifest(
        schema_version="capability_discovery_fixture_manifest.v1",
        fixtures=entries,
    )
    assert len(manifest.fixtures) == 4

    duplicate = manifest.model_dump(mode="json")
    duplicate["fixtures"][1]["fixture_id"] = duplicate["fixtures"][0]["fixture_id"]
    with pytest.raises(ValidationError, match="duplicate_fixture_id"):
        CapabilityDiscoveryFixtureManifest.model_validate(duplicate)

    invalid_hash = manifest.model_dump(mode="json")
    invalid_hash["fixtures"][0]["expected_sha256"] = "A" * 64
    with pytest.raises(ValidationError):
        CapabilityDiscoveryFixtureManifest.model_validate(invalid_hash)

    with pytest.raises(ValidationError):
        CapabilityDiscoveryFixtureManifest(
            schema_version="capability_discovery_fixture_manifest.v1",
            fixtures=entries[:3],
        )


def test_candidate_fixed_values_and_fingerprint_cannot_be_overridden() -> None:
    candidate = build_candidate()
    assert candidate.support_status == "candidate"
    assert candidate.verification_status == "unverified"
    assert candidate.executable is False
    assert candidate.publishable is False
    assert "last_verified_at" not in CapabilityCandidateAssertionPreview.model_fields
    assert "score_profile" not in CapabilityCandidateAssertionPreview.model_fields

    for field_name, invalid_value in (
        ("support_status", "verified"),
        ("verification_status", "verified"),
        ("executable", True),
        ("publishable", True),
        ("candidate_fingerprint", "sha256:UPPERCASE"),
    ):
        payload = candidate.model_dump(mode="json")
        payload[field_name] = invalid_value
        with pytest.raises(ValidationError):
            CapabilityCandidateAssertionPreview.model_validate(payload)


def test_parser_output_enforces_candidate_and_diagnostic_caps() -> None:
    output = CapabilityDiscoveryParserOutput(
        proposed_implementations=[build_proposed_implementation()],
        candidate_assertions=[build_candidate()],
        evidence=[build_evidence()],
        diagnostics=[],
    )
    assert len(output.candidate_assertions) == 1

    with pytest.raises(ValidationError):
        CapabilityDiscoveryParserOutput(
            proposed_implementations=[build_proposed_implementation()],
            candidate_assertions=[build_candidate()] * 33,
            evidence=[build_evidence()],
            diagnostics=[],
        )

    diagnostic = CapabilityDiscoveryDiagnostic(
        schema_version="capability_discovery_diagnostic.v1",
        fixture_id="fixture",
        severity="info",
        code="mapped",
        message="Mapped source claim.",
        source_claim_ref="claim:one",
    )
    with pytest.raises(ValidationError):
        CapabilityDiscoveryParserOutput(
            proposed_implementations=[build_proposed_implementation()],
            candidate_assertions=[build_candidate()],
            evidence=[build_evidence()],
            diagnostics=[diagnostic] * 65,
        )


def test_preview_response_validates_references_summary_and_boundaries() -> None:
    response = build_response()
    assert response.database_write is False
    assert response.provider_call is False
    assert response.provider_call_attempted is False
    assert response.actor_run is False
    assert response.browser_run is False
    assert response.llm_call is False
    assert response.credential_read_attempted is False
    assert response.database_migration is False
    assert response.workflow_run_created is False
    assert response.candidate_publish_allowed is False
    assert response.production_write_allowed is False

    invalid_payloads = []
    wrong_summary = response.model_dump(mode="json")
    wrong_summary["summary"]["candidate_assertion_count"] = 2
    invalid_payloads.append(wrong_summary)

    unknown_evidence = response.model_dump(mode="json")
    unknown_evidence["candidate_assertions"][0]["evidence_refs"] = [
        "evidence:missing"
    ]
    invalid_payloads.append(unknown_evidence)

    unknown_implementation = response.model_dump(mode="json")
    unknown_implementation["candidate_assertions"][0][
        "proposed_implementation_id"
    ] = "proposed:missing"
    invalid_payloads.append(unknown_implementation)

    error_diagnostic = response.model_dump(mode="json")
    error_diagnostic["diagnostics"][0]["severity"] = "error"
    error_diagnostic["summary"]["warning_count"] = 0
    error_diagnostic["summary"]["error_count"] = 1
    invalid_payloads.append(error_diagnostic)

    true_boundary = response.model_dump(mode="json")
    true_boundary["provider_call"] = True
    invalid_payloads.append(true_boundary)

    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            CapabilityDiscoveryPreviewResponse.model_validate(payload)


def test_discovery_error_messages_are_stable_and_allowlisted() -> None:
    assert (
        CapabilityDiscoveryFixtureUnknownError.message
        == "capability_discovery_fixture_unknown"
    )
    assert (
        CapabilityDiscoveryFixtureInvalidError.message
        == "capability_discovery_fixture_invalid"
    )
    assert (
        CapabilityDiscoveryContractInvalidError.message
        == "capability_discovery_contract_invalid"
    )
