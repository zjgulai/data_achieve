from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Protocol, cast

MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "202607230038_workflow_run_state_semantics.py"
)


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
    op: object

    def upgrade(self) -> None: ...

    def downgrade(self) -> None: ...


def _load_migration() -> MigrationModule:
    spec = importlib.util.spec_from_file_location("workflow_run_state_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(MigrationModule, module)


def test_revision_038_is_linear_source_only_successor() -> None:
    module = _load_migration()
    assert module.revision == "202607230038"
    assert module.down_revision == "202607220037"


def test_upgrade_adds_state_facts_constraints_and_fallback_links_without_data_write() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.upgrade()

    names = [name for name, _, _ in recorder.calls]
    assert "execute" not in names
    assert names.count("add_column") == 6
    assert names.count("alter_column") == 5
    assert names.count("create_foreign_key") == 2
    assert names.count("create_check_constraint") == 7
    constraint_names = {
        str(args[0])
        for name, args, _ in recorder.calls
        if name == "create_check_constraint"
    }
    assert {
        "ck_workflow_runs_status",
        "ck_workflow_runs_state_snapshot",
        "ck_step_runs_status",
        "ck_step_runs_records_count",
        "ck_step_runs_state_snapshot",
        "ck_workflow_run_requests_outcome",
        "ck_workflow_fallback_decisions_run_step_pair",
    } <= constraint_names


def test_downgrade_guards_state_data_before_restoring_revision_037_shape() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.downgrade()

    assert recorder.calls[0][0] == "execute"
    guard_sql = str(recorder.calls[0][1][0])
    assert "RUN-04 state data exists" in guard_sql
    assert "workflow_runs" in guard_sql
    assert "step_runs" in guard_sql
    assert "workflow_run_requests" in guard_sql
    assert "workflow_fallback_decisions" in guard_sql
    assert [
        args[1]
        for name, args, _ in recorder.calls
        if name == "drop_column"
    ] == [
        "step_run_id",
        "workflow_run_id",
        "recovery_action_codes",
        "missing_fields",
        "impact_code",
        "status_reason_code",
    ]
