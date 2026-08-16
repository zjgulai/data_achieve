from __future__ import annotations

from typing import cast

from sqlalchemy import Boolean, CheckConstraint, ForeignKeyConstraint, Table, UniqueConstraint

from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.workflow_execution import WorkflowFallbackDecision


def _table() -> Table:
    return cast(Table, WorkflowFallbackDecision.__table__)


def test_fallback_decision_is_append_only_tenant_scoped_and_idempotent() -> None:
    table = _table()

    assert table.name == "workflow_fallback_decisions"
    assert set(table.c.keys()) == {
        "id",
        "workspace_id",
        "project_id",
        "workflow_plan_id",
        "workflow_version_id",
        "workflow_run_id",
        "step_run_id",
        "created_by_user_id",
        "idempotency_scope",
        "idempotency_key_hash",
        "request_hash",
        "step_ref",
        "requirement_ref",
        "contract_version",
        "decision_digest",
        "primary_failure_code",
        "primary_assertion_id",
        "primary_implementation_id",
        "fallback_assertion_id",
        "fallback_implementation_id",
        "outcome",
        "gate_snapshot",
        "field_difference",
        "cost_snapshot",
        "evidence_refs",
        "approval_required",
        "approval_status",
        "switch_executed",
        "provider_call_attempted",
        "credential_read_attempted",
        "actor_run",
        "browser_run",
        "llm_call",
        "production_write_allowed",
        "created_at",
    }
    assert "updated_at" not in table.c
    assert not WorkflowFallbackDecision.__mapper__.relationships

    unique_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert (
        "workspace_id",
        "created_by_user_id",
        "idempotency_scope",
        "idempotency_key_hash",
        "step_ref",
    ) in unique_sets

    foreign_keys = {
        (
            tuple(element.parent.name for element in constraint.elements),
            tuple(element.target_fullname for element in constraint.elements),
        )
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    assert (
        ("workspace_id", "project_id", "workflow_plan_id", "workflow_version_id"),
        (
            "workflow_versions.workspace_id",
            "workflow_versions.project_id",
            "workflow_versions.workflow_plan_id",
            "workflow_versions.id",
        ),
    ) in foreign_keys
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
        "ck_workflow_fallback_decisions_contract_version",
        "ck_workflow_fallback_decisions_outcome",
        "ck_workflow_fallback_decisions_candidate_identity",
        "ck_workflow_fallback_decisions_no_silent_switch",
        "ck_workflow_fallback_decisions_run_step_pair",
        "ck_workflow_fallback_decisions_fixture_boundaries",
    } <= constraint_names


def test_fallback_decision_external_flags_default_false() -> None:
    table = _table()
    for name in (
        "switch_executed",
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

    assert WorkflowFallbackDecision.metadata is Base.metadata
