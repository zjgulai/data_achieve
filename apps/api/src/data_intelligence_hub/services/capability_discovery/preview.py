from __future__ import annotations

from typing import cast

from pydantic import BaseModel, JsonValue, ValidationError

from data_intelligence_hub.schemas.capability_catalog import CapabilityEvidence
from data_intelligence_hub.schemas.capability_discovery import (
    CapabilityCandidateAssertionPreview,
    CapabilityDiscoveryDiagnostic,
    CapabilityDiscoveryParserOutput,
    CapabilityDiscoveryPreviewRequest,
    CapabilityDiscoveryPreviewResponse,
    CapabilityDiscoverySummary,
    CapabilityProposedImplementationPreview,
    CapabilitySourceSnapshotPreview,
)
from data_intelligence_hub.services.capability_discovery.fingerprint import (
    canonical_json_bytes,
    canonical_json_sha256,
)
from data_intelligence_hub.services.capability_discovery.fixture_loader import (
    LoadedCapabilityDiscoveryFixture,
    load_capability_discovery_fixtures,
)
from data_intelligence_hub.services.capability_discovery.parsers import (
    parse_capability_discovery_fixture,
)
from data_intelligence_hub.services.exceptions import (
    CapabilityDiscoveryContractInvalidError,
)


def _model_key(model: BaseModel, *, exclude: set[str] | None = None) -> bytes:
    return canonical_json_bytes(
        cast(
            JsonValue,
            model.model_dump(mode="json", exclude=exclude or set()),
        )
    )


def _merge_proposed_implementations(
    outputs: list[CapabilityDiscoveryParserOutput],
) -> list[CapabilityProposedImplementationPreview]:
    merged: dict[str, CapabilityProposedImplementationPreview] = {}
    for output in outputs:
        for item in output.proposed_implementations:
            existing = merged.get(item.proposed_implementation_id)
            if existing is None:
                merged[item.proposed_implementation_id] = item.model_copy(deep=True)
                continue
            if _model_key(existing, exclude={"evidence_refs"}) != _model_key(
                item,
                exclude={"evidence_refs"},
            ):
                raise CapabilityDiscoveryContractInvalidError
            payload = existing.model_dump(mode="json")
            payload["evidence_refs"] = sorted(
                set(existing.evidence_refs) | set(item.evidence_refs)
            )
            merged[item.proposed_implementation_id] = (
                CapabilityProposedImplementationPreview.model_validate(payload)
            )
    return sorted(
        merged.values(),
        key=lambda item: item.proposed_implementation_id,
    )


def _merge_candidates(
    outputs: list[CapabilityDiscoveryParserOutput],
) -> list[CapabilityCandidateAssertionPreview]:
    merged: dict[str, CapabilityCandidateAssertionPreview] = {}
    fingerprint_to_id: dict[str, str] = {}
    for output in outputs:
        for item in output.candidate_assertions:
            fingerprint_identity = fingerprint_to_id.get(item.candidate_fingerprint)
            if fingerprint_identity is not None and fingerprint_identity != item.candidate_id:
                raise CapabilityDiscoveryContractInvalidError
            fingerprint_to_id[item.candidate_fingerprint] = item.candidate_id

            existing = merged.get(item.candidate_id)
            if existing is None:
                merged[item.candidate_id] = item.model_copy(deep=True)
                continue
            if _model_key(
                existing,
                exclude={"evidence_refs", "source_claim_refs"},
            ) != _model_key(
                item,
                exclude={"evidence_refs", "source_claim_refs"},
            ):
                raise CapabilityDiscoveryContractInvalidError
            payload = existing.model_dump(mode="json")
            payload["evidence_refs"] = sorted(
                set(existing.evidence_refs) | set(item.evidence_refs)
            )
            payload["source_claim_refs"] = sorted(
                set(existing.source_claim_refs) | set(item.source_claim_refs)
            )
            merged[item.candidate_id] = (
                CapabilityCandidateAssertionPreview.model_validate(payload)
            )
    return sorted(
        merged.values(),
        key=lambda item: (
            item.proposed_implementation_id,
            item.resource_type.value,
            item.operation.value,
            item.candidate_id,
        ),
    )


def _merge_evidence(
    outputs: list[CapabilityDiscoveryParserOutput],
) -> list[CapabilityEvidence]:
    merged: dict[str, CapabilityEvidence] = {}
    for output in outputs:
        for item in output.evidence:
            existing = merged.get(item.evidence_id)
            if existing is not None and _model_key(existing) != _model_key(item):
                raise CapabilityDiscoveryContractInvalidError
            merged[item.evidence_id] = item.model_copy(deep=True)
    return sorted(merged.values(), key=lambda item: item.evidence_id)


def _merge_diagnostics(
    outputs: list[CapabilityDiscoveryParserOutput],
) -> list[CapabilityDiscoveryDiagnostic]:
    unique: dict[bytes, CapabilityDiscoveryDiagnostic] = {}
    for output in outputs:
        for item in output.diagnostics:
            if item.severity == "error":
                raise CapabilityDiscoveryContractInvalidError
            unique[_model_key(item)] = item.model_copy(deep=True)
    return sorted(
        unique.values(),
        key=lambda item: (
            item.fixture_id,
            item.severity,
            item.code,
            item.source_claim_ref,
        ),
    )


def _source_previews(
    loaded_fixtures: list[LoadedCapabilityDiscoveryFixture],
) -> list[CapabilitySourceSnapshotPreview]:
    previews = [
        CapabilitySourceSnapshotPreview(
            schema_version="capability_source_snapshot_preview.v1",
            fixture_id=loaded.snapshot.fixture_id,
            source_kind=loaded.snapshot.source_kind,
            source_name=loaded.snapshot.source_name,
            source_url=loaded.snapshot.source_url,
            source_version=loaded.snapshot.source_version,
            observed_at=loaded.snapshot.observed_at,
            parser_id=loaded.snapshot.parser_id,
            content_hash=loaded.content_hash,
        )
        for loaded in loaded_fixtures
    ]
    return sorted(previews, key=lambda item: item.fixture_id)


def _validate_references(
    *,
    sources: list[CapabilitySourceSnapshotPreview],
    proposed: list[CapabilityProposedImplementationPreview],
    candidates: list[CapabilityCandidateAssertionPreview],
    evidence: list[CapabilityEvidence],
    diagnostics: list[CapabilityDiscoveryDiagnostic],
) -> None:
    source_ids = {item.fixture_id for item in sources}
    source_parser_ids = {item.parser_id for item in sources}
    proposed_ids = {item.proposed_implementation_id for item in proposed}
    evidence_ids = {item.evidence_id for item in evidence}
    source_claim_refs = {item.source_claim_ref for item in diagnostics}

    if any(diagnostic.fixture_id not in source_ids for diagnostic in diagnostics):
        raise CapabilityDiscoveryContractInvalidError
    if any(candidate.parser_id not in source_parser_ids for candidate in candidates):
        raise CapabilityDiscoveryContractInvalidError
    for proposed_item in proposed:
        if not proposed_item.evidence_refs or any(
            ref not in evidence_ids for ref in proposed_item.evidence_refs
        ):
            raise CapabilityDiscoveryContractInvalidError
    for candidate_item in candidates:
        if candidate_item.proposed_implementation_id not in proposed_ids:
            raise CapabilityDiscoveryContractInvalidError
        if not candidate_item.evidence_refs or any(
            ref not in evidence_ids for ref in candidate_item.evidence_refs
        ):
            raise CapabilityDiscoveryContractInvalidError
        if not candidate_item.source_claim_refs or any(
            ref not in source_claim_refs for ref in candidate_item.source_claim_refs
        ):
            raise CapabilityDiscoveryContractInvalidError
    for evidence_item in evidence:
        if not any(
            evidence_item.source_url == source.source_url
            and evidence_item.source_version == source.source_version
            and evidence_item.observed_at == source.observed_at
            and evidence_item.content_hash == source.content_hash
            for source in sources
        ):
            raise CapabilityDiscoveryContractInvalidError


def _build_preview(
    request: CapabilityDiscoveryPreviewRequest,
) -> CapabilityDiscoveryPreviewResponse:
    fixture_ids = sorted(request.fixture_ids)
    loaded_fixtures = load_capability_discovery_fixtures(fixture_ids)
    loaded_ids = [item.snapshot.fixture_id for item in loaded_fixtures]
    if sorted(loaded_ids) != fixture_ids or len(loaded_ids) != len(set(loaded_ids)):
        raise CapabilityDiscoveryContractInvalidError

    outputs = [
        parse_capability_discovery_fixture(loaded) for loaded in loaded_fixtures
    ]
    sources = _source_previews(loaded_fixtures)
    proposed = _merge_proposed_implementations(outputs)
    candidates = _merge_candidates(outputs)
    evidence = _merge_evidence(outputs)
    diagnostics = _merge_diagnostics(outputs)
    _validate_references(
        sources=sources,
        proposed=proposed,
        candidates=candidates,
        evidence=evidence,
        diagnostics=diagnostics,
    )

    summary = CapabilityDiscoverySummary(
        source_count=len(sources),
        market_source_count=sum(
            item.source_kind == "public_market" for item in sources
        ),
        official_doc_source_count=sum(
            item.source_kind == "official_doc" for item in sources
        ),
        proposed_implementation_count=len(proposed),
        candidate_assertion_count=len(candidates),
        evidence_count=len(evidence),
        warning_count=sum(item.severity == "warning" for item in diagnostics),
        error_count=0,
    )
    draft = CapabilityDiscoveryPreviewResponse(
        schema_version="capability_discovery_preview.v1",
        evidence_grade="L2-fixture-or-dry-run",
        preview_mode="fixture_replay",
        preview_fingerprint=f"sha256:{'0' * 64}",
        generated_from_observed_at=max(item.observed_at for item in sources),
        source_snapshots=sources,
        proposed_implementations=proposed,
        candidate_assertions=candidates,
        evidence=evidence,
        diagnostics=diagnostics,
        summary=summary,
    )
    fingerprint_body = draft.model_dump(mode="json")
    fingerprint_body.pop("preview_fingerprint")
    fingerprint = f"sha256:{canonical_json_sha256(cast(JsonValue, fingerprint_body))}"
    payload = draft.model_dump(mode="json")
    payload["preview_fingerprint"] = fingerprint
    return CapabilityDiscoveryPreviewResponse.model_validate(payload)


def build_capability_discovery_preview(
    request: CapabilityDiscoveryPreviewRequest,
) -> CapabilityDiscoveryPreviewResponse:
    try:
        return _build_preview(request)
    except CapabilityDiscoveryContractInvalidError:
        raise
    except (TypeError, ValueError, ValidationError) as exc:
        raise CapabilityDiscoveryContractInvalidError from exc
