from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import cast

from pydantic import BaseModel, JsonValue

from data_intelligence_hub.schemas.workflow_plan_persistence import (
    WorkflowPlanCompareChange,
    WorkflowPlanCompareSection,
)
from data_intelligence_hub.schemas.workflow_planner import (
    CompiledPlatformQuery,
    QueryTerm,
    RoutePlanStatus,
    WorkflowPlanPreview,
)


def _json_sort_key(value: JsonValue) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _canonical_json(value: object) -> JsonValue:
    if isinstance(value, BaseModel):
        return _canonical_json(value.model_dump(mode="json"))
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_json(value[key])
            for key in sorted(value, key=str)
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        items = [_canonical_json(item) for item in value]
        return sorted(items, key=_json_sort_key)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise TypeError(f"workflow_plan_compare_value_not_json:{type(value).__name__}")


def _ordered_string_list(values: Sequence[str]) -> list[JsonValue]:
    return list(values)


def _append_change(
    changes: list[WorkflowPlanCompareChange],
    *,
    field: str,
    before: object,
    after: object,
) -> None:
    canonical_before = _canonical_json(before)
    canonical_after = _canonical_json(after)
    if canonical_before != canonical_after:
        changes.append(
            WorkflowPlanCompareChange(
                field=field,
                before=canonical_before,
                after=canonical_after,
            )
        )


def _append_order_change(
    changes: list[WorkflowPlanCompareChange],
    *,
    field: str,
    before: Sequence[str],
    after: Sequence[str],
) -> None:
    ordered_before = _ordered_string_list(before)
    ordered_after = _ordered_string_list(after)
    if ordered_before != ordered_after:
        changes.append(
            WorkflowPlanCompareChange(
                field=field,
                before=ordered_before,
                after=ordered_after,
            )
        )


def _section(
    key: str,
    changes: list[WorkflowPlanCompareChange],
) -> WorkflowPlanCompareSection | None:
    if not changes:
        return None
    return WorkflowPlanCompareSection(key=key, changes=changes)


def _plan_section(
    base: WorkflowPlanPreview,
    target: WorkflowPlanPreview,
) -> WorkflowPlanCompareSection | None:
    changes: list[WorkflowPlanCompareChange] = []
    fields = (
        ("schema_version", base.schema_version, target.schema_version),
        ("flow_mode", base.flow_mode, target.flow_mode),
        ("planning_status", base.planning_status, target.planning_status),
        (
            "purpose",
            base.normalized_input.purpose,
            target.normalized_input.purpose,
        ),
        (
            "policy_profile",
            base.normalized_input.policy_profile,
            target.normalized_input.policy_profile,
        ),
        (
            "schedule_intent",
            base.normalized_input.schedule_intent,
            target.normalized_input.schedule_intent,
        ),
        (
            "delivery_intent",
            base.normalized_input.delivery_intent,
            target.normalized_input.delivery_intent,
        ),
        (
            "required_fields",
            base.normalized_input.required_fields,
            target.normalized_input.required_fields,
        ),
        (
            "optional_fields",
            base.normalized_input.optional_fields,
            target.normalized_input.optional_fields,
        ),
        (
            "allow_partial_degradation",
            base.normalized_input.allow_partial_degradation,
            target.normalized_input.allow_partial_degradation,
        ),
        ("coverage", base.coverage, target.coverage),
        (
            "attribution_contract",
            base.attribution_contract,
            target.attribution_contract,
        ),
    )
    for field, before, after in fields:
        _append_change(changes, field=field, before=before, after=after)
    return _section("plan", changes)


def _scope_payload(scope: BaseModel) -> dict[str, JsonValue]:
    payload = scope.model_dump(mode="json", exclude={"source_scope_refs"})
    return cast(dict[str, JsonValue], _canonical_json(payload))


def _scopes_section(
    base: WorkflowPlanPreview,
    target: WorkflowPlanPreview,
) -> WorkflowPlanCompareSection | None:
    changes: list[WorkflowPlanCompareChange] = []
    base_by_key = {
        scope.scope_key: _scope_payload(scope)
        for scope in base.normalized_input.scopes
    }
    target_by_key = {
        scope.scope_key: _scope_payload(scope)
        for scope in target.normalized_input.scopes
    }
    base_keys = set(base_by_key)
    target_keys = set(target_by_key)

    added_keys = sorted(target_keys - base_keys)
    removed_keys = sorted(base_keys - target_keys)
    if added_keys:
        _append_change(
            changes,
            field="added",
            before=[],
            after=[target_by_key[key] for key in added_keys],
        )
    if removed_keys:
        _append_change(
            changes,
            field="removed",
            before=[base_by_key[key] for key in removed_keys],
            after=[],
        )

    common_keys = base_keys & target_keys
    _append_order_change(
        changes,
        field="order",
        before=[
            scope.scope_key
            for scope in base.normalized_input.scopes
            if scope.scope_key in common_keys
        ],
        after=[
            scope.scope_key
            for scope in target.normalized_input.scopes
            if scope.scope_key in common_keys
        ],
    )

    changed_keys = [
        key
        for key in sorted(common_keys)
        if base_by_key[key] != target_by_key[key]
    ]
    if changed_keys:
        _append_change(
            changes,
            field="changed",
            before=[base_by_key[key] for key in changed_keys],
            after=[target_by_key[key] for key in changed_keys],
        )
    return _section("scopes", changes)


def _term_identity(term: QueryTerm) -> dict[str, JsonValue]:
    return {
        "normalized_term": term.normalized_term,
        "origin": term.origin,
        "scope_key": term.scope_key,
        "source": term.source,
        "term": term.term,
    }


def _term_identity_key(term: QueryTerm) -> str:
    return _json_sort_key(_term_identity(term))


def _term_payload(term: QueryTerm) -> dict[str, JsonValue]:
    payload = term.model_dump(mode="json", exclude={"scope_ref"})
    return cast(dict[str, JsonValue], _canonical_json(payload))


def _term_payload_without_status(term: QueryTerm) -> dict[str, JsonValue]:
    payload = _term_payload(term)
    payload.pop("status", None)
    return payload


def _compiled_query_payload(
    query: CompiledPlatformQuery,
) -> dict[str, JsonValue]:
    payload = query.model_dump(mode="json", exclude={"source_scope_refs"})
    expression = json.loads(query.normalized_expression)
    payload["normalized_expression"] = _json_sort_key(_canonical_json(expression))
    return cast(dict[str, JsonValue], _canonical_json(payload))


def _compiled_query_payloads(
    preview: WorkflowPlanPreview,
) -> list[dict[str, JsonValue]]:
    return [_compiled_query_payload(query) for query in preview.compiled_queries]


def _query_terms_section(
    base: WorkflowPlanPreview,
    target: WorkflowPlanPreview,
) -> WorkflowPlanCompareSection | None:
    changes: list[WorkflowPlanCompareChange] = []
    base_by_key = {_term_identity_key(term): term for term in base.query_terms}
    target_by_key = {_term_identity_key(term): term for term in target.query_terms}
    base_keys = set(base_by_key)
    target_keys = set(target_by_key)

    added_keys = sorted(target_keys - base_keys)
    removed_keys = sorted(base_keys - target_keys)
    if added_keys:
        _append_change(
            changes,
            field="added",
            before=[],
            after=[_term_payload(target_by_key[key]) for key in added_keys],
        )
    if removed_keys:
        _append_change(
            changes,
            field="removed",
            before=[_term_payload(base_by_key[key]) for key in removed_keys],
            after=[],
        )

    common_keys = sorted(base_keys & target_keys)
    status_keys = [
        key
        for key in common_keys
        if base_by_key[key].status != target_by_key[key].status
    ]
    if status_keys:
        _append_change(
            changes,
            field="status_changed",
            before=[
                {**_term_identity(base_by_key[key]), "status": base_by_key[key].status}
                for key in status_keys
            ],
            after=[
                {
                    **_term_identity(target_by_key[key]),
                    "status": target_by_key[key].status,
                }
                for key in status_keys
            ],
        )

    changed_keys = [
        key
        for key in common_keys
        if _term_payload_without_status(base_by_key[key])
        != _term_payload_without_status(target_by_key[key])
    ]
    if changed_keys:
        _append_change(
            changes,
            field="changed",
            before=[_term_payload(base_by_key[key]) for key in changed_keys],
            after=[_term_payload(target_by_key[key]) for key in changed_keys],
        )

    _append_change(
        changes,
        field="compiled_queries",
        before=_compiled_query_payloads(base),
        after=_compiled_query_payloads(target),
    )
    return _section("query_terms", changes)


def _versions_section(
    base: WorkflowPlanPreview,
    target: WorkflowPlanPreview,
) -> WorkflowPlanCompareSection | None:
    changes: list[WorkflowPlanCompareChange] = []
    fields = (
        (
            "planner_contract_version",
            base.planner_contract_version,
            target.planner_contract_version,
        ),
        ("catalog_snapshot_id", base.catalog_snapshot_id, target.catalog_snapshot_id),
        ("policy_version", base.policy_version, target.policy_version),
        (
            "mode_template_version",
            base.mode_template_version,
            target.mode_template_version,
        ),
        ("query_versions", base.query_versions, target.query_versions),
    )
    for field, before, after in fields:
        _append_change(changes, field=field, before=before, after=after)
    return _section("versions", changes)


def _warnings_section(
    base: WorkflowPlanPreview,
    target: WorkflowPlanPreview,
) -> WorkflowPlanCompareSection | None:
    changes: list[WorkflowPlanCompareChange] = []
    _append_change(
        changes,
        field="input_diagnostics",
        before=base.decision_trace.input_diagnostics,
        after=target.decision_trace.input_diagnostics,
    )
    return _section("warnings", changes)


def _blocking_issues(preview: WorkflowPlanPreview) -> list[dict[str, JsonValue]]:
    issues: list[dict[str, JsonValue]] = []
    for route in preview.route_plans:
        if route.status is RoutePlanStatus.RESOLVED and not route.approval_required:
            continue
        issues.append(
            cast(
                dict[str, JsonValue],
                _canonical_json(
                    {
                        "approval_reasons": route.approval_reasons,
                        "approval_required": route.approval_required,
                        "degradation_rule": route.degradation_rule,
                        "exclusion_reasons": route.exclusion_reasons,
                        "policy_gates": route.policy_gates,
                        "requirement_ref": route.requirement_ref,
                        "status": route.status,
                    }
                ),
            )
        )
    return sorted(issues, key=_json_sort_key)


def _blocking_issues_section(
    base: WorkflowPlanPreview,
    target: WorkflowPlanPreview,
) -> WorkflowPlanCompareSection | None:
    changes: list[WorkflowPlanCompareChange] = []
    _append_change(
        changes,
        field="items",
        before=_blocking_issues(base),
        after=_blocking_issues(target),
    )
    return _section("blocking_issues", changes)


def _routes_section(
    base: WorkflowPlanPreview,
    target: WorkflowPlanPreview,
) -> WorkflowPlanCompareSection | None:
    changes: list[WorkflowPlanCompareChange] = []
    _append_change(
        changes,
        field="route_requirements",
        before=base.route_requirements,
        after=target.route_requirements,
    )
    _append_change(
        changes,
        field="route_plans",
        before=base.route_plans,
        after=target.route_plans,
    )
    return _section("routes", changes)


def _budget_section(
    base: WorkflowPlanPreview,
    target: WorkflowPlanPreview,
) -> WorkflowPlanCompareSection | None:
    changes: list[WorkflowPlanCompareChange] = []
    _append_change(
        changes,
        field="budget_ceiling",
        before=base.normalized_input.budget_ceiling,
        after=target.normalized_input.budget_ceiling,
    )
    _append_change(
        changes,
        field="budget_summary",
        before=base.budget_summary,
        after=target.budget_summary,
    )
    return _section("budget", changes)


def _limits_section(
    base: WorkflowPlanPreview,
    target: WorkflowPlanPreview,
) -> WorkflowPlanCompareSection | None:
    changes: list[WorkflowPlanCompareChange] = []
    fields = (
        (
            "rate_limit_intent",
            base.normalized_input.rate_limit_intent,
            target.normalized_input.rate_limit_intent,
        ),
        (
            "retention_intent",
            base.normalized_input.retention_intent,
            target.normalized_input.retention_intent,
        ),
        ("limitations", base.limitations, target.limitations),
    )
    for field, before, after in fields:
        _append_change(changes, field=field, before=before, after=after)
    return _section("limits", changes)


def _steps_section(
    base: WorkflowPlanPreview,
    target: WorkflowPlanPreview,
) -> WorkflowPlanCompareSection | None:
    changes: list[WorkflowPlanCompareChange] = []
    _append_change(changes, field="items", before=base.steps, after=target.steps)
    return _section("steps", changes)


def compare_workflow_plan_previews(
    base: WorkflowPlanPreview,
    target: WorkflowPlanPreview,
) -> list[WorkflowPlanCompareSection]:
    """Return stable structured changes without mutating or accessing persistence."""

    sections = (
        _plan_section(base, target),
        _scopes_section(base, target),
        _query_terms_section(base, target),
        _versions_section(base, target),
        _warnings_section(base, target),
        _blocking_issues_section(base, target),
        _routes_section(base, target),
        _budget_section(base, target),
        _limits_section(base, target),
        _steps_section(base, target),
    )
    return [section for section in sections if section is not None]


__all__ = ["compare_workflow_plan_previews"]
