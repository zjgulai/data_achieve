from __future__ import annotations

import inspect
import math
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityAssertion,
    CapabilityCatalog,
    CapabilityConstraint,
    CapabilityImplementation,
    CapabilityOperation,
    CapabilityStatus,
    ConstraintSeverity,
    EvidenceType,
    PlatformId,
    ResourceType,
)
from data_intelligence_hub.schemas.workflow_planner import (
    AuthReadiness,
    BudgetCeiling,
    BudgetStatus,
    CapabilityReadinessSnapshot,
    DecisionReason,
    PolicyProfile,
    RetentionIntent,
    RoutePlanPreview,
    RouteRequirement,
)
from data_intelligence_hub.services.capability_catalog import (
    clear_capability_catalog_cache,
    get_capability_catalog,
)
from data_intelligence_hub.services.workflow_planner import capability_resolver
from data_intelligence_hub.services.workflow_planner.capability_resolver import (
    derive_product_readiness,
    resolve_route_plans,
)
from data_intelligence_hub.services.workflow_planner.policies import (
    MARKET_MONITORING_BALANCED_WEIGHTS,
    calculate_weighted_score,
    get_routing_policy,
)

FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "workflow_planner"
    / "synthetic_capability_catalog_v1.json"
)
EXPECTED_GATE_CODES = [
    "capability_status_passed",
    "policy_passed",
    "auth_readiness_passed",
    "purpose_scope_passed",
    "region_scope_passed",
    "capability_match_passed",
    "required_fields_passed",
    "budget_passed",
]


def load_synthetic_catalog() -> CapabilityCatalog:
    return CapabilityCatalog.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def isolate_catalog_cache() -> Iterator[None]:
    clear_capability_catalog_cache()
    yield
    clear_capability_catalog_cache()


@pytest.fixture()
def search_requirement() -> RouteRequirement:
    return RouteRequirement(
        requirement_ref="requirement:search",
        scope_keys=["sha256:" + ("a" * 64)],
        step_refs=["step:discover"],
        platform=PlatformId.YOUTUBE,
        resource_type=ResourceType.CONTENT,
        operation=CapabilityOperation.SEARCH_DISCOVER,
        purpose="market_research",
        regions=["US"],
        required_fields=["id", "url", "text"],
        optional_fields=["author", "published_at", "metrics"],
        budget_ceiling=None,
        freshness_requirement=None,
        rate_limit_requirement=None,
        retention_requirement=RetentionIntent(days=30),
        allow_partial_degradation=False,
    )


def requirement_with(
    requirement: RouteRequirement,
    **updates: object,
) -> RouteRequirement:
    payload = requirement.model_dump(mode="json")
    payload.update(updates)
    return RouteRequirement.model_validate(payload)


def catalog_subset(
    catalog: CapabilityCatalog,
    implementation_ids: set[str],
    *,
    operation: CapabilityOperation | None = CapabilityOperation.SEARCH_DISCOVER,
) -> CapabilityCatalog:
    implementations = [
        implementation
        for implementation in catalog.implementations
        if implementation.implementation_id in implementation_ids
    ]
    assertions = [
        assertion
        for assertion in catalog.assertions
        if assertion.implementation_id in implementation_ids
        and (operation is None or assertion.operation is operation)
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


def replace_implementation(
    catalog: CapabilityCatalog,
    implementation_id: str,
    **updates: object,
) -> CapabilityCatalog:
    implementations = [
        (
            item.model_copy(update=updates, deep=True)
            if item.implementation_id == implementation_id
            else item
        )
        for item in catalog.implementations
    ]
    return catalog.model_copy(update={"implementations": implementations}, deep=True)


def replace_assertion(
    catalog: CapabilityCatalog,
    assertion_id: str,
    **updates: object,
) -> CapabilityCatalog:
    assertions = [
        (
            item.model_copy(update=updates, deep=True)
            if item.assertion_id == assertion_id
            else item
        )
        for item in catalog.assertions
    ]
    return catalog.model_copy(update={"assertions": assertions}, deep=True)


def resolve_one(
    requirement: RouteRequirement,
    catalog: CapabilityCatalog,
    *,
    readiness: dict[str, CapabilityReadinessSnapshot] | None = None,
) -> RoutePlanPreview:
    routes = resolve_route_plans(
        [requirement],
        catalog,
        policy=get_routing_policy(PolicyProfile.MARKET_MONITORING_BALANCED),
        readiness_snapshots=(
            derive_product_readiness(catalog) if readiness is None else readiness
        ),
    )
    assert len(routes) == 1
    return routes[0]


def reason_codes(route: RoutePlanPreview) -> list[str]:
    return [reason.code for reason in route.exclusion_reasons]


def search_assertion(catalog: CapabilityCatalog, implementation_id: str) -> CapabilityAssertion:
    return next(
        assertion
        for assertion in catalog.assertions
        if assertion.implementation_id == implementation_id
        and assertion.operation is CapabilityOperation.SEARCH_DISCOVER
    )


def implementation(
    catalog: CapabilityCatalog,
    implementation_id: str,
) -> CapabilityImplementation:
    return next(
        item
        for item in catalog.implementations
        if item.implementation_id == implementation_id
    )


def test_synthetic_catalog_is_strict_unique_and_l2_only() -> None:
    catalog = load_synthetic_catalog()
    expected = {
        "fixture.primary": {
            "status": CapabilityStatus.VERIFIED,
            "cost": 0.01,
            "required": ["id", "url", "text"],
            "optional": ["author", "published_at", "metrics"],
            "score": {
                "coverage": 5,
                "freshness": 5,
                "history": 4,
                "reliability": 5,
                "schema_stability": 5,
                "cost_efficiency": 4,
                "maintainability": 5,
                "evidence_confidence": 5,
            },
        },
        "fixture.fallback": {
            "status": CapabilityStatus.VERIFIED,
            "cost": 0.02,
            "required": ["id", "url", "text"],
            "optional": ["author", "published_at"],
            "score": {
                "coverage": 4,
                "freshness": 4,
                "history": 4,
                "reliability": 4,
                "schema_stability": 4,
                "cost_efficiency": 3,
                "maintainability": 4,
                "evidence_confidence": 5,
            },
        },
        "fixture.partial": {
            "status": CapabilityStatus.PARTIAL,
            "cost": 0.005,
            "required": ["id", "url", "text"],
            "optional": ["author"],
            "score": {
                "coverage": 5,
                "freshness": 4,
                "history": 3,
                "reliability": 3,
                "schema_stability": 3,
                "cost_efficiency": 5,
                "maintainability": 3,
                "evidence_confidence": 4,
            },
        },
    }

    assert catalog.evidence_level == "L2-fixture-or-dry-run"
    assert catalog.provider_call is False
    assert catalog.production_write_allowed is False
    assert len(catalog.implementations) == 3
    assert len(catalog.assertions) == 12
    assert len(catalog.evidence) == 12
    assert {item.implementation_id for item in catalog.implementations} == {
        "fixture.primary",
        "fixture.fallback",
        "fixture.partial",
    }
    for item in catalog.implementations:
        assert item.platform is PlatformId.YOUTUBE
        assert item.access_channel.value == "official_authorized_api"
        assert item.delivery_form.value == "endpoint"
        assert item.deployment_mode.value == "managed_saas"
        assert item.lifecycle_status == "active"
        assert item.required_credentials == []
        assert item.cost_hint == {
            "unit_cost_usd": expected[item.implementation_id]["cost"]
        }
    assert {item.operation for item in catalog.assertions} == {
        CapabilityOperation.SEARCH_DISCOVER,
        CapabilityOperation.RESOLVE_DETAIL,
        CapabilityOperation.MONITOR_INCREMENTAL,
        CapabilityOperation.BATCH_PARSE,
    }
    for assertion in catalog.assertions:
        implementation_expected = expected[assertion.implementation_id]
        assert assertion.assertion_id == (
            f"{assertion.implementation_id}:content:{assertion.operation.value}"
        )
        assert assertion.support_status is implementation_expected["status"]
        assert assertion.region_scope == ["global"]
        assert assertion.purpose_scope == ["market_research"]
        assert assertion.auth_scope == ["not_required"]
        assert assertion.constraints == []
        assert assertion.field_contract == {
            "required": implementation_expected["required"],
            "optional": implementation_expected["optional"],
        }
        assert assertion.score_profile.model_dump() == implementation_expected["score"]
    assert all(item.evidence_type is EvidenceType.FIXTURE for item in catalog.evidence)
    assert {item.evidence_grade for item in catalog.evidence} == {"L2-fixture"}
    assert all(item.hash_scope == "source_reference_only" for item in catalog.evidence)
    assert all(re.fullmatch(r"[0-9a-f]{64}", item.content_hash) for item in catalog.evidence)
    assert all(not item.provider_call_attempted for item in catalog.evidence)
    assert all(not item.credential_read_attempted for item in catalog.evidence)
    assert all(not item.live_client_created for item in catalog.evidence)
    assert all(not item.production_write_attempted for item in catalog.evidence)
    evidence_refs = [
        assertion.evidence_refs[0] for assertion in catalog.assertions
    ]
    assert all(len(assertion.evidence_refs) == 1 for assertion in catalog.assertions)
    assert len(evidence_refs) == len(set(evidence_refs)) == 12
    assert set(evidence_refs) == {item.evidence_id for item in catalog.evidence}


def test_policy_weights_and_known_fixture_scores_are_locked() -> None:
    catalog = load_synthetic_catalog()
    policy = get_routing_policy(PolicyProfile.MARKET_MONITORING_BALANCED)

    assert policy.version == "market_monitoring_balanced.v1"
    assert policy.allow_partial_proposals is True
    assert MARKET_MONITORING_BALANCED_WEIGHTS == {
        "coverage": 15,
        "freshness": 15,
        "history": 5,
        "reliability": 20,
        "schema_stability": 15,
        "cost_efficiency": 10,
        "maintainability": 5,
        "evidence_confidence": 15,
    }
    assert sum(MARKET_MONITORING_BALANCED_WEIGHTS.values()) == 100

    expected_scores = {
        "fixture.primary": 485,
        "fixture.fallback": 405,
        "fixture.partial": 380,
    }
    implementations = {
        item.implementation_id: item for item in catalog.implementations
    }
    for assertion in catalog.assertions:
        item = implementations[assertion.implementation_id]
        breakdown = calculate_weighted_score(
            assertion.score_profile,
            unit_cost_usd=item.cost_hint["unit_cost_usd"],
            budget_ceiling=None,
            policy=policy,
        )
        assert breakdown.weighted_score == expected_scores[assertion.implementation_id]
        assert breakdown.raw_dimensions == breakdown.effective_dimensions
        assert breakdown.trace_codes == []


def test_canonical_candidate_catalog_is_held(
    search_requirement: RouteRequirement,
) -> None:
    catalog = get_capability_catalog()
    before = catalog.model_dump(mode="json")

    route = resolve_one(search_requirement, catalog)

    assert route.status == "held"
    assert route.primary_implementation is None
    assert route.fallback_implementations == []
    assert route.score_breakdown is None
    assert route.execution_authorized is False
    assert "candidate_not_execution_eligible" in reason_codes(route)
    assert catalog.model_dump(mode="json") == before


def test_empty_atomic_catalog_has_an_explicit_held_reason(
    search_requirement: RouteRequirement,
) -> None:
    catalog = load_synthetic_catalog().model_copy(
        update={"implementations": [], "assertions": [], "evidence": []},
        deep=True,
    )

    route = resolve_one(search_requirement, catalog)

    assert route.status == "held"
    assert reason_codes(route) == ["unresolved_no_verified_capability"]


def test_synthetic_catalog_selects_stable_primary_fallback_and_shadow(
    search_requirement: RouteRequirement,
) -> None:
    catalog = load_synthetic_catalog()
    route = resolve_one(search_requirement, catalog)

    assert route.status == "resolved"
    assert route.primary_implementation is not None
    assert route.primary_implementation.implementation_id == "fixture.primary"
    assert route.primary_implementation.weighted_score == 485
    assert [item.implementation_id for item in route.fallback_implementations] == [
        "fixture.fallback"
    ]
    assert route.fallback_implementations[0].weighted_score == 405
    assert "partial_degradation_not_allowed" in reason_codes(route)
    assert [gate.code for gate in route.policy_gates] == EXPECTED_GATE_CODES
    assert route.budget_status is BudgetStatus.NOT_APPLICABLE
    assert route.shadow_rule.enabled is True
    assert route.shadow_rule.fallback_implementation_id == "fixture.fallback"
    assert route.shadow_rule.sample_rate == 0.05
    assert route.shadow_rule.max_items == 10
    assert route.shadow_rule.execution_authorized is False
    assert route.execution_authorized is False


def test_partial_is_excluded_without_flag_and_proposed_with_explicit_flag(
    search_requirement: RouteRequirement,
) -> None:
    partial_only = catalog_subset(
        load_synthetic_catalog(),
        {"fixture.partial"},
    )

    held = resolve_one(search_requirement, partial_only)
    proposed = resolve_one(
        requirement_with(search_requirement, allow_partial_degradation=True),
        partial_only,
    )

    assert held.status == "held"
    assert held.primary_implementation is None
    assert "partial_degradation_not_allowed" in reason_codes(held)
    assert proposed.status == "partial"
    assert proposed.primary_implementation is not None
    assert proposed.primary_implementation.implementation_id == "fixture.partial"
    assert proposed.primary_implementation.weighted_score == 380
    assert proposed.primary_implementation.approval_required is True
    assert proposed.approval_required is True
    assert proposed.execution_authorized is False


def test_verified_primary_precedes_partial_and_partial_fallback_needs_approval(
    search_requirement: RouteRequirement,
) -> None:
    catalog = load_synthetic_catalog()
    requirement = requirement_with(
        search_requirement,
        allow_partial_degradation=True,
    )

    route = resolve_one(requirement, catalog)

    assert route.primary_implementation is not None
    assert route.primary_implementation.implementation_id == "fixture.primary"
    assert [item.implementation_id for item in route.fallback_implementations] == [
        "fixture.fallback",
        "fixture.partial",
    ]
    partial = route.fallback_implementations[1]
    assert partial.capability_status is CapabilityStatus.PARTIAL
    assert partial.approval_required is True
    assert partial.approval_reasons
    assert route.approval_required is True
    assert route.execution_authorized is False


def test_stable_tie_break_and_duplicate_implementation_suppression(
    search_requirement: RouteRequirement,
) -> None:
    catalog = catalog_subset(
        load_synthetic_catalog(),
        {"fixture.primary", "fixture.fallback"},
    )
    primary = search_assertion(catalog, "fixture.primary")
    fallback = search_assertion(catalog, "fixture.fallback")
    tied = replace_assertion(
        catalog,
        fallback.assertion_id,
        score_profile=primary.score_profile,
    )
    duplicate = primary.model_copy(
        update={"assertion_id": f"{primary.assertion_id}:zzz"},
        deep=True,
    )
    tied = tied.model_copy(
        update={"assertions": [*tied.assertions, duplicate]},
        deep=True,
    )

    route = resolve_one(search_requirement, tied)

    assert route.primary_implementation is not None
    assert route.primary_implementation.implementation_id == "fixture.fallback"
    assert route.primary_implementation.weighted_score == 485
    decisions = [route.primary_implementation, *route.fallback_implementations]
    assert [item.implementation_id for item in decisions] == [
        "fixture.fallback",
        "fixture.primary",
    ]
    primary_decision = next(
        item for item in decisions if item.implementation_id == "fixture.primary"
    )
    assert primary_decision.assertion_id == primary.assertion_id


def test_capability_status_gate_is_first_and_fail_fast(
    search_requirement: RouteRequirement,
) -> None:
    catalog = catalog_subset(load_synthetic_catalog(), {"fixture.primary"})
    assertion = search_assertion(catalog, "fixture.primary")
    blocking = CapabilityConstraint(
        constraint_type="policy",
        severity=ConstraintSeverity.BLOCKING,
        code="fixture_policy_block",
        details={},
    )
    candidate = replace_assertion(
        catalog,
        assertion.assertion_id,
        support_status=CapabilityStatus.CANDIDATE,
        constraints=[blocking],
        purpose_scope=["wrong-purpose"],
        region_scope=["EU"],
    )

    route = resolve_one(search_requirement, candidate)

    assert reason_codes(route) == ["candidate_not_execution_eligible"]
    assert route.policy_gates == []


def test_blocking_policy_and_blocked_action_constraints_exclude(
    search_requirement: RouteRequirement,
) -> None:
    source = catalog_subset(load_synthetic_catalog(), {"fixture.primary"})
    assertion = search_assertion(source, "fixture.primary")

    for constraint_type, code in (
        ("policy", "fixture_policy_block"),
        ("blocked_action", "fixture_action_block"),
    ):
        constraint = CapabilityConstraint(
            constraint_type=constraint_type,
            severity=ConstraintSeverity.BLOCKING,
            code=code,
            details={},
        )
        catalog = replace_assertion(
            source,
            assertion.assertion_id,
            constraints=[constraint],
        )
        route = resolve_one(search_requirement, catalog)
        assert route.status == "held"
        assert reason_codes(route) == [code]


def test_lifecycle_limited_does_not_self_block(
    search_requirement: RouteRequirement,
) -> None:
    catalog = catalog_subset(load_synthetic_catalog(), {"fixture.primary"})
    catalog = replace_implementation(
        catalog,
        "fixture.primary",
        lifecycle_status="limited",
    )

    route = resolve_one(search_requirement, catalog)

    assert route.status == "resolved"
    assert route.primary_implementation is not None


@pytest.mark.parametrize(
    ("status", "expected_code"),
    [
        (CapabilityStatus.UNKNOWN, "capability_unknown"),
        (CapabilityStatus.BLOCKED, "capability_blocked"),
        (CapabilityStatus.UNSUPPORTED, "operation_unsupported"),
        (CapabilityStatus.DEPRECATED, "implementation_deprecated"),
    ],
)
def test_ineligible_capability_statuses_never_route(
    search_requirement: RouteRequirement,
    status: CapabilityStatus,
    expected_code: str,
) -> None:
    catalog = catalog_subset(load_synthetic_catalog(), {"fixture.primary"})
    assertion = search_assertion(catalog, "fixture.primary")
    catalog = replace_assertion(
        catalog,
        assertion.assertion_id,
        support_status=status,
    )

    route = resolve_one(search_requirement, catalog)

    assert route.status == "held"
    assert reason_codes(route) == [expected_code]


@pytest.mark.parametrize(
    ("updates", "expected_code"),
    [
        ({"purpose_scope": ["brand_monitoring"]}, "purpose_not_supported"),
        ({"region_scope": ["EU"]}, "region_not_supported"),
        (
            {"field_contract": {"required": ["id", "url"], "optional": ["text"]}},
            "required_fields_missing",
        ),
        ({"operation": CapabilityOperation.RESOLVE_DETAIL}, "capability_requirement_mismatch"),
    ],
)
def test_purpose_region_exact_match_and_required_field_gates_exclude(
    search_requirement: RouteRequirement,
    updates: dict[str, object],
    expected_code: str,
) -> None:
    catalog = catalog_subset(load_synthetic_catalog(), {"fixture.primary"})
    assertion = search_assertion(catalog, "fixture.primary")
    catalog = replace_assertion(catalog, assertion.assertion_id, **updates)

    route = resolve_one(search_requirement, catalog)

    assert route.status == "held"
    assert reason_codes(route) == [expected_code]
    if expected_code == "required_fields_missing":
        assert "text" in route.exclusion_reasons[0].reason


@pytest.mark.parametrize("missing_key", ["required", "optional"])
def test_field_contract_requires_both_list_keys_even_without_required_fields(
    search_requirement: RouteRequirement,
    missing_key: str,
) -> None:
    catalog = catalog_subset(load_synthetic_catalog(), {"fixture.primary"})
    assertion = search_assertion(catalog, "fixture.primary")
    field_contract = dict(assertion.field_contract)
    del field_contract[missing_key]
    catalog = replace_assertion(
        catalog,
        assertion.assertion_id,
        field_contract=field_contract,
    )
    requirement = requirement_with(search_requirement, required_fields=[])

    route = resolve_one(requirement, catalog)

    assert route.status == "held"
    assert route.primary_implementation is None
    assert reason_codes(route) == ["field_contract_invalid"]


def test_known_budget_ceiling_excludes_and_no_ceiling_is_not_applicable(
    search_requirement: RouteRequirement,
) -> None:
    catalog = catalog_subset(load_synthetic_catalog(), {"fixture.primary"})

    no_ceiling = resolve_one(search_requirement, catalog)
    exceeded = resolve_one(
        requirement_with(
            search_requirement,
            budget_ceiling=BudgetCeiling(amount="0.009", currency="USD").model_dump(
                mode="json"
            ),
        ),
        catalog,
    )

    assert no_ceiling.status == "resolved"
    assert no_ceiling.budget_status is BudgetStatus.NOT_APPLICABLE
    assert exceeded.status == "held"
    assert exceeded.budget_status is BudgetStatus.EXCEEDED
    assert reason_codes(exceeded) == ["budget_ceiling_exceeded"]


def test_unknown_cost_without_ceiling_is_capped_and_with_ceiling_is_excluded(
    search_requirement: RouteRequirement,
) -> None:
    catalog = catalog_subset(load_synthetic_catalog(), {"fixture.primary"})
    catalog = replace_implementation(
        catalog,
        "fixture.primary",
        cost_hint={},
    )

    no_ceiling = resolve_one(search_requirement, catalog)
    with_ceiling = resolve_one(
        requirement_with(
            search_requirement,
            budget_ceiling={"amount": "1", "currency": "USD"},
        ),
        catalog,
    )

    assert no_ceiling.status == "resolved"
    assert no_ceiling.budget_status is BudgetStatus.UNKNOWN
    assert no_ceiling.primary_implementation is not None
    breakdown = no_ceiling.primary_implementation.score_breakdown
    assert breakdown is not None
    assert breakdown.raw_dimensions["cost_efficiency"] == 4
    assert breakdown.effective_dimensions["cost_efficiency"] == 1
    assert breakdown.weighted_score == 455
    assert "cost_score_capped_unknown" in breakdown.trace_codes
    assert with_ceiling.status == "held"
    assert with_ceiling.budget_status is BudgetStatus.UNKNOWN
    assert reason_codes(with_ceiling) == ["budget_unknown_under_ceiling"]


@pytest.mark.parametrize(
    "invalid_cost",
    [True, "0.01", -0.01, math.nan, math.inf, -math.inf],
)
def test_invalid_cost_metadata_fails_closed(
    search_requirement: RouteRequirement,
    invalid_cost: object,
) -> None:
    catalog = catalog_subset(load_synthetic_catalog(), {"fixture.primary"})
    catalog = replace_implementation(
        catalog,
        "fixture.primary",
        cost_hint={"unit_cost_usd": invalid_cost},
    )

    route = resolve_one(search_requirement, catalog)

    assert route.status == "held"
    assert route.primary_implementation is None
    assert reason_codes(route) == ["invalid_unit_cost"]


def test_auth_readiness_derives_metadata_without_reading_credentials(
    search_requirement: RouteRequirement,
) -> None:
    catalog = catalog_subset(load_synthetic_catalog(), {"fixture.primary"})
    not_required = derive_product_readiness(catalog)
    assert not_required["fixture.primary"].auth_readiness is AuthReadiness.NOT_REQUIRED
    assert not_required["fixture.primary"].credential_read_status == "not_read"

    credentialed = replace_implementation(
        catalog,
        "fixture.primary",
        required_credentials=["fixture_token"],
    )
    product_readiness = derive_product_readiness(credentialed)
    assert product_readiness["fixture.primary"].auth_readiness is AuthReadiness.NOT_CHECKED
    assert product_readiness["fixture.primary"].credential_read_status == "not_read"
    held = resolve_one(search_requirement, credentialed)
    assert held.status == "held"
    assert reason_codes(held) == ["auth_readiness_not_checked"]

    ready = {
        "fixture.primary": CapabilityReadinessSnapshot(
            implementation_id="fixture.primary",
            auth_readiness=AuthReadiness.READY,
            source="test_fixture",
            credential_read_status="not_read",
        )
    }
    resolved = resolve_one(search_requirement, credentialed, readiness=ready)
    assert resolved.status == "resolved"
    assert resolved.readiness_status is AuthReadiness.READY
    assert resolved.execution_authorized is False


def test_non_test_ready_snapshot_is_not_trusted(
    search_requirement: RouteRequirement,
) -> None:
    catalog = catalog_subset(load_synthetic_catalog(), {"fixture.primary"})
    catalog = replace_implementation(
        catalog,
        "fixture.primary",
        required_credentials=["fixture_token"],
    )
    injected = {
        "fixture.primary": CapabilityReadinessSnapshot(
            implementation_id="fixture.primary",
            auth_readiness=AuthReadiness.READY,
            source="http_request",
            credential_read_status="not_read",
        )
    }

    route = resolve_one(search_requirement, catalog, readiness=injected)

    assert route.status == "held"
    assert reason_codes(route) == ["auth_readiness_not_checked"]


def test_readiness_mapping_key_must_match_snapshot_and_catalog(
    search_requirement: RouteRequirement,
) -> None:
    catalog = catalog_subset(load_synthetic_catalog(), {"fixture.primary"})
    mismatched = {
        "wrong-key": CapabilityReadinessSnapshot(
            implementation_id="fixture.primary",
            auth_readiness=AuthReadiness.READY,
            source="test_fixture",
            credential_read_status="not_read",
        )
    }

    with pytest.raises(ValueError, match="readiness_snapshot_key_mismatch"):
        resolve_one(search_requirement, catalog, readiness=mismatched)

    unknown = {
        "fixture.unknown": CapabilityReadinessSnapshot(
            implementation_id="fixture.unknown",
            auth_readiness=AuthReadiness.READY,
            source="test_fixture",
            credential_read_status="not_read",
        )
    }
    with pytest.raises(ValueError, match="readiness_snapshot_implementation_unknown"):
        resolve_one(search_requirement, catalog, readiness=unknown)


def test_shadow_requires_a_verified_unique_fallback(
    search_requirement: RouteRequirement,
) -> None:
    catalog = load_synthetic_catalog()
    primary_only = catalog_subset(catalog, {"fixture.primary"})
    primary_partial = catalog_subset(
        catalog,
        {"fixture.primary", "fixture.partial"},
    )

    no_fallback = resolve_one(search_requirement, primary_only)
    partial_fallback = resolve_one(
        requirement_with(search_requirement, allow_partial_degradation=True),
        primary_partial,
    )

    assert no_fallback.shadow_rule.enabled is False
    assert no_fallback.shadow_rule.fallback_implementation_id is None
    assert partial_fallback.fallback_implementations[0].implementation_id == "fixture.partial"
    assert partial_fallback.shadow_rule.enabled is False
    assert partial_fallback.shadow_rule.execution_authorized is False


def test_compiler_missing_precondition_has_absolute_priority_and_zero_score(
    search_requirement: RouteRequirement,
) -> None:
    requirement = requirement_with(
        search_requirement,
        precondition_failures=[
            DecisionReason(
                code="compiler_missing",
                reason="Query compiler missing for youtube",
            ).model_dump(mode="json")
        ],
    )

    route = resolve_one(requirement, load_synthetic_catalog())

    assert route.status == "held"
    assert route.primary_implementation is None
    assert route.fallback_implementations == []
    assert route.score_breakdown is None
    assert route.policy_gates == []
    assert reason_codes(route) == ["compiler_missing"]
    assert route.execution_authorized is False


def test_resolver_uses_atomic_assertions_without_an_evidence_grade_gate(
    search_requirement: RouteRequirement,
) -> None:
    catalog = catalog_subset(load_synthetic_catalog(), {"fixture.primary"})
    downgraded_evidence = [
        item.model_copy(update={"evidence_grade": "L0-unverified"}, deep=True)
        for item in catalog.evidence
    ]
    catalog = catalog.model_copy(update={"evidence": downgraded_evidence}, deep=True)

    route = resolve_one(search_requirement, catalog)

    assert route.status == "resolved"
    assert route.primary_implementation is not None
    assert route.primary_implementation.evidence_refs
    source = inspect.getsource(capability_resolver)
    assert "capability_matrix" not in source
    assert "evidence_grade" not in source


def test_resolver_does_not_mutate_input_catalog(
    search_requirement: RouteRequirement,
) -> None:
    catalog = load_synthetic_catalog()
    before = catalog.model_dump(mode="json")

    first = resolve_one(search_requirement, catalog)
    second = resolve_one(search_requirement, catalog)

    assert first == second
    assert catalog.model_dump(mode="json") == before
