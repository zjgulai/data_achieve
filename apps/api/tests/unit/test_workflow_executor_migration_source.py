from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Protocol, cast

from sqlalchemy import Constraint, ForeignKeyConstraint

MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "202607280044_workflow_executor_persistence.py"
)

TABLES = [
    "workflow_execution_dispatches",
    "workflow_execution_leases",
    "workflow_execution_events",
    "workflow_credential_resolution_permits",
    "workflow_provider_call_permits",
    "workflow_provider_call_audits",
    "workflow_cancellation_requests",
    "workflow_cancellation_acknowledgements",
]


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
    spec = importlib.util.spec_from_file_location("workflow_executor_persistence", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(MigrationModule, module)


def test_revision_044_is_linear_source_only_and_additive() -> None:
    assert MIGRATION_PATH.is_file()
    module = _load_migration()
    assert module.revision == "202607280044"
    assert module.down_revision == "202607270043"
    recorder = RecordingOp()
    module.op = recorder
    module.upgrade()
    assert "execute" not in [name for name, _, _ in recorder.calls]
    assert [args[0] for name, args, _ in recorder.calls if name == "create_table"] == TABLES


def test_revision_044_retains_named_tenant_and_lineage_constraints() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.upgrade()
    table_calls = [args for name, args, _ in recorder.calls if name == "create_table"]
    names = {
        cast(str, item.name)
        for args in table_calls
        for item in args[1:]
        if isinstance(item, Constraint) and item.name is not None
    }
    assert {
        "pk_workflow_execution_dispatches",
        "uq_workflow_execution_dispatches_semantic_key",
        "pk_workflow_execution_leases",
        "uq_workflow_execution_leases_dispatch_head",
        "pk_workflow_execution_events",
        "uq_workflow_execution_events_dispatch_sequence",
        "pk_workflow_credential_resolution_permits",
        "pk_workflow_provider_call_permits",
        "pk_workflow_provider_call_audits",
        "pk_workflow_cancellation_requests",
        "pk_workflow_cancellation_acknowledgements",
    } <= names
    assert (
        sum(isinstance(item, ForeignKeyConstraint) for args in table_calls for item in args[1:])
        >= 24
    )


def test_revision_044_downgrade_refuses_evidence_then_reverses_dependencies() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.downgrade()
    assert recorder.calls[0][0] == "execute"
    guard_sql = cast(str, recorder.calls[0][1][0])
    for table in TABLES:
        assert table in guard_sql
    assert [args[0] for name, args, _ in recorder.calls if name == "drop_table"] == list(
        reversed(TABLES)
    )
