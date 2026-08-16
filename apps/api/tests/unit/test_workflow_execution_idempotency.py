from __future__ import annotations

import uuid

from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from data_intelligence_hub.repositories.workflow_execution import (
    completed_workflow_run_request_statement,
)
from data_intelligence_hub.services.workflow_execution.execution import (
    WorkflowExecutionIdempotencyConflictError,
    is_workflow_run_idempotency_unique_violation,
)


class FakeDatabaseError(Exception):
    def __init__(self, *, sqlstate: str, constraint_name: str | None) -> None:
        super().__init__("sanitized database failure")
        self.sqlstate = sqlstate
        self.constraint_name = constraint_name


def _integrity_error(
    *,
    sqlstate: str,
    constraint_name: str | None,
) -> IntegrityError:
    return IntegrityError(
        "INSERT INTO workflow_run_requests ...",
        {},
        FakeDatabaseError(
            sqlstate=sqlstate,
            constraint_name=constraint_name,
        ),
    )


def test_completed_request_statement_is_exactly_actor_and_path_scoped() -> None:
    statement = completed_workflow_run_request_statement(
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
        "POST:/api/projects/example/fixture-runs",
        "sha256:" + "a" * 64,
    )
    dialect = postgresql.dialect()  # type: ignore[no-untyped-call]
    sql = str(statement.compile(dialect=dialect))

    for column_name in (
        "workspace_id",
        "project_id",
        "created_by_user_id",
        "idempotency_scope",
        "idempotency_key_hash",
        "outcome",
    ):
        assert f"workflow_run_requests.{column_name}" in sql
    assert "FOR UPDATE" not in sql


def test_only_exact_postgres_idempotency_constraint_is_recoverable() -> None:
    exact = _integrity_error(
        sqlstate="23505",
        constraint_name="uq_workflow_run_requests_idempotency",
    )
    wrong_constraint = _integrity_error(
        sqlstate="23505",
        constraint_name="uq_step_runs_run_step_ref",
    )
    wrong_state = _integrity_error(
        sqlstate="23503",
        constraint_name="uq_workflow_run_requests_idempotency",
    )
    missing_constraint = _integrity_error(
        sqlstate="23505",
        constraint_name=None,
    )

    assert is_workflow_run_idempotency_unique_violation(exact) is True
    assert is_workflow_run_idempotency_unique_violation(wrong_constraint) is False
    assert is_workflow_run_idempotency_unique_violation(wrong_state) is False
    assert is_workflow_run_idempotency_unique_violation(missing_constraint) is False


def test_idempotency_conflict_has_one_sanitized_detail() -> None:
    error = WorkflowExecutionIdempotencyConflictError("idempotency_conflict")
    assert str(error) == "idempotency_conflict"
