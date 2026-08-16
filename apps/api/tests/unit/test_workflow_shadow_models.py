from __future__ import annotations

from typing import cast

from sqlalchemy import Boolean, CheckConstraint, ForeignKeyConstraint, Table, UniqueConstraint

from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.workflow_execution import WorkflowShadowComparison


def _table() -> Table:
    return cast(Table, WorkflowShadowComparison.__table__)


def test_shadow_comparison_is_append_only_tenant_scoped_step_evidence() -> None:
    table = _table()
    assert table.name == "workflow_shadow_comparisons"
    assert "updated_at" not in table.c
    assert not WorkflowShadowComparison.__mapper__.relationships
    assert WorkflowShadowComparison.metadata is Base.metadata

    unique_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("workflow_run_id", "step_run_id") in unique_sets

    foreign_keys = {
        (
            tuple(element.parent.name for element in constraint.elements),
            tuple(element.target_fullname for element in constraint.elements),
        )
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    assert (
        ("workspace_id", "project_id", "workflow_run_id"),
        (
            "workflow_runs.workspace_id",
            "workflow_runs.project_id",
            "workflow_runs.id",
        ),
    ) in foreign_keys
    assert (
        ("workspace_id", "project_id", "workflow_run_id", "step_run_id"),
        (
            "step_runs.workspace_id",
            "step_runs.project_id",
            "step_runs.workflow_run_id",
            "step_runs.id",
        ),
    ) in foreign_keys

    constraint_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert {
        "ck_workflow_shadow_comparisons_contract_version",
        "ck_workflow_shadow_comparisons_sample_budget",
        "ck_workflow_shadow_comparisons_comparison_counts",
        "ck_workflow_shadow_comparisons_equivalence_status",
        "ck_workflow_shadow_comparisons_recommendation",
        "ck_workflow_shadow_comparisons_no_automatic_governance_mutation",
        "ck_workflow_shadow_comparisons_fixture_boundaries",
    } <= constraint_names


def test_shadow_comparison_mutation_and_external_flags_default_false() -> None:
    table = _table()
    for name in (
        "catalog_mutation_applied",
        "route_ranking_mutation_applied",
        "provider_call_attempted",
        "credential_read_attempted",
        "actor_run",
        "browser_run",
        "llm_call",
        "production_write_allowed",
    ):
        column = table.c[name]
        assert isinstance(column.type, Boolean)
        assert column.nullable is False
        assert column.default is not None
        assert cast(bool, column.default.arg) is False
