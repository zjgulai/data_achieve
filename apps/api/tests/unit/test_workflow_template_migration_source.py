from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Protocol, cast

from sqlalchemy import Constraint

MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "202607160031_workflow_template_lifecycle.py"
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
        "workflow_template_lifecycle_migration",
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


def test_revision_is_linear() -> None:
    module = _load_migration()
    assert module.revision == "202607160031"
    assert module.down_revision == "202607160030"


def test_upgrade_replaces_plan_status_check_and_creates_template_table() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder

    module.upgrade()

    assert any(
        name == "drop_constraint"
        and args == ("ck_workflow_plans_status_previewed", "workflow_plans")
        and kwargs == {"type_": "check"}
        for name, args, kwargs in recorder.calls
    )
    status_check = next(
        args
        for name, args, _ in recorder.calls
        if name == "create_check_constraint"
        and args[0] == "ck_workflow_plans_status"
    )
    assert "status IN" in str(status_check[2])
    table_args = next(
        args for name, args, _ in recorder.calls if name == "create_table"
    )
    assert str(table_args[0]) == "workflow_templates"
    assert {
        "pk_workflow_templates",
        "uq_workflow_templates_tenant_key",
        "uq_workflow_templates_tenant_id",
        "fk_workflow_templates_project_tenant",
        "fk_workflow_templates_created_by_user",
        "ck_workflow_templates_status",
    } <= _constraint_names(table_args)
    assert any(
        name == "create_index"
        and args[0] == "ix_workflow_templates_project_updated_at"
        for name, args, _ in recorder.calls
    )


def test_downgrade_restores_previewed_status_check_and_drops_template_table() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder

    module.downgrade()

    assert ("drop_table", ("workflow_templates",), {}) in recorder.calls
    assert (
        "create_check_constraint",
        (
            "ck_workflow_plans_status_previewed",
            "workflow_plans",
            "status = 'previewed'",
        ),
        {},
    ) in recorder.calls
