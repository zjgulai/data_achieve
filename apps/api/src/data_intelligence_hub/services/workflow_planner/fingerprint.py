from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import cast

from pydantic import JsonValue

from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityCatalog,
    PlatformId,
)
from data_intelligence_hub.schemas.workflow_planner import (
    FINGERPRINT_FORBIDDEN_REFERENCE_FIELDS,
    BudgetSummary,
    CompiledPlatformQuery,
    CoverageSummary,
    DecisionReason,
    DecisionTraceEntry,
    MatchMode,
    QueryTerm,
    RouteCandidateDecision,
    RoutePlanPreview,
    SemanticCompiledPlatformQuery,
    SemanticQueryTerm,
    StepDataContract,
    WorkflowPlanFingerprintPayload,
    WorkflowStepPreview,
)

type CanonicalValue = JsonValue

_IMPLEMENTATION_SET_LIKE_FIELDS = frozenset(
    {
        "blocked_actions",
        "data_domains",
        "official_docs",
        "policy_flags",
        "required_credentials",
        "resource_groups",
        "supported_endpoints",
    }
)
_ASSERTION_SET_LIKE_FIELDS = frozenset(
    {"auth_scope", "evidence_refs", "purpose_scope", "region_scope"}
)
_PLATFORM_ORDER = {platform: index for index, platform in enumerate(PlatformId)}
_EXPRESSION_FIELDS = frozenset(
    {
        "accounts",
        "active_terms",
        "exclusions",
        "match_mode",
        "platform",
        "url_inputs",
    }
)
_TYPED_QUERY_TERM_ORIGINS = {
    "include_terms": frozenset({"canonical", "alias", "include"}),
    "account_filters": frozenset({"official_account"}),
    "url_inputs": frozenset({"seed_url"}),
}


def canonical_json_bytes(value: CanonicalValue) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_id(value: CanonicalValue) -> str:
    return f"sha256:{hashlib.sha256(canonical_json_bytes(value)).hexdigest()}"


def _canonical_sort_key(value: object) -> bytes:
    return canonical_json_bytes(cast(JsonValue, value))


def _sorted_set_like(value: object) -> object:
    if not isinstance(value, list):
        return value
    return sorted(value, key=_canonical_sort_key)


def _reject_non_finite_values(value: object, *, error_code: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(error_code)
    if isinstance(value, Mapping):
        for nested in value.values():
            _reject_non_finite_values(nested, error_code=error_code)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _reject_non_finite_values(nested, error_code=error_code)


def _canonical_catalog_payload(catalog: CapabilityCatalog) -> dict[str, JsonValue]:
    _reject_non_finite_values(
        catalog.model_dump(mode="python"),
        error_code="catalog_snapshot_non_finite_value",
    )
    payload = cast(dict[str, JsonValue], catalog.model_dump(mode="json"))
    payload.pop("generated_at")

    implementations = cast(list[dict[str, object]], payload["implementations"])
    for implementation in implementations:
        for field_name in _IMPLEMENTATION_SET_LIKE_FIELDS:
            if field_name in implementation:
                implementation[field_name] = _sorted_set_like(
                    implementation[field_name]
                )
    implementations.sort(key=lambda item: cast(str, item["implementation_id"]))

    assertions = cast(list[dict[str, object]], payload["assertions"])
    for assertion in assertions:
        for field_name in _ASSERTION_SET_LIKE_FIELDS:
            if field_name in assertion:
                assertion[field_name] = _sorted_set_like(assertion[field_name])
        field_contract = assertion.get("field_contract")
        if isinstance(field_contract, dict):
            for field_name in ("required", "optional"):
                if field_name in field_contract:
                    field_contract[field_name] = _sorted_set_like(
                        field_contract[field_name]
                    )
        constraints = assertion.get("constraints")
        if isinstance(constraints, list):
            constraints.sort(
                key=lambda item: (
                    cast(dict[str, object], item).get("constraint_type"),
                    cast(dict[str, object], item).get("severity"),
                    cast(dict[str, object], item).get("code"),
                    _canonical_sort_key(
                        cast(dict[str, object], item).get("details", {})
                    ),
                )
            )
    assertions.sort(key=lambda item: cast(str, item["assertion_id"]))

    evidence = cast(list[dict[str, object]], payload["evidence"])
    evidence.sort(key=lambda item: cast(str, item["evidence_id"]))
    return payload


def compute_catalog_snapshot_id(catalog: CapabilityCatalog) -> str:
    return sha256_id(cast(JsonValue, _canonical_catalog_payload(catalog)))


def _semantic_query_term(term: QueryTerm) -> SemanticQueryTerm:
    return SemanticQueryTerm(
        term=term.normalized_term,
        normalized_term=term.normalized_term,
        scope_key=term.scope_key,
        origin=term.origin,
        status=term.status,
        reason=term.reason,
        source=term.source,
        score=term.score,
        conflict_codes=sorted(set(term.conflict_codes)),
    )


def _reject_expression_reference_fields(value: object) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if key in FINGERPRINT_FORBIDDEN_REFERENCE_FIELDS:
                raise ValueError(f"compiled_query_expression_reference_forbidden:{key}")
            _reject_expression_reference_fields(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_expression_reference_fields(nested)


def _canonical_string_list(value: object, *, field_name: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"compiled_query_expression_string_list_invalid:{field_name}")
    return sorted(set(cast(list[str], value)))


def _validate_typed_query_term_sources(
    query: CompiledPlatformQuery,
    query_terms: Sequence[QueryTerm],
) -> None:
    query_scope_keys = set(query.scope_keys)
    for field_name, allowed_origins in _TYPED_QUERY_TERM_ORIGINS.items():
        allowed_values = {
            term.normalized_term
            for term in query_terms
            if term.scope_key in query_scope_keys
            and term.status == "active"
            and term.origin in allowed_origins
        }
        typed_values = cast(list[str], getattr(query, field_name))
        if not set(typed_values).issubset(allowed_values):
            raise ValueError(f"compiled_query_typed_input_not_active:{field_name}")


def _fingerprint_scope_match_modes(
    fingerprint_input: Mapping[str, JsonValue],
) -> dict[str, MatchMode]:
    scopes = fingerprint_input.get("scopes")
    if not isinstance(scopes, list):
        raise ValueError("fingerprint_input_scopes_invalid")

    match_modes: dict[str, MatchMode] = {}
    for scope_value in scopes:
        if not isinstance(scope_value, dict):
            raise ValueError("fingerprint_input_scope_invalid")
        scope = cast(dict[str, object], scope_value)
        scope_key = scope.get("scope_key")
        if not isinstance(scope_key, str) or not scope_key.strip():
            raise ValueError("fingerprint_input_scope_key_invalid")
        if scope_key in match_modes:
            raise ValueError("fingerprint_input_scope_key_duplicate")
        match_mode_value = scope.get("match_mode")
        if not isinstance(match_mode_value, str):
            raise ValueError("fingerprint_input_scope_match_mode_invalid")
        try:
            match_modes[scope_key] = MatchMode(match_mode_value)
        except ValueError as exc:
            raise ValueError("fingerprint_input_scope_match_mode_invalid") from exc
    return match_modes


def _query_match_mode(
    query: CompiledPlatformQuery,
    scope_match_modes: Mapping[str, MatchMode],
) -> MatchMode:
    match_modes: set[MatchMode] = set()
    for scope_key in query.scope_keys:
        match_mode = scope_match_modes.get(scope_key)
        if match_mode is None:
            raise ValueError(f"compiled_query_scope_key_missing:{scope_key}")
        match_modes.add(match_mode)
    if len(match_modes) != 1:
        raise ValueError("compiled_query_scope_match_mode_conflict")
    return next(iter(match_modes))


def _canonical_expression(
    query: CompiledPlatformQuery,
    *,
    expected_match_mode: MatchMode,
) -> str:
    try:
        parsed_value = cast(object, json.loads(query.normalized_expression))
    except json.JSONDecodeError as exc:
        raise ValueError("compiled_query_expression_invalid") from exc
    if not isinstance(parsed_value, dict):
        raise ValueError("compiled_query_expression_object_required")
    parsed = cast(dict[str, object], parsed_value)
    _reject_non_finite_values(
        parsed,
        error_code="compiled_query_expression_non_finite_value",
    )
    _reject_expression_reference_fields(parsed)
    if set(parsed) != _EXPRESSION_FIELDS:
        raise ValueError("compiled_query_expression_fields_mismatch")
    if parsed["platform"] != query.platform.value:
        raise ValueError("compiled_query_expression_platform_mismatch")
    match_mode = parsed["match_mode"]
    if not isinstance(match_mode, str):
        raise ValueError("compiled_query_expression_match_mode_invalid")
    try:
        expression_match_mode = MatchMode(match_mode)
    except (TypeError, ValueError) as exc:
        raise ValueError("compiled_query_expression_match_mode_invalid") from exc
    if expression_match_mode is not expected_match_mode:
        raise ValueError("compiled_query_expression_match_mode_mismatch")

    expression_to_typed = {
        "active_terms": query.include_terms,
        "exclusions": query.exclude_terms,
        "accounts": query.account_filters,
        "url_inputs": query.url_inputs,
    }
    for field_name, typed_values in expression_to_typed.items():
        canonical_values = _canonical_string_list(
            parsed[field_name],
            field_name=field_name,
        )
        if canonical_values != sorted(set(typed_values)):
            raise ValueError(
                f"compiled_query_expression_typed_mismatch:{field_name}"
            )
        parsed[field_name] = canonical_values
    return canonical_json_bytes(cast(JsonValue, parsed)).decode("utf-8")


def _semantic_compiled_query(
    query: CompiledPlatformQuery,
    query_terms: Sequence[QueryTerm],
    scope_match_modes: Mapping[str, MatchMode],
) -> SemanticCompiledPlatformQuery:
    _validate_typed_query_term_sources(query, query_terms)
    expected_match_mode = _query_match_mode(query, scope_match_modes)
    return SemanticCompiledPlatformQuery(
        platform=query.platform,
        scope_keys=sorted(set(query.scope_keys)),
        resource_type=query.resource_type,
        operation=query.operation,
        query_version=query.query_version,
        normalized_expression=_canonical_expression(
            query,
            expected_match_mode=expected_match_mode,
        ),
        include_terms=sorted(set(query.include_terms)),
        exclude_terms=sorted(set(query.exclude_terms)),
        account_filters=sorted(set(query.account_filters)),
        url_inputs=sorted(set(query.url_inputs)),
        limitations=sorted(set(query.limitations)),
    )


def _canonical_contract(contract: StepDataContract) -> StepDataContract:
    return contract.model_copy(
        update={"fields": sorted(contract.fields, key=lambda item: item.name)},
        deep=True,
    )


def _semantic_step(step: WorkflowStepPreview) -> WorkflowStepPreview:
    return step.model_copy(
        update={
            "depends_on": sorted(set(step.depends_on)),
            "scope_keys": sorted(set(step.scope_keys)),
            "input_contract": _canonical_contract(step.input_contract),
            "output_contract": _canonical_contract(step.output_contract),
            "limitations": sorted(set(step.limitations)),
        },
        deep=True,
    )


def _sorted_reasons(reasons: Sequence[DecisionReason]) -> list[DecisionReason]:
    return sorted(reasons, key=lambda item: (item.code, item.reason))


def _semantic_candidate(candidate: RouteCandidateDecision) -> RouteCandidateDecision:
    return candidate.model_copy(
        update={
            "approval_reasons": _sorted_reasons(candidate.approval_reasons),
            "missing_optional_fields": sorted(set(candidate.missing_optional_fields)),
            "evidence_refs": sorted(set(candidate.evidence_refs)),
        },
        deep=True,
    )


def _semantic_route(route: RoutePlanPreview) -> RoutePlanPreview:
    primary = (
        _semantic_candidate(route.primary_implementation)
        if route.primary_implementation is not None
        else None
    )
    return route.model_copy(
        update={
            "primary_implementation": primary,
            "fallback_implementations": [
                _semantic_candidate(candidate)
                for candidate in route.fallback_implementations
            ],
            "required_fields": sorted(set(route.required_fields)),
            "optional_fields": sorted(set(route.optional_fields)),
            "missing_optional_fields": sorted(set(route.missing_optional_fields)),
            "approval_reasons": _sorted_reasons(route.approval_reasons),
            "exclusion_reasons": _sorted_reasons(route.exclusion_reasons),
            "limitations": sorted(set(route.limitations)),
        },
        deep=True,
    )


def _trace_sort_key(entry: DecisionTraceEntry) -> tuple[object, ...]:
    return (
        entry.scope_keys,
        entry.requirement_ref or "",
        entry.code,
        entry.reason,
        _canonical_sort_key(entry.details),
    )


def _canonical_trace_entries(
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


def build_preview_fingerprint_payload(
    *,
    planner_contract_version: str,
    fingerprint_input: Mapping[str, JsonValue],
    catalog_snapshot_id: str,
    policy_version: str,
    mode_template_version: str,
    query_versions: Mapping[PlatformId, str],
    candidate_fixture_version: str,
    query_terms: Sequence[QueryTerm],
    steps: Sequence[WorkflowStepPreview],
    compiled_queries: Sequence[CompiledPlatformQuery],
    route_plans: Sequence[RoutePlanPreview],
    coverage: CoverageSummary,
    budget_summary: BudgetSummary,
    limitations: Sequence[str],
    semantic_decision_trace: Sequence[DecisionTraceEntry],
) -> WorkflowPlanFingerprintPayload:
    scope_match_modes = _fingerprint_scope_match_modes(fingerprint_input)
    semantic_terms = sorted(
        (_semantic_query_term(term) for term in query_terms),
        key=lambda item: (
            item.scope_key,
            item.normalized_term,
            item.origin,
            item.status,
            item.source,
            item.reason or "",
        ),
    )
    semantic_queries = sorted(
        (
            _semantic_compiled_query(query, query_terms, scope_match_modes)
            for query in compiled_queries
        ),
        key=lambda item: (
            _PLATFORM_ORDER[item.platform],
            item.scope_keys,
            item.resource_type.value,
            item.operation.value,
            item.query_version,
            item.normalized_expression,
        ),
    )
    semantic_steps = sorted(
        (_semantic_step(step) for step in steps),
        key=lambda item: (item.sequence, item.step_ref),
    )
    semantic_routes = sorted(
        (_semantic_route(route) for route in route_plans),
        key=lambda item: item.requirement_ref,
    )
    return WorkflowPlanFingerprintPayload(
        planner_contract_version=planner_contract_version,
        fingerprint_input=deepcopy(dict(fingerprint_input)),
        catalog_snapshot_id=catalog_snapshot_id,
        policy_version=policy_version,
        mode_template_version=mode_template_version,
        query_versions={
            platform: query_versions[platform]
            for platform in sorted(query_versions, key=lambda item: _PLATFORM_ORDER[item])
        },
        candidate_fixture_version=candidate_fixture_version,
        semantic_query_terms=semantic_terms,
        semantic_steps=semantic_steps,
        semantic_compiled_queries=semantic_queries,
        route_plans=semantic_routes,
        coverage=coverage.model_copy(deep=True),
        budget_summary=budget_summary.model_copy(deep=True),
        limitations=sorted(set(limitations)),
        semantic_decision_trace=_canonical_trace_entries(semantic_decision_trace),
    )


def compute_preview_fingerprint(payload: WorkflowPlanFingerprintPayload) -> str:
    return sha256_id(cast(JsonValue, payload.model_dump(mode="json")))
