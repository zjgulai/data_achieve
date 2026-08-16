from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, model_validator

from data_intelligence_hub.schemas.capability_catalog import (
    AccessChannel,
    CapabilityConstraint,
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
    CapabilityDiscoveryParserId,
    CapabilityDiscoveryParserOutput,
    CapabilityProposedImplementationPreview,
    CapabilitySourceSnapshotFixture,
)
from data_intelligence_hub.services.capability_discovery.fingerprint import (
    canonical_json_bytes,
    canonical_json_sha256,
)
from data_intelligence_hub.services.capability_discovery.fixture_loader import (
    LoadedCapabilityDiscoveryFixture,
)
from data_intelligence_hub.services.exceptions import (
    CapabilityDiscoveryContractInvalidError,
)

NonEmptyString = Annotated[str, Field(min_length=1, max_length=500)]
SHA256_CHARS = frozenset("0123456789abcdef")


class _ParserContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _SourceClaim(_ParserContract):
    claim_ref: NonEmptyString
    resource_type: ResourceType
    operation: CapabilityOperation
    claimed_field_contract: dict[str, JsonValue]
    claimed_constraints: list[CapabilityConstraint] = Field(max_length=64)
    region_scope: list[NonEmptyString] = Field(max_length=32)
    purpose_scope: list[NonEmptyString] = Field(max_length=32)
    auth_scope: list[NonEmptyString] = Field(max_length=32)


class _UnmappedSourceClaim(_ParserContract):
    claim_ref: NonEmptyString
    summary: NonEmptyString


class _SourcePayload(_ParserContract):
    provider_id: NonEmptyString
    platform: PlatformId
    access_channel: AccessChannel
    delivery_form: DeliveryForm
    deployment_mode: DeploymentMode
    claimed_auth_mode: NonEmptyString
    claimed_required_credentials: list[NonEmptyString] = Field(max_length=32)
    claimed_limitations: list[NonEmptyString] = Field(max_length=64)
    claims: list[_SourceClaim] = Field(min_length=1, max_length=32)
    source_summary: list[NonEmptyString] = Field(min_length=1, max_length=16)
    related_source_urls: list[NonEmptyString] = Field(default_factory=list, max_length=16)
    unmapped_claims: list[_UnmappedSourceClaim] = Field(
        default_factory=list,
        max_length=32,
    )

    @model_validator(mode="after")
    def validate_claim_refs(self) -> Self:
        claim_refs = [item.claim_ref for item in self.claims]
        unmapped_refs = [item.claim_ref for item in self.unmapped_claims]
        all_refs = claim_refs + unmapped_refs
        if len(all_refs) != len(set(all_refs)):
            raise ValueError("duplicate_source_claim_ref")
        return self


@dataclass(frozen=True, slots=True)
class _ParserSpec:
    parser_id: CapabilityDiscoveryParserId
    source_kind: Literal["public_market", "official_doc"]
    platform: PlatformId
    access_channel: AccessChannel
    delivery_form: DeliveryForm
    deployment_mode: DeploymentMode
    evidence_type: EvidenceType


TIKHUB_SPEC = _ParserSpec(
    parser_id=CapabilityDiscoveryParserId.TIKHUB_PUBLIC_MARKET_V1,
    source_kind="public_market",
    platform=PlatformId.YOUTUBE,
    access_channel=AccessChannel.MANAGED_OPAQUE_COLLECTOR,
    delivery_form=DeliveryForm.ENDPOINT,
    deployment_mode=DeploymentMode.MANAGED_SAAS,
    evidence_type=EvidenceType.PUBLIC_MARKET,
)
APIFY_SPEC = _ParserSpec(
    parser_id=CapabilityDiscoveryParserId.APIFY_PUBLIC_MARKET_V1,
    source_kind="public_market",
    platform=PlatformId.REDDIT,
    access_channel=AccessChannel.MANAGED_OPAQUE_COLLECTOR,
    delivery_form=DeliveryForm.ACTOR,
    deployment_mode=DeploymentMode.MANAGED_SAAS,
    evidence_type=EvidenceType.PUBLIC_MARKET,
)
YOUTUBE_SPEC = _ParserSpec(
    parser_id=CapabilityDiscoveryParserId.YOUTUBE_OFFICIAL_DOC_V1,
    source_kind="official_doc",
    platform=PlatformId.YOUTUBE,
    access_channel=AccessChannel.OFFICIAL_AUTHORIZED_API,
    delivery_form=DeliveryForm.ENDPOINT,
    deployment_mode=DeploymentMode.OFFICIAL_CLOUD,
    evidence_type=EvidenceType.OFFICIAL_DOC,
)
REDDIT_SPEC = _ParserSpec(
    parser_id=CapabilityDiscoveryParserId.REDDIT_OFFICIAL_DOC_V1,
    source_kind="official_doc",
    platform=PlatformId.REDDIT,
    access_channel=AccessChannel.OFFICIAL_AUTHORIZED_API,
    delivery_form=DeliveryForm.ENDPOINT,
    deployment_mode=DeploymentMode.OFFICIAL_CLOUD,
    evidence_type=EvidenceType.OFFICIAL_DOC,
)


def _stable_strings(values: list[str]) -> list[str]:
    return sorted(set(values))


def _stable_constraints(
    values: list[CapabilityConstraint],
) -> list[CapabilityConstraint]:
    return sorted(
        (item.model_copy(deep=True) for item in values),
        key=lambda item: canonical_json_bytes(
            cast(JsonValue, item.model_dump(mode="json"))
        ),
    )


def _candidate_fingerprint(
    *,
    candidate_id: str,
    proposed_implementation_id: str,
    payload: _SourcePayload,
    claim: _SourceClaim,
    constraints: list[CapabilityConstraint],
) -> str:
    semantic_payload = cast(
        JsonValue,
        {
            "schema_version": "capability_candidate_semantics.v1",
            "candidate_id": candidate_id,
            "proposed_implementation_id": proposed_implementation_id,
            "platform": payload.platform.value,
            "access_channel": payload.access_channel.value,
            "resource_type": claim.resource_type.value,
            "operation": claim.operation.value,
            "claimed_field_contract": claim.claimed_field_contract,
            "claimed_constraints": [
                item.model_dump(mode="json") for item in constraints
            ],
            "region_scope": _stable_strings(claim.region_scope),
            "purpose_scope": _stable_strings(claim.purpose_scope),
            "auth_scope": _stable_strings(claim.auth_scope),
        },
    )
    return f"sha256:{canonical_json_sha256(semantic_payload)}"


def _validate_loaded_snapshot(
    snapshot: CapabilitySourceSnapshotFixture,
    content_hash: str,
) -> None:
    if len(content_hash) != 64 or any(char not in SHA256_CHARS for char in content_hash):
        raise CapabilityDiscoveryContractInvalidError
    snapshot_json = cast(JsonValue, snapshot.model_dump(mode="json"))
    if canonical_json_sha256(snapshot_json) != content_hash:
        raise CapabilityDiscoveryContractInvalidError


def _validate_source_contract(
    snapshot: CapabilitySourceSnapshotFixture,
    payload: _SourcePayload,
    spec: _ParserSpec,
) -> None:
    if (
        snapshot.parser_id != spec.parser_id
        or snapshot.source_kind != spec.source_kind
        or payload.platform != spec.platform
        or payload.access_channel != spec.access_channel
        or payload.delivery_form != spec.delivery_form
        or payload.deployment_mode != spec.deployment_mode
    ):
        raise CapabilityDiscoveryContractInvalidError


def _parse_source(
    snapshot: CapabilitySourceSnapshotFixture,
    content_hash: str,
    spec: _ParserSpec,
) -> CapabilityDiscoveryParserOutput:
    try:
        _validate_loaded_snapshot(snapshot, content_hash)
        payload = _SourcePayload.model_validate(snapshot.payload)
        _validate_source_contract(snapshot, payload, spec)

        evidence_id = f"evidence:{snapshot.fixture_id}"
        proposed_implementation_id = f"proposed:{payload.provider_id}"
        evidence = CapabilityEvidence(
            schema_version="capability_evidence.v1",
            evidence_id=evidence_id,
            evidence_type=spec.evidence_type,
            source_url=snapshot.source_url,
            source_version=snapshot.source_version,
            observed_at=snapshot.observed_at,
            content_hash=content_hash,
            hash_scope="retrieved_content",
            evidence_grade="L2-fixture-or-dry-run",
            provider_call_attempted=False,
            credential_read_attempted=False,
            live_client_created=False,
            production_write_attempted=False,
        )
        proposed = CapabilityProposedImplementationPreview(
            schema_version="capability_proposed_implementation_preview.v1",
            proposed_implementation_id=proposed_implementation_id,
            provider_id=payload.provider_id,
            platform=payload.platform,
            access_channel=payload.access_channel,
            delivery_form=payload.delivery_form,
            deployment_mode=payload.deployment_mode,
            source_label=snapshot.source_name,
            claimed_auth_mode=payload.claimed_auth_mode,
            claimed_required_credentials=_stable_strings(
                payload.claimed_required_credentials
            ),
            claimed_limitations=_stable_strings(payload.claimed_limitations),
            evidence_refs=[evidence_id],
        )

        candidates: list[CapabilityCandidateAssertionPreview] = []
        diagnostics: list[CapabilityDiscoveryDiagnostic] = []
        candidate_ids: set[str] = set()
        for claim in payload.claims:
            candidate_id = (
                f"candidate:{payload.provider_id}:"
                f"{claim.resource_type.value}:{claim.operation.value}"
            )
            if candidate_id in candidate_ids:
                raise CapabilityDiscoveryContractInvalidError
            candidate_ids.add(candidate_id)
            constraints = _stable_constraints(claim.claimed_constraints)
            candidates.append(
                CapabilityCandidateAssertionPreview(
                    schema_version="capability_candidate_assertion_preview.v1",
                    candidate_id=candidate_id,
                    proposed_implementation_id=proposed_implementation_id,
                    platform=payload.platform,
                    access_channel=payload.access_channel,
                    resource_type=claim.resource_type,
                    operation=claim.operation,
                    support_status="candidate",
                    verification_status="unverified",
                    executable=False,
                    publishable=False,
                    claimed_field_contract=claim.claimed_field_contract,
                    claimed_constraints=constraints,
                    region_scope=_stable_strings(claim.region_scope),
                    purpose_scope=_stable_strings(claim.purpose_scope),
                    auth_scope=_stable_strings(claim.auth_scope),
                    source_claim_refs=[claim.claim_ref],
                    evidence_refs=[evidence_id],
                    parser_id=spec.parser_id,
                    candidate_fingerprint=_candidate_fingerprint(
                        candidate_id=candidate_id,
                        proposed_implementation_id=proposed_implementation_id,
                        payload=payload,
                        claim=claim,
                        constraints=constraints,
                    ),
                )
            )
            diagnostics.append(
                CapabilityDiscoveryDiagnostic(
                    schema_version="capability_discovery_diagnostic.v1",
                    fixture_id=snapshot.fixture_id,
                    severity="info",
                    code="source_claim_mapped",
                    message="Source claim mapped to a candidate assertion.",
                    source_claim_ref=claim.claim_ref,
                )
            )

        diagnostics.extend(
            CapabilityDiscoveryDiagnostic(
                schema_version="capability_discovery_diagnostic.v1",
                fixture_id=snapshot.fixture_id,
                severity="warning",
                code="source_claim_not_mapped",
                message=(
                    "Source claim was retained as a warning and did not create "
                    "a candidate assertion."
                ),
                source_claim_ref=claim.claim_ref,
            )
            for claim in payload.unmapped_claims
        )
        return CapabilityDiscoveryParserOutput(
            proposed_implementations=[proposed],
            candidate_assertions=candidates,
            evidence=[evidence],
            diagnostics=diagnostics,
        )
    except CapabilityDiscoveryContractInvalidError:
        raise
    except (TypeError, ValueError, ValidationError) as exc:
        raise CapabilityDiscoveryContractInvalidError from exc


def parse_tikhub_public_market(
    snapshot: CapabilitySourceSnapshotFixture,
    content_hash: str,
) -> CapabilityDiscoveryParserOutput:
    return _parse_source(snapshot, content_hash, TIKHUB_SPEC)


def parse_apify_public_market(
    snapshot: CapabilitySourceSnapshotFixture,
    content_hash: str,
) -> CapabilityDiscoveryParserOutput:
    return _parse_source(snapshot, content_hash, APIFY_SPEC)


def parse_youtube_official_doc(
    snapshot: CapabilitySourceSnapshotFixture,
    content_hash: str,
) -> CapabilityDiscoveryParserOutput:
    return _parse_source(snapshot, content_hash, YOUTUBE_SPEC)


def parse_reddit_official_doc(
    snapshot: CapabilitySourceSnapshotFixture,
    content_hash: str,
) -> CapabilityDiscoveryParserOutput:
    return _parse_source(snapshot, content_hash, REDDIT_SPEC)


Parser = Callable[
    [CapabilitySourceSnapshotFixture, str],
    CapabilityDiscoveryParserOutput,
]
PARSERS: dict[CapabilityDiscoveryParserId, Parser] = {
    CapabilityDiscoveryParserId.TIKHUB_PUBLIC_MARKET_V1: parse_tikhub_public_market,
    CapabilityDiscoveryParserId.APIFY_PUBLIC_MARKET_V1: parse_apify_public_market,
    CapabilityDiscoveryParserId.YOUTUBE_OFFICIAL_DOC_V1: parse_youtube_official_doc,
    CapabilityDiscoveryParserId.REDDIT_OFFICIAL_DOC_V1: parse_reddit_official_doc,
}


def parse_capability_discovery_fixture(
    loaded: LoadedCapabilityDiscoveryFixture,
) -> CapabilityDiscoveryParserOutput:
    parser = PARSERS.get(loaded.snapshot.parser_id)
    if parser is None:
        raise CapabilityDiscoveryContractInvalidError
    return parser(loaded.snapshot, loaded.content_hash)
