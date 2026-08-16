from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Protocol, cast

MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "202606110028_capability_governance.py"
)

EXPECTED_TABLES = {
    "capability_governance_memberships",
    "capability_discovery_batches",
    "capability_source_snapshots",
    "capability_discovery_batch_sources",
    "capability_evidence",
    "capability_candidate_versions",
    "capability_candidate_evidence",
    "capability_verification_tasks",
    "capability_verification_decisions",
    "capability_catalog_snapshots",
    "capability_publication_revisions",
    "capability_catalog_head",
    "capability_governance_requests",
}


class RecordingOp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def __getattr__(self, name: str) -> Any:
        def record(*args: object, **kwargs: object) -> None:
            self.calls.append((name, args, kwargs))

        return record


class MigrationModule(Protocol):
    revision: str
    down_revision: str
    GOVERNANCE_TABLES: tuple[str, ...]
    IMMUTABLE_TABLES: tuple[str, ...]
    op: object

    def upgrade(self) -> None: ...

    def downgrade(self) -> None: ...


def _load_migration() -> MigrationModule:
    spec = importlib.util.spec_from_file_location("capability_governance_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(MigrationModule, module)


def test_migration_is_single_linear_successor_with_bounded_tables() -> None:
    module = _load_migration()
    assert module.revision == "202606110028"
    assert module.down_revision == "202606110027"
    assert set(module.GOVERNANCE_TABLES) == EXPECTED_TABLES
    assert set(module.IMMUTABLE_TABLES) == {
        "capability_discovery_batches",
        "capability_source_snapshots",
        "capability_discovery_batch_sources",
        "capability_evidence",
        "capability_candidate_versions",
        "capability_candidate_evidence",
        "capability_verification_decisions",
        "capability_catalog_snapshots",
        "capability_publication_revisions",
        "capability_governance_requests",
    }


def test_upgrade_creates_empty_fail_closed_schema_and_only_null_head_seed() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.upgrade()

    created_tables = {
        str(args[0]) for name, args, _ in recorder.calls if name == "create_table"
    }
    assert created_tables == EXPECTED_TABLES
    inserts = [call for call in recorder.calls if call[0] == "bulk_insert"]
    assert len(inserts) == 1
    rows = inserts[0][1][1]
    assert rows == [
        {
            "singleton_key": "global",
            "current_revision_id": None,
            "head_version": 0,
        }
    ]
    assert not any(
        name in {"execute", "bulk_insert"} and "governor" in repr(args).lower()
        for name, args, _ in recorder.calls
    )


def test_downgrade_drops_every_governance_table_in_reverse_order() -> None:
    module = _load_migration()
    recorder = RecordingOp()
    module.op = recorder
    module.downgrade()

    dropped = [str(args[0]) for name, args, _ in recorder.calls if name == "drop_table"]
    assert dropped == list(reversed(module.GOVERNANCE_TABLES))
