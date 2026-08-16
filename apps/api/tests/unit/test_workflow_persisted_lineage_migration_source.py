from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Protocol, cast

from sqlalchemy import Constraint, ForeignKeyConstraint

MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "202607160033_workflow_raw_dataset_lineage.py"
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
        "workflow_raw_dataset_lineage_migration",
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


def test_revision_is_linear_and_source_only() -> None:
    module = _load_migration()
    assert module.revision == "202607160033"
    assert module.down_revision == "202607160032"


def test_upgrade_adds_only_named_v2_lineage_contract_objects() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.upgrade()

    assert any(
        name == "alter_column" and args[0] == "raw_records" for name, args, _ in recorder.calls
    )
    assert any(
        name == "add_column" and args[0] == "raw_records" for name, args, _ in recorder.calls
    )
    assert any(
        name == "add_column" and args[0] == "dataset_versions" for name, args, _ in recorder.calls
    )
    assert any(
        name == "create_unique_constraint" and args[0] == "uq_step_runs_tenant_run_id"
        for name, args, _ in recorder.calls
    )
    assert any(
        name == "create_check_constraint" and args[0] == "ck_raw_records_source_provenance"
        for name, args, _ in recorder.calls
    )
    assert any(
        name == "create_check_constraint"
        and args[0] == "ck_dataset_versions_workflow_lineage_contract"
        for name, args, _ in recorder.calls
    )
    raw_contract = cast(
        str,
        next(
            args[2]
            for name, args, _ in recorder.calls
            if name == "create_check_constraint"
            and args[0] == "ck_raw_records_workflow_lineage_contract"
        ),
    )
    dataset_contract = cast(
        str,
        next(
            args[2]
            for name, args, _ in recorder.calls
            if name == "create_check_constraint"
            and args[0] == "ck_dataset_versions_workflow_lineage_contract"
        ),
    )
    assert "workflow_lineage_contract_version IS NOT NULL" in raw_contract
    assert "lineage_contract_version IS NOT NULL" in dataset_contract
    assert not any(name in {"bulk_insert", "execute"} for name, _, _ in recorder.calls)


def test_upgrade_declares_tenant_fks_and_downgrade_data_guard() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.upgrade()

    fk_call = next(
        args
        for name, args, _ in recorder.calls
        if name == "create_foreign_key" and args[0] == "fk_raw_records_workflow_step_tenant"
    )
    assert fk_call[1:4] == (
        "raw_records",
        "step_runs",
        ["workspace_id", "project_id", "workflow_run_id", "workflow_step_run_id"],
    )

    recorder = RecordingOp()
    module.op = recorder
    module.downgrade()
    assert any(
        name == "execute" and "workflow_lineage_contract_version" in str(args[0])
        for name, args, _ in recorder.calls
    )
    assert any(
        name == "drop_constraint" and args[0] == "ck_raw_records_source_provenance"
        for name, args, _ in recorder.calls
    )
