from __future__ import annotations

from uuid import uuid4

from sqlalchemy.dialects import postgresql

from data_intelligence_hub.repositories.workflow_lineage import (
    workflow_run_lock_statement,
    workspace_lock_statement,
)


def test_materialization_lock_statements_compile_to_postgresql_for_update() -> None:
    workspace_id = uuid4()
    project_id = uuid4()
    run_id = uuid4()
    workspace_sql = str(
        workspace_lock_statement(workspace_id).compile(
            dialect=postgresql.dialect(),  # type: ignore[no-untyped-call]
            compile_kwargs={"literal_binds": True},
        )
    )
    run_sql = str(
        workflow_run_lock_statement(workspace_id, project_id, run_id).compile(
            dialect=postgresql.dialect(),  # type: ignore[no-untyped-call]
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "workspaces.id" in workspace_sql
    assert "FOR UPDATE" in workspace_sql
    assert "workflow_runs.workspace_id" in run_sql
    assert "workflow_runs.project_id" in run_sql
    assert "workflow_runs.id" in run_sql
    assert "FOR UPDATE" in run_sql
