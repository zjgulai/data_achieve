from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest
from pydantic import JsonValue

from data_intelligence_hub.schemas.capability_catalog import EvidenceType
from data_intelligence_hub.schemas.capability_discovery import (
    CapabilityDiscoveryParserId,
)
from data_intelligence_hub.services.capability_discovery.fingerprint import (
    canonical_json_sha256,
)
from data_intelligence_hub.services.capability_discovery.fixture_loader import (
    LoadedCapabilityDiscoveryFixture,
    load_capability_discovery_fixture,
)
from data_intelligence_hub.services.capability_discovery.parsers import (
    parse_capability_discovery_fixture,
)
from data_intelligence_hub.services.exceptions import (
    CapabilityDiscoveryContractInvalidError,
)

PARSERS_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "data_intelligence_hub"
    / "services"
    / "capability_discovery"
    / "parsers.py"
)

GOLDEN_CASES = [
    (
        "tikhub-youtube-market-v1",
        "proposed:tikhub.youtube.v1",
        EvidenceType.PUBLIC_MARKET,
        {
            "candidate:tikhub.youtube.v1:content:resolve_detail",
            "candidate:tikhub.youtube.v1:conversation:list_enumerate",
            "candidate:tikhub.youtube.v1:content:search_discover",
        },
        1,
    ),
    (
        "apify-reddit-market-v1",
        "proposed:apify.prodiger-reddit-scraper.v1",
        EvidenceType.PUBLIC_MARKET,
        {
            "candidate:apify.prodiger-reddit-scraper.v1:content:search_discover",
            "candidate:apify.prodiger-reddit-scraper.v1:conversation:list_enumerate",
        },
        1,
    ),
    (
        "youtube-data-api-doc-v1",
        "proposed:youtube.data-api.v3",
        EvidenceType.OFFICIAL_DOC,
        {"candidate:youtube.data-api.v3:content:resolve_detail"},
        0,
    ),
    (
        "reddit-data-api-doc-v1",
        "proposed:reddit.data-api.v1",
        EvidenceType.OFFICIAL_DOC,
        {"candidate:reddit.data-api.v1:content:search_discover"},
        0,
    ),
]


def _json_hash_for_snapshot(snapshot: object) -> str:
    dumped = cast(JsonValue, snapshot)
    return canonical_json_sha256(dumped)


def _replace_payload(
    loaded: LoadedCapabilityDiscoveryFixture,
    payload: dict[str, JsonValue],
) -> LoadedCapabilityDiscoveryFixture:
    snapshot = loaded.snapshot.model_copy(update={"payload": payload}, deep=True)
    return LoadedCapabilityDiscoveryFixture(
        snapshot=snapshot,
        content_hash=_json_hash_for_snapshot(snapshot.model_dump(mode="json")),
    )


@pytest.mark.parametrize(
    (
        "fixture_id",
        "proposed_id",
        "evidence_type",
        "candidate_ids",
        "warning_count",
    ),
    GOLDEN_CASES,
)
def test_each_source_parser_matches_its_golden_contract(
    fixture_id: str,
    proposed_id: str,
    evidence_type: EvidenceType,
    candidate_ids: set[str],
    warning_count: int,
) -> None:
    loaded = load_capability_discovery_fixture(fixture_id)
    output = parse_capability_discovery_fixture(loaded)

    assert [item.proposed_implementation_id for item in output.proposed_implementations] == [
        proposed_id
    ]
    assert {item.candidate_id for item in output.candidate_assertions} == candidate_ids
    assert len(output.evidence) == 1
    assert output.evidence[0].evidence_id == f"evidence:{fixture_id}"
    assert output.evidence[0].evidence_type == evidence_type
    assert output.evidence[0].content_hash == loaded.content_hash
    assert output.evidence[0].hash_scope == "retrieved_content"
    assert output.evidence[0].provider_call_attempted is False
    assert output.evidence[0].credential_read_attempted is False
    assert output.evidence[0].live_client_created is False
    assert output.evidence[0].production_write_attempted is False
    assert sum(item.severity == "warning" for item in output.diagnostics) == warning_count
    assert sum(item.severity == "info" for item in output.diagnostics) == len(
        candidate_ids
    )

    for candidate in output.candidate_assertions:
        assert candidate.support_status == "candidate"
        assert candidate.verification_status == "unverified"
        assert candidate.executable is False
        assert candidate.publishable is False
        assert candidate.candidate_fingerprint.startswith("sha256:")
        assert len(candidate.candidate_fingerprint) == 71
        assert candidate.evidence_refs == [f"evidence:{fixture_id}"]
        assert candidate.source_claim_refs
        assert candidate.claimed_field_contract


def test_candidate_identity_and_fingerprint_do_not_depend_on_claim_position() -> None:
    loaded = load_capability_discovery_fixture("tikhub-youtube-market-v1")
    original = parse_capability_discovery_fixture(loaded)
    payload = deepcopy(loaded.snapshot.payload)
    claims = cast(list[JsonValue], payload["claims"])
    payload["claims"] = list(reversed(claims))
    reordered = parse_capability_discovery_fixture(_replace_payload(loaded, payload))

    original_by_id = {
        item.candidate_id: item.candidate_fingerprint
        for item in original.candidate_assertions
    }
    reordered_by_id = {
        item.candidate_id: item.candidate_fingerprint
        for item in reordered.candidate_assertions
    }
    assert reordered_by_id == original_by_id


def test_candidate_fingerprint_changes_with_claimed_contract_not_position() -> None:
    loaded = load_capability_discovery_fixture("youtube-data-api-doc-v1")
    original = parse_capability_discovery_fixture(loaded).candidate_assertions[0]
    payload = deepcopy(loaded.snapshot.payload)
    claims = cast(list[dict[str, JsonValue]], payload["claims"])
    first_claim = claims[0]
    field_contract = cast(dict[str, JsonValue], first_claim["claimed_field_contract"])
    optional = cast(list[JsonValue], field_contract["optional"])
    optional.append("new_source_field")
    modified = parse_capability_discovery_fixture(_replace_payload(loaded, payload))
    changed = modified.candidate_assertions[0]

    assert changed.candidate_id == original.candidate_id
    assert changed.candidate_fingerprint != original.candidate_fingerprint


def test_unmapped_claims_emit_warnings_without_inventing_candidates() -> None:
    for fixture_id, forbidden_claim in (
        ("tikhub-youtube-market-v1", "claim:tikhub:channel-profile"),
        ("apify-reddit-market-v1", "claim:apify:user-profile"),
    ):
        output = parse_capability_discovery_fixture(
            load_capability_discovery_fixture(fixture_id)
        )
        warnings = [item for item in output.diagnostics if item.severity == "warning"]
        serialized_candidates = str(
            [item.model_dump(mode="json") for item in output.candidate_assertions]
        )

        assert [item.source_claim_ref for item in warnings] == [forbidden_claim]
        assert all(
            forbidden_claim not in item.source_claim_refs
            for item in output.candidate_assertions
        )
        assert forbidden_claim not in serialized_candidates


def test_duplicate_candidate_identity_fails_closed() -> None:
    loaded = load_capability_discovery_fixture("youtube-data-api-doc-v1")
    payload = deepcopy(loaded.snapshot.payload)
    claims = cast(list[dict[str, JsonValue]], payload["claims"])
    duplicate = deepcopy(claims[0])
    duplicate["claim_ref"] = "claim:youtube:duplicate-identity"
    claims.append(duplicate)

    with pytest.raises(CapabilityDiscoveryContractInvalidError):
        parse_capability_discovery_fixture(_replace_payload(loaded, payload))


def test_invalid_or_oversized_parser_payload_fails_closed() -> None:
    loaded = load_capability_discovery_fixture("youtube-data-api-doc-v1")

    extra_payload = deepcopy(loaded.snapshot.payload)
    extra_payload["invented_capability"] = True
    with pytest.raises(CapabilityDiscoveryContractInvalidError):
        parse_capability_discovery_fixture(_replace_payload(loaded, extra_payload))

    oversized_payload = deepcopy(loaded.snapshot.payload)
    claims = cast(list[dict[str, JsonValue]], oversized_payload["claims"])
    oversized_payload["claims"] = [deepcopy(claims[0]) for _ in range(33)]
    with pytest.raises(CapabilityDiscoveryContractInvalidError):
        parse_capability_discovery_fixture(
            _replace_payload(loaded, oversized_payload)
        )


def test_parser_source_contract_and_content_hash_fail_closed() -> None:
    loaded = load_capability_discovery_fixture("tikhub-youtube-market-v1")
    mismatched_snapshot = loaded.snapshot.model_copy(
        update={"parser_id": CapabilityDiscoveryParserId.APIFY_PUBLIC_MARKET_V1}
    )
    mismatched = LoadedCapabilityDiscoveryFixture(
        snapshot=mismatched_snapshot,
        content_hash=_json_hash_for_snapshot(
            mismatched_snapshot.model_dump(mode="json")
        ),
    )

    with pytest.raises(CapabilityDiscoveryContractInvalidError):
        parse_capability_discovery_fixture(mismatched)
    with pytest.raises(CapabilityDiscoveryContractInvalidError):
        parse_capability_discovery_fixture(
            LoadedCapabilityDiscoveryFixture(
                snapshot=loaded.snapshot,
                content_hash="not-a-sha256",
            )
        )


def test_parser_module_has_no_file_network_environment_or_database_access() -> None:
    tree = ast.parse(PARSERS_PATH.read_text(encoding="utf-8"))
    forbidden_import_roots = {
        "aiohttp",
        "httpx",
        "os",
        "pathlib",
        "requests",
        "selenium",
        "socket",
        "sqlalchemy",
        "urllib",
    }
    forbidden_calls = {
        "connect",
        "getenv",
        "open",
        "read_bytes",
        "read_text",
        "urlopen",
        "write_bytes",
        "write_text",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                alias.name.split(".")[0] not in forbidden_import_roots
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            assert node.module.split(".")[0] not in forbidden_import_roots
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden_calls
            if isinstance(node.func, ast.Attribute):
                assert node.func.attr not in forbidden_calls
