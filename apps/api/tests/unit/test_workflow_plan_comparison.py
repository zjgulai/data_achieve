from __future__ import annotations

import ast
import inspect
import json
from collections.abc import Sequence
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from pydantic import JsonValue

from data_intelligence_hub.schemas.workflow_plan_persistence import (
    WorkflowPlanCompareSection,
)
from data_intelligence_hub.schemas.workflow_planner import (
    DecisionTraceEntry,
    PlanningInput,
    PlanningStatus,
    QueryTerm,
    RoutePlanStatus,
    WorkflowPlanPreview,
    WorkflowStepPlanningStatus,
)
from data_intelligence_hub.services.capability_catalog import (
    get_capability_catalog,
)
from data_intelligence_hub.services.workflow_planner.comparison import (
    compare_workflow_plan_previews,
)
from data_intelligence_hub.services.workflow_planner.planner import (
    build_workflow_plan_preview,
)

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "workflow_planner"
PERIODIC_FIXTURE = FIXTURE_DIR / "periodic_monitoring_request_v1.json"
PROJECT_ID = UUID("00000000-0000-0000-0000-000000000001")
GENERATED_AT = datetime(2026, 7, 13, tzinfo=UTC)
EXPECTED_SECTION_ORDER = [
    "plan",
    "scopes",
    "query_terms",
    "versions",
    "warnings",
    "blocking_issues",
    "routes",
    "budget",
    "limits",
    "steps",
]


def build_preview() -> WorkflowPlanPreview:
    planning_input = PlanningInput.model_validate_json(PERIODIC_FIXTURE.read_text(encoding="utf-8"))
    return build_workflow_plan_preview(
        project_id=PROJECT_ID,
        planning_input=planning_input,
        catalog=get_capability_catalog(),
        generated_at=GENERATED_AT,
        request_id="workflow-plan-compare",
    )


def sections_by_key(
    preview_sections: Sequence[WorkflowPlanCompareSection],
) -> dict[str, WorkflowPlanCompareSection]:
    return {section.key: section for section in preview_sections}


def change_fields(section: WorkflowPlanCompareSection) -> list[str]:
    return [change.field for change in section.changes]


def json_object_at(value: JsonValue | None, index: int) -> dict[str, JsonValue]:
    assert isinstance(value, list)
    item = value[index]
    assert isinstance(item, dict)
    return item


def test_same_snapshot_returns_empty_sections_without_mutating_inputs() -> None:
    base = build_preview()
    target = base.model_copy(deep=True)
    base_before = base.model_dump(mode="json")
    target_before = target.model_dump(mode="json")

    sections = compare_workflow_plan_previews(base, target)

    assert sections == []
    assert base.model_dump(mode="json") == base_before
    assert target.model_dump(mode="json") == target_before


def test_json_key_order_and_set_like_order_do_not_create_changes() -> None:
    base = build_preview()
    reordered = deepcopy(base.model_dump(mode="json"))

    reordered["generated_at"] = "2026-07-13T01:00:00Z"
    reordered["request_id"] = "another-request"
    reordered["query_versions"] = dict(reversed(list(reordered["query_versions"].items())))
    reordered["limitations"] = list(reversed(reordered["limitations"]))
    reordered["query_terms"] = list(reversed(reordered["query_terms"]))
    reordered["compiled_queries"] = list(reversed(reordered["compiled_queries"]))
    reordered["route_requirements"] = list(reversed(reordered["route_requirements"]))
    reordered["route_plans"] = list(reversed(reordered["route_plans"]))
    reordered["steps"] = list(reversed(reordered["steps"]))
    for scope in reordered["normalized_input"]["scopes"]:
        scope["source_scope_refs"] = ["renamed-ref"]
        scope["aliases"] = list(reversed(scope["aliases"]))
        scope["effective_platforms"] = list(reversed(scope["effective_platforms"]))
    for term in reordered["query_terms"]:
        term["scope_ref"] = "renamed-ref"
    for query in reordered["compiled_queries"]:
        query["source_scope_refs"] = ["renamed-ref"]
        expression = json.loads(query["normalized_expression"])
        query["normalized_expression"] = json.dumps(
            {
                key: list(reversed(value)) if isinstance(value, list) else value
                for key, value in reversed(list(expression.items()))
            },
            ensure_ascii=False,
        )
    for entry in reordered["decision_trace"]["semantic_entries"]:
        entry["details"] = dict(reversed(list(entry["details"].items())))

    target = WorkflowPlanPreview.model_validate(reordered)

    assert compare_workflow_plan_previews(base, target) == []


def test_scope_add_and_remove_are_not_misreported_as_reordering() -> None:
    base = build_preview()
    first, second = base.normalized_input.scopes
    added = first.model_copy(
        update={
            "scope_key": "sha256:" + ("f" * 64),
            "canonical_term": "added scope",
            "source_scope_refs": ["added-scope"],
        },
        deep=True,
    )
    target_input = base.normalized_input.model_copy(
        update={"scopes": [second.model_copy(deep=True), added]},
        deep=True,
    )
    target = base.model_copy(update={"normalized_input": target_input}, deep=True)

    sections = compare_workflow_plan_previews(base, target)

    assert [section.key for section in sections] == ["scopes"]
    scope_section = sections[0]
    assert change_fields(scope_section) == ["added", "removed"]
    assert json_object_at(scope_section.changes[0].after, 0)["scope_key"] == (added.scope_key)
    assert json_object_at(scope_section.changes[1].before, 0)["scope_key"] == (first.scope_key)


def test_scope_semantic_order_change_is_reported_for_shared_scopes() -> None:
    base = build_preview()
    first, second = base.normalized_input.scopes
    target_input = base.normalized_input.model_copy(
        update={"scopes": [second.model_copy(deep=True), first.model_copy(deep=True)]},
        deep=True,
    )
    target = base.model_copy(update={"normalized_input": target_input}, deep=True)

    sections = compare_workflow_plan_previews(base, target)

    assert [section.key for section in sections] == ["scopes"]
    scope_section = sections[0]
    assert change_fields(scope_section) == ["order"]
    assert scope_section.changes[0].before == [first.scope_key, second.scope_key]
    assert scope_section.changes[0].after == [second.scope_key, first.scope_key]


def test_query_term_add_remove_and_status_changes_are_reported() -> None:
    base = build_preview()
    removed = base.query_terms[0]
    status_before = base.query_terms[1]
    status_after = status_before.model_copy(update={"status": "rejected"}, deep=True)
    added = QueryTerm(
        term="new term",
        normalized_term="new term",
        scope_ref=status_before.scope_ref,
        scope_key=status_before.scope_key,
        origin="include",
        status="active",
        reason=None,
        source="user_input",
        score=None,
        conflict_codes=[],
    )
    target = base.model_copy(
        update={"query_terms": [*base.query_terms[1:2], *base.query_terms[2:], added]},
        deep=True,
    )
    target.query_terms[0] = status_after

    sections = compare_workflow_plan_previews(base, target)

    assert [section.key for section in sections] == ["query_terms"]
    term_section = sections[0]
    assert change_fields(term_section) == ["added", "removed", "status_changed"]
    assert json_object_at(term_section.changes[0].after, 0)["normalized_term"] == ("new term")
    assert json_object_at(term_section.changes[1].before, 0)["normalized_term"] == (
        removed.normalized_term
    )
    assert json_object_at(term_section.changes[2].before, 0)["status"] == (status_before.status)
    assert json_object_at(term_section.changes[2].after, 0)["status"] == ("rejected")


def test_all_required_changed_sections_are_stable_and_structured() -> None:
    base = build_preview()
    first_scope, second_scope = base.normalized_input.scopes
    target_input = base.normalized_input.model_copy(
        update={
            "scopes": [second_scope.model_copy(deep=True), first_scope.model_copy(deep=True)],
            "purpose": "competitive_research",
            "budget_ceiling": {"amount": "25", "currency": "USD"},
            "rate_limit_intent": {"max_requests": 12, "period_seconds": 60},
            "retention_intent": {"days": 90},
        },
        deep=True,
    )
    changed_term = base.query_terms[0].model_copy(update={"status": "rejected"}, deep=True)
    warning = DecisionTraceEntry(
        code="input_warning",
        reason="Input was normalized",
        scope_keys=[first_scope.scope_key],
        requirement_ref=None,
        details={"z": "last", "a": "first"},
    )
    target_trace = base.decision_trace.model_copy(
        update={"input_diagnostics": [warning]}, deep=True
    )
    changed_route = base.route_plans[0].model_copy(
        update={"status": RoutePlanStatus.RESOLVED}, deep=True
    )
    changed_step = base.steps[0].model_copy(
        update={"planning_status": WorkflowStepPlanningStatus.HELD}, deep=True
    )
    target_budget = base.budget_summary.model_copy(
        update={"unknown_count": base.budget_summary.unknown_count + 1}, deep=True
    )
    target = base.model_copy(
        update={
            "planning_status": PlanningStatus.PARTIALLY_RESOLVED,
            "normalized_input": target_input,
            "query_terms": [changed_term, *base.query_terms[1:]],
            "planner_contract_version": "workflow_planner.v2",
            "catalog_snapshot_id": "sha256:" + ("e" * 64),
            "policy_version": "market_monitoring_balanced.v2",
            "mode_template_version": "periodic_monitoring.v2",
            "query_versions": {**base.query_versions, "reddit": "reddit.v2"},
            "decision_trace": target_trace,
            "route_plans": [changed_route, *base.route_plans[1:]],
            "budget_summary": target_budget,
            "limitations": [*base.limitations, "new_limit"],
            "steps": [changed_step, *base.steps[1:]],
        },
        deep=True,
    )

    sections = compare_workflow_plan_previews(base, target)

    assert [section.key for section in sections] == EXPECTED_SECTION_ORDER
    by_key = sections_by_key(sections)
    assert change_fields(by_key["plan"]) == ["planning_status", "purpose"]
    assert change_fields(by_key["scopes"]) == ["order"]
    assert change_fields(by_key["query_terms"]) == ["status_changed"]
    assert change_fields(by_key["versions"]) == [
        "planner_contract_version",
        "catalog_snapshot_id",
        "policy_version",
        "mode_template_version",
        "query_versions",
    ]
    assert change_fields(by_key["warnings"]) == ["input_diagnostics"]
    assert change_fields(by_key["blocking_issues"]) == ["items"]
    assert change_fields(by_key["routes"]) == ["route_plans"]
    assert change_fields(by_key["budget"]) == ["budget_ceiling", "budget_summary"]
    assert change_fields(by_key["limits"]) == [
        "rate_limit_intent",
        "retention_intent",
        "limitations",
    ]
    assert change_fields(by_key["steps"]) == ["items"]


def test_comparator_module_has_no_database_or_external_side_effect_imports() -> None:
    import data_intelligence_hub.services.workflow_planner.comparison as comparison

    tree = ast.parse(inspect.getsource(comparison))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    forbidden_prefixes = (
        "data_intelligence_hub.api",
        "data_intelligence_hub.database",
        "data_intelligence_hub.db",
        "data_intelligence_hub.models",
        "data_intelligence_hub.repositories",
        "httpx",
        "requests",
        "sqlalchemy",
        "urllib",
    )
    assert not any(module.startswith(forbidden_prefixes) for module in imported_modules)
    assert not inspect.iscoroutinefunction(compare_workflow_plan_previews)
