from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Protocol, cast

from sqlalchemy import Constraint, ForeignKeyConstraint

MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "202606110029_workflow_execution_fixture.py"
)

EXPECTED_TABLES = ("workflow_runs", "step_runs", "workflow_run_requests")


class RecordingOp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def __getattr__(self, name: str) -> Any:
        def record(*args: object, **kwargs: object) -> None:
            self.calls.append((name, args, kwargs))

        return record


class MigrationModule(Protocol):
    revision: str
    down_revision: str | None
    WORKFLOW_EXECUTION_TABLES: tuple[str, ...]
    op: object

    def upgrade(self) -> None: ...

    def downgrade(self) -> None: ...


def _load_migration() -> MigrationModule:
    spec = importlib.util.spec_from_file_location(
        "workflow_execution_migration",
        MIGRATION_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(MigrationModule, module)


def _created_table_calls(
    recorder: RecordingOp,
) -> dict[str, tuple[object, ...]]:
    return {
        str(args[0]): args
        for name, args, _ in recorder.calls
        if name == "create_table"
    }


def _constraint_names(args: tuple[object, ...]) -> set[str]:
    return {
        cast(str, item.name)
        for item in args[1:]
        if isinstance(item, Constraint) and item.name is not None
    }


def _foreign_key_signatures(
    args: tuple[object, ...],
) -> set[tuple[tuple[str, ...], tuple[str, ...]]]:
    return {
        (
            tuple(item.column_keys),
            tuple(element.target_fullname for element in item.elements),
        )
        for item in args[1:]
        if isinstance(item, ForeignKeyConstraint)
    }


def test_revision_029_is_single_linear_bounded_successor() -> None:
    assert MIGRATION_PATH.is_file()
    module = _load_migration()
    assert module.revision == "202606110029"
    assert module.down_revision == "202606110028"
    assert module.WORKFLOW_EXECUTION_TABLES == EXPECTED_TABLES


def test_upgrade_creates_only_empty_workflow_execution_tables() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.upgrade()

    assert [name for name, _, _ in recorder.calls] == ["create_table"] * 3
    created = _created_table_calls(recorder)
    assert tuple(created) == EXPECTED_TABLES
    assert not any(
        name in {"bulk_insert", "execute", "add_column", "alter_column"}
        for name, _, _ in recorder.calls
    )


def test_migration_has_named_tenant_fks_uniqueness_and_checks() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.upgrade()
    created = _created_table_calls(recorder)

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
    ) in _foreign_key_signatures(created["workflow_runs"])
    run_owner_fk = (
        ("workspace_id", "project_id", "workflow_run_id"),
        (
            "workflow_runs.workspace_id",
            "workflow_runs.project_id",
            "workflow_runs.id",
        ),
    )
    assert run_owner_fk in _foreign_key_signatures(created["step_runs"])
    assert run_owner_fk in _foreign_key_signatures(created["workflow_run_requests"])

    expected_names = {
        "workflow_runs": {
            "pk_workflow_runs",
            "uq_workflow_runs_tenant_id",
            "fk_workflow_runs_version_tenant",
            "fk_workflow_runs_created_by_user",
            "ck_workflow_runs_execution_contract",
            "ck_workflow_runs_execution_mode",
            "ck_workflow_runs_status",
            "ck_workflow_runs_counts",
            "ck_workflow_runs_completed_snapshot",
            "ck_workflow_runs_fixture_boundaries",
        },
        "step_runs": {
            "pk_step_runs",
            "uq_step_runs_tenant_id",
            "uq_step_runs_run_step_ref",
            "uq_step_runs_run_requirement_implementation",
            "fk_step_runs_run_tenant",
            "ck_step_runs_sequence",
            "ck_step_runs_status",
            "ck_step_runs_records_count",
            "ck_step_runs_completed_snapshot",
            "ck_step_runs_fixture_boundaries",
        },
        "workflow_run_requests": {
            "pk_workflow_run_requests",
            "uq_workflow_run_requests_idempotency",
            "fk_workflow_run_requests_run_tenant",
            "fk_workflow_run_requests_created_by_user",
            "ck_workflow_run_requests_outcome",
            "ck_workflow_run_requests_response_status",
        },
    }
    for table_name, names in expected_names.items():
        assert names <= _constraint_names(created[table_name])


def test_downgrade_drops_only_three_tables_in_reverse_order() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.downgrade()

    assert recorder.calls == [
        ("drop_table", (table_name,), {})
        for table_name in reversed(EXPECTED_TABLES)
    ]

