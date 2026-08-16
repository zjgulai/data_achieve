from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Protocol, cast

from sqlalchemy import Constraint, ForeignKeyConstraint

MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "202607230039_workflow_shadow_comparisons.py"
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
    spec = importlib.util.spec_from_file_location("workflow_shadow_comparisons", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(MigrationModule, module)


def test_revision_039_is_linear_additive_and_source_only() -> None:
    module = _load_migration()
    assert module.revision == "202607230039"
    assert module.down_revision == "202607230038"

    recorder = RecordingOp()
    module.op = recorder
    module.upgrade()
    assert [name for name, _, _ in recorder.calls] == ["create_table"]
    _, args, _ = recorder.calls[0]
    assert args[0] == "workflow_shadow_comparisons"


def test_revision_039_retains_budget_governance_and_tenant_constraints() -> None:
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
        "pk_workflow_shadow_comparisons",
        "uq_workflow_shadow_comparisons_run_step",
        "fk_workflow_shadow_comparisons_run_tenant",
        "fk_workflow_shadow_comparisons_step_tenant",
        "ck_workflow_shadow_comparisons_sample_budget",
        "ck_workflow_shadow_comparisons_recommendation",
        "ck_workflow_shadow_comparisons_no_automatic_governance_mutation",
        "ck_workflow_shadow_comparisons_fixture_boundaries",
    } <= names
    assert len(
        [item for item in args[1:] if isinstance(item, ForeignKeyConstraint)]
    ) == 2


def test_revision_039_downgrade_refuses_nonempty_evidence() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.downgrade()
    assert [name for name, _, _ in recorder.calls] == ["execute", "drop_table"]
    assert recorder.calls[-1] == (
        "drop_table",
        ("workflow_shadow_comparisons",),
        {},
    )
