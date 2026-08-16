from __future__ import annotations

import ast
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from pydantic import JsonValue

from data_intelligence_hub.schemas.capability_discovery import (
    CapabilityDiscoveryDiagnostic,
    CapabilityDiscoveryParserOutput,
    CapabilityDiscoveryPreviewRequest,
)
from data_intelligence_hub.services import capability_catalog
from data_intelligence_hub.services.capability_discovery import preview as preview_module
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
from data_intelligence_hub.services.capability_discovery.preview import (
    build_capability_discovery_preview,
)
from data_intelligence_hub.services.exceptions import (
    CapabilityDiscoveryContractInvalidError,
)

PREVIEW_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "data_intelligence_hub"
    / "services"
    / "capability_discovery"
    / "preview.py"
)
FIXTURE_IDS = [
    "tikhub-youtube-market-v1",
    "apify-reddit-market-v1",
    "youtube-data-api-doc-v1",
    "reddit-data-api-doc-v1",
]
Parser = Callable[[LoadedCapabilityDiscoveryFixture], CapabilityDiscoveryParserOutput]


def _request(fixture_ids: Sequence[str] = FIXTURE_IDS) -> CapabilityDiscoveryPreviewRequest:
    return CapabilityDiscoveryPreviewRequest(
        schema_version="capability_discovery_preview_request.v1",
        preview_mode="fixture_replay",
        fixture_ids=list(fixture_ids),
    )


def _snapshot_hash(snapshot: object) -> str:
    return canonical_json_sha256(cast(JsonValue, snapshot))


def _with_observed_at(
    loaded: LoadedCapabilityDiscoveryFixture,
    observed_at: datetime,
) -> LoadedCapabilityDiscoveryFixture:
    snapshot = loaded.snapshot.model_copy(update={"observed_at": observed_at}, deep=True)
    return LoadedCapabilityDiscoveryFixture(
        snapshot=snapshot,
        content_hash=_snapshot_hash(snapshot.model_dump(mode="json")),
    )


def _duplicate_semantic_parser(real_parser: Parser) -> Parser:
    template = real_parser(
        load_capability_discovery_fixture("tikhub-youtube-market-v1")
    )
    template_proposed = template.proposed_implementations[0]
    template_candidate = template.candidate_assertions[0]

    def parse(loaded: LoadedCapabilityDiscoveryFixture) -> CapabilityDiscoveryParserOutput:
        actual = real_parser(loaded)
        evidence = actual.evidence[0]
        evidence_ref = evidence.evidence_id
        source_claim_ref = f"claim:duplicate:{loaded.snapshot.fixture_id}"
        proposed = template_proposed.model_copy(
            update={"evidence_refs": [evidence_ref]},
            deep=True,
        )
        candidate = template_candidate.model_copy(
            update={
                "evidence_refs": [evidence_ref],
                "source_claim_refs": [source_claim_ref],
            },
            deep=True,
        )
        diagnostic = CapabilityDiscoveryDiagnostic(
            schema_version="capability_discovery_diagnostic.v1",
            fixture_id=loaded.snapshot.fixture_id,
            severity="info",
            code="source_claim_mapped",
            message="Source claim mapped to a candidate assertion.",
            source_claim_ref=source_claim_ref,
        )
        return CapabilityDiscoveryParserOutput(
            proposed_implementations=[proposed],
            candidate_assertions=[candidate],
            evidence=[evidence],
            diagnostics=[diagnostic],
        )

    return parse


def test_preview_is_order_independent_byte_stable_and_completely_fingerprinted() -> None:
    first = build_capability_discovery_preview(_request())
    repeated = build_capability_discovery_preview(_request())
    reversed_request = build_capability_discovery_preview(
        _request(list(reversed(FIXTURE_IDS)))
    )

    assert first.model_dump_json() == repeated.model_dump_json()
    assert first.model_dump_json() == reversed_request.model_dump_json()
    assert first.preview_fingerprint == repeated.preview_fingerprint

    body = first.model_dump(mode="json")
    body.pop("preview_fingerprint")
    assert first.preview_fingerprint == (
        f"sha256:{canonical_json_sha256(cast(JsonValue, body))}"
    )


def test_preview_sorts_every_collection_and_uses_max_observation_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    earlier = datetime(2026, 7, 13, 8, tzinfo=UTC)
    later = datetime(2026, 7, 15, 9, tzinfo=UTC)

    def load_fixture_set(
        fixture_ids: Sequence[str],
    ) -> list[LoadedCapabilityDiscoveryFixture]:
        loaded = [load_capability_discovery_fixture(item) for item in fixture_ids]
        loaded[0] = _with_observed_at(loaded[0], earlier)
        loaded[-1] = _with_observed_at(loaded[-1], later)
        return loaded

    monkeypatch.setattr(
        preview_module,
        "load_capability_discovery_fixtures",
        load_fixture_set,
    )
    response = build_capability_discovery_preview(_request(FIXTURE_IDS[:2]))

    assert response.generated_from_observed_at == later
    assert [item.fixture_id for item in response.source_snapshots] == sorted(
        item.fixture_id for item in response.source_snapshots
    )
    proposed_ids = [
        item.proposed_implementation_id for item in response.proposed_implementations
    ]
    assert proposed_ids == sorted(proposed_ids)
    assert [item.evidence_id for item in response.evidence] == sorted(
        item.evidence_id for item in response.evidence
    )
    candidate_keys = [
        (
            item.proposed_implementation_id,
            item.resource_type.value,
            item.operation.value,
            item.candidate_id,
        )
        for item in response.candidate_assertions
    ]
    diagnostic_keys = [
        (item.fixture_id, item.severity, item.code, item.source_claim_ref)
        for item in response.diagnostics
    ]
    assert candidate_keys == sorted(candidate_keys)
    assert diagnostic_keys == sorted(diagnostic_keys)


def test_preview_merges_identical_semantics_with_stable_references(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duplicate_parser = _duplicate_semantic_parser(parse_capability_discovery_fixture)
    monkeypatch.setattr(
        preview_module,
        "parse_capability_discovery_fixture",
        duplicate_parser,
    )

    response = build_capability_discovery_preview(_request(FIXTURE_IDS[:2]))

    assert len(response.proposed_implementations) == 1
    assert len(response.candidate_assertions) == 1
    assert len(response.evidence) == 2
    assert response.proposed_implementations[0].evidence_refs == sorted(
        item.evidence_id for item in response.evidence
    )
    assert response.candidate_assertions[0].evidence_refs == sorted(
        item.evidence_id for item in response.evidence
    )
    assert response.candidate_assertions[0].source_claim_refs == sorted(
        item.source_claim_ref for item in response.diagnostics
    )


def test_conflicting_proposed_implementation_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duplicate_parser = _duplicate_semantic_parser(parse_capability_discovery_fixture)

    def conflicting_parser(
        loaded: LoadedCapabilityDiscoveryFixture,
    ) -> CapabilityDiscoveryParserOutput:
        output = duplicate_parser(loaded)
        if loaded.snapshot.fixture_id == "apify-reddit-market-v1":
            proposed = output.proposed_implementations[0].model_copy(
                update={"claimed_auth_mode": "conflicting_auth_mode"},
                deep=True,
            )
            output = output.model_copy(
                update={"proposed_implementations": [proposed]},
                deep=True,
            )
        return output

    monkeypatch.setattr(
        preview_module,
        "parse_capability_discovery_fixture",
        conflicting_parser,
    )
    with pytest.raises(CapabilityDiscoveryContractInvalidError):
        build_capability_discovery_preview(_request(FIXTURE_IDS[:2]))


def test_conflicting_candidate_identity_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duplicate_parser = _duplicate_semantic_parser(parse_capability_discovery_fixture)

    def conflicting_parser(
        loaded: LoadedCapabilityDiscoveryFixture,
    ) -> CapabilityDiscoveryParserOutput:
        output = duplicate_parser(loaded)
        if loaded.snapshot.fixture_id == "apify-reddit-market-v1":
            candidate = output.candidate_assertions[0].model_copy(
                update={"claimed_field_contract": {"required": ["conflict"]}},
                deep=True,
            )
            output = output.model_copy(
                update={"candidate_assertions": [candidate]},
                deep=True,
            )
        return output

    monkeypatch.setattr(
        preview_module,
        "parse_capability_discovery_fixture",
        conflicting_parser,
    )
    with pytest.raises(CapabilityDiscoveryContractInvalidError):
        build_capability_discovery_preview(_request(FIXTURE_IDS[:2]))


@pytest.mark.parametrize(
    "broken_ref",
    ["proposed_evidence", "candidate_evidence", "candidate_proposed", "source_claim"],
)
def test_dangling_references_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    broken_ref: str,
) -> None:
    real_parser = parse_capability_discovery_fixture

    def dangling_parser(
        loaded: LoadedCapabilityDiscoveryFixture,
    ) -> CapabilityDiscoveryParserOutput:
        output = real_parser(loaded)
        proposed = output.proposed_implementations[0]
        candidate = output.candidate_assertions[0]
        if broken_ref == "proposed_evidence":
            proposed = proposed.model_copy(update={"evidence_refs": ["evidence:missing"]})
        elif broken_ref == "candidate_evidence":
            candidate = candidate.model_copy(update={"evidence_refs": ["evidence:missing"]})
        elif broken_ref == "candidate_proposed":
            candidate = candidate.model_copy(
                update={"proposed_implementation_id": "proposed:missing"}
            )
        else:
            candidate = candidate.model_copy(
                update={"source_claim_refs": ["claim:missing"]}
            )
        return output.model_copy(
            update={
                "proposed_implementations": [proposed],
                "candidate_assertions": [candidate],
            },
            deep=True,
        )

    monkeypatch.setattr(
        preview_module,
        "parse_capability_discovery_fixture",
        dangling_parser,
    )
    with pytest.raises(CapabilityDiscoveryContractInvalidError):
        build_capability_discovery_preview(_request([FIXTURE_IDS[0]]))


def test_parser_error_returns_no_partial_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_parser = parse_capability_discovery_fixture
    parsed_fixture_ids: list[str] = []

    def error_parser(
        loaded: LoadedCapabilityDiscoveryFixture,
    ) -> CapabilityDiscoveryParserOutput:
        parsed_fixture_ids.append(loaded.snapshot.fixture_id)
        output = real_parser(loaded)
        if len(parsed_fixture_ids) == 2:
            error = CapabilityDiscoveryDiagnostic(
                schema_version="capability_discovery_diagnostic.v1",
                fixture_id=loaded.snapshot.fixture_id,
                severity="error",
                code="parser_error",
                message="Parser contract failed.",
                source_claim_ref="claim:error",
            )
            return output.model_copy(
                update={"diagnostics": [*output.diagnostics, error]},
                deep=True,
            )
        return output

    monkeypatch.setattr(
        preview_module,
        "parse_capability_discovery_fixture",
        error_parser,
    )
    with pytest.raises(CapabilityDiscoveryContractInvalidError):
        build_capability_discovery_preview(_request(FIXTURE_IDS[:2]))
    assert len(parsed_fixture_ids) == 2


def test_success_boundaries_summary_and_catalog_independence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_catalog_call(*args: object, **kwargs: object) -> object:
        raise AssertionError("canonical catalog must not be read")

    monkeypatch.setattr(
        capability_catalog,
        "get_capability_catalog",
        forbidden_catalog_call,
    )
    response = build_capability_discovery_preview(_request())

    assert response.summary.model_dump() == {
        "source_count": 4,
        "market_source_count": 2,
        "official_doc_source_count": 2,
        "proposed_implementation_count": 4,
        "candidate_assertion_count": 7,
        "evidence_count": 4,
        "warning_count": 2,
        "error_count": 0,
    }
    assert response.provider_call is False
    assert response.provider_call_attempted is False
    assert response.actor_run is False
    assert response.browser_run is False
    assert response.llm_call is False
    assert response.credential_read_attempted is False
    assert response.database_write is False
    assert response.database_migration is False
    assert response.workflow_run_created is False
    assert response.candidate_publish_allowed is False
    assert response.production_write_allowed is False


def test_each_call_returns_fresh_nested_collections() -> None:
    first = build_capability_discovery_preview(_request())
    first.diagnostics.clear()
    second = build_capability_discovery_preview(_request())

    assert len(second.diagnostics) == 9
    assert second.summary.warning_count == 2


def test_preview_module_has_no_auth_session_repository_catalog_or_write_access() -> None:
    source = PREVIEW_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_import_fragments = (
        ".api.",
        ".auth",
        ".database",
        ".models",
        ".repositories",
        "data_intelligence_hub.services.capability_catalog",
        "sqlalchemy",
    )
    forbidden_calls = {"add", "commit", "delete", "execute", "flush", "open", "write"}

    assert "AuthContext" not in source
    assert "Session" not in source
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not any(fragment in alias.name for fragment in forbidden_import_fragments)
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            assert not any(
                fragment in node.module for fragment in forbidden_import_fragments
            )
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden_calls
            if isinstance(node.func, ast.Attribute):
                assert node.func.attr not in forbidden_calls
