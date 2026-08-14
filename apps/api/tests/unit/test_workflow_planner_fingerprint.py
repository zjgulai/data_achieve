from __future__ import annotations

import ast
import json
import math
from collections.abc import Callable, Iterator, Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import cast
from uuid import UUID

import pytest
from pydantic import JsonValue

from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityCatalog,
    CapabilityConstraint,
    ConstraintSeverity,
    PlatformId,
)
from data_intelligence_hub.schemas.workflow_planner import (
    CompiledPlatformQuery,
    MatchMode,
    NormalizedPlanningInput,
    PlanningInput,
    QueryTerm,
    WorkflowPlanFingerprintPayload,
    WorkflowPlanPreview,
)
from data_intelligence_hub.services.capability_catalog import (
    clear_capability_catalog_cache,
    get_capability_catalog,
)
from data_intelligence_hub.services.workflow_planner.candidate_expansion import (
    FixtureCandidateExpansionAdapter,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import (
    build_preview_fingerprint_payload,
    compute_catalog_snapshot_id,
    compute_preview_fingerprint,
)
from data_intelligence_hub.services.workflow_planner.normalization import (
    normalize_planning_input,
)
from data_intelligence_hub.services.workflow_planner.planner import (
    build_workflow_plan_preview,
    build_workflow_plan_result,
)
from data_intelligence_hub.services.workflow_planner.query_compiler import (
    DeclarativePlatformQueryCompiler,
    build_query_terms,
)

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "workflow_planner"
PERIODIC_FIXTURE = FIXTURE_DIR / "periodic_monitoring_request_v1.json"
PROJECT_ID = UUID("00000000-0000-0000-0000-000000000001")
GENERATED_AT = datetime(2026, 7, 12, tzinfo=UTC)
FORBIDDEN_FINGERPRINT_KEYS = {
    "generated_at",
    "input_diagnostics",
    "project_id",
    "request_id",
    "scope_ref",
    "scope_ref_map",
    "source_scope_refs",
}
FORBIDDEN_IMPORT_ROOTS = {
    "anthropic",
    "boto3",
    "browsers",
    "httpx",
    "openai",
    "requests",
    "selenium",
    "sqlalchemy",
}
FORBIDDEN_IMPORT_FRAGMENTS = (
    ".api.",
    ".collectors",
    ".database",
    ".db",
    ".llm",
    ".models",
    ".repositories",
    ".settings",
)


@pytest.fixture(autouse=True)
def isolate_capability_catalog_cache() -> Iterator[None]:
    clear_capability_catalog_cache()
    yield
    clear_capability_catalog_cache()


def load_periodic_payload() -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads(PERIODIC_FIXTURE.read_text(encoding="utf-8")),
    )


def build_periodic_preview(
    *,
    payload: dict[str, object] | None = None,
    project_id: UUID = PROJECT_ID,
    generated_at: datetime = GENERATED_AT,
    request_id: str = "request-1",
    catalog: CapabilityCatalog | None = None,
) -> WorkflowPlanPreview:
    return build_workflow_plan_preview(
        project_id=project_id,
        planning_input=PlanningInput.model_validate(payload or load_periodic_payload()),
        catalog=catalog or get_capability_catalog(),
        generated_at=generated_at,
        request_id=request_id,
    )


def test_internal_build_result_preserves_preview_and_exact_fingerprint_payload() -> None:
    planning_input = PlanningInput.model_validate(load_periodic_payload())
    catalog = get_capability_catalog()
    result = build_workflow_plan_result(
        project_id=PROJECT_ID,
        planning_input=planning_input,
        catalog=catalog,
        generated_at=GENERATED_AT,
        request_id="request-1",
    )
    preview = build_workflow_plan_preview(
        project_id=PROJECT_ID,
        planning_input=planning_input,
        catalog=catalog,
        generated_at=GENERATED_AT,
        request_id="request-1",
    )

    assert result.preview == preview
    assert compute_preview_fingerprint(result.fingerprint_payload) == (
        preview.preview_fingerprint
    )
    assert result.preview.database_write is False
    assert result.preview.provider_call is False


def fingerprint_payload_for_preview(
    preview: WorkflowPlanPreview,
    planning_input: PlanningInput,
    *,
    fingerprint_input: Mapping[str, JsonValue] | None = None,
    compiled_queries: Sequence[CompiledPlatformQuery] | None = None,
) -> WorkflowPlanFingerprintPayload:
    adapter = FixtureCandidateExpansionAdapter.from_default_fixture()
    normalization = normalize_planning_input(planning_input)
    return build_preview_fingerprint_payload(
        planner_contract_version=preview.planner_contract_version,
        fingerprint_input=(
            normalization.fingerprint_input
            if fingerprint_input is None
            else fingerprint_input
        ),
        catalog_snapshot_id=preview.catalog_snapshot_id,
        policy_version=preview.policy_version,
        mode_template_version=preview.mode_template_version,
        query_versions=preview.query_versions,
        candidate_fixture_version=adapter.version,
        query_terms=preview.query_terms,
        steps=preview.steps,
        compiled_queries=(
            preview.compiled_queries
            if compiled_queries is None
            else compiled_queries
        ),
        route_plans=preview.route_plans,
        coverage=preview.coverage,
        budget_summary=preview.budget_summary,
        limitations=preview.limitations,
        semantic_decision_trace=preview.decision_trace.semantic_entries,
    )


def nested_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(
            *(nested_keys(nested) for nested in value.values()),
        )
    if isinstance(value, list):
        return set().union(*(nested_keys(item) for item in value))
    return set()


class TransformingYouTubeCompiler:
    platform = PlatformId.YOUTUBE
    query_version = "youtube.declarative.v1"

    def __init__(
        self,
        transform: Callable[[CompiledPlatformQuery], CompiledPlatformQuery],
    ) -> None:
        self._transform = transform

    def compile(
        self,
        normalized_input: NormalizedPlanningInput,
        query_terms: Sequence[QueryTerm],
    ) -> list[CompiledPlatformQuery]:
        delegate = DeclarativePlatformQueryCompiler(
            platform=self.platform,
            query_version=self.query_version,
        )
        return [
            self._transform(query)
            for query in delegate.compile(normalized_input, query_terms)
        ]


def build_with_injected_compiler(
    transform: Callable[[CompiledPlatformQuery], CompiledPlatformQuery],
) -> WorkflowPlanPreview:
    return build_workflow_plan_preview(
        project_id=PROJECT_ID,
        planning_input=PlanningInput.model_validate(load_periodic_payload()),
        catalog=get_capability_catalog(),
        generated_at=GENERATED_AT,
        request_id="injected-compiler",
        query_compilers={
            PlatformId.YOUTUBE: TransformingYouTubeCompiler(transform),
        },
    )


def replace_expression(
    query: CompiledPlatformQuery,
    expression: object,
) -> CompiledPlatformQuery:
    return query.model_copy(
        update={
            "normalized_expression": json.dumps(
                expression,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        },
        deep=True,
    )


def test_catalog_snapshot_ignores_only_top_level_generated_at() -> None:
    catalog = get_capability_catalog()
    shifted = catalog.model_copy(
        update={"generated_at": catalog.generated_at + timedelta(days=1)},
        deep=True,
    )
    assert compute_catalog_snapshot_id(catalog) == compute_catalog_snapshot_id(shifted)

    evidence = catalog.evidence[0]
    changed_evidence = evidence.model_copy(
        update={"observed_at": evidence.observed_at + timedelta(seconds=1)},
        deep=True,
    )
    changed = catalog.model_copy(
        update={"evidence": [changed_evidence, *catalog.evidence[1:]]},
        deep=True,
    )
    assert compute_catalog_snapshot_id(catalog) != compute_catalog_snapshot_id(changed)


def test_catalog_snapshot_normalizes_top_level_and_set_like_order() -> None:
    catalog = get_capability_catalog()
    implementation = catalog.implementations[0]
    assertion = catalog.assertions[0]
    first_constraint = CapabilityConstraint(
        constraint_type="policy",
        severity=ConstraintSeverity.BLOCKING,
        code="z-policy",
        details={"z": 1, "a": ["b", "a"]},
    )
    second_constraint = CapabilityConstraint(
        constraint_type="blocked_action",
        severity=ConstraintSeverity.BLOCKING,
        code="a-action",
        details={"nested": {"z": 2, "a": 1}},
    )

    def reordered(reverse: bool) -> CapabilityCatalog:
        implementations = list(reversed(catalog.implementations))
        assertions = list(reversed(catalog.assertions))
        evidence = list(reversed(catalog.evidence))
        replacement_implementation = implementation.model_copy(
            update={
                "blocked_actions": ["z", "a"][:: -1 if reverse else 1],
                "data_domains": ["z", "a"][:: -1 if reverse else 1],
                "official_docs": ["fixture://z", "fixture://a"][:: -1 if reverse else 1],
                "policy_flags": ["z", "a"][:: -1 if reverse else 1],
                "required_credentials": ["z", "a"][:: -1 if reverse else 1],
                "resource_groups": ["z", "a"][:: -1 if reverse else 1],
                "supported_endpoints": ["z", "a"][:: -1 if reverse else 1],
            },
            deep=True,
        )
        replacement_assertion = assertion.model_copy(
            update={
                "auth_scope": ["z", "a"][:: -1 if reverse else 1],
                "constraints": (
                    [second_constraint, first_constraint]
                    if reverse
                    else [first_constraint, second_constraint]
                ),
                "evidence_refs": list(reversed(assertion.evidence_refs))
                if reverse
                else list(assertion.evidence_refs),
                "purpose_scope": ["z", "a"][:: -1 if reverse else 1],
                "region_scope": ["z", "a"][:: -1 if reverse else 1],
            },
            deep=True,
        )
        implementations = [
            replacement_implementation
            if item.implementation_id == implementation.implementation_id
            else item
            for item in implementations
        ]
        assertions = [
            replacement_assertion if item.assertion_id == assertion.assertion_id else item
            for item in assertions
        ]
        return catalog.model_copy(
            update={
                "implementations": implementations,
                "assertions": assertions,
                "evidence": evidence,
            },
            deep=True,
        )

    assert compute_catalog_snapshot_id(reordered(False)) == compute_catalog_snapshot_id(
        reordered(True)
    )


@pytest.mark.parametrize(
    ("collection", "field_name", "changed_value"),
    [
        ("implementations", "api_version", "semantic-change.v2"),
        ("assertions", "source_resource_group", "semantic-change"),
        ("evidence", "source_version", "semantic-change.v2"),
    ],
)
def test_catalog_snapshot_changes_for_semantic_content(
    collection: str,
    field_name: str,
    changed_value: str,
) -> None:
    catalog = get_capability_catalog()
    items = list(getattr(catalog, collection))
    items[0] = items[0].model_copy(update={field_name: changed_value}, deep=True)
    changed = catalog.model_copy(update={collection: items}, deep=True)

    snapshot_id = compute_catalog_snapshot_id(changed)
    assert snapshot_id != compute_catalog_snapshot_id(catalog)
    assert snapshot_id.startswith("sha256:")
    assert len(snapshot_id) == 71


def test_catalog_snapshot_changes_for_constraint_semantics() -> None:
    catalog = get_capability_catalog()
    assertion = catalog.assertions[0]
    first_constraint = CapabilityConstraint(
        constraint_type="policy",
        severity=ConstraintSeverity.BLOCKING,
        code="fixture-policy",
        details={"mode": "first"},
    )
    second_constraint = first_constraint.model_copy(
        update={"details": {"mode": "second"}},
        deep=True,
    )
    first_assertion = assertion.model_copy(
        update={"constraints": [first_constraint]},
        deep=True,
    )
    second_assertion = assertion.model_copy(
        update={"constraints": [second_constraint]},
        deep=True,
    )
    first = catalog.model_copy(
        update={"assertions": [first_assertion, *catalog.assertions[1:]]},
        deep=True,
    )
    second = catalog.model_copy(
        update={"assertions": [second_assertion, *catalog.assertions[1:]]},
        deep=True,
    )

    assert compute_catalog_snapshot_id(first) != compute_catalog_snapshot_id(second)


@pytest.mark.parametrize(
    "non_finite",
    [math.nan, math.inf, -math.inf],
    ids=["nan", "positive-infinity", "negative-infinity"],
)
def test_catalog_snapshot_rejects_non_finite_values_in_any_subtree(
    non_finite: float,
) -> None:
    catalog = get_capability_catalog()
    assertion = catalog.assertions[0]
    constraint = CapabilityConstraint(
        constraint_type="policy",
        severity=ConstraintSeverity.BLOCKING,
        code="non-finite-review-fixture",
        details={"nested": {"value": 0.0}},
    ).model_copy(
        update={"details": {"nested": {"value": non_finite}}},
        deep=True,
    )
    changed_assertion = assertion.model_copy(
        update={"constraints": [constraint, *assertion.constraints]},
        deep=True,
    )
    changed_catalog = catalog.model_copy(
        update={"assertions": [changed_assertion, *catalog.assertions[1:]]},
        deep=True,
    )

    with pytest.raises(ValueError, match="catalog_snapshot_non_finite_value"):
        compute_catalog_snapshot_id(changed_catalog)


@pytest.mark.parametrize(
    "mutation",
    [
        "non_object",
        "extra_key",
        "nested_forbidden_reference",
        "platform_mismatch",
        "match_mode_invalid",
        "active_terms_mismatch",
        "exclusions_mismatch",
        "accounts_mismatch",
        "url_inputs_mismatch",
    ],
)
def test_injected_compiler_expression_contract_fails_fast(mutation: str) -> None:
    def transform(query: CompiledPlatformQuery) -> CompiledPlatformQuery:
        if mutation == "non_object":
            return replace_expression(query, ["not-an-object"])

        expression = cast(
            dict[str, object],
            json.loads(query.normalized_expression),
        )
        if mutation == "extra_key":
            expression["unexpected"] = "not-allowed"
        elif mutation == "nested_forbidden_reference":
            expression["active_terms"] = [
                {"nested": {"scope_ref": "must-not-enter-fingerprint"}}
            ]
        elif mutation == "platform_mismatch":
            expression["platform"] = PlatformId.REDDIT.value
        elif mutation == "match_mode_invalid":
            expression["match_mode"] = "not-a-match-mode"
        else:
            expression_field = {
                "active_terms_mismatch": "active_terms",
                "exclusions_mismatch": "exclusions",
                "accounts_mismatch": "accounts",
                "url_inputs_mismatch": "url_inputs",
            }[mutation]
            expression[expression_field] = [
                *cast(list[str], expression[expression_field]),
                "expression-only-value",
            ]
        return replace_expression(query, expression)

    with pytest.raises(ValueError, match="compiled_query_expression"):
        build_with_injected_compiler(transform)


def test_injected_compiler_match_mode_must_match_corresponding_scope() -> None:
    def transform(query: CompiledPlatformQuery) -> CompiledPlatformQuery:
        expression = cast(
            dict[str, object],
            json.loads(query.normalized_expression),
        )
        current = MatchMode(cast(str, expression["match_mode"]))
        expression["match_mode"] = (
            MatchMode.EXACT.value
            if current is not MatchMode.EXACT
            else MatchMode.PHRASE.value
        )
        return replace_expression(query, expression)

    with pytest.raises(
        ValueError,
        match="compiled_query_expression_match_mode_mismatch",
    ):
        build_with_injected_compiler(transform)


def test_compiled_query_scope_key_must_exist_in_fingerprint_input() -> None:
    planning_input = PlanningInput.model_validate(load_periodic_payload())
    normalization = normalize_planning_input(planning_input)
    preview = build_periodic_preview()
    fingerprint_input = deepcopy(normalization.fingerprint_input)
    query_scope_key = preview.compiled_queries[0].scope_keys[0]
    scopes = cast(list[dict[str, JsonValue]], fingerprint_input["scopes"])
    fingerprint_input["scopes"] = [
        scope for scope in scopes if scope["scope_key"] != query_scope_key
    ]

    with pytest.raises(ValueError, match="compiled_query_scope_key_missing"):
        fingerprint_payload_for_preview(
            preview,
            planning_input,
            fingerprint_input=fingerprint_input,
        )


def test_compiled_query_scope_keys_must_share_one_match_mode() -> None:
    planning_input = PlanningInput.model_validate(load_periodic_payload())
    normalization = normalize_planning_input(planning_input)
    preview = build_periodic_preview()
    scopes = cast(
        list[dict[str, JsonValue]],
        normalization.fingerprint_input["scopes"],
    )
    scope_keys = sorted(cast(str, scope["scope_key"]) for scope in scopes)
    assert len({scope["match_mode"] for scope in scopes}) > 1
    combined_query = preview.compiled_queries[0].model_copy(
        update={"scope_keys": scope_keys},
        deep=True,
    )

    with pytest.raises(ValueError, match="compiled_query_scope_match_mode_conflict"):
        fingerprint_payload_for_preview(
            preview,
            planning_input,
            compiled_queries=[combined_query, *preview.compiled_queries[1:]],
        )


@pytest.mark.parametrize(
    ("term_status", "typed_field", "expression_field"),
    [
        ("candidate", "include_terms", "active_terms"),
        ("candidate", "account_filters", "accounts"),
        ("candidate", "url_inputs", "url_inputs"),
        ("rejected", "include_terms", "active_terms"),
        ("rejected", "account_filters", "accounts"),
        ("rejected", "url_inputs", "url_inputs"),
    ],
)
def test_injected_compiler_cannot_promote_non_active_query_terms(
    term_status: str,
    typed_field: str,
    expression_field: str,
) -> None:
    planning_input = PlanningInput.model_validate(load_periodic_payload())
    normalization = normalize_planning_input(planning_input)
    query_terms = build_query_terms(
        normalization,
        candidate_adapter=FixtureCandidateExpansionAdapter.from_default_fixture(),
    )
    target = next(term for term in query_terms if term.status == term_status)

    def transform(query: CompiledPlatformQuery) -> CompiledPlatformQuery:
        if target.scope_key not in query.scope_keys:
            return query
        typed_values = {
            "include_terms": query.include_terms,
            "account_filters": query.account_filters,
            "url_inputs": query.url_inputs,
        }[typed_field]
        changed_values = sorted({*typed_values, target.normalized_term})
        expression = cast(
            dict[str, object],
            json.loads(query.normalized_expression),
        )
        expression[expression_field] = changed_values
        return replace_expression(query, expression).model_copy(
            update={typed_field: changed_values},
            deep=True,
        )

    with pytest.raises(ValueError, match="compiled_query_typed_input_not_active"):
        build_with_injected_compiler(transform)


def test_scope_ref_project_and_runtime_metadata_do_not_change_fingerprint() -> None:
    first_payload = load_periodic_payload()
    second_payload = deepcopy(first_payload)
    scopes = cast(list[dict[str, object]], second_payload["scopes"])
    scopes[0]["scope_ref"] = "renamed-scope"

    first = build_periodic_preview(payload=first_payload, request_id="request-1")
    second = build_periodic_preview(
        payload=second_payload,
        project_id=UUID("00000000-0000-0000-0000-000000000002"),
        generated_at=GENERATED_AT + timedelta(days=1),
        request_id="request-2",
    )

    assert first.preview_fingerprint == second.preview_fingerprint
    assert first.project_id != second.project_id
    assert first.generated_at != second.generated_at
    assert first.request_id != second.request_id
    assert first.scope_ref_map != second.scope_ref_map


def test_scope_order_list_order_and_case_do_not_change_fingerprint() -> None:
    first_payload = load_periodic_payload()
    second_payload = deepcopy(first_payload)
    scopes = cast(list[dict[str, object]], second_payload["scopes"])
    scopes.reverse()
    for scope in scopes:
        if isinstance(scope.get("canonical_term"), str):
            scope["canonical_term"] = f"  {cast(str, scope['canonical_term']).swapcase()}  "
        for field in ("aliases", "include_terms", "exclude_terms"):
            values = cast(list[str], scope[field])
            scope[field] = [f"  {value.swapcase()}  " for value in reversed(values)]

    first = build_periodic_preview(payload=first_payload)
    second = build_periodic_preview(payload=second_payload)
    assert first.preview_fingerprint == second.preview_fingerprint


def test_semantic_input_and_catalog_changes_change_preview_fingerprint() -> None:
    first_payload = load_periodic_payload()
    changed_payload = deepcopy(first_payload)
    scopes = cast(list[dict[str, object]], changed_payload["scopes"])
    scopes[0]["canonical_term"] = "different brand"

    catalog = get_capability_catalog()
    assertion = catalog.assertions[0]
    changed_assertion = assertion.model_copy(
        update={"source_resource_group": "semantic-change"},
        deep=True,
    )
    changed_catalog = catalog.model_copy(
        update={"assertions": [changed_assertion, *catalog.assertions[1:]]},
        deep=True,
    )

    baseline = build_periodic_preview(payload=first_payload, catalog=catalog)
    semantic_input = build_periodic_preview(payload=changed_payload, catalog=catalog)
    semantic_catalog = build_periodic_preview(
        payload=first_payload,
        catalog=changed_catalog,
    )
    assert baseline.preview_fingerprint != semantic_input.preview_fingerprint
    assert baseline.preview_fingerprint != semantic_catalog.preview_fingerprint


def test_fingerprint_payload_is_explicitly_reference_free() -> None:
    planning_input = PlanningInput.model_validate(load_periodic_payload())
    preview = build_periodic_preview()
    payload = fingerprint_payload_for_preview(preview, planning_input)
    dumped = payload.model_dump(mode="json")

    assert not (nested_keys(dumped) & FORBIDDEN_FINGERPRINT_KEYS)
    assert all(
        term.term == term.normalized_term for term in payload.semantic_query_terms
    )
    assert compute_preview_fingerprint(payload) == preview.preview_fingerprint


@pytest.mark.parametrize(
    ("field_name", "changed_value"),
    [
        ("planner_contract_version", "workflow_planner.v2"),
        ("policy_version", "market_monitoring_balanced.v2"),
        ("mode_template_version", "periodic_monitoring.v2"),
        ("candidate_fixture_version", "candidate-expansion.v2"),
        (
            "query_versions",
            {PlatformId.YOUTUBE: "youtube.declarative.v2"},
        ),
    ],
)
def test_every_version_input_changes_fingerprint(
    field_name: str,
    changed_value: object,
) -> None:
    planning_input = PlanningInput.model_validate(load_periodic_payload())
    preview = build_periodic_preview()
    payload = fingerprint_payload_for_preview(preview, planning_input)
    changed = payload.model_copy(update={field_name: changed_value}, deep=True)

    assert compute_preview_fingerprint(payload) != compute_preview_fingerprint(changed)


def test_query_version_mapping_insertion_order_does_not_change_fingerprint() -> None:
    planning_input = PlanningInput.model_validate(load_periodic_payload())
    preview = build_periodic_preview()
    payload = fingerprint_payload_for_preview(preview, planning_input)
    first = payload.model_copy(
        update={
            "query_versions": {
                PlatformId.YOUTUBE: "youtube.declarative.v1",
                PlatformId.REDDIT: "reddit.declarative.v1",
            }
        },
        deep=True,
    )
    second = payload.model_copy(
        update={
            "query_versions": {
                PlatformId.REDDIT: "reddit.declarative.v1",
                PlatformId.YOUTUBE: "youtube.declarative.v1",
            }
        },
        deep=True,
    )
    assert compute_preview_fingerprint(first) == compute_preview_fingerprint(second)


def test_catalog_loader_returns_mutation_isolated_deep_copies() -> None:
    first = get_capability_catalog()
    original_id = first.implementations[0].implementation_id
    first.implementations[0].implementation_id = "mutated-local-copy"

    second = get_capability_catalog()
    assert second.implementations[0].implementation_id == original_id


def test_fixture_preview_p95_is_below_three_seconds() -> None:
    payload = PlanningInput.model_validate(load_periodic_payload())
    catalog = get_capability_catalog()

    for index in range(5):
        build_workflow_plan_preview(
            project_id=PROJECT_ID,
            planning_input=payload,
            catalog=catalog,
            generated_at=GENERATED_AT,
            request_id=f"warmup-{index}",
        )

    durations: list[float] = []
    for index in range(50):
        started = perf_counter()
        build_workflow_plan_preview(
            project_id=PROJECT_ID,
            planning_input=payload,
            catalog=catalog,
            generated_at=GENERATED_AT,
            request_id=f"measured-{index}",
        )
        durations.append(perf_counter() - started)

    p95_seconds = sorted(durations)[math.ceil(len(durations) * 0.95) - 1]
    print(f"preview_p95_ms={p95_seconds * 1000:.3f}")
    assert p95_seconds < 3.0


def test_planner_modules_have_pure_import_boundaries() -> None:
    service_dir = (
        Path(__file__).parents[2]
        / "src"
        / "data_intelligence_hub"
        / "services"
        / "workflow_planner"
    )
    for filename in ("fingerprint.py", "planner.py"):
        source = (service_dir / filename).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_roots = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        assert not (imported_roots & FORBIDDEN_IMPORT_ROOTS)
        imported_modules = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        assert not any(
            fragment in module
            for module in imported_modules
            for fragment in FORBIDDEN_IMPORT_FRAGMENTS
        )
