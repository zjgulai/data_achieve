from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Protocol, cast

from sqlalchemy import Constraint, ForeignKeyConstraint

MIGRATION_PATH = (
    Path(__file__).parents[2] / "alembic" / "versions" / "202607230042_provider_health_snapshots.py"
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
    spec = importlib.util.spec_from_file_location("provider_health", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(MigrationModule, module)


def test_revision_042_is_linear_additive_and_source_only() -> None:
    module = _load_migration()
    assert module.revision == "202607230042"
    assert module.down_revision == "202607230041"
    recorder = RecordingOp()
    module.op = recorder
    module.upgrade()
    assert [name for name, _, _ in recorder.calls] == ["create_table", "create_table"]
    assert [args[0] for _, args, _ in recorder.calls] == [
        "provider_health_snapshots",
        "provider_health_route_feedbacks",
    ]


def test_revision_042_retains_version_tenant_and_boundary_constraints() -> None:
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
        "pk_provider_health_snapshots",
        "uq_provider_health_snapshots_scope_version",
        "uq_provider_health_snapshots_aggregation",
        "fk_provider_health_snapshots_project_tenant",
        "ck_provider_health_snapshots_fixture_boundaries",
        "pk_provider_health_route_feedbacks",
        "uq_provider_health_feedbacks_route_version",
        "uq_provider_health_feedbacks_key",
        "fk_provider_health_feedbacks_project_tenant",
        "ck_provider_health_route_feedbacks_fixture_boundaries",
    } <= names
    assert (
        sum(
            isinstance(item, ForeignKeyConstraint)
            for _, args, _ in recorder.calls
            for item in args[1:]
        )
        == 2
    )


def test_revision_042_downgrade_refuses_any_health_evidence() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.downgrade()
    assert [name for name, _, _ in recorder.calls] == [
        "execute",
        "drop_table",
        "drop_table",
    ]
    refusal = cast(str, recorder.calls[0][1][0])
    assert "provider_health_route_feedbacks" in refusal
    assert "provider_health_snapshots" in refusal
    assert [args for name, args, _ in recorder.calls if name == "drop_table"] == [
        ("provider_health_route_feedbacks",),
        ("provider_health_snapshots",),
    ]
