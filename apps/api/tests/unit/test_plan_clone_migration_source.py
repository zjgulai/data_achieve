from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Protocol, cast

from sqlalchemy import Constraint, ForeignKeyConstraint

MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "202607160030_plan_clone_scope_templates.py"
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
        "plan_clone_scope_template_migration",
        MIGRATION_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(MigrationModule, module)


def _created_tables(recorder: RecordingOp) -> set[str]:
    return {
        str(args[0])
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


def test_revision_is_linear_and_bounded() -> None:
    module = _load_migration()

    assert module.revision == "202607160030"
    assert module.down_revision == "202606110029"


def test_upgrade_is_source_only_and_creates_template_table() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder

    module.upgrade()

    assert _created_tables(recorder) == {"monitoring_scope_templates"}
    assert not any(
        name == "bulk_insert"
        for name, _, _ in recorder.calls
    )
    table_args = next(
        args for name, args, _ in recorder.calls if name == "create_table"
    )
    assert {
        "pk_monitoring_scope_templates",
        "uq_monitoring_scope_templates_tenant_id",
        "fk_monitoring_scope_templates_project_tenant",
        "fk_monitoring_scope_templates_source_version_tenant",
        "ck_monitoring_scope_templates_scope_type",
        "ck_monitoring_scope_templates_match_mode",
    } <= _constraint_names(table_args)
    assert (
        (
            "workspace_id",
            "project_id",
            "source_workflow_plan_id",
            "source_workflow_version_id",
        ),
        (
            "workflow_versions.workspace_id",
            "workflow_versions.project_id",
            "workflow_versions.workflow_plan_id",
            "workflow_versions.id",
        ),
    ) in _foreign_key_signatures(table_args)
    add_columns = [
        (str(args[0]), str(getattr(args[1], "name", None)))
        for name, args, _ in recorder.calls
        if name == "add_column"
    ]
    assert add_columns == [
        ("workflow_plans", "source_workflow_plan_id"),
        ("workflow_plans", "source_workflow_version_id"),
    ]
    assert any(
        name == "create_foreign_key"
        and args[0] == "fk_workflow_plans_source_version_owner"
        for name, args, _ in recorder.calls
    )
    assert any(
        name == "create_check_constraint"
        and args[0] == "ck_workflow_plans_source_version_pair"
        for name, args, _ in recorder.calls
    )
    assert any(
        name == "execute"
        and "trg_monitoring_scope_templates_immutable" in str(args[0])
        for name, args, _ in recorder.calls
    )


def test_downgrade_drops_only_template_table() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder

    module.downgrade()

    assert [
        (name, args, kwargs)
        for name, args, kwargs in recorder.calls
        if name in {"drop_table", "drop_index", "drop_constraint", "drop_column"}
    ] == [
        (
            "drop_index",
            ("ix_monitoring_scope_templates_project_created_at",),
            {"table_name": "monitoring_scope_templates"},
        ),
        ("drop_table", ("monitoring_scope_templates",), {}),
        (
            "drop_constraint",
            ("fk_workflow_plans_source_version_owner", "workflow_plans"),
            {"type_": "foreignkey"},
        ),
        (
            "drop_constraint",
            ("ck_workflow_plans_source_version_pair", "workflow_plans"),
            {"type_": "check"},
        ),
        ("drop_column", ("workflow_plans", "source_workflow_version_id"), {}),
        ("drop_column", ("workflow_plans", "source_workflow_plan_id"), {}),
    ]
