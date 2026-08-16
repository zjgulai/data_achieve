from __future__ import annotations

from typing import cast

from sqlalchemy import Boolean, CheckConstraint, ForeignKeyConstraint, Table, UniqueConstraint

from data_intelligence_hub.models.base import Base
from data_intelligence_hub.models.workflow_execution import StepRunAttempt


def _table() -> Table:
    return cast(Table, StepRunAttempt.__table__)


def test_step_run_attempt_is_append_only_tenant_scoped_and_idempotent() -> None:
    table = _table()

    assert table.name == "step_run_attempts"
    assert set(table.c.keys()) == {
        "id",
        "workspace_id",
        "project_id",
        "workflow_run_id",
        "step_run_id",
        "retry_generation",
        "attempt_number",
        "attempt_key_hash",
        "status",
        "error_code",
        "backoff_ms",
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
    assert "updated_at" not in table.c
    assert not StepRunAttempt.__mapper__.relationships

    unique_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("step_run_id", "retry_generation", "attempt_number") in unique_sets
    assert ("step_run_id", "attempt_number") not in unique_sets
    assert ("step_run_id", "attempt_key_hash") in unique_sets

    foreign_keys = {
        (
            tuple(element.parent.name for element in constraint.elements),
            tuple(element.target_fullname for element in constraint.elements),
        )
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
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
        "ck_step_run_attempts_attempt_number",
        "ck_step_run_attempts_retry_generation",
        "ck_step_run_attempts_status",
        "ck_step_run_attempts_outcome",
        "ck_step_run_attempts_time_order",
        "ck_step_run_attempts_fixture_boundaries",
    } <= constraint_names


def test_step_run_attempt_external_flags_default_false() -> None:
    table = _table()
    for name in (
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

    assert StepRunAttempt.metadata is Base.metadata
