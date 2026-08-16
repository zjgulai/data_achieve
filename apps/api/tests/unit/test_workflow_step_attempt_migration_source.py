from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Protocol, cast

from sqlalchemy import Constraint, ForeignKeyConstraint

MIGRATION_PATH = (
    Path(__file__).parents[2] / "alembic" / "versions" / "202607220036_workflow_step_attempts.py"
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
    spec = importlib.util.spec_from_file_location("workflow_step_attempts", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(MigrationModule, module)


def test_revision_036_is_linear_additive_and_source_only() -> None:
    assert MIGRATION_PATH.is_file()
    module = _load_migration()
    assert module.revision == "202607220036"
    assert module.down_revision == "202607220035"

    recorder = RecordingOp()
    module.op = recorder
    module.upgrade()
    assert [name for name, _, _ in recorder.calls] == ["create_table"]
    _, args, _ = recorder.calls[0]
    assert args[0] == "step_run_attempts"
    assert not any(
        name in {"execute", "bulk_insert", "add_column"} for name, _, _ in recorder.calls
    )


def test_revision_036_has_exact_fk_and_named_constraints() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.upgrade()
    _, args, _ = recorder.calls[0]

    names = {
        cast(str, item.name)
        for item in args[1:]
        if isinstance(item, Constraint) and item.name is not None
    }
    assert {
        "pk_step_run_attempts",
        "uq_step_run_attempts_step_number",
        "uq_step_run_attempts_step_key",
        "fk_step_run_attempts_step_tenant",
        "ck_step_run_attempts_attempt_number",
        "ck_step_run_attempts_status",
        "ck_step_run_attempts_outcome",
        "ck_step_run_attempts_time_order",
        "ck_step_run_attempts_fixture_boundaries",
    } <= names

    foreign_keys = [item for item in args[1:] if isinstance(item, ForeignKeyConstraint)]
    assert len(foreign_keys) == 1
    foreign_key = foreign_keys[0]
    assert tuple(foreign_key.column_keys) == (
        "workspace_id",
        "project_id",
        "workflow_run_id",
        "step_run_id",
    )
    assert tuple(element.target_fullname for element in foreign_key.elements) == (
        "step_runs.workspace_id",
        "step_runs.project_id",
        "step_runs.workflow_run_id",
        "step_runs.id",
    )


def test_revision_036_downgrade_refuses_nonempty_attempt_ledger() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.downgrade()

    assert [name for name, _, _ in recorder.calls] == ["execute", "drop_table"]
    assert recorder.calls[-1] == ("drop_table", ("step_run_attempts",), {})
