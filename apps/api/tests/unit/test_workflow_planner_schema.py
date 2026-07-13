from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import BaseModel, ValidationError

from data_intelligence_hub.schemas.workflow_planner import (
    AttributionContract,
    BudgetCeiling,
    BudgetSummary,
    CapabilityReadinessSnapshot,
    CompiledPlatformQuery,
    CoverageSummary,
    DecisionReason,
    DecisionTrace,
    DecisionTraceEntry,
    DeliveryIntent,
    MonitoringScopeDraft,
    NormalizedMonitoringScope,
    NormalizedPlanningInput,
    PlanningInput,
    QueryCompilerFailure,
    QueryTerm,
    RateLimitIntent,
    RetentionIntent,
    RouteCandidateDecision,
    RoutePlanPreview,
    RouteRequirement,
    ScheduleIntent,
    ScopeRefMapping,
    ScoreBreakdown,
    ShadowRule,
    StepDataContract,
    StepDataContractField,
    WorkflowPlanFingerprintPayload,
    WorkflowPlanPreview,
    WorkflowStepPreview,
)

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "workflow_planner"
SCOPE_KEY = f"sha256:{'a' * 64}"
PROJECT_ID = "00000000-0000-0000-0000-000000000001"
GENERATED_AT = "2026-07-12T00:00:00Z"
PREVIEW_BOUNDARY_FIELDS = (
    "execution_authorized",
    "provider_call",
    "actor_run",
    "browser_run",
    "llm_call",
    "workflow_run_created",
    "database_write",
)
FINGERPRINT_FORBIDDEN_FIELDS = (
    "scope_ref",
    "source_scope_refs",
    "project_id",
    "generated_at",
    "request_id",
)


def load_request(name: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8")),
    )


def build_score_breakdown_payload() -> dict[str, Any]:
    return {
        "raw_dimensions": {"coverage": 5},
        "effective_dimensions": {"coverage": 5},
        "weights": {"coverage": 15},
        "weighted_score": 75,
        "trace_codes": [],
    }


def build_step_data_contract_payload() -> dict[str, Any]:
    return {
        "schema_version": "step_data_contract.v1",
        "fields": [
            {
                "name": "query",
                "data_type": "string",
                "cardinality": "one",
                "required": True,
                "source_step_ref": None,
                "description": "Normalized query input",
            }
        ],
    }


def build_query_term_payload() -> dict[str, Any]:
    return {
        "term": "Acme",
        "normalized_term": "acme",
        "scope_ref": "scope-1",
        "scope_key": SCOPE_KEY,
        "origin": "canonical",
        "status": "active",
        "reason": "deterministic_input",
        "source": "user_input",
        "score": None,
        "conflict_codes": [],
    }


def build_compiled_query_payload() -> dict[str, Any]:
    return {
        "platform": "youtube",
        "scope_keys": [SCOPE_KEY],
        "source_scope_refs": ["scope-1"],
        "resource_type": "content",
        "operation": "search_discover",
        "query_version": "youtube.declarative.v1",
        "normalized_expression": "{}",
        "include_terms": ["acme"],
        "exclude_terms": ["jobs"],
        "account_filters": ["@acme"],
        "url_inputs": [],
        "limitations": ["declarative_preview_only"],
    }


def build_step_payload() -> dict[str, Any]:
    return {
        "step_ref": "step:discover",
        "template_key": "discover_content",
        "sequence": 1,
        "label": "Discover content",
        "execution_kind": "future_capability",
        "depends_on": [],
        "platform": "youtube",
        "scope_keys": [SCOPE_KEY],
        "resource_type": "content",
        "operation": "search_discover",
        "requirement_ref": "requirement:search",
        "input_contract": build_step_data_contract_payload(),
        "output_contract": build_step_data_contract_payload(),
        "planning_status": "planned",
        "limitations": ["preview_only"],
    }


def build_candidate_payload() -> dict[str, Any]:
    return {
        "assertion_id": "assertion:fixture-primary",
        "implementation_id": "fixture.primary",
        "capability_status": "verified",
        "score_breakdown": build_score_breakdown_payload(),
        "weighted_score": 75,
        "route_eligible": True,
        "readiness_status": "not_required",
        "approval_required": False,
        "approval_reasons": [],
        "missing_optional_fields": [],
        "evidence_refs": ["evidence:fixture"],
    }


def build_route_plan_payload() -> dict[str, Any]:
    return {
        "requirement_ref": "requirement:search",
        "status": "resolved",
        "primary_implementation": build_candidate_payload(),
        "fallback_implementations": [],
        "shadow_rule": {
            "enabled": False,
            "fallback_implementation_id": None,
            "sample_rate": None,
            "max_items": None,
            "reason": "no_fallback",
            "execution_authorized": False,
        },
        "required_fields": ["id", "url", "text"],
        "optional_fields": ["author"],
        "missing_optional_fields": [],
        "budget_status": "within_ceiling",
        "rate_limit_policy": {"max_requests": 10, "period_seconds": 60},
        "retention_policy": {"days": 30},
        "route_eligible": True,
        "readiness_status": "not_required",
        "approval_required": False,
        "approval_reasons": [],
        "policy_gates": [{"code": "policy_allowed", "reason": "Policy permits route"}],
        "score_breakdown": build_score_breakdown_payload(),
        "exclusion_reasons": [],
        "degradation_rule": None,
        "limitations": ["preview_only"],
        "execution_authorized": False,
    }


def build_normalized_input_payload() -> dict[str, Any]:
    return {
        "flow_mode": "periodic_monitoring",
        "scopes": [
            {
                "scope_key": SCOPE_KEY,
                "source_scope_refs": ["scope-1"],
                "scope_type": "brand",
                "canonical_term": "acme",
                "aliases": ["acme"],
                "include_terms": ["running shoes"],
                "exclude_terms": ["jobs"],
                "official_accounts": ["@acme"],
                "seed_urls": [],
                "effective_languages": ["en"],
                "effective_regions": ["US"],
                "effective_platforms": ["youtube"],
                "match_mode": "phrase",
            }
        ],
        "schedule_intent": {"cadence": "daily", "timezone": "UTC"},
        "delivery_intent": {"outputs": ["brief"]},
        "policy_profile": "market_monitoring_balanced",
        "purpose": "market_research",
        "required_fields": ["id", "url", "text"],
        "optional_fields": ["author"],
        "budget_ceiling": {"amount": "1.00", "currency": "USD"},
        "rate_limit_intent": {"max_requests": 10, "period_seconds": 60},
        "retention_intent": {"days": 30},
        "allow_partial_degradation": False,
    }


def build_trace_entry_payload() -> dict[str, Any]:
    return {
        "code": "route_selected",
        "reason": "Verified route selected",
        "scope_keys": [SCOPE_KEY],
        "requirement_ref": "requirement:search",
        "details": {"implementation_id": "fixture.primary"},
    }


def build_coverage_payload() -> dict[str, Any]:
    return {
        "total_requirements": 1,
        "resolved_requirements": 1,
        "partial_requirements": 0,
        "held_requirements": 0,
    }


def build_budget_summary_payload() -> dict[str, Any]:
    return {
        "currency": "USD",
        "known_selected_unit_cost": "0.01",
        "unknown_count": 0,
        "budget_status": "within_ceiling",
    }


def build_preview_payload() -> dict[str, Any]:
    return {
        "schema_version": "workflow_plan_preview.v1",
        "planner_contract_version": "workflow_planner.v1",
        "project_id": PROJECT_ID,
        "flow_mode": "periodic_monitoring",
        "planning_status": "resolved",
        "normalized_input": build_normalized_input_payload(),
        "scope_ref_map": [{"scope_ref": "scope-1", "scope_key": SCOPE_KEY}],
        "query_terms": [build_query_term_payload()],
        "compiled_queries": [build_compiled_query_payload()],
        "steps": [build_step_payload()],
        "route_requirements": [
            {
                "requirement_ref": "requirement:search",
                "scope_keys": [SCOPE_KEY],
                "step_refs": ["step:discover"],
                "platform": "youtube",
                "resource_type": "content",
                "operation": "search_discover",
                "purpose": "market_research",
                "regions": ["US"],
                "required_fields": ["id", "url", "text"],
                "optional_fields": ["author"],
                "budget_ceiling": {"amount": "1.00", "currency": "USD"},
                "freshness_requirement": "daily",
                "rate_limit_requirement": {
                    "max_requests": 10,
                    "period_seconds": 60,
                },
                "retention_requirement": {"days": 30},
                "allow_partial_degradation": False,
                "precondition_failures": [],
            }
        ],
        "route_plans": [build_route_plan_payload()],
        "coverage": build_coverage_payload(),
        "budget_summary": build_budget_summary_payload(),
        "limitations": ["preview_only"],
        "decision_trace": {
            "semantic_entries": [build_trace_entry_payload()],
            "input_diagnostics": [],
        },
        "attribution_contract": {
            "matched_scope_id": "string",
            "matched_term": "string",
            "match_reason": "string",
            "query_version": "string",
            "requirement_ref": "string",
            "route_plan_ref": "string",
        },
        "catalog_snapshot_id": f"sha256:{'b' * 64}",
        "policy_version": "market_monitoring_balanced.v1",
        "mode_template_version": "periodic_monitoring.v1",
        "query_versions": {"youtube": "youtube.declarative.v1"},
        "preview_fingerprint": f"sha256:{'c' * 64}",
        "execution_authorized": False,
        "provider_call": False,
        "actor_run": False,
        "browser_run": False,
        "llm_call": False,
        "workflow_run_created": False,
        "database_write": False,
        "generated_at": GENERATED_AT,
        "request_id": "request-1",
    }


def build_fingerprint_payload() -> dict[str, Any]:
    semantic_query_term = build_query_term_payload()
    semantic_query_term.pop("scope_ref")
    semantic_compiled_query = build_compiled_query_payload()
    semantic_compiled_query.pop("source_scope_refs")
    return {
        "planner_contract_version": "workflow_planner.v1",
        "fingerprint_input": {
            "flow_mode": "periodic_monitoring",
            "scopes": [{"scope_key": SCOPE_KEY, "canonical_term": "acme"}],
        },
        "catalog_snapshot_id": f"sha256:{'b' * 64}",
        "policy_version": "market_monitoring_balanced.v1",
        "mode_template_version": "periodic_monitoring.v1",
        "query_versions": {"youtube": "youtube.declarative.v1"},
        "candidate_fixture_version": "candidate_expansions.v1",
        "semantic_query_terms": [semantic_query_term],
        "semantic_steps": [build_step_payload()],
        "semantic_compiled_queries": [semantic_compiled_query],
        "route_plans": [build_route_plan_payload()],
        "coverage": build_coverage_payload(),
        "budget_summary": build_budget_summary_payload(),
        "limitations": ["preview_only"],
        "semantic_decision_trace": [build_trace_entry_payload()],
    }


def test_periodic_request_requires_schedule_and_effective_platform() -> None:
    payload = load_request("periodic_monitoring_request_v1.json")
    parsed = PlanningInput.model_validate(payload)
    assert parsed.flow_mode.value == "periodic_monitoring"
    assert parsed.schedule_intent is not None

    payload["schedule_intent"] = None
    with pytest.raises(ValidationError):
        PlanningInput.model_validate(payload)

    payload = load_request("periodic_monitoring_request_v1.json")
    payload["default_platforms"] = []
    for scope in payload["scopes"]:
        scope["platforms"] = []
        scope["seed_urls"] = []
    with pytest.raises(ValidationError):
        PlanningInput.model_validate(payload)


def test_batch_request_preserves_seed_urls_and_rejects_schedule() -> None:
    payload = load_request("batch_research_request_v1.json")
    parsed = PlanningInput.model_validate(payload)
    assert parsed.flow_mode.value == "batch_research"
    assert len(parsed.scopes[0].seed_urls) == 2
    assert "schedule_intent" not in parsed.model_fields_set

    for forbidden_value in (
        None,
        {"cadence": "daily", "timezone": "UTC"},
    ):
        payload["schedule_intent"] = forbidden_value
        with pytest.raises(ValidationError):
            PlanningInput.model_validate(payload)


@pytest.mark.parametrize("extra_field", ["project_id", "scope_key", "readiness_snapshots"])
def test_request_rejects_server_owned_or_unknown_fields(extra_field: str) -> None:
    payload = load_request("periodic_monitoring_request_v1.json")
    payload[extra_field] = "forbidden"
    with pytest.raises(ValidationError):
        PlanningInput.model_validate(payload)


def test_scope_refs_are_unique_and_lists_are_bounded() -> None:
    payload = load_request("periodic_monitoring_request_v1.json")
    payload["scopes"][1]["scope_ref"] = "scope-1"
    with pytest.raises(ValidationError):
        PlanningInput.model_validate(payload)

    payload = load_request("periodic_monitoring_request_v1.json")
    payload["scopes"][0]["aliases"] = [f"alias-{index}" for index in range(51)]
    with pytest.raises(ValidationError):
        PlanningInput.model_validate(payload)


def test_periodic_seed_url_only_topic_request_is_valid() -> None:
    payload = load_request("periodic_monitoring_request_v1.json")
    payload["default_platforms"] = []
    payload["scopes"] = [
        {
            "scope_ref": "scope-seed-only",
            "scope_type": "topic",
            "canonical_term": None,
            "aliases": [],
            "include_terms": [],
            "exclude_terms": [],
            "official_accounts": [],
            "seed_urls": ["https://example.com/research/demo"],
            "languages": ["en"],
            "regions": ["US"],
            "platforms": [],
            "match_mode": "phrase",
        }
    ]

    parsed = PlanningInput.model_validate(payload)

    assert parsed.scopes[0].seed_urls == ["https://example.com/research/demo"]
    assert parsed.scopes[0].platforms == []


def test_named_contracts_validate_through_preview_and_standalone_payloads() -> None:
    request = PlanningInput.model_validate(load_request("periodic_monitoring_request_v1.json"))
    assert isinstance(request.scopes[0], MonitoringScopeDraft)
    assert isinstance(request.schedule_intent, ScheduleIntent)
    assert isinstance(request.delivery_intent, DeliveryIntent)
    assert isinstance(request.retention_intent, RetentionIntent)
    assert isinstance(BudgetCeiling.model_validate({"amount": "1.00"}), BudgetCeiling)
    assert isinstance(
        RateLimitIntent.model_validate({"max_requests": 10, "period_seconds": 60}),
        RateLimitIntent,
    )

    preview = WorkflowPlanPreview.model_validate(build_preview_payload())
    assert isinstance(preview.normalized_input, NormalizedPlanningInput)
    assert isinstance(preview.normalized_input.scopes[0], NormalizedMonitoringScope)
    assert isinstance(preview.scope_ref_map[0], ScopeRefMapping)
    assert isinstance(preview.query_terms[0], QueryTerm)
    assert isinstance(preview.compiled_queries[0], CompiledPlatformQuery)
    assert isinstance(preview.steps[0], WorkflowStepPreview)
    assert isinstance(preview.steps[0].input_contract, StepDataContract)
    assert isinstance(preview.steps[0].input_contract.fields[0], StepDataContractField)
    assert isinstance(preview.route_plans[0], RoutePlanPreview)
    assert isinstance(preview.route_plans[0].primary_implementation, RouteCandidateDecision)
    assert isinstance(preview.route_plans[0].shadow_rule, ShadowRule)
    assert isinstance(preview.route_plans[0].score_breakdown, ScoreBreakdown)
    assert isinstance(preview.route_plans[0].policy_gates[0], DecisionReason)
    assert isinstance(preview.coverage, CoverageSummary)
    assert isinstance(preview.budget_summary, BudgetSummary)
    assert isinstance(preview.decision_trace, DecisionTrace)
    assert isinstance(preview.decision_trace.semantic_entries[0], DecisionTraceEntry)
    assert isinstance(preview.attribution_contract, AttributionContract)

    compiler_failure = QueryCompilerFailure.model_validate(
        {
            "platform": "reddit",
            "scope_keys": [SCOPE_KEY],
            "reason": "Query compiler missing for reddit",
        }
    )
    assert compiler_failure.code == "compiler_missing"
    route_requirement = RouteRequirement.model_validate(
        {
            "requirement_ref": "requirement:search",
            "scope_keys": [SCOPE_KEY],
            "step_refs": ["step:discover"],
            "platform": "youtube",
            "resource_type": "content",
            "operation": "search_discover",
            "purpose": "market_research",
            "regions": ["US"],
            "required_fields": ["id", "url", "text"],
            "optional_fields": ["author"],
            "budget_ceiling": {"amount": "1.00"},
            "freshness_requirement": "daily",
            "rate_limit_requirement": {"max_requests": 10, "period_seconds": 60},
            "retention_requirement": {"days": 30},
            "allow_partial_degradation": False,
            "precondition_failures": [],
        }
    )
    assert route_requirement.platform.value == "youtube"
    readiness = CapabilityReadinessSnapshot.model_validate(
        {
            "implementation_id": "fixture.primary",
            "auth_readiness": "not_required",
            "source": "derived",
            "credential_read_status": "not_read",
        }
    )
    assert readiness.credential_read_status == "not_read"

    fingerprint = WorkflowPlanFingerprintPayload.model_validate(build_fingerprint_payload())
    assert isinstance(fingerprint.semantic_query_terms[0], BaseModel)
    assert isinstance(fingerprint.semantic_steps[0], WorkflowStepPreview)
    assert isinstance(fingerprint.semantic_compiled_queries[0], BaseModel)


@pytest.mark.parametrize(
    "semantic_field",
    ["semantic_query_terms", "semantic_steps", "semantic_compiled_queries"],
)
def test_fingerprint_rejects_untyped_semantic_subtrees(semantic_field: str) -> None:
    payload = build_fingerprint_payload()
    payload[semantic_field] = [{"arbitrary": "value"}]

    with pytest.raises(ValidationError):
        WorkflowPlanFingerprintPayload.model_validate(payload)


@pytest.mark.parametrize(
    "semantic_field",
    ["semantic_query_terms", "semantic_steps", "semantic_compiled_queries"],
)
@pytest.mark.parametrize("forbidden_field", FINGERPRINT_FORBIDDEN_FIELDS)
def test_fingerprint_semantic_subtrees_reject_reference_fields(
    semantic_field: str,
    forbidden_field: str,
) -> None:
    payload = build_fingerprint_payload()
    subtree = cast(list[dict[str, Any]], payload[semantic_field])
    subtree[0][forbidden_field] = "forbidden"

    with pytest.raises(ValidationError):
        WorkflowPlanFingerprintPayload.model_validate(payload)


@pytest.mark.parametrize("forbidden_field", FINGERPRINT_FORBIDDEN_FIELDS)
def test_fingerprint_input_rejects_reference_fields_at_any_depth(
    forbidden_field: str,
) -> None:
    payload = build_fingerprint_payload()
    fingerprint_input = cast(dict[str, Any], payload["fingerprint_input"])
    scopes = cast(list[dict[str, Any]], fingerprint_input["scopes"])
    scopes[0][forbidden_field] = "forbidden"

    with pytest.raises(ValidationError):
        WorkflowPlanFingerprintPayload.model_validate(payload)


@pytest.mark.parametrize("boundary_field", PREVIEW_BOUNDARY_FIELDS)
def test_preview_rejects_true_boundary_fields(boundary_field: str) -> None:
    payload = build_preview_payload()
    payload[boundary_field] = True

    with pytest.raises(ValidationError):
        WorkflowPlanPreview.model_validate(payload)


def test_shadow_rule_rejects_execution_authorized_true() -> None:
    payload = build_route_plan_payload()
    shadow_rule = cast(dict[str, Any], payload["shadow_rule"])
    shadow_rule["execution_authorized"] = True

    with pytest.raises(ValidationError):
        RoutePlanPreview.model_validate(payload)


def test_readiness_snapshot_rejects_credential_read_status_other_than_not_read() -> None:
    with pytest.raises(ValidationError):
        CapabilityReadinessSnapshot.model_validate(
            {
                "implementation_id": "fixture.primary",
                "auth_readiness": "not_required",
                "source": "derived",
                "credential_read_status": "read",
            }
        )


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [("project_id", "not-a-uuid"), ("generated_at", "not-a-datetime")],
)
def test_preview_rejects_invalid_uuid_and_datetime(
    field_name: str,
    invalid_value: str,
) -> None:
    payload = build_preview_payload()
    payload[field_name] = invalid_value

    with pytest.raises(ValidationError):
        WorkflowPlanPreview.model_validate(payload)


def test_response_contracts_reject_extra_fields() -> None:
    preview_payload = build_preview_payload()
    preview_payload["unknown_field"] = "forbidden"
    with pytest.raises(ValidationError):
        WorkflowPlanPreview.model_validate(preview_payload)

    route_payload = build_route_plan_payload()
    candidate = cast(dict[str, Any], route_payload["primary_implementation"])
    candidate["unknown_field"] = "forbidden"
    with pytest.raises(ValidationError):
        RoutePlanPreview.model_validate(route_payload)


@pytest.mark.parametrize(
    "field_name",
    ["route_requirements", "mode_template_version", "query_versions"],
)
def test_preview_requires_backend_routing_and_version_facts(field_name: str) -> None:
    payload = build_preview_payload()
    payload.pop(field_name)

    with pytest.raises(ValidationError):
        WorkflowPlanPreview.model_validate(payload)


def test_fingerprint_semantic_trace_details_reject_reference_fields() -> None:
    for forbidden_field in FINGERPRINT_FORBIDDEN_FIELDS:
        payload = deepcopy(build_fingerprint_payload())
        entries = cast(list[dict[str, Any]], payload["semantic_decision_trace"])
        details = cast(dict[str, Any], entries[0]["details"])
        details[forbidden_field] = "forbidden"

        with pytest.raises(ValidationError):
            WorkflowPlanFingerprintPayload.model_validate(payload)
