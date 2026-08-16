from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Protocol, cast

from sqlalchemy import Constraint, ForeignKeyConstraint

MIGRATION_PATH = (
    Path(__file__).parents[2] / "alembic" / "versions" / "202607230041_workflow_budget_ledger.py"
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
    spec = importlib.util.spec_from_file_location("workflow_budget_ledger", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(MigrationModule, module)


def test_revision_041_is_linear_additive_and_source_only() -> None:
    module = _load_migration()
    assert module.revision == "202607230041"
    assert module.down_revision == "202607230040"

    recorder = RecordingOp()
    module.op = recorder
    module.upgrade()
    assert [name for name, _, _ in recorder.calls] == ["create_table", "create_table"]
    assert [args[0] for _, args, _ in recorder.calls] == [
        "workflow_budget_accounts",
        "workflow_budget_ledger_entries",
    ]


def test_revision_041_retains_budget_identity_and_tenant_constraints() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.upgrade()
    names = {
        cast(str, item.name)
        for _, args, _ in recorder.calls
        for item in args[1:]
        if isinstance(item, Constraint) and item.name is not None
    }
    assert {
        "pk_workflow_budget_accounts",
        "uq_workflow_budget_accounts_execution_session",
        "fk_workflow_budget_accounts_version_tenant",
        "pk_workflow_budget_ledger_entries",
        "uq_workflow_budget_ledger_entries_account_number",
        "uq_workflow_budget_ledger_entries_account_step_page",
        "uq_workflow_budget_ledger_entries_account_side_effect_key",
        "fk_workflow_budget_ledger_entries_account_tenant",
        "ck_workflow_budget_ledger_entries_fixture_boundaries",
    } <= names
    assert (
        sum(
            isinstance(item, ForeignKeyConstraint)
            for _, args, _ in recorder.calls
            for item in args[1:]
        )
        == 2
    )


def test_revision_041_downgrade_refuses_any_budget_evidence() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.downgrade()
    assert [name for name, _, _ in recorder.calls] == [
        "execute",
        "drop_table",
        "drop_table",
    ]
    assert "workflow_budget_ledger_entries" in cast(str, recorder.calls[0][1][0])
    assert "workflow_budget_accounts" in cast(str, recorder.calls[0][1][0])
    assert [args for name, args, _ in recorder.calls if name == "drop_table"] == [
        ("workflow_budget_ledger_entries",),
        ("workflow_budget_accounts",),
    ]
