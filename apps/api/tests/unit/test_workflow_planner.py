from __future__ import annotations

import json
import math
from collections.abc import Iterator, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest

from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityCatalog,
    CapabilityOperation,
    PlatformId,
)
from data_intelligence_hub.schemas.workflow_planner import (
    BudgetStatus,
    CapabilityReadinessSnapshot,
    FlowMode,
    NormalizedMonitoringScope,
    PlanningInput,
    PlanningStatus,
    QueryTerm,
    RoutePlanPreview,
    RoutePlanStatus,
    RouteRequirement,
    WorkflowPlanPreview,
    WorkflowStepPlanningStatus,
)
from data_intelligence_hub.services.capability_catalog import (
    clear_capability_catalog_cache,
    get_capability_catalog,
)
from data_intelligence_hub.services.workflow_planner.candidate_expansion import (
    CandidateExpansionAdapter,
    FixtureCandidateExpansionAdapter,
)
from data_intelligence_hub.services.workflow_planner.capability_resolver import (
    derive_product_readiness,
    resolve_route_plans,
)
from data_intelligence_hub.services.workflow_planner.normalization import (
    NormalizationResult,
    normalize_planning_input,
)
from data_intelligence_hub.services.workflow_planner.planner import (
    assemble_workflow_plan_preview,
    build_workflow_plan_preview,
)
from data_intelligence_hub.services.workflow_planner.policies import (
    RoutingPolicy,
    get_routing_policy,
)
from data_intelligence_hub.services.workflow_planner.query_compiler import (
    PlatformQueryCompiler,
    QueryCompilationResult,
    build_query_terms,
    compile_platform_queries,
    default_platform_query_compilers,
)
from data_intelligence_hub.services.workflow_planner.templates import (
    TemplateBuildResult,
    build_workflow_template,
)

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "workflow_planner"
PERIODIC_FIXTURE = FIXTURE_DIR / "periodic_monitoring_request_v1.json"
BATCH_FIXTURE = FIXTURE_DIR / "batch_research_request_v1.json"
SYNTHETIC_CATALOG_FIXTURE = FIXTURE_DIR / "synthetic_capability_catalog_v1.json"
PROJECT_ID = UUID("00000000-0000-0000-0000-000000000001")
GENERATED_AT = datetime(2026, 7, 12, tzinfo=UTC)
BOUNDARY_FIELDS = (
    "execution_authorized",
    "provider_call",
    "actor_run",
    "browser_run",
    "llm_call",
    "workflow_run_created",
    "database_write",
)


@pytest.fixture(autouse=True)
def isolate_capability_catalog_cache() -> Iterator[None]:
    clear_capability_catalog_cache()
    yield
    clear_capability_catalog_cache()


def load_planning_input(path: Path) -> PlanningInput:
    return PlanningInput.model_validate_json(path.read_text(encoding="utf-8"))


def load_synthetic_catalog() -> CapabilityCatalog:
    return CapabilityCatalog.model_validate_json(
        SYNTHETIC_CATALOG_FIXTURE.read_text(encoding="utf-8")
    )


def synthetic_periodic_input() -> PlanningInput:
    payload = cast(
        dict[str, object],
        json.loads(PERIODIC_FIXTURE.read_text(encoding="utf-8")),
    )
    payload["required_fields"] = ["id", "url", "text"]
    return PlanningInput.model_validate(payload)


def synthetic_batch_input() -> PlanningInput:
    payload = cast(
        dict[str, object],
        json.loads(BATCH_FIXTURE.read_text(encoding="utf-8")),
    )
    scopes = cast(list[dict[str, object]], payload["scopes"])
    scopes[0]["platforms"] = ["youtube"]
    scopes[0]["seed_urls"] = ["https://www.youtube.com/watch?v=demo"]
    payload["default_platforms"] = ["youtube"]
    return PlanningInput.model_validate(payload)


def build_preview(
    planning_input: PlanningInput,
    *,
    catalog: CapabilityCatalog | None = None,
    request_id: str = "request-1",
    candidate_adapter: CandidateExpansionAdapter | None = None,
    query_compilers: Mapping[PlatformId, PlatformQueryCompiler] | None = None,
    readiness_snapshots: Mapping[str, CapabilityReadinessSnapshot] | None = None,
) -> WorkflowPlanPreview:
    return build_workflow_plan_preview(
        project_id=PROJECT_ID,
        planning_input=planning_input,
        catalog=catalog or get_capability_catalog(),
        generated_at=GENERATED_AT,
        request_id=request_id,
        candidate_adapter=candidate_adapter,
        query_compilers=query_compilers,
        readiness_snapshots=readiness_snapshots,
    )


def catalog_subset(
    catalog: CapabilityCatalog,
    implementation_ids: set[str],
) -> CapabilityCatalog:
    implementations = [
        item
        for item in catalog.implementations
        if item.implementation_id in implementation_ids
    ]
    assertions = [
        item
        for item in catalog.assertions
        if item.implementation_id in implementation_ids
    ]
    evidence_refs = {
        evidence_ref
        for assertion in assertions
        for evidence_ref in assertion.evidence_refs
    }
    evidence = [
        item for item in catalog.evidence if item.evidence_id in evidence_refs
    ]
    return catalog.model_copy(
        update={
            "implementations": implementations,
            "assertions": assertions,
            "evidence": evidence,
        },
        deep=True,
    )


def build_upstream(
    planning_input: PlanningInput,
    catalog: CapabilityCatalog,
) -> tuple[
    NormalizationResult,
    FixtureCandidateExpansionAdapter,
    QueryCompilationResult,
    TemplateBuildResult,
    RoutingPolicy,
    list[RoutePlanPreview],
]:
    normalization = normalize_planning_input(planning_input)
    adapter = FixtureCandidateExpansionAdapter.from_default_fixture()
    terms = build_query_terms(normalization, candidate_adapter=adapter)
    query_result = compile_platform_queries(
        normalization,
        terms,
        compilers=default_platform_query_compilers(),
    )
    template_result = build_workflow_template(
        normalization.normalized_input,
        query_result,
    )
    policy = get_routing_policy(planning_input.policy_profile)
    routes = resolve_route_plans(
        template_result.requirements,
        catalog,
        policy=policy,
        readiness_snapshots=derive_product_readiness(catalog),
    )
    return normalization, adapter, query_result, template_result, policy, routes


def test_periodic_and_batch_canonical_previews_are_deterministic_held() -> None:
    for fixture in (PERIODIC_FIXTURE, BATCH_FIXTURE):
        planning_input = load_planning_input(fixture)
        first = build_preview(planning_input, request_id="same-request")
        second = build_preview(planning_input, request_id="same-request")

        assert first == second
        assert first.planning_status is PlanningStatus.HELD
        assert first.coverage.total_requirements == len(first.route_requirements)
        assert first.coverage.held_requirements == len(first.route_requirements)
        assert all(route.status is RoutePlanStatus.HELD for route in first.route_plans)
        assert all(route.primary_implementation is None for route in first.route_plans)
        assert all(
            step.planning_status is WorkflowStepPlanningStatus.HELD
            for step in first.steps
            if step.requirement_ref is not None
        )


def test_batch_preserves_unclassified_seed_url_in_input_diagnostics() -> None:
    preview = build_preview(load_planning_input(BATCH_FIXTURE))
    diagnostics = [
        entry
        for entry in preview.decision_trace.input_diagnostics
        if entry.code == "seed_url_unclassified"
    ]

    assert diagnostics
    assert any(
        entry.details.get("seed_url") == "https://example.com/research/demo"
        for entry in diagnostics
    )


def test_synthetic_catalog_resolves_all_four_operations_and_backend_facts() -> None:
    catalog = load_synthetic_catalog()
    periodic = build_preview(synthetic_periodic_input(), catalog=catalog)
    batch = build_preview(synthetic_batch_input(), catalog=catalog)
    previews = (periodic, batch)

    operations = {
        requirement.operation
        for preview in previews
        for requirement in preview.route_requirements
    }
    assert operations == {
        CapabilityOperation.SEARCH_DISCOVER,
        CapabilityOperation.RESOLVE_DETAIL,
        CapabilityOperation.MONITOR_INCREMENTAL,
        CapabilityOperation.BATCH_PARSE,
    }
    assert all(preview.planning_status is PlanningStatus.RESOLVED for preview in previews)
    assert all(
        route.status is RoutePlanStatus.RESOLVED
        for preview in previews
        for route in preview.route_plans
    )
    assert periodic.mode_template_version == "periodic_monitoring.v1"
    assert batch.mode_template_version == "batch_research.v1"
    assert periodic.query_versions == {
        PlatformId.YOUTUBE: "youtube.declarative.v1"
    }
    assert [route.requirement_ref for route in periodic.route_plans] == [
        requirement.requirement_ref for requirement in periodic.route_requirements
    ]


def test_route_status_synchronizes_future_steps_and_coverage() -> None:
    partial_catalog = catalog_subset(load_synthetic_catalog(), {"fixture.partial"})
    payload = synthetic_periodic_input().model_dump(mode="json")
    payload["allow_partial_degradation"] = True
    preview = build_preview(
        PlanningInput.model_validate(payload),
        catalog=partial_catalog,
    )
    routes_by_ref = {route.requirement_ref: route for route in preview.route_plans}

    assert preview.planning_status is PlanningStatus.PARTIALLY_RESOLVED
    assert preview.coverage.partial_requirements == len(preview.route_plans)
    assert preview.coverage.resolved_requirements == 0
    assert preview.coverage.held_requirements == 0
    for step in preview.steps:
        if step.requirement_ref is not None:
            assert routes_by_ref[step.requirement_ref].status is RoutePlanStatus.PARTIAL
            assert step.planning_status is WorkflowStepPlanningStatus.PARTIAL


def test_explicit_empty_compiler_registry_stays_fail_closed() -> None:
    preview = build_preview(
        synthetic_periodic_input(),
        catalog=load_synthetic_catalog(),
        query_compilers={},
    )
    compiler_held_routes = [
        route
        for route in preview.route_plans
        if any(reason.code == "compiler_missing" for reason in route.exclusion_reasons)
    ]

    assert preview.query_versions == {}
    assert compiler_held_routes
    assert all(route.status is RoutePlanStatus.HELD for route in compiler_held_routes)
    assert all(route.primary_implementation is None for route in compiler_held_routes)
    held_refs = {route.requirement_ref for route in compiler_held_routes}
    assert all(
        step.planning_status is WorkflowStepPlanningStatus.HELD
        for step in preview.steps
        if step.requirement_ref in held_refs
    )


class FalseyCandidateAdapter(CandidateExpansionAdapter):
    version = "falsey-candidate-adapter.v1"

    def __bool__(self) -> bool:
        return False

    def expand(
        self,
        scope: NormalizedMonitoringScope,
        *,
        flow_mode: FlowMode,
    ) -> list[QueryTerm]:
        del scope, flow_mode
        return []


def test_explicit_falsey_candidate_adapter_is_not_replaced() -> None:
    preview = build_preview(
        load_planning_input(PERIODIC_FIXTURE),
        candidate_adapter=FalseyCandidateAdapter(),
    )

    assert all(term.origin != "fixture_candidate_expansion" for term in preview.query_terms)


def test_explicit_empty_readiness_mapping_is_passed_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[Mapping[str, CapabilityReadinessSnapshot] | None] = []
    original = resolve_route_plans

    def capture_readiness(
        requirements: Sequence[RouteRequirement],
        catalog: CapabilityCatalog,
        *,
        policy: RoutingPolicy,
        readiness_snapshots: Mapping[str, CapabilityReadinessSnapshot] | None,
    ) -> list[RoutePlanPreview]:
        captured.append(readiness_snapshots)
        return original(
            requirements,
            catalog,
            policy=policy,
            readiness_snapshots=readiness_snapshots,
        )

    monkeypatch.setattr(
        "data_intelligence_hub.services.workflow_planner.planner.resolve_route_plans",
        capture_readiness,
    )
    build_preview(
        synthetic_periodic_input(),
        catalog=load_synthetic_catalog(),
        readiness_snapshots={},
    )

    assert captured == [{}]


def test_empty_requirement_preview_is_held_without_fake_budget_zero() -> None:
    payload = cast(
        dict[str, object],
        json.loads(BATCH_FIXTURE.read_text(encoding="utf-8")),
    )
    scopes = cast(list[dict[str, object]], payload["scopes"])
    scopes[0].update(
        {
            "canonical_term": None,
            "aliases": [],
            "include_terms": [],
            "official_accounts": [],
            "seed_urls": ["https://example.com/unclassified"],
            "platforms": [],
        }
    )
    payload["default_platforms"] = []
    preview = build_preview(PlanningInput.model_validate(payload))

    assert preview.route_requirements == []
    assert preview.route_plans == []
    assert preview.planning_status is PlanningStatus.HELD
    assert preview.coverage.model_dump() == {
        "total_requirements": 0,
        "resolved_requirements": 0,
        "partial_requirements": 0,
        "held_requirements": 0,
    }
    assert preview.budget_summary.known_selected_unit_cost is None
    assert preview.budget_summary.unknown_count == 0
    assert preview.budget_summary.budget_status is BudgetStatus.NOT_APPLICABLE


def test_budget_summary_uses_selected_primary_finite_costs_only() -> None:
    catalog = catalog_subset(load_synthetic_catalog(), {"fixture.primary"})
    known = build_preview(synthetic_periodic_input(), catalog=catalog)
    assert known.budget_summary.known_selected_unit_cost is not None
    assert str(known.budget_summary.known_selected_unit_cost) == "0.03"
    assert known.budget_summary.unknown_count == 0
    assert known.budget_summary.budget_status is BudgetStatus.NOT_APPLICABLE

    zero_implementation = catalog.implementations[0].model_copy(
        update={"cost_hint": {"unit_cost_usd": 0}},
        deep=True,
    )
    zero_catalog = catalog.model_copy(
        update={"implementations": [zero_implementation]},
        deep=True,
    )
    zero = build_preview(synthetic_periodic_input(), catalog=zero_catalog)
    assert zero.budget_summary.known_selected_unit_cost == 0
    assert zero.budget_summary.unknown_count == 0

    unknown_implementation = catalog.implementations[0].model_copy(
        update={"cost_hint": {}},
        deep=True,
    )
    unknown_catalog = catalog.model_copy(
        update={"implementations": [unknown_implementation]},
        deep=True,
    )
    unknown = build_preview(synthetic_periodic_input(), catalog=unknown_catalog)
    assert unknown.budget_summary.known_selected_unit_cost is None
    assert unknown.budget_summary.unknown_count == len(unknown.route_plans)
    assert unknown.budget_summary.budget_status is BudgetStatus.UNKNOWN


@pytest.mark.parametrize(
    "invalid_cost",
    [True, "0.01", -1, math.nan, math.inf, -math.inf],
)
def test_budget_assembly_rejects_invalid_selected_primary_cost(
    invalid_cost: object,
) -> None:
    catalog = catalog_subset(load_synthetic_catalog(), {"fixture.primary"})
    planning_input = synthetic_periodic_input()
    normalization, adapter, query_result, template_result, policy, routes = build_upstream(
        planning_input,
        catalog,
    )
    invalid_implementation = catalog.implementations[0].model_copy(
        update={"cost_hint": {"unit_cost_usd": invalid_cost}},
        deep=True,
    )
    invalid_catalog = catalog.model_copy(
        update={"implementations": [invalid_implementation]},
        deep=True,
    )

    with pytest.raises(ValueError, match="selected_implementation_cost_invalid"):
        assemble_workflow_plan_preview(
            project_id=PROJECT_ID,
            generated_at=GENERATED_AT,
            request_id="invalid-cost",
            normalization=normalization,
            query_result=query_result,
            template_result=template_result,
            route_plans=routes,
            catalog=invalid_catalog,
            policy=policy,
            candidate_fixture_version=adapter.version,
        )


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "unknown"])
def test_assembly_fails_fast_on_requirement_route_mismatch(mutation: str) -> None:
    catalog = load_synthetic_catalog()
    planning_input = synthetic_periodic_input()
    normalization, adapter, query_result, template_result, policy, routes = build_upstream(
        planning_input,
        catalog,
    )
    changed_routes = list(routes)
    if mutation == "missing":
        changed_routes.pop()
    elif mutation == "duplicate":
        changed_routes.append(changed_routes[0])
    else:
        changed_routes[0] = changed_routes[0].model_copy(
            update={"requirement_ref": "requirement:unknown"},
            deep=True,
        )

    with pytest.raises(ValueError, match="route_requirement"):
        assemble_workflow_plan_preview(
            project_id=PROJECT_ID,
            generated_at=GENERATED_AT,
            request_id="route-mismatch",
            normalization=normalization,
            query_result=query_result,
            template_result=template_result,
            route_plans=changed_routes,
            catalog=catalog,
            policy=policy,
            candidate_fixture_version=adapter.version,
        )


def test_assembly_rejects_future_step_missing_from_requirement_step_refs() -> None:
    catalog = load_synthetic_catalog()
    planning_input = synthetic_periodic_input()
    normalization, adapter, query_result, template_result, policy, routes = build_upstream(
        planning_input,
        catalog,
    )
    requirement = template_result.requirements[0]
    future_step = next(
        step
        for step in template_result.steps
        if step.requirement_ref == requirement.requirement_ref
    )
    unlisted_step = future_step.model_copy(
        update={
            "step_ref": f"{future_step.step_ref}:unlisted",
            "sequence": len(template_result.steps) + 1,
        },
        deep=True,
    )
    changed_template = TemplateBuildResult(
        mode_template_version=template_result.mode_template_version,
        steps=(*template_result.steps, unlisted_step),
        requirements=template_result.requirements,
        semantic_entries=template_result.semantic_entries,
    )

    with pytest.raises(ValueError, match="route_requirement_step_set_mismatch"):
        assemble_workflow_plan_preview(
            project_id=PROJECT_ID,
            generated_at=GENERATED_AT,
            request_id="unlisted-future-step",
            normalization=normalization,
            query_result=query_result,
            template_result=changed_template,
            route_plans=routes,
            catalog=catalog,
            policy=policy,
            candidate_fixture_version=adapter.version,
        )


def test_assembly_rejects_duplicate_requirement_step_refs() -> None:
    catalog = load_synthetic_catalog()
    planning_input = synthetic_periodic_input()
    normalization, adapter, query_result, template_result, policy, routes = build_upstream(
        planning_input,
        catalog,
    )
    requirement = template_result.requirements[0]
    duplicate = requirement.model_copy(
        update={"step_refs": [requirement.step_refs[0], requirement.step_refs[0]]},
        deep=True,
    )
    changed_template = TemplateBuildResult(
        mode_template_version=template_result.mode_template_version,
        steps=template_result.steps,
        requirements=(duplicate, *template_result.requirements[1:]),
        semantic_entries=template_result.semantic_entries,
    )

    with pytest.raises(ValueError, match="duplicate_route_requirement_step_ref"):
        assemble_workflow_plan_preview(
            project_id=PROJECT_ID,
            generated_at=GENERATED_AT,
            request_id="duplicate-requirement-step-ref",
            normalization=normalization,
            query_result=query_result,
            template_result=changed_template,
            route_plans=routes,
            catalog=catalog,
            policy=policy,
            candidate_fixture_version=adapter.version,
        )


def test_preview_is_stable_bounded_and_does_not_mutate_inputs() -> None:
    planning_input = synthetic_periodic_input()
    catalog = load_synthetic_catalog()
    input_before = planning_input.model_dump(mode="json")
    catalog_before = catalog.model_dump(mode="json")

    preview = build_preview(planning_input, catalog=catalog)

    assert planning_input.model_dump(mode="json") == input_before
    assert catalog.model_dump(mode="json") == catalog_before
    assert all(getattr(preview, field) is False for field in BOUNDARY_FIELDS)
    assert preview.attribution_contract.model_dump() == {
        "matched_scope_id": "future.monitoring_scope_id.v1",
        "matched_term": "future.matched_term.v1",
        "match_reason": "future.match_reason.v1",
        "query_version": "future.query_version.v1",
        "requirement_ref": "future.requirement_ref.v1",
        "route_plan_ref": "future.route_plan_ref.v1",
    }
    assert preview.limitations == sorted(set(preview.limitations))
    semantic_trace = [
        entry.model_dump(mode="json")
        for entry in preview.decision_trace.semantic_entries
    ]
    assert semantic_trace == sorted(
        semantic_trace,
        key=lambda entry: (
            entry["scope_keys"],
            entry["requirement_ref"] or "",
            entry["code"],
            entry["reason"],
            json.dumps(entry["details"], ensure_ascii=False, sort_keys=True),
        ),
    )
    trace_keys = {
        json.dumps(entry, ensure_ascii=False, sort_keys=True)
        for entry in semantic_trace
    }
    assert len(trace_keys) == len(semantic_trace)
