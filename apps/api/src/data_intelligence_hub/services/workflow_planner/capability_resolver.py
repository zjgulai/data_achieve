from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityAssertion,
    CapabilityCatalog,
    CapabilityConstraint,
    CapabilityImplementation,
    CapabilityStatus,
    ConstraintSeverity,
)
from data_intelligence_hub.schemas.workflow_planner import (
    AuthReadiness,
    BudgetStatus,
    CapabilityReadinessSnapshot,
    DecisionReason,
    RouteCandidateDecision,
    RoutePlanPreview,
    RoutePlanStatus,
    RouteRequirement,
    ShadowRule,
)
from data_intelligence_hub.services.workflow_planner.policies import (
    RoutingPolicy,
    calculate_weighted_score,
)


@dataclass(frozen=True)
class _CostAssessment:
    state: str
    unit_cost_usd: Decimal | None


@dataclass(frozen=True)
class _QualifiedCandidate:
    decision: RouteCandidateDecision
    gate_trace: tuple[DecisionReason, ...]
    cost: _CostAssessment


def derive_product_readiness(
    catalog: CapabilityCatalog,
) -> dict[str, CapabilityReadinessSnapshot]:
    return {
        implementation.implementation_id: CapabilityReadinessSnapshot(
            implementation_id=implementation.implementation_id,
            auth_readiness=(
                AuthReadiness.NOT_REQUIRED
                if not implementation.required_credentials
                else AuthReadiness.NOT_CHECKED
            ),
            source="catalog_metadata",
            credential_read_status="not_read",
        )
        for implementation in sorted(
            catalog.implementations,
            key=lambda item: item.implementation_id,
        )
    }


def resolve_route_plans(
    requirements: Sequence[RouteRequirement],
    catalog: CapabilityCatalog,
    *,
    policy: RoutingPolicy,
    readiness_snapshots: Mapping[str, CapabilityReadinessSnapshot] | None,
) -> list[RoutePlanPreview]:
    implementations = {
        implementation.implementation_id: implementation
        for implementation in catalog.implementations
    }
    readiness = _merge_readiness(
        catalog,
        readiness_snapshots,
        implementation_ids=set(implementations),
    )
    assertions = sorted(catalog.assertions, key=lambda item: item.assertion_id)

    routes: list[RoutePlanPreview] = []
    for requirement in requirements:
        if requirement.precondition_failures:
            routes.append(
                _held_route(
                    requirement,
                    exclusions=requirement.precondition_failures,
                )
            )
            continue

        qualified: list[_QualifiedCandidate] = []
        exclusions: list[DecisionReason] = []
        for assertion in assertions:
            implementation = implementations[assertion.implementation_id]
            candidate, failure = _evaluate_assertion(
                requirement,
                assertion,
                implementation,
                readiness[implementation.implementation_id],
                policy,
            )
            if failure is not None:
                exclusions.append(failure)
            elif candidate is not None:
                qualified.append(candidate)

        ordered = _deduplicate_candidates(qualified)
        routes.append(
            _build_route(
                requirement,
                ordered,
                exclusions=_deduplicate_reasons(exclusions),
                policy=policy,
            )
        )
    return routes


def _merge_readiness(
    catalog: CapabilityCatalog,
    readiness_snapshots: Mapping[str, CapabilityReadinessSnapshot] | None,
    *,
    implementation_ids: set[str],
) -> dict[str, CapabilityReadinessSnapshot]:
    merged = derive_product_readiness(catalog)
    if readiness_snapshots is None:
        return merged
    for key, snapshot in readiness_snapshots.items():
        if key != snapshot.implementation_id:
            raise ValueError("readiness_snapshot_key_mismatch")
        if key not in implementation_ids:
            raise ValueError("readiness_snapshot_implementation_unknown")
        merged[key] = snapshot
    return merged


def _evaluate_assertion(
    requirement: RouteRequirement,
    assertion: CapabilityAssertion,
    implementation: CapabilityImplementation,
    readiness_snapshot: CapabilityReadinessSnapshot,
    policy: RoutingPolicy,
) -> tuple[_QualifiedCandidate | None, DecisionReason | None]:
    gate_trace: list[DecisionReason] = []

    status_failure = _capability_status_failure(
        requirement,
        assertion,
        implementation,
        policy,
    )
    if status_failure is not None:
        return None, status_failure
    gate_trace.append(_passed("capability_status_passed", "Capability status eligible"))

    policy_failure = _policy_failure(assertion)
    if policy_failure is not None:
        return None, policy_failure
    gate_trace.append(_passed("policy_passed", "No blocking phase-one policy"))

    effective_readiness = _effective_readiness(implementation, readiness_snapshot)
    auth_failure = _auth_failure(assertion, effective_readiness)
    if auth_failure is not None:
        return None, auth_failure
    gate_trace.append(_passed("auth_readiness_passed", "Auth metadata is route eligible"))

    if (
        requirement.purpose not in assertion.purpose_scope
        and "global" not in assertion.purpose_scope
    ):
        return None, _failed(
            "purpose_not_supported",
            assertion,
            f"Purpose {requirement.purpose} is outside the Assertion scope",
        )
    gate_trace.append(_passed("purpose_scope_passed", "Purpose is covered"))

    uncovered_regions = sorted(
        region
        for region in requirement.regions
        if region not in assertion.region_scope and "global" not in assertion.region_scope
    )
    if uncovered_regions:
        return None, _failed(
            "region_not_supported",
            assertion,
            f"Regions not covered: {','.join(uncovered_regions)}",
        )
    gate_trace.append(_passed("region_scope_passed", "Regions are covered"))

    if (
        implementation.platform is not requirement.platform
        or assertion.resource_type is not requirement.resource_type
        or assertion.operation is not requirement.operation
    ):
        return None, _failed(
            "capability_requirement_mismatch",
            assertion,
            "Assertion does not exactly match platform/resource/operation",
        )
    gate_trace.append(_passed("capability_match_passed", "Capability identity matches"))

    required_fields, optional_fields = _field_contract(assertion)
    if required_fields is None or optional_fields is None:
        return None, _failed(
            "field_contract_invalid",
            assertion,
            "Assertion field_contract is not a list-of-strings contract",
        )
    missing_required = sorted(set(requirement.required_fields) - required_fields)
    if missing_required:
        return None, _failed(
            "required_fields_missing",
            assertion,
            f"Required fields missing: {','.join(missing_required)}",
        )
    gate_trace.append(_passed("required_fields_passed", "Required fields are covered"))

    cost = _assess_unit_cost(implementation)
    budget_failure = _budget_failure(requirement, assertion, cost)
    if budget_failure is not None:
        return None, budget_failure
    gate_trace.append(_passed("budget_passed", "Budget gate passed"))

    breakdown = calculate_weighted_score(
        assertion.score_profile,
        unit_cost_usd=cost.unit_cost_usd,
        budget_ceiling=requirement.budget_ceiling,
        policy=policy,
    )
    approval_reasons: list[DecisionReason] = []
    if assertion.support_status is CapabilityStatus.PARTIAL:
        approval_reasons.append(
            DecisionReason(
                code="partial_route_requires_approval",
                reason="Partial route is proposal-only and requires a future approval object",
            )
        )
    missing_optional = sorted(
        set(requirement.optional_fields) - required_fields - optional_fields
    )
    decision = RouteCandidateDecision(
        assertion_id=assertion.assertion_id,
        implementation_id=assertion.implementation_id,
        capability_status=assertion.support_status,
        score_breakdown=breakdown,
        weighted_score=breakdown.weighted_score,
        route_eligible=True,
        readiness_status=effective_readiness,
        approval_required=bool(approval_reasons),
        approval_reasons=approval_reasons,
        missing_optional_fields=missing_optional,
        evidence_refs=sorted(set(assertion.evidence_refs)),
    )
    return (
        _QualifiedCandidate(
            decision=decision,
            gate_trace=tuple(gate_trace),
            cost=cost,
        ),
        None,
    )


def _capability_status_failure(
    requirement: RouteRequirement,
    assertion: CapabilityAssertion,
    implementation: CapabilityImplementation,
    policy: RoutingPolicy,
) -> DecisionReason | None:
    if implementation.lifecycle_status == "deprecated":
        return _failed(
            "implementation_deprecated",
            assertion,
            "Implementation lifecycle is deprecated",
        )
    status = assertion.support_status
    if status is CapabilityStatus.VERIFIED:
        return None
    if status is CapabilityStatus.PARTIAL:
        if policy.allow_partial_proposals and requirement.allow_partial_degradation:
            return None
        return _failed(
            "partial_degradation_not_allowed",
            assertion,
            "Partial route proposal was not explicitly enabled",
        )
    if status is CapabilityStatus.CANDIDATE:
        return _failed(
            "candidate_not_execution_eligible",
            assertion,
            "Candidate capability is not route eligible",
        )
    if status is CapabilityStatus.UNKNOWN:
        return _failed("capability_unknown", assertion, "Capability status is unknown")
    if status is CapabilityStatus.BLOCKED:
        blocking = _blocking_constraints(assertion)
        if blocking:
            return _failed(
                blocking[0].code,
                assertion,
                "Capability status is blocked by its atomic Assertion",
            )
        return _failed("capability_blocked", assertion, "Capability status is blocked")
    if status is CapabilityStatus.UNSUPPORTED:
        return _failed(
            "operation_unsupported",
            assertion,
            "Capability operation is unsupported",
        )
    return _failed(
        "implementation_deprecated",
        assertion,
        "Capability Assertion is deprecated",
    )


def _blocking_constraints(
    assertion: CapabilityAssertion,
) -> list[CapabilityConstraint]:
    return sorted(
        (
            constraint
            for constraint in assertion.constraints
            if constraint.severity is ConstraintSeverity.BLOCKING
            and constraint.constraint_type in {"policy", "blocked_action"}
        ),
        key=lambda constraint: (constraint.constraint_type, constraint.code),
    )


def _policy_failure(assertion: CapabilityAssertion) -> DecisionReason | None:
    blocking = _blocking_constraints(assertion)
    if not blocking:
        return None
    constraint = blocking[0]
    return _failed(
        constraint.code,
        assertion,
        f"Blocking {constraint.constraint_type} constraint",
    )


def _effective_readiness(
    implementation: CapabilityImplementation,
    snapshot: CapabilityReadinessSnapshot,
) -> AuthReadiness:
    if implementation.required_credentials:
        if (
            snapshot.auth_readiness is AuthReadiness.READY
            and snapshot.source == "test_fixture"
        ):
            return AuthReadiness.READY
        if snapshot.auth_readiness is AuthReadiness.MISSING:
            return AuthReadiness.MISSING
        return AuthReadiness.NOT_CHECKED
    if (
        snapshot.auth_readiness is AuthReadiness.READY
        and snapshot.source == "test_fixture"
    ):
        return AuthReadiness.READY
    if snapshot.auth_readiness is AuthReadiness.MISSING:
        return AuthReadiness.MISSING
    if snapshot.auth_readiness is AuthReadiness.NOT_CHECKED:
        return AuthReadiness.NOT_CHECKED
    return AuthReadiness.NOT_REQUIRED


def _auth_failure(
    assertion: CapabilityAssertion,
    readiness: AuthReadiness,
) -> DecisionReason | None:
    if readiness in {AuthReadiness.NOT_REQUIRED, AuthReadiness.READY}:
        return None
    if readiness is AuthReadiness.MISSING:
        return _failed(
            "auth_readiness_missing",
            assertion,
            "Required authentication metadata is missing",
        )
    return _failed(
        "auth_readiness_not_checked",
        assertion,
        "Credential-requiring capability was not checked; no credential was read",
    )


def _field_contract(
    assertion: CapabilityAssertion,
) -> tuple[set[str] | None, set[str] | None]:
    if (
        "required" not in assertion.field_contract
        or "optional" not in assertion.field_contract
    ):
        return None, None
    required = assertion.field_contract["required"]
    optional = assertion.field_contract["optional"]
    if not _is_string_list(required) or not _is_string_list(optional):
        return None, None
    return set(required), set(optional)


def _is_string_list(value: object) -> bool:
    return isinstance(value, list) and all(
        isinstance(item, str) and bool(item) for item in value
    )


def _assess_unit_cost(
    implementation: CapabilityImplementation,
) -> _CostAssessment:
    if "unit_cost_usd" not in implementation.cost_hint:
        return _CostAssessment(state="unknown", unit_cost_usd=None)
    value = implementation.cost_hint["unit_cost_usd"]
    if value is None:
        return _CostAssessment(state="unknown", unit_cost_usd=None)
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return _CostAssessment(state="invalid", unit_cost_usd=None)
    if isinstance(value, float) and not math.isfinite(value):
        return _CostAssessment(state="invalid", unit_cost_usd=None)
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return _CostAssessment(state="invalid", unit_cost_usd=None)
    if not decimal_value.is_finite() or decimal_value < 0:
        return _CostAssessment(state="invalid", unit_cost_usd=None)
    return _CostAssessment(state="known", unit_cost_usd=decimal_value)


def _budget_failure(
    requirement: RouteRequirement,
    assertion: CapabilityAssertion,
    cost: _CostAssessment,
) -> DecisionReason | None:
    if cost.state == "invalid":
        return _failed(
            "invalid_unit_cost",
            assertion,
            "unit_cost_usd metadata is invalid and cannot be used for routing",
        )
    if cost.state == "unknown" and requirement.budget_ceiling is not None:
        return _failed(
            "budget_unknown_under_ceiling",
            assertion,
            "Unknown unit cost cannot prove compliance with the budget ceiling",
        )
    if (
        cost.unit_cost_usd is not None
        and requirement.budget_ceiling is not None
        and cost.unit_cost_usd > requirement.budget_ceiling.amount
    ):
        return _failed(
            "budget_ceiling_exceeded",
            assertion,
            "Known unit cost exceeds the RouteRequirement budget ceiling",
        )
    return None


def _deduplicate_candidates(
    candidates: Sequence[_QualifiedCandidate],
) -> list[_QualifiedCandidate]:
    ordered = sorted(candidates, key=_candidate_sort_key)
    unique: list[_QualifiedCandidate] = []
    seen_implementations: set[str] = set()
    for candidate in ordered:
        implementation_id = candidate.decision.implementation_id
        if implementation_id in seen_implementations:
            continue
        seen_implementations.add(implementation_id)
        unique.append(candidate)
    return unique


def _candidate_sort_key(
    candidate: _QualifiedCandidate,
) -> tuple[int, int, str, str]:
    weighted_score = candidate.decision.weighted_score
    if weighted_score is None:
        raise ValueError("qualified_candidate_missing_score")
    status_priority = (
        0
        if candidate.decision.capability_status is CapabilityStatus.VERIFIED
        else 1
    )
    return (
        status_priority,
        -weighted_score,
        candidate.decision.implementation_id,
        candidate.decision.assertion_id,
    )


def _build_route(
    requirement: RouteRequirement,
    candidates: Sequence[_QualifiedCandidate],
    *,
    exclusions: Sequence[DecisionReason],
    policy: RoutingPolicy,
) -> RoutePlanPreview:
    if not candidates:
        effective_exclusions = list(exclusions)
        if not effective_exclusions:
            effective_exclusions.append(
                DecisionReason(
                    code="unresolved_no_verified_capability",
                    reason="No atomic Capability Assertion was available for routing",
                )
            )
        return _held_route(requirement, exclusions=effective_exclusions)

    primary_candidate = candidates[0]
    fallback_candidates = list(candidates[1:])
    primary = primary_candidate.decision
    fallbacks = [candidate.decision for candidate in fallback_candidates]
    status = (
        RoutePlanStatus.RESOLVED
        if primary.capability_status is CapabilityStatus.VERIFIED
        else RoutePlanStatus.PARTIAL
    )
    approval_reasons = _deduplicate_reasons(
        [
            reason
            for candidate in candidates
            for reason in candidate.decision.approval_reasons
        ]
    )
    partial_present = any(
        candidate.decision.capability_status is CapabilityStatus.PARTIAL
        for candidate in candidates
    )
    degradation_rule = (
        DecisionReason(
            code="partial_degradation_requires_approval",
            reason="A partial proposed route cannot execute without a future approval object",
        )
        if partial_present
        else None
    )
    limitations = {"execution_authorized=false", "route_preview_only"}
    if primary_candidate.cost.state == "unknown":
        limitations.add("cost_unknown")

    return RoutePlanPreview(
        requirement_ref=requirement.requirement_ref,
        status=status,
        primary_implementation=primary,
        fallback_implementations=fallbacks,
        shadow_rule=_shadow_rule(fallback_candidates, policy),
        required_fields=sorted(set(requirement.required_fields)),
        optional_fields=sorted(set(requirement.optional_fields)),
        missing_optional_fields=primary.missing_optional_fields,
        budget_status=_selected_budget_status(requirement, primary_candidate.cost),
        rate_limit_policy=requirement.rate_limit_requirement,
        retention_policy=requirement.retention_requirement,
        route_eligible=True,
        readiness_status=primary.readiness_status,
        approval_required=bool(approval_reasons),
        approval_reasons=approval_reasons,
        policy_gates=list(primary_candidate.gate_trace),
        score_breakdown=primary.score_breakdown,
        exclusion_reasons=list(exclusions),
        degradation_rule=degradation_rule,
        limitations=sorted(limitations),
        execution_authorized=False,
    )


def _held_route(
    requirement: RouteRequirement,
    *,
    exclusions: Sequence[DecisionReason],
) -> RoutePlanPreview:
    return RoutePlanPreview(
        requirement_ref=requirement.requirement_ref,
        status=RoutePlanStatus.HELD,
        primary_implementation=None,
        fallback_implementations=[],
        shadow_rule=ShadowRule(
            enabled=False,
            fallback_implementation_id=None,
            sample_rate=None,
            max_items=None,
            reason="no_verified_fallback",
            execution_authorized=False,
        ),
        required_fields=sorted(set(requirement.required_fields)),
        optional_fields=sorted(set(requirement.optional_fields)),
        missing_optional_fields=sorted(set(requirement.optional_fields)),
        budget_status=_held_budget_status(requirement, exclusions),
        rate_limit_policy=requirement.rate_limit_requirement,
        retention_policy=requirement.retention_requirement,
        route_eligible=False,
        readiness_status=None,
        approval_required=False,
        approval_reasons=[],
        policy_gates=[],
        score_breakdown=None,
        exclusion_reasons=list(exclusions),
        degradation_rule=None,
        limitations=["execution_authorized=false", "route_preview_only"],
        execution_authorized=False,
    )


def _shadow_rule(
    fallback_candidates: Sequence[_QualifiedCandidate],
    policy: RoutingPolicy,
) -> ShadowRule:
    verified_fallback = next(
        (
            candidate
            for candidate in fallback_candidates
            if candidate.decision.capability_status is CapabilityStatus.VERIFIED
        ),
        None,
    )
    if verified_fallback is None:
        return ShadowRule(
            enabled=False,
            fallback_implementation_id=None,
            sample_rate=None,
            max_items=None,
            reason="no_verified_fallback",
            execution_authorized=False,
        )
    return ShadowRule(
        enabled=True,
        fallback_implementation_id=verified_fallback.decision.implementation_id,
        sample_rate=policy.shadow_sample_rate,
        max_items=policy.shadow_max_items,
        reason="declarative_verified_fallback_sample",
        execution_authorized=False,
    )


def _selected_budget_status(
    requirement: RouteRequirement,
    cost: _CostAssessment,
) -> BudgetStatus:
    if cost.state == "unknown":
        return BudgetStatus.UNKNOWN
    if requirement.budget_ceiling is None:
        return BudgetStatus.NOT_APPLICABLE
    return BudgetStatus.WITHIN_CEILING


def _held_budget_status(
    requirement: RouteRequirement,
    exclusions: Sequence[DecisionReason],
) -> BudgetStatus:
    codes = {reason.code for reason in exclusions}
    if "budget_ceiling_exceeded" in codes:
        return BudgetStatus.EXCEEDED
    if {"budget_unknown_under_ceiling", "invalid_unit_cost"} & codes:
        return BudgetStatus.UNKNOWN
    if requirement.budget_ceiling is None:
        return BudgetStatus.NOT_APPLICABLE
    return BudgetStatus.UNKNOWN


def _deduplicate_reasons(
    reasons: Sequence[DecisionReason],
) -> list[DecisionReason]:
    unique: list[DecisionReason] = []
    seen: set[tuple[str, str]] = set()
    for reason in reasons:
        key = (reason.code, reason.reason)
        if key in seen:
            continue
        seen.add(key)
        unique.append(reason)
    return unique


def _passed(code: str, reason: str) -> DecisionReason:
    return DecisionReason(code=code, reason=reason)


def _failed(
    code: str,
    assertion: CapabilityAssertion,
    reason: str,
) -> DecisionReason:
    return DecisionReason(
        code=code,
        reason=f"{assertion.assertion_id}: {reason}",
    )
