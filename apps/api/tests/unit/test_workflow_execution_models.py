from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ColumnDefault,
    ForeignKeyConstraint,
    Table,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB

from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.workflow_execution import (
    StepRun,
    WorkflowRun,
    WorkflowRunRequest,
)

MODELS: tuple[type[Base], ...] = (WorkflowRun, StepRun, WorkflowRunRequest)


def _table(model: type[Base]) -> Table:
    return cast(Table, model.__table__)


def _unique_column_sets(table: Table) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _foreign_key_signatures(
    table: Table,
) -> set[tuple[tuple[str, ...], tuple[str, ...]]]:
    return {
        (
            tuple(element.parent.name for element in constraint.elements),
            tuple(element.target_fullname for element in constraint.elements),
        )
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }


def _constraint_names(table: Table, kind: type[CheckConstraint]) -> set[str]:
    return {
        cast(str, constraint.name)
        for constraint in table.constraints
        if isinstance(constraint, kind) and constraint.name is not None
    }


def _assert_no_delete_cascade(tables: Iterable[Table]) -> None:
    for table in tables:
        for constraint in table.constraints:
            if isinstance(constraint, ForeignKeyConstraint):
                assert constraint.ondelete is None


def test_workflow_execution_metadata_contains_exact_three_append_only_tables() -> None:
    assert {_table(model).name for model in MODELS} == {
        "workflow_runs",
        "step_runs",
        "workflow_run_requests",
    }
    for model in MODELS:
        table = _table(model)
        assert "created_at" in table.c
        assert "updated_at" not in table.c
        assert isinstance(table.c.id.type, Uuid)
        assert table.c.id.default is not None
        assert table.c.id.default.is_callable
        assert table.c.id.server_default is None
        assert not model.__mapper__.relationships
    _assert_no_delete_cascade(_table(model) for model in MODELS)


def test_workflow_run_has_frozen_context_counts_and_false_boundaries() -> None:
    table = _table(WorkflowRun)
    assert set(table.c.keys()) == {
        "id",
        "workspace_id",
        "project_id",
        "workflow_plan_id",
        "workflow_version_id",
        "created_by_user_id",
        "execution_contract_version",
        "execution_mode",
        "status",
        "planner_contract_version",
        "preview_fingerprint",
        "catalog_snapshot_id",
        "policy_version",
        "mode_template_version",
        "query_versions",
        "fixture_profile_id",
        "fixture_profile_hash",
        "total_steps",
        "completed_steps",
        "records_count",
        "status_reason_code",
        "impact_code",
        "missing_fields",
        "recovery_action_codes",
        "provider_call_attempted",
        "credential_read_attempted",
        "actor_run",
        "browser_run",
        "llm_call",
        "production_write_allowed",
        "started_at",
        "finished_at",
        "created_at",
    }
    for column_name in ("query_versions", "missing_fields", "recovery_action_codes"):
        assert isinstance(table.c[column_name].type, JSON)
        assert not isinstance(table.c[column_name].type, JSONB)
    assert table.c.finished_at.nullable is True
    assert ("workspace_id", "project_id", "id") in _unique_column_sets(table)
    assert (
        (
            "workspace_id",
            "project_id",
            "workflow_plan_id",
            "workflow_version_id",
        ),
        (
            "workflow_versions.workspace_id",
            "workflow_versions.project_id",
            "workflow_versions.workflow_plan_id",
            "workflow_versions.id",
        ),
    ) in _foreign_key_signatures(table)
    assert {
        "ck_workflow_runs_execution_contract",
        "ck_workflow_runs_execution_mode",
        "ck_workflow_runs_status",
        "ck_workflow_runs_counts",
        "ck_workflow_runs_state_snapshot",
        "ck_workflow_runs_fixture_boundaries",
    } <= _constraint_names(table, CheckConstraint)


def test_step_run_binds_exact_run_primary_route_and_idempotency() -> None:
    table = _table(StepRun)
    assert set(table.c.keys()) == {
        "id",
        "workflow_run_id",
        "workspace_id",
        "project_id",
        "step_ref",
        "requirement_ref",
        "sequence",
        "retry_generation",
        "platform",
        "resource_type",
        "operation",
        "assertion_id",
        "implementation_id",
        "route_plan_snapshot",
        "evidence_refs",
        "fixture_case_id",
        "fixture_content_hash",
        "input_digest",
        "output_digest",
        "idempotency_scope",
        "idempotency_key_hash",
        "status",
        "records_count",
        "provider_call_attempted",
        "credential_read_attempted",
        "actor_run",
        "browser_run",
        "llm_call",
        "production_write_allowed",
        "started_at",
        "finished_at",
        "created_at",
    }
    for column_name in ("route_plan_snapshot", "evidence_refs"):
        column_type = table.c[column_name].type
        assert isinstance(column_type, JSON)
        assert not isinstance(column_type, JSONB)
    for column_name in (
        "fixture_case_id",
        "fixture_content_hash",
        "output_digest",
        "finished_at",
    ):
        assert table.c[column_name].nullable is True
    assert (
        ("workspace_id", "project_id", "workflow_run_id"),
        (
            "workflow_runs.workspace_id",
            "workflow_runs.project_id",
            "workflow_runs.id",
        ),
    ) in _foreign_key_signatures(table)
    unique_sets = _unique_column_sets(table)
    assert ("workflow_run_id", "step_ref") in unique_sets
    assert ("workflow_run_id", "requirement_ref", "implementation_id") in unique_sets
    assert {
        "ck_step_runs_sequence",
        "ck_step_runs_retry_generation",
        "ck_step_runs_status",
        "ck_step_runs_records_count",
        "ck_step_runs_state_snapshot",
        "ck_step_runs_fixture_boundaries",
    } <= _constraint_names(table, CheckConstraint)


def test_request_ledger_is_actor_scoped_and_binds_one_tenant_run() -> None:
    table = _table(WorkflowRunRequest)
    assert set(table.c.keys()) == {
        "id",
        "workspace_id",
        "project_id",
        "created_by_user_id",
        "idempotency_scope",
        "idempotency_key_hash",
        "request_hash",
        "workflow_run_id",
        "outcome",
        "response_status",
        "response_payload",
        "created_at",
    }
    assert (
        "workspace_id",
        "created_by_user_id",
        "idempotency_scope",
        "idempotency_key_hash",
    ) in _unique_column_sets(table)
    assert (
        ("workspace_id", "project_id", "workflow_run_id"),
        (
            "workflow_runs.workspace_id",
            "workflow_runs.project_id",
            "workflow_runs.id",
        ),
    ) in _foreign_key_signatures(table)
    assert {
        "ck_workflow_run_requests_outcome",
        "ck_workflow_run_requests_response_status",
    } <= _constraint_names(table, CheckConstraint)
    assert isinstance(table.c.response_payload.type, JSON)
    assert not isinstance(table.c.response_payload.type, JSONB)


def test_all_external_flags_have_python_false_defaults() -> None:
    flag_names = {
        "provider_call_attempted",
        "credential_read_attempted",
        "actor_run",
        "browser_run",
        "llm_call",
        "production_write_allowed",
    }
    for model in (WorkflowRun, StepRun):
        table = _table(model)
        for flag_name in flag_names:
            column = table.c[flag_name]
            assert isinstance(column.type, Boolean)
            assert column.nullable is False
            assert isinstance(column.default, ColumnDefault)
            assert cast(bool, column.default.arg) is False
