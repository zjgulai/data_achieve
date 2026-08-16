from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Protocol, cast

from sqlalchemy import Constraint, ForeignKeyConstraint

MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "202607220037_workflow_fallback_decisions.py"
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
    spec = importlib.util.spec_from_file_location("workflow_fallback_decisions", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(MigrationModule, module)


def test_revision_037_is_linear_additive_and_source_only() -> None:
    assert MIGRATION_PATH.is_file()
    module = _load_migration()
    assert module.revision == "202607220037"
    assert module.down_revision == "202607220036"

    recorder = RecordingOp()
    module.op = recorder
    module.upgrade()
    assert [name for name, _, _ in recorder.calls] == ["create_table"]
    _, args, _ = recorder.calls[0]
    assert args[0] == "workflow_fallback_decisions"
    assert not any(
        name in {"execute", "bulk_insert", "add_column"} for name, _, _ in recorder.calls
    )


def test_revision_037_has_exact_fk_and_named_constraints() -> None:
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
        "pk_workflow_fallback_decisions",
        "uq_workflow_fallback_decisions_request_step",
        "fk_workflow_fallback_decisions_version_tenant",
        "fk_workflow_fallback_decisions_created_by_user",
        "ck_workflow_fallback_decisions_contract_version",
        "ck_workflow_fallback_decisions_outcome",
        "ck_workflow_fallback_decisions_candidate_identity",
        "ck_workflow_fallback_decisions_no_silent_switch",
        "ck_workflow_fallback_decisions_fixture_boundaries",
    } <= names

    foreign_keys = [item for item in args[1:] if isinstance(item, ForeignKeyConstraint)]
    assert len(foreign_keys) == 2


def test_revision_037_downgrade_refuses_nonempty_decision_ledger() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.downgrade()

    assert [name for name, _, _ in recorder.calls] == ["execute", "drop_table"]
    assert recorder.calls[-1] == (
        "drop_table",
        ("workflow_fallback_decisions",),
        {},
    )
