from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Literal, cast
from uuid import UUID

from pydantic import JsonValue

from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityCatalog,
    CapabilityImplementation,
    CapabilityStatus,
    PlatformId,
)
from data_intelligence_hub.schemas.workflow_planner import (
    AttributionContract,
    BudgetStatus,
    BudgetSummary,
    CapabilityReadinessSnapshot,
    CoverageSummary,
    DecisionTrace,
    DecisionTraceEntry,
    PlanningInput,
    PlanningStatus,
    RoutePlanPreview,
    RoutePlanStatus,
    WorkflowPlanFingerprintPayload,
    WorkflowPlanPreview,
    WorkflowStepPlanningStatus,
    WorkflowStepPreview,
)
from data_intelligence_hub.services.workflow_planner.candidate_expansion import (
    CandidateExpansionAdapter,
    FixtureCandidateExpansionAdapter,
)
from data_intelligence_hub.services.workflow_planner.capability_resolver import (
    derive_product_readiness,
    resolve_route_plans,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import (
    build_preview_fingerprint_payload,
    canonical_json_bytes,
    compute_catalog_snapshot_id,
    compute_preview_fingerprint,
)
from data_intelligence_hub.services.workflow_planner.normalization import (
    NormalizationResult,
    normalize_planning_input,
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
    validate_step_graph,
)

PLANNER_CONTRACT_VERSION = "workflow_planner.v1"


@dataclass(frozen=True, slots=True)
class WorkflowPlanBuildResult:
    preview: WorkflowPlanPreview
    fingerprint_payload: WorkflowPlanFingerprintPayload


def _validate_requirement_route_alignment(
    template_result: TemplateBuildResult,
    route_plans: Sequence[RoutePlanPreview],
) -> list[RoutePlanPreview]:
    requirement_refs = [
        requirement.requirement_ref for requirement in template_result.requirements
    ]
    if len(requirement_refs) != len(set(requirement_refs)):
        raise ValueError("duplicate_route_requirement_ref")

    route_refs = [route.requirement_ref for route in route_plans]
    if len(route_refs) != len(set(route_refs)):
        raise ValueError("duplicate_route_requirement_plan_ref")
    if set(requirement_refs) != set(route_refs):
        raise ValueError("route_requirement_set_mismatch")

    route_by_ref = {route.requirement_ref: route for route in route_plans}
    return [route_by_ref[requirement_ref] for requirement_ref in requirement_refs]


def _validate_step_requirement_alignment(
    template_result: TemplateBuildResult,
) -> None:
    validate_step_graph(template_result.steps)
    requirements_by_ref = {
        requirement.requirement_ref: requirement
        for requirement in template_result.requirements
    }
    future_step_refs_by_requirement: dict[str, list[str]] = {
        requirement_ref: [] for requirement_ref in requirements_by_ref
    }

    for step in template_result.steps:
        if step.execution_kind == "planner_internal":
            if step.requirement_ref is not None:
                raise ValueError("planner_internal_step_has_route_requirement")
            continue
        if (
            step.requirement_ref is None
            or step.requirement_ref not in requirements_by_ref
        ):
            raise ValueError("future_step_route_requirement_mismatch")
        future_step_refs_by_requirement[step.requirement_ref].append(step.step_ref)

    for requirement in template_result.requirements:
        if not requirement.step_refs:
            raise ValueError("route_requirement_step_refs_empty")
        if len(requirement.step_refs) != len(set(requirement.step_refs)):
            raise ValueError("duplicate_route_requirement_step_ref")
        if set(requirement.step_refs) != set(
            future_step_refs_by_requirement[requirement.requirement_ref]
        ):
            raise ValueError("route_requirement_step_set_mismatch")


def _validate_route_primary_contract(route: RoutePlanPreview) -> None:
    primary = route.primary_implementation
    if route.status is RoutePlanStatus.HELD:
        if primary is not None:
            raise ValueError("route_status_primary_mismatch")
        return
    if primary is None:
        raise ValueError("route_status_primary_mismatch")
    if (
        route.status is RoutePlanStatus.RESOLVED
        and primary.capability_status is not CapabilityStatus.VERIFIED
    ):
        raise ValueError("route_status_primary_mismatch")
    if (
        route.status is RoutePlanStatus.PARTIAL
        and primary.capability_status is not CapabilityStatus.PARTIAL
    ):
        raise ValueError("route_status_primary_mismatch")


def _synchronize_step_statuses(
    steps: Sequence[WorkflowStepPreview],
    routes: Sequence[RoutePlanPreview],
) -> list[WorkflowStepPreview]:
    route_by_ref = {route.requirement_ref: route for route in routes}
    status_by_route = {
        RoutePlanStatus.RESOLVED: WorkflowStepPlanningStatus.PLANNED,
        RoutePlanStatus.PARTIAL: WorkflowStepPlanningStatus.PARTIAL,
        RoutePlanStatus.HELD: WorkflowStepPlanningStatus.HELD,
    }
    synchronized: list[WorkflowStepPreview] = []
    for step in steps:
        status = step.planning_status
        if step.requirement_ref is not None:
            status = status_by_route[route_by_ref[step.requirement_ref].status]
        synchronized.append(
            step.model_copy(update={"planning_status": status}, deep=True)
        )
    return sorted(synchronized, key=lambda item: (item.sequence, item.step_ref))


def _planning_status(routes: Sequence[RoutePlanPreview]) -> PlanningStatus:
    routeable = [
        route
        for route in routes
        if route.status in {RoutePlanStatus.RESOLVED, RoutePlanStatus.PARTIAL}
    ]
    if not routes or not routeable:
        return PlanningStatus.HELD
    if all(route.status is RoutePlanStatus.RESOLVED for route in routes):
        return PlanningStatus.RESOLVED
    return PlanningStatus.PARTIALLY_RESOLVED


def _coverage(routes: Sequence[RoutePlanPreview]) -> CoverageSummary:
    return CoverageSummary(
        total_requirements=len(routes),
        resolved_requirements=sum(
            route.status is RoutePlanStatus.RESOLVED for route in routes
        ),
        partial_requirements=sum(
            route.status is RoutePlanStatus.PARTIAL for route in routes
        ),
        held_requirements=sum(route.status is RoutePlanStatus.HELD for route in routes),
    )


def _unit_cost(
    implementation: CapabilityImplementation,
) -> tuple[Literal["known", "unknown", "invalid"], Decimal | None]:
    if "unit_cost_usd" not in implementation.cost_hint:
        return "unknown", None
    value = implementation.cost_hint["unit_cost_usd"]
    if value is None:
        return "unknown", None
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return "invalid", None
    if isinstance(value, float) and not math.isfinite(value):
        return "invalid", None
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return "invalid", None
    if not decimal_value.is_finite() or decimal_value < 0:
        return "invalid", None
    return "known", decimal_value


def _budget_summary(
    routes: Sequence[RoutePlanPreview],
    catalog: CapabilityCatalog,
) -> BudgetSummary:
    implementations = {
        implementation.implementation_id: implementation
        for implementation in catalog.implementations
    }
    known_costs: list[Decimal] = []
    unknown_count = 0
    for route in routes:
        primary = route.primary_implementation
        if primary is None:
            continue
        implementation = implementations.get(primary.implementation_id)
        if implementation is None:
            raise ValueError("selected_implementation_unknown")
        state, cost = _unit_cost(implementation)
        if state == "invalid":
            raise ValueError("selected_implementation_cost_invalid")
        if state == "unknown":
            unknown_count += 1
        elif cost is not None:
            known_costs.append(cost)

    route_budget_statuses = {route.budget_status for route in routes}
    if BudgetStatus.EXCEEDED in route_budget_statuses:
        budget_status = BudgetStatus.EXCEEDED
    elif unknown_count or BudgetStatus.UNKNOWN in route_budget_statuses:
        budget_status = BudgetStatus.UNKNOWN
    elif BudgetStatus.WITHIN_CEILING in route_budget_statuses:
        budget_status = BudgetStatus.WITHIN_CEILING
    else:
        budget_status = BudgetStatus.NOT_APPLICABLE
    return BudgetSummary(
        currency="USD",
        known_selected_unit_cost=(sum(known_costs, Decimal("0")) if known_costs else None),
        unknown_count=unknown_count,
        budget_status=budget_status,
    )


def _trace_sort_key(entry: DecisionTraceEntry) -> tuple[object, ...]:
    return (
        entry.scope_keys,
        entry.requirement_ref or "",
        entry.code,
        entry.reason,
        canonical_json_bytes(cast(JsonValue, entry.details)),
    )


def _stable_trace_entries(
    entries: Sequence[DecisionTraceEntry],
) -> list[DecisionTraceEntry]:
    unique: dict[bytes, DecisionTraceEntry] = {}
    for entry in entries:
        canonical = entry.model_copy(
            update={"scope_keys": sorted(set(entry.scope_keys))},
            deep=True,
        )
        key = canonical_json_bytes(
            cast(JsonValue, canonical.model_dump(mode="json"))
        )
        unique[key] = canonical
    return sorted(unique.values(), key=_trace_sort_key)


def _route_trace_entries(
    template_result: TemplateBuildResult,
    routes: Sequence[RoutePlanPreview],
) -> list[DecisionTraceEntry]:
    requirements = {
        requirement.requirement_ref: requirement
        for requirement in template_result.requirements
    }
    entries: list[DecisionTraceEntry] = []
    for route in routes:
        requirement = requirements[route.requirement_ref]
        primary_id = (
            route.primary_implementation.implementation_id
            if route.primary_implementation is not None
            else None
        )
        entries.append(
            DecisionTraceEntry(
                code=f"route_{route.status.value}",
                reason=f"Capability route resolved as {route.status.value}",
                scope_keys=sorted(set(requirement.scope_keys)),
                requirement_ref=route.requirement_ref,
                details={
                    "approval_required": route.approval_required,
                    "budget_status": route.budget_status.value,
                    "exclusion_codes": sorted(
                        {reason.code for reason in route.exclusion_reasons}
                    ),
                    "primary_implementation_id": primary_id,
                    "status": route.status.value,
                },
            )
        )
    return entries


def _limitations(
    query_result: QueryCompilationResult,
    steps: Sequence[WorkflowStepPreview],
    routes: Sequence[RoutePlanPreview],
) -> list[str]:
    values = {
        "execution_authorized=false",
        "fixture_candidate_expansion_only",
        "preview_only",
        *query_result.limitations,
        *(limitation for step in steps for limitation in step.limitations),
        *(limitation for route in routes for limitation in route.limitations),
        *(reason.code for route in routes for reason in route.exclusion_reasons),
        *(reason.code for route in routes for reason in route.approval_reasons),
    }
    return sorted(values)


def _attribution_contract() -> AttributionContract:
    return AttributionContract(
        matched_scope_id="future.monitoring_scope_id.v1",
        matched_term="future.matched_term.v1",
        match_reason="future.match_reason.v1",
        query_version="future.query_version.v1",
        requirement_ref="future.requirement_ref.v1",
        route_plan_ref="future.route_plan_ref.v1",
    )


def assemble_workflow_plan_result(
    *,
    project_id: UUID,
    generated_at: datetime,
    request_id: str,
    normalization: NormalizationResult,
    query_result: QueryCompilationResult,
    template_result: TemplateBuildResult,
    route_plans: Sequence[RoutePlanPreview],
    catalog: CapabilityCatalog,
    policy: RoutingPolicy,
    candidate_fixture_version: str,
) -> WorkflowPlanBuildResult:
    if policy.profile is not normalization.normalized_input.policy_profile:
        raise ValueError("routing_policy_profile_mismatch")
    _validate_step_requirement_alignment(template_result)
    ordered_routes = _validate_requirement_route_alignment(template_result, route_plans)
    for route in ordered_routes:
        _validate_route_primary_contract(route)

    steps = _synchronize_step_statuses(template_result.steps, ordered_routes)
    coverage = _coverage(ordered_routes)
    budget_summary = _budget_summary(ordered_routes, catalog)
    limitations = _limitations(query_result, steps, ordered_routes)
    semantic_entries = _stable_trace_entries(
        [
            *normalization.semantic_entries,
            *query_result.semantic_entries,
            *template_result.semantic_entries,
            *_route_trace_entries(template_result, ordered_routes),
        ]
    )
    input_diagnostics = _stable_trace_entries(normalization.input_diagnostics)
    catalog_snapshot_id = compute_catalog_snapshot_id(catalog)
    fingerprint_payload = build_preview_fingerprint_payload(
        planner_contract_version=PLANNER_CONTRACT_VERSION,
        fingerprint_input=normalization.fingerprint_input,
        catalog_snapshot_id=catalog_snapshot_id,
        policy_version=policy.version,
        mode_template_version=template_result.mode_template_version,
        query_versions=query_result.query_versions,
        candidate_fixture_version=candidate_fixture_version,
        query_terms=query_result.query_terms,
        steps=steps,
        compiled_queries=query_result.compiled_queries,
        route_plans=ordered_routes,
        coverage=coverage,
        budget_summary=budget_summary,
        limitations=limitations,
        semantic_decision_trace=semantic_entries,
    )
    preview_fingerprint = compute_preview_fingerprint(fingerprint_payload)
    preview = WorkflowPlanPreview(
        schema_version="workflow_plan_preview.v1",
        planner_contract_version=PLANNER_CONTRACT_VERSION,
        project_id=project_id,
        flow_mode=normalization.normalized_input.flow_mode,
        planning_status=_planning_status(ordered_routes),
        normalized_input=normalization.normalized_input.model_copy(deep=True),
        scope_ref_map=list(normalization.scope_ref_map),
        query_terms=list(query_result.query_terms),
        compiled_queries=list(query_result.compiled_queries),
        steps=steps,
        route_requirements=list(template_result.requirements),
        route_plans=ordered_routes,
        coverage=coverage,
        budget_summary=budget_summary,
        limitations=limitations,
        decision_trace=DecisionTrace(
            semantic_entries=semantic_entries,
            input_diagnostics=input_diagnostics,
        ),
        attribution_contract=_attribution_contract(),
        catalog_snapshot_id=catalog_snapshot_id,
        policy_version=policy.version,
        mode_template_version=template_result.mode_template_version,
        query_versions=dict(query_result.query_versions),
        preview_fingerprint=preview_fingerprint,
        execution_authorized=False,
        provider_call=False,
        actor_run=False,
        browser_run=False,
        llm_call=False,
        workflow_run_created=False,
        database_write=False,
        generated_at=generated_at,
        request_id=request_id,
    )
    return WorkflowPlanBuildResult(
        preview=preview,
        fingerprint_payload=fingerprint_payload,
    )


def assemble_workflow_plan_preview(
    *,
    project_id: UUID,
    generated_at: datetime,
    request_id: str,
    normalization: NormalizationResult,
    query_result: QueryCompilationResult,
    template_result: TemplateBuildResult,
    route_plans: Sequence[RoutePlanPreview],
    catalog: CapabilityCatalog,
    policy: RoutingPolicy,
    candidate_fixture_version: str,
) -> WorkflowPlanPreview:
    return assemble_workflow_plan_result(
        project_id=project_id,
        generated_at=generated_at,
        request_id=request_id,
        normalization=normalization,
        query_result=query_result,
        template_result=template_result,
        route_plans=route_plans,
        catalog=catalog,
        policy=policy,
        candidate_fixture_version=candidate_fixture_version,
    ).preview


def build_workflow_plan_result(
    *,
    project_id: UUID,
    planning_input: PlanningInput,
    catalog: CapabilityCatalog,
    generated_at: datetime,
    request_id: str,
    candidate_adapter: CandidateExpansionAdapter | None = None,
    query_compilers: Mapping[PlatformId, PlatformQueryCompiler] | None = None,
    readiness_snapshots: Mapping[str, CapabilityReadinessSnapshot] | None = None,
) -> WorkflowPlanBuildResult:
    normalization = normalize_planning_input(planning_input)
    adapter = (
        FixtureCandidateExpansionAdapter.from_default_fixture()
        if candidate_adapter is None
        else candidate_adapter
    )
    query_terms = build_query_terms(
        normalization,
        candidate_adapter=adapter,
    )
    compilers = (
        default_platform_query_compilers()
        if query_compilers is None
        else query_compilers
    )
    query_result = compile_platform_queries(
        normalization,
        query_terms,
        compilers=compilers,
    )
    template_result = build_workflow_template(
        normalization.normalized_input,
        query_result,
    )
    policy = get_routing_policy(planning_input.policy_profile)
    readiness = (
        derive_product_readiness(catalog)
        if readiness_snapshots is None
        else readiness_snapshots
    )
    route_plans = resolve_route_plans(
        template_result.requirements,
        catalog,
        policy=policy,
        readiness_snapshots=readiness,
    )
    return assemble_workflow_plan_result(
        project_id=project_id,
        generated_at=generated_at,
        request_id=request_id,
        normalization=normalization,
        query_result=query_result,
        template_result=template_result,
        route_plans=route_plans,
        catalog=catalog,
        policy=policy,
        candidate_fixture_version=adapter.version,
    )


def build_workflow_plan_preview(
    *,
    project_id: UUID,
    planning_input: PlanningInput,
    catalog: CapabilityCatalog,
    generated_at: datetime,
    request_id: str,
    candidate_adapter: CandidateExpansionAdapter | None = None,
    query_compilers: Mapping[PlatformId, PlatformQueryCompiler] | None = None,
    readiness_snapshots: Mapping[str, CapabilityReadinessSnapshot] | None = None,
) -> WorkflowPlanPreview:
    return build_workflow_plan_result(
        project_id=project_id,
        planning_input=planning_input,
        catalog=catalog,
        generated_at=generated_at,
        request_id=request_id,
        candidate_adapter=candidate_adapter,
        query_compilers=query_compilers,
        readiness_snapshots=readiness_snapshots,
    ).preview
