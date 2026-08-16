from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Protocol, cast

MIGRATION_PATH = (
    Path(__file__).parents[2] / "alembic" / "versions" / "202607220035_platform_credential_vault.py"
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


def _load() -> MigrationModule:
    assert MIGRATION_PATH.is_file()
    spec = importlib.util.spec_from_file_location("platform_credential_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(MigrationModule, module)


def test_revision_035_is_linear_and_creates_workspace_scoped_vault() -> None:
    module = _load()
    assert module.revision == "202607220035"
    assert module.down_revision == "202607170034"
    recorder = RecordingOp()
    module.op = recorder
    module.upgrade()

    create = next(args for name, args, _ in recorder.calls if name == "create_table")
    assert create[0] == "platform_credential_bundles"
    assert "encrypted_payload" in {getattr(column, "name", None) for column in create[1:]}
    assert "configured_fields" in {getattr(column, "name", None) for column in create[1:]}


def test_revision_035_downgrade_refuses_nonempty_vault_before_drop() -> None:
    module = _load()
    recorder = RecordingOp()
    module.op = recorder
    module.downgrade()

    execute_index = next(
        index for index, (name, _, _) in enumerate(recorder.calls) if name == "execute"
    )
    drop_index = next(
        index
        for index, (name, args, _) in enumerate(recorder.calls)
        if name == "drop_table" and args[0] == "platform_credential_bundles"
    )
    assert execute_index < drop_index
    assert "downgrade refused" in str(recorder.calls[execute_index][1][0])
