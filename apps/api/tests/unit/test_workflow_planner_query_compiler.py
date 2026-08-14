from __future__ import annotations

import json
import socket
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import fields as dataclass_fields
from pathlib import Path
from typing import NoReturn

import httpx
import pytest
from pydantic import ValidationError

from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityOperation,
    PlatformId,
)
from data_intelligence_hub.schemas.workflow_planner import (
    CompiledPlatformQuery,
    NormalizedPlanningInput,
    PlanningInput,
    QueryTerm,
)
from data_intelligence_hub.services.workflow_planner.candidate_expansion import (
    DEFAULT_CANDIDATE_FIXTURE_PATH,
    CandidateExpansionFixture,
    FixtureCandidateExpansionAdapter,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import (
    canonical_json_bytes,
)
from data_intelligence_hub.services.workflow_planner.normalization import (
    NormalizationResult,
    normalize_planning_input,
)
from data_intelligence_hub.services.workflow_planner.query_compiler import (
    DeclarativePlatformQueryCompiler,
    QueryCompilationResult,
    build_query_terms,
    compile_platform_queries,
    default_platform_query_compilers,
)

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "workflow_planner"
PERIODIC_FIXTURE = FIXTURE_DIR / "periodic_monitoring_request_v1.json"
BATCH_FIXTURE = FIXTURE_DIR / "batch_research_request_v1.json"


def load_payload(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def normalize_payload(payload: dict[str, object]) -> NormalizationResult:
    return normalize_planning_input(PlanningInput.model_validate(payload))


@pytest.fixture()
def periodic_normalization() -> NormalizationResult:
    return normalize_payload(load_payload(PERIODIC_FIXTURE))


@pytest.fixture()
def batch_normalization() -> NormalizationResult:
    return normalize_payload(load_payload(BATCH_FIXTURE))


def compile_fixture_queries(
    normalization: NormalizationResult,
) -> QueryCompilationResult:
    adapter = FixtureCandidateExpansionAdapter.from_default_fixture()
    terms = build_query_terms(normalization, candidate_adapter=adapter)
    return compile_platform_queries(
        normalization,
        terms,
        compilers=default_platform_query_compilers(),
    )


def test_candidate_fixture_is_strict_and_schema_valid() -> None:
    fixture = CandidateExpansionFixture.model_validate_json(
        DEFAULT_CANDIDATE_FIXTURE_PATH.read_text(encoding="utf-8")
    )

    assert fixture.schema_version == "workflow_candidate_expansion_fixture.v1"
    assert fixture.version == "candidate-expansion.v1"
    assert CandidateExpansionFixture.model_json_schema()["type"] == "object"

    payload = json.loads(DEFAULT_CANDIDATE_FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["unknown_field"] = "forbidden"
    with pytest.raises(ValidationError):
        CandidateExpansionFixture.model_validate(payload)


def test_fixture_expansion_uses_only_the_normalized_canonical_term() -> None:
    payload = load_payload(PERIODIC_FIXTURE)
    scopes = payload["scopes"]
    assert isinstance(scopes, list)
    scope = scopes[0]
    assert isinstance(scope, dict)
    scope["canonical_term"] = "Unknown brand"
    scope["aliases"] = ["Acme"]
    payload["scopes"] = [scope]
    normalization = normalize_payload(payload)
    adapter = FixtureCandidateExpansionAdapter.from_default_fixture()

    assert adapter.expand(
        normalization.normalized_input.scopes[0],
        flow_mode=normalization.normalized_input.flow_mode,
    ) == []


def test_fixture_outputs_preserve_candidate_and_rejected_metadata(
    periodic_normalization: NormalizationResult,
) -> None:
    adapter = FixtureCandidateExpansionAdapter.from_default_fixture()
    brand_candidates = adapter.expand(
        periodic_normalization.normalized_input.scopes[0],
        flow_mode=periodic_normalization.normalized_input.flow_mode,
    )
    category_candidates = adapter.expand(
        periodic_normalization.normalized_input.scopes[1],
        flow_mode=periodic_normalization.normalized_input.flow_mode,
    )

    assert [(term.normalized_term, term.status) for term in brand_candidates] == [
        ("acme official", "candidate")
    ]
    assert [
        (term.normalized_term, term.status, term.score, term.conflict_codes)
        for term in category_candidates
    ] == [
        ("performance running footwear", "candidate", 0.75, []),
        ("shoe jobs", "rejected", 0.2, ["excluded_term_overlap"]),
    ]
    assert category_candidates[1].reason == (
        "Fixture candidate intentionally conflicting with exclusions"
    )
    assert category_candidates[1].source == "fixture:running-shoes"


def test_fixture_adapter_version_has_one_source_of_truth() -> None:
    fixture = CandidateExpansionFixture.model_validate_json(
        DEFAULT_CANDIDATE_FIXTURE_PATH.read_text(encoding="utf-8")
    )

    adapter = FixtureCandidateExpansionAdapter(fixture=fixture)

    assert adapter.version == fixture.version
    assert [field.name for field in dataclass_fields(adapter)] == ["fixture"]


def test_query_terms_use_stable_scope_ref_and_exclusion_precedence() -> None:
    payload = load_payload(PERIODIC_FIXTURE)
    scopes = payload["scopes"]
    assert isinstance(scopes, list)
    first = scopes[0]
    assert isinstance(first, dict)
    first["scope_ref"] = "scope-z"
    first["include_terms"] = ["Jobs"]
    duplicate = deepcopy(first)
    duplicate["scope_ref"] = "scope-a"
    payload["scopes"] = [first, duplicate]
    normalization = normalize_payload(payload)

    terms = build_query_terms(
        normalization,
        candidate_adapter=FixtureCandidateExpansionAdapter.from_default_fixture(),
    )

    assert {term.scope_ref for term in terms} == {"scope-a"}
    rejected = next(
        term
        for term in terms
        if term.origin == "include" and term.normalized_term == "jobs"
    )
    assert rejected.status == "rejected"
    assert rejected.reason == "excluded_term_precedence"
    assert rejected.conflict_codes == ["excluded_term_overlap"]
    assert terms == sorted(
        terms,
        key=lambda term: (
            term.scope_key,
            term.normalized_term,
            term.origin,
            term.term,
            term.source,
        ),
    )


def test_brand_include_is_rejected_when_every_anchor_is_excluded() -> None:
    payload = load_payload(PERIODIC_FIXTURE)
    scopes = payload["scopes"]
    assert isinstance(scopes, list)
    scope = scopes[0]
    assert isinstance(scope, dict)
    scope["canonical_term"] = "Acme"
    scope["aliases"] = ["Acme alias"]
    scope["official_accounts"] = ["@acme"]
    scope["include_terms"] = ["running shoes"]
    scope["exclude_terms"] = ["acme", "acme alias", "@acme"]
    payload["scopes"] = [scope]
    normalization = normalize_payload(payload)
    terms = build_query_terms(
        normalization,
        candidate_adapter=FixtureCandidateExpansionAdapter.from_default_fixture(),
    )

    anchors = [
        term
        for term in terms
        if term.origin in {"canonical", "alias", "official_account"}
    ]
    include = next(term for term in terms if term.origin == "include")
    result = compile_platform_queries(
        normalization,
        terms,
        compilers=default_platform_query_compilers(),
    )

    assert anchors and all(term.status == "rejected" for term in anchors)
    assert include.status == "rejected"
    assert include.reason == "brand_anchor_required"
    assert "running shoes" not in json.loads(
        result.compiled_queries[0].normalized_expression
    )["active_terms"]


def test_candidate_and_rejected_terms_never_enter_compiled_expression(
    periodic_normalization: NormalizationResult,
) -> None:
    result = compile_fixture_queries(periodic_normalization)
    blocked_terms = {
        term.normalized_term
        for term in result.query_terms
        if term.status in {"candidate", "rejected"}
    }

    assert blocked_terms
    for query in result.compiled_queries:
        expression = json.loads(query.normalized_expression)
        serialized = json.dumps(expression, ensure_ascii=False, sort_keys=True)
        assert blocked_terms.isdisjoint(expression["active_terms"])
        assert blocked_terms.isdisjoint(expression["accounts"])
        assert blocked_terms.isdisjoint(expression["url_inputs"])
        assert "performance running footwear" not in serialized
        assert "shoe jobs" not in serialized
        assert query.normalized_expression == canonical_json_bytes(expression).decode()


def test_every_platform_has_a_stable_declarative_version() -> None:
    compilers = default_platform_query_compilers()

    assert set(compilers) == set(PlatformId)
    assert {compiler.query_version for compiler in compilers.values()} == {
        f"{platform.value}.declarative.v1" for platform in PlatformId
    }


def test_only_requested_platforms_are_compiled_and_versioned(
    periodic_normalization: NormalizationResult,
) -> None:
    result = compile_fixture_queries(periodic_normalization)

    assert set(result.query_versions) == {PlatformId.YOUTUBE}
    assert result.query_versions[PlatformId.YOUTUBE] == "youtube.declarative.v1"
    assert {query.platform for query in result.compiled_queries} == {
        PlatformId.YOUTUBE
    }
    assert all(query.scope_keys == sorted(query.scope_keys) for query in result.compiled_queries)


def test_missing_compiler_retains_failure_and_limitation(
    batch_normalization: NormalizationResult,
) -> None:
    adapter = FixtureCandidateExpansionAdapter.from_default_fixture()
    terms = build_query_terms(batch_normalization, candidate_adapter=adapter)
    compilers = default_platform_query_compilers()
    del compilers[PlatformId.REDDIT]

    result = compile_platform_queries(
        batch_normalization,
        terms,
        compilers=compilers,
    )

    assert result.compiled_queries == ()
    assert result.query_versions == {}
    assert result.limitations == ("compiler_missing:reddit",)
    assert len(result.compiler_failures) == 1
    failure = result.compiler_failures[0]
    assert failure.platform is PlatformId.REDDIT
    assert failure.code == "compiler_missing"
    assert failure.scope_keys == sorted(failure.scope_keys)
    assert failure.reason == "Query compiler missing for reddit"


class ExplodingCompiler:
    platform = PlatformId.YOUTUBE
    query_version = "youtube.exploding.v1"

    def compile(
        self,
        normalized_input: NormalizedPlanningInput,
        query_terms: Sequence[QueryTerm],
    ) -> list[CompiledPlatformQuery]:
        del normalized_input, query_terms
        raise RuntimeError("compiler exploded")


class RecordingCompiler:
    platform = PlatformId.YOUTUBE
    query_version = "youtube.recording.v1"

    def __init__(self) -> None:
        self.received_terms: tuple[QueryTerm, ...] = ()

    def compile(
        self,
        normalized_input: NormalizedPlanningInput,
        query_terms: Sequence[QueryTerm],
    ) -> list[CompiledPlatformQuery]:
        self.received_terms = tuple(query_terms)
        delegate = DeclarativePlatformQueryCompiler(
            platform=self.platform,
            query_version=self.query_version,
        )
        return delegate.compile(normalized_input, query_terms)


class PlatformRecordingCompiler:
    def __init__(self, platform: PlatformId) -> None:
        self.platform = platform
        self.query_version = f"{platform.value}.recording.v1"
        self.received_terms: tuple[QueryTerm, ...] = ()

    def compile(
        self,
        normalized_input: NormalizedPlanningInput,
        query_terms: Sequence[QueryTerm],
    ) -> list[CompiledPlatformQuery]:
        self.received_terms = tuple(query_terms)
        delegate = DeclarativePlatformQueryCompiler(
            platform=self.platform,
            query_version=self.query_version,
        )
        return delegate.compile(normalized_input, query_terms)


class MalformedCompiler:
    platform = PlatformId.YOUTUBE
    query_version = "youtube.malformed.v1"

    def __init__(self, mutation: str) -> None:
        self.mutation = mutation

    def compile(
        self,
        normalized_input: NormalizedPlanningInput,
        query_terms: Sequence[QueryTerm],
    ) -> list[CompiledPlatformQuery]:
        delegate = DeclarativePlatformQueryCompiler(
            platform=self.platform,
            query_version=self.query_version,
        )
        query = delegate.compile(normalized_input, query_terms)[0]
        updates: dict[str, object]
        if self.mutation == "platform":
            updates = {"platform": PlatformId.REDDIT}
        elif self.mutation == "query_version":
            updates = {"query_version": "youtube.other.v1"}
        elif self.mutation == "empty_scope_keys":
            updates = {"scope_keys": []}
        elif self.mutation == "foreign_scope_key":
            updates = {"scope_keys": [f"sha256:{'f' * 64}"]}
        elif self.mutation == "source_scope_refs":
            updates = {"source_scope_refs": ["foreign-scope-ref"]}
        else:
            raise AssertionError(f"unknown mutation: {self.mutation}")
        return [query.model_copy(update=updates)]


def test_injected_compiler_receives_only_active_query_terms(
    periodic_normalization: NormalizationResult,
) -> None:
    terms = build_query_terms(
        periodic_normalization,
        candidate_adapter=FixtureCandidateExpansionAdapter.from_default_fixture(),
    )
    compiler = RecordingCompiler()

    result = compile_platform_queries(
        periodic_normalization,
        terms,
        compilers={PlatformId.YOUTUBE: compiler},
    )

    assert compiler.received_terms
    assert all(term.status == "active" for term in compiler.received_terms)
    assert any(term.status == "candidate" for term in result.query_terms)
    assert any(term.status == "rejected" for term in result.query_terms)


def test_each_platform_compiler_receives_only_its_active_scope_terms() -> None:
    payload = load_payload(PERIODIC_FIXTURE)
    scopes = payload["scopes"]
    assert isinstance(scopes, list)
    first, second = scopes
    assert isinstance(first, dict)
    assert isinstance(second, dict)
    first["platforms"] = ["youtube"]
    second["platforms"] = ["reddit"]
    payload["default_platforms"] = []
    normalization = normalize_payload(payload)
    terms = build_query_terms(
        normalization,
        candidate_adapter=FixtureCandidateExpansionAdapter.from_default_fixture(),
    )
    youtube = PlatformRecordingCompiler(PlatformId.YOUTUBE)
    reddit = PlatformRecordingCompiler(PlatformId.REDDIT)

    compile_platform_queries(
        normalization,
        terms,
        compilers={
            PlatformId.YOUTUBE: youtube,
            PlatformId.REDDIT: reddit,
        },
    )

    requested_scope_keys = {
        platform: {
            scope.scope_key
            for scope in normalization.normalized_input.scopes
            if platform in scope.effective_platforms
        }
        for platform in (PlatformId.YOUTUBE, PlatformId.REDDIT)
    }
    for platform, compiler in (
        (PlatformId.YOUTUBE, youtube),
        (PlatformId.REDDIT, reddit),
    ):
        assert compiler.received_terms
        assert all(term.status == "active" for term in compiler.received_terms)
        assert {
            term.scope_key for term in compiler.received_terms
        } <= requested_scope_keys[platform]
    assert requested_scope_keys[PlatformId.YOUTUBE].isdisjoint(
        requested_scope_keys[PlatformId.REDDIT]
    )


@pytest.mark.parametrize(
    ("mutation", "error_code"),
    [
        ("platform", "query_compiler_output_platform_mismatch"),
        ("query_version", "query_compiler_output_version_mismatch"),
        ("empty_scope_keys", "query_compiler_output_scope_keys_empty"),
        ("foreign_scope_key", "query_compiler_output_scope_keys_invalid"),
        ("source_scope_refs", "query_compiler_output_source_refs_mismatch"),
    ],
)
def test_injected_compiler_output_must_match_requested_normalized_scopes(
    mutation: str,
    error_code: str,
) -> None:
    payload = load_payload(PERIODIC_FIXTURE)
    scopes = payload["scopes"]
    assert isinstance(scopes, list)
    payload["scopes"] = [scopes[0]]
    normalization = normalize_payload(payload)
    terms = build_query_terms(
        normalization,
        candidate_adapter=FixtureCandidateExpansionAdapter.from_default_fixture(),
    )

    with pytest.raises(ValueError, match=error_code):
        compile_platform_queries(
            normalization,
            terms,
            compilers={PlatformId.YOUTUBE: MalformedCompiler(mutation)},
        )


def test_compiler_runtime_error_is_not_converted_to_missing(
    periodic_normalization: NormalizationResult,
) -> None:
    adapter = FixtureCandidateExpansionAdapter.from_default_fixture()
    terms = build_query_terms(periodic_normalization, candidate_adapter=adapter)

    with pytest.raises(RuntimeError, match="compiler exploded"):
        compile_platform_queries(
            periodic_normalization,
            terms,
            compilers={PlatformId.YOUTUBE: ExplodingCompiler()},
        )


def test_unknown_fixture_term_adds_stateless_semantic_trace() -> None:
    adapter = FixtureCandidateExpansionAdapter.from_default_fixture()
    payload = load_payload(PERIODIC_FIXTURE)
    scopes = payload["scopes"]
    assert isinstance(scopes, list)
    first = scopes[0]
    assert isinstance(first, dict)
    first["canonical_term"] = "Unknown brand"
    first["aliases"] = []
    payload["scopes"] = [first]
    unknown_normalization = normalize_payload(payload)
    unknown_terms = build_query_terms(
        unknown_normalization,
        candidate_adapter=adapter,
    )
    unknown_result = compile_platform_queries(
        unknown_normalization,
        unknown_terms,
        compilers=default_platform_query_compilers(),
    )

    known_result = compile_fixture_queries(
        normalize_payload(load_payload(PERIODIC_FIXTURE))
    )

    no_matches = [
        entry
        for entry in unknown_result.semantic_entries
        if entry.code == "fixture_expansion_no_match"
    ]
    assert len(no_matches) == 1
    assert no_matches[0].scope_keys == [
        unknown_normalization.normalized_input.scopes[0].scope_key
    ]
    assert not any(
        entry.code == "fixture_expansion_no_match"
        and entry.scope_keys == no_matches[0].scope_keys
        for entry in known_result.semantic_entries
    )


def test_scope_and_platform_input_order_do_not_change_compiled_queries() -> None:
    payload = load_payload(PERIODIC_FIXTURE)
    scopes = payload["scopes"]
    assert isinstance(scopes, list)
    for scope in scopes:
        assert isinstance(scope, dict)
        scope["platforms"] = ["reddit", "youtube"]
    payload["default_platforms"] = ["youtube", "reddit"]
    first = compile_fixture_queries(normalize_payload(deepcopy(payload)))

    reversed_payload = deepcopy(payload)
    reversed_scopes = reversed_payload["scopes"]
    assert isinstance(reversed_scopes, list)
    reordered_scopes = list(reversed(reversed_scopes))
    reversed_payload["scopes"] = reordered_scopes
    for scope in reordered_scopes:
        assert isinstance(scope, dict)
        platforms = scope["platforms"]
        assert isinstance(platforms, list)
        scope["platforms"] = list(reversed(platforms))
    reversed_payload["default_platforms"] = ["reddit", "youtube"]
    second = compile_fixture_queries(normalize_payload(reversed_payload))

    assert [query.model_dump(mode="json") for query in first.compiled_queries] == [
        query.model_dump(mode="json") for query in second.compiled_queries
    ]
    assert dict(first.query_versions) == dict(second.query_versions)


def test_adapter_reads_only_the_local_default_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[Path] = []
    original_read_text = Path.read_text

    def tracked_read_text(
        path: Path,
        encoding: str | None = None,
        errors: str | None = None,
    ) -> str:
        opened.append(path)
        assert path == DEFAULT_CANDIDATE_FIXTURE_PATH
        return original_read_text(path, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", tracked_read_text)

    FixtureCandidateExpansionAdapter.from_default_fixture()

    assert opened == [DEFAULT_CANDIDATE_FIXTURE_PATH]


def test_fixture_compilation_never_uses_network(
    periodic_normalization: NormalizationResult,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_network(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        raise AssertionError("workflow planner compilation attempted network I/O")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    monkeypatch.setattr(httpx.Client, "request", fail_network)
    monkeypatch.setattr(httpx.AsyncClient, "request", fail_network)

    result = compile_fixture_queries(periodic_normalization)

    assert result.compiled_queries
    assert all(
        "declarative_preview_only" in query.limitations
        for query in result.compiled_queries
    )


def test_seed_url_only_input_does_not_fabricate_resolve_capability() -> None:
    payload = load_payload(BATCH_FIXTURE)
    scopes = payload["scopes"]
    assert isinstance(scopes, list)
    scope = scopes[0]
    assert isinstance(scope, dict)
    scope["canonical_term"] = None
    scope["aliases"] = []
    scope["include_terms"] = []
    scope["official_accounts"] = []
    scope["seed_urls"] = ["https://www.reddit.com/r/demo"]
    scope["platforms"] = []
    payload["default_platforms"] = []
    result = compile_fixture_queries(normalize_payload(payload))

    assert all(
        query.operation is CapabilityOperation.SEARCH_DISCOVER
        for query in result.compiled_queries
    )
    assert all(
        query.operation
        not in {CapabilityOperation.RESOLVE_DETAIL, CapabilityOperation.BATCH_PARSE}
        for query in result.compiled_queries
    )
