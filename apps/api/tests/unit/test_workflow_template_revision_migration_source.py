from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Protocol, cast

from sqlalchemy import Constraint

MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "202607160032_workflow_template_revision_association.py"
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
    assert MIGRATION_PATH.is_file()
    spec = importlib.util.spec_from_file_location(
        "workflow_template_revision_association_migration",
        MIGRATION_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(MigrationModule, module)


def _constraint_names(args: tuple[object, ...]) -> set[str]:
    return {
        cast(str, item.name)
        for item in args[1:]
        if isinstance(item, Constraint) and item.name is not None
    }


def test_revision_is_linear_and_source_only() -> None:
    module = _load_migration()
    assert module.revision == "202607160032"
    assert module.down_revision == "202607160031"


def test_upgrade_requires_empty_031_template_table_and_adds_revision_contract() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.upgrade()

    assert any(
        name == "execute" and "workflow_templates" in str(args[0])
        for name, args, _ in recorder.calls
    )
    revision_table = next(
        args
        for name, args, _ in recorder.calls
        if name == "create_table" and args[0] == "workflow_template_revisions"
    )
    assert {
        "pk_workflow_template_revisions",
        "uq_workflow_template_revisions_template_tenant_id",
        "uq_workflow_template_revisions_tenant_number",
        "fk_workflow_template_revisions_template_tenant",
        "fk_workflow_template_revisions_created_by_user",
        "ck_workflow_template_revisions_revision_number",
    } <= _constraint_names(revision_table)
    assert any(
        name == "add_column"
        and args[0] in {"workflow_templates", "workflow_plans", "workflow_versions"}
        for name, args, _ in recorder.calls
    )
    assert any(
        name == "execute"
        and "trg_workflow_template_revisions_immutable" in str(args[0])
        and "BEFORE UPDATE OR DELETE" in str(args[0])
        for name, args, _ in recorder.calls
    )


def test_downgrade_has_data_loss_guard_and_removes_revision_contract() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.downgrade()

    assert any(
        name == "execute" and "workflow_template_revisions" in str(args[0])
        for name, args, _ in recorder.calls
    )
    assert any(
        name == "drop_table" and args == ("workflow_template_revisions",)
        for name, args, _ in recorder.calls
    )
    assert any(
        name == "execute"
        and "DROP TRIGGER IF EXISTS trg_workflow_template_revisions_immutable" in str(args[0])
        for name, args, _ in recorder.calls
    )
