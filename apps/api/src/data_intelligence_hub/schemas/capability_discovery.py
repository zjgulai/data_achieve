from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from data_intelligence_hub.schemas.capability_catalog import (
    AccessChannel,
    CapabilityConstraint,
    CapabilityEvidence,
    CapabilityOperation,
    DeliveryForm,
    DeploymentMode,
    PlatformId,
    ResourceType,
)

SHA256_HEX_PATTERN = r"^[0-9a-f]{64}$"
FINGERPRINT_PATTERN = r"^sha256:[0-9a-f]{64}$"
FIXTURE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,99}$")
SHA256_HEX = re.compile(SHA256_HEX_PATTERN)

Sha256Hex = Annotated[str, Field(pattern=SHA256_HEX_PATTERN)]
Sha256Fingerprint = Annotated[str, Field(pattern=FINGERPRINT_PATTERN)]
NonEmptyString = Annotated[str, Field(min_length=1, max_length=500)]


class CapabilityDiscoveryContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CapabilityDiscoveryParserId(StrEnum):
    TIKHUB_PUBLIC_MARKET_V1 = "tikhub_public_market.v1"
    APIFY_PUBLIC_MARKET_V1 = "apify_public_market.v1"
    YOUTUBE_OFFICIAL_DOC_V1 = "youtube_official_doc.v1"
    REDDIT_OFFICIAL_DOC_V1 = "reddit_official_doc.v1"


def validate_https_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("source_url_must_be_https")
    return value


def validate_timezone_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("observed_at_timezone_required")
    return value


def validate_fixture_id(value: str) -> str:
    if FIXTURE_ID_PATTERN.fullmatch(value) is None:
        raise ValueError("fixture_id_invalid")
    return value


class CapabilityDiscoveryPreviewRequest(CapabilityDiscoveryContract):
    schema_version: Literal["capability_discovery_preview_request.v1"]
    preview_mode: Literal["fixture_replay"] = "fixture_replay"
    fixture_ids: list[str] = Field(min_length=1, max_length=4)

    @field_validator("fixture_ids")
    @classmethod
    def validate_fixture_ids(cls, value: list[str]) -> list[str]:
        for fixture_id in value:
            validate_fixture_id(fixture_id)
        if len(value) != len(set(value)):
            raise ValueError("duplicate_fixture_id")
        return value


class CapabilitySourceSnapshotFixture(CapabilityDiscoveryContract):
    schema_version: Literal["capability_source_snapshot_fixture.v1"]
    fixture_id: str
    source_kind: Literal["public_market", "official_doc"]
    source_name: NonEmptyString
    source_url: str
    source_version: NonEmptyString
    observed_at: datetime
    parser_id: CapabilityDiscoveryParserId
    payload: dict[str, JsonValue]

    _validate_fixture_id = field_validator("fixture_id")(validate_fixture_id)
    _validate_source_url = field_validator("source_url")(validate_https_url)
    _validate_observed_at = field_validator("observed_at")(validate_timezone_aware)


class CapabilityDiscoveryFixtureManifestEntry(CapabilityDiscoveryContract):
    fixture_id: str
    relative_path: NonEmptyString
    parser_id: CapabilityDiscoveryParserId
    expected_sha256: Sha256Hex

    _validate_fixture_id = field_validator("fixture_id")(validate_fixture_id)


class CapabilityDiscoveryFixtureManifest(CapabilityDiscoveryContract):
    schema_version: Literal["capability_discovery_fixture_manifest.v1"]
    fixtures: list[CapabilityDiscoveryFixtureManifestEntry] = Field(
        min_length=4,
        max_length=4,
    )

    @model_validator(mode="after")
    def validate_unique_entries(self) -> Self:
        fixture_ids = [entry.fixture_id for entry in self.fixtures]
        relative_paths = [entry.relative_path for entry in self.fixtures]
        if len(fixture_ids) != len(set(fixture_ids)):
            raise ValueError("duplicate_fixture_id")
        if len(relative_paths) != len(set(relative_paths)):
            raise ValueError("duplicate_fixture_path")
        return self


class CapabilitySourceSnapshotPreview(CapabilityDiscoveryContract):
    schema_version: Literal["capability_source_snapshot_preview.v1"]
    fixture_id: str
    source_kind: Literal["public_market", "official_doc"]
    source_name: NonEmptyString
    source_url: str
    source_version: NonEmptyString
    observed_at: datetime
    parser_id: CapabilityDiscoveryParserId
    content_hash: Sha256Hex

    _validate_fixture_id = field_validator("fixture_id")(validate_fixture_id)
    _validate_source_url = field_validator("source_url")(validate_https_url)
    _validate_observed_at = field_validator("observed_at")(validate_timezone_aware)


class CapabilityProposedImplementationPreview(CapabilityDiscoveryContract):
    schema_version: Literal["capability_proposed_implementation_preview.v1"]
    proposed_implementation_id: NonEmptyString
    provider_id: NonEmptyString
    platform: PlatformId
    access_channel: AccessChannel
    delivery_form: DeliveryForm
    deployment_mode: DeploymentMode
    source_label: NonEmptyString
    claimed_auth_mode: NonEmptyString
    claimed_required_credentials: list[NonEmptyString] = Field(max_length=32)
    claimed_limitations: list[NonEmptyString] = Field(max_length=64)
    evidence_refs: list[NonEmptyString] = Field(min_length=1, max_length=64)


class CapabilityCandidateAssertionPreview(CapabilityDiscoveryContract):
    schema_version: Literal["capability_candidate_assertion_preview.v1"]
    candidate_id: NonEmptyString
    proposed_implementation_id: NonEmptyString
    platform: PlatformId
    access_channel: AccessChannel
    resource_type: ResourceType
    operation: CapabilityOperation
    support_status: Literal["candidate"] = "candidate"
    verification_status: Literal["unverified"] = "unverified"
    executable: Literal[False] = False
    publishable: Literal[False] = False
    claimed_field_contract: dict[str, JsonValue]
    claimed_constraints: list[CapabilityConstraint] = Field(max_length=64)
    region_scope: list[NonEmptyString] = Field(max_length=32)
    purpose_scope: list[NonEmptyString] = Field(max_length=32)
    auth_scope: list[NonEmptyString] = Field(max_length=32)
    source_claim_refs: list[NonEmptyString] = Field(min_length=1, max_length=64)
    evidence_refs: list[NonEmptyString] = Field(min_length=1, max_length=64)
    parser_id: CapabilityDiscoveryParserId
    candidate_fingerprint: Sha256Fingerprint


class CapabilityDiscoveryDiagnostic(CapabilityDiscoveryContract):
    schema_version: Literal["capability_discovery_diagnostic.v1"]
    fixture_id: NonEmptyString
    severity: Literal["info", "warning", "error"]
    code: NonEmptyString
    message: NonEmptyString
    source_claim_ref: NonEmptyString


class CapabilityDiscoveryParserOutput(CapabilityDiscoveryContract):
    schema_version: Literal["capability_discovery_parser_output.v1"] = (
        "capability_discovery_parser_output.v1"
    )
    proposed_implementations: list[CapabilityProposedImplementationPreview] = Field(
        max_length=32
    )
    candidate_assertions: list[CapabilityCandidateAssertionPreview] = Field(
        max_length=32
    )
    evidence: list[CapabilityEvidence] = Field(max_length=64)
    diagnostics: list[CapabilityDiscoveryDiagnostic] = Field(max_length=64)


class CapabilityDiscoverySummary(CapabilityDiscoveryContract):
    source_count: int = Field(ge=1, le=4)
    market_source_count: int = Field(ge=0, le=4)
    official_doc_source_count: int = Field(ge=0, le=4)
    proposed_implementation_count: int = Field(ge=1)
    candidate_assertion_count: int = Field(ge=1)
    evidence_count: int = Field(ge=1)
    warning_count: int = Field(ge=0)
    error_count: Literal[0] = 0


class CapabilityDiscoveryPreviewResponse(CapabilityDiscoveryContract):
    schema_version: Literal["capability_discovery_preview.v1"]
    evidence_grade: Literal["L2-fixture-or-dry-run"]
    preview_mode: Literal["fixture_replay"]
    preview_fingerprint: Sha256Fingerprint
    generated_from_observed_at: datetime
    source_snapshots: list[CapabilitySourceSnapshotPreview] = Field(
        min_length=1,
        max_length=4,
    )
    proposed_implementations: list[CapabilityProposedImplementationPreview] = Field(
        min_length=1
    )
    candidate_assertions: list[CapabilityCandidateAssertionPreview] = Field(
        min_length=1
    )
    evidence: list[CapabilityEvidence] = Field(min_length=1)
    diagnostics: list[CapabilityDiscoveryDiagnostic]
    summary: CapabilityDiscoverySummary
    provider_call: Literal[False] = False
    provider_call_attempted: Literal[False] = False
    actor_run: Literal[False] = False
    browser_run: Literal[False] = False
    llm_call: Literal[False] = False
    credential_read_attempted: Literal[False] = False
    database_write: Literal[False] = False
    database_migration: Literal[False] = False
    workflow_run_created: Literal[False] = False
    candidate_publish_allowed: Literal[False] = False
    production_write_allowed: Literal[False] = False

    _validate_generated_at = field_validator("generated_from_observed_at")(
        validate_timezone_aware
    )

    @model_validator(mode="after")
    def validate_summary_and_references(self) -> Self:
        source_ids = [source.fixture_id for source in self.source_snapshots]
        proposed_ids = [
            implementation.proposed_implementation_id
            for implementation in self.proposed_implementations
        ]
        candidate_ids = [candidate.candidate_id for candidate in self.candidate_assertions]
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("duplicate_source_snapshot")
        if len(proposed_ids) != len(set(proposed_ids)):
            raise ValueError("duplicate_proposed_implementation")
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("duplicate_candidate")
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("duplicate_evidence")

        expected_summary = {
            "source_count": len(self.source_snapshots),
            "market_source_count": sum(
                source.source_kind == "public_market" for source in self.source_snapshots
            ),
            "official_doc_source_count": sum(
                source.source_kind == "official_doc" for source in self.source_snapshots
            ),
            "proposed_implementation_count": len(self.proposed_implementations),
            "candidate_assertion_count": len(self.candidate_assertions),
            "evidence_count": len(self.evidence),
            "warning_count": sum(
                diagnostic.severity == "warning" for diagnostic in self.diagnostics
            ),
            "error_count": sum(
                diagnostic.severity == "error" for diagnostic in self.diagnostics
            ),
        }
        if self.summary.model_dump() != expected_summary:
            raise ValueError("capability_discovery_summary_mismatch")
        if expected_summary["error_count"] != 0:
            raise ValueError("capability_discovery_error_diagnostic")

        proposed_set = set(proposed_ids)
        evidence_set = set(evidence_ids)
        proposed_by_id = {
            item.proposed_implementation_id: item
            for item in self.proposed_implementations
        }
        for implementation in self.proposed_implementations:
            if any(ref not in evidence_set for ref in implementation.evidence_refs):
                raise ValueError("unknown_proposed_implementation_evidence_ref")
        for candidate in self.candidate_assertions:
            if candidate.proposed_implementation_id not in proposed_set:
                raise ValueError("unknown_candidate_proposed_implementation_ref")
            if any(ref not in evidence_set for ref in candidate.evidence_refs):
                raise ValueError("unknown_candidate_evidence_ref")
            implementation = proposed_by_id[candidate.proposed_implementation_id]
            if (
                candidate.platform != implementation.platform
                or candidate.access_channel != implementation.access_channel
            ):
                raise ValueError("candidate_proposed_implementation_scope_mismatch")
        for item in self.evidence:
            if (
                item.hash_scope != "retrieved_content"
                or SHA256_HEX.fullmatch(item.content_hash) is None
                or item.provider_call_attempted
                or item.credential_read_attempted
                or item.live_client_created
                or item.production_write_attempted
            ):
                raise ValueError("capability_discovery_evidence_boundary_invalid")
        return self
