from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Protocol, cast

from sqlalchemy import Constraint, ForeignKeyConstraint

MIGRATION_PATH = (
    Path(__file__).parents[2] / "alembic" / "versions" / "202607230040_workflow_step_checkpoints.py"
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
    spec = importlib.util.spec_from_file_location("workflow_step_checkpoints", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(MigrationModule, module)


def test_revision_040_is_linear_additive_and_source_only() -> None:
    module = _load_migration()
    assert module.revision == "202607230040"
    assert module.down_revision == "202607230039"

    recorder = RecordingOp()
    module.op = recorder
    module.upgrade()
    assert [name for name, _, _ in recorder.calls] == ["create_table"]
    _, args, _ = recorder.calls[0]
    assert args[0] == "workflow_step_checkpoints"


def test_revision_040_retains_resume_idempotency_and_tenant_constraints() -> None:
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
        "pk_workflow_step_checkpoints",
        "uq_workflow_step_checkpoints_session_step_page",
        "uq_workflow_step_checkpoints_session_step_cursor",
        "uq_workflow_step_checkpoints_session_side_effect_key",
        "fk_workflow_step_checkpoints_version_tenant",
        "ck_workflow_step_checkpoints_cursor_before",
        "ck_workflow_step_checkpoints_cursor_after",
        "ck_workflow_step_checkpoints_fixture_boundaries",
    } <= names
    assert len([item for item in args[1:] if isinstance(item, ForeignKeyConstraint)]) == 1


def test_revision_040_downgrade_refuses_nonempty_checkpoint_evidence() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.downgrade()
    assert [name for name, _, _ in recorder.calls] == ["execute", "drop_table"]
    assert recorder.calls[-1] == (
        "drop_table",
        ("workflow_step_checkpoints",),
        {},
    )
