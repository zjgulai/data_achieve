from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from sqlalchemy import Engine, create_engine, text

API_ROOT = Path(__file__).resolve().parents[2]


class LineageSeed(Protocol):
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    workflow_run_id: uuid.UUID
    workflow_step_run_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class LegacyIds:
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    source_id: uuid.UUID
    collection_task_id: uuid.UUID
    task_run_id: uuid.UUID
    raw_record_id: uuid.UUID
    dataset_id: uuid.UUID
    dataset_version_id: uuid.UUID


def _sync_database_url(database_url: str) -> str:
    return database_url.replace(
        "postgresql+asyncpg://",
        "postgresql+psycopg://",
        1,
    )


def _engine(database_url: str, *, autocommit: bool = False) -> Engine:
    return create_engine(
        _sync_database_url(database_url),
        isolation_level="AUTOCOMMIT" if autocommit else None,
    )


def _run_alembic(
    database_url: str,
    *arguments: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    return subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=API_ROOT,
        env=environment,
        check=check,
        capture_output=True,
        text=True,
    )


def _reset_public_schema(database_url: str) -> None:
    engine = _engine(database_url, autocommit=True)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
            connection.exec_driver_sql("CREATE SCHEMA public")
    finally:
        engine.dispose()


def _revision(database_url: str) -> str:
    engine = _engine(database_url)
    try:
        with engine.connect() as connection:
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
    finally:
        engine.dispose()
    assert isinstance(revision, str)
    return revision


def _columns(database_url: str, table_name: str) -> set[str]:
    engine = _engine(database_url)
    try:
        with engine.connect() as connection:
            return set(
                connection.scalars(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND table_name = :table_name"
                    ),
                    {"table_name": table_name},
                )
            )
    finally:
        engine.dispose()


def _seed_legacy_state(database_url: str) -> LegacyIds:
    ids = LegacyIds(*(uuid.uuid4() for _ in range(9)))
    engine = _engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (id, email, password_hash, name, status) "
                    "VALUES (:id, :email, 'not-real', 'Legacy User', 'active')"
                ),
                {"id": ids.user_id, "email": f"{ids.user_id}@example.test"},
            )
            connection.execute(
                text(
                    "INSERT INTO workspaces (id, name, slug, owner_id) "
                    "VALUES (:id, 'Legacy Workspace', :slug, :owner_id)"
                ),
                {
                    "id": ids.workspace_id,
                    "slug": f"legacy-{ids.workspace_id}",
                    "owner_id": ids.user_id,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO projects "
                    "(id, workspace_id, name, description, domain, status, owner_id) "
                    "VALUES (:id, :workspace_id, 'Legacy Project', NULL, "
                    "'social', 'active', :owner_id)"
                ),
                {
                    "id": ids.project_id,
                    "workspace_id": ids.workspace_id,
                    "owner_id": ids.user_id,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO sources "
                    "(id, workspace_id, project_id, name, type, url, config, "
                    "schedule_cron, enabled) VALUES "
                    "(:id, :workspace_id, :project_id, 'Legacy Source', 'api', NULL, "
                    "CAST(:config AS JSON), NULL, false)"
                ),
                {
                    "id": ids.source_id,
                    "workspace_id": ids.workspace_id,
                    "project_id": ids.project_id,
                    "config": json.dumps({}),
                },
            )
            connection.execute(
                text(
                    "INSERT INTO collection_tasks "
                    "(id, workspace_id, project_id, source_id, collector_type, name, "
                    "schedule_cron, status, config, success_count, failure_count, last_run_at) "
                    "VALUES (:id, :workspace_id, :project_id, :source_id, 'api', "
                    "'Legacy Task', NULL, 'active', CAST(:config AS JSON), 1, 0, NOW())"
                ),
                {
                    "id": ids.collection_task_id,
                    "workspace_id": ids.workspace_id,
                    "project_id": ids.project_id,
                    "source_id": ids.source_id,
                    "config": json.dumps({}),
                },
            )
            connection.execute(
                text(
                    "INSERT INTO task_runs "
                    "(id, task_id, workspace_id, status, started_at, finished_at, "
                    "records_count, entities_count, error_message, error_traceback, logs, "
                    "created_at) VALUES (:id, :task_id, :workspace_id, 'completed', "
                    "NOW(), NOW(), 1, 0, NULL, NULL, CAST(:logs AS JSON), NOW())"
                ),
                {
                    "id": ids.task_run_id,
                    "task_id": ids.collection_task_id,
                    "workspace_id": ids.workspace_id,
                    "logs": json.dumps([]),
                },
            )
            connection.execute(
                text(
                    "INSERT INTO raw_records "
                    "(id, workspace_id, project_id, source_id, task_run_id, record_type, "
                    "source_url, content, content_hash, screenshot_url, collected_at, created_at) "
                    "VALUES (:id, :workspace_id, :project_id, :source_id, :task_run_id, "
                    "'legacy.social', NULL, CAST(:content AS JSON), :content_hash, NULL, "
                    "NOW(), NOW())"
                ),
                {
                    "id": ids.raw_record_id,
                    "workspace_id": ids.workspace_id,
                    "project_id": ids.project_id,
                    "source_id": ids.source_id,
                    "task_run_id": ids.task_run_id,
                    "content": json.dumps({"legacy": True}),
                    "content_hash": "e" * 64,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO datasets "
                    "(id, workspace_id, project_id, name, dataset_type, status, description) "
                    "VALUES (:id, :workspace_id, :project_id, 'Legacy Dataset', "
                    "'social_raw', 'active', NULL)"
                ),
                {
                    "id": ids.dataset_id,
                    "workspace_id": ids.workspace_id,
                    "project_id": ids.project_id,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO dataset_versions "
                    "(id, dataset_id, workspace_id, project_id, created_by_user_id, "
                    "cleaning_plan_id, version_number, source_task_run_ids, selected_fields, "
                    "cleaning_script, rows, export_preview, row_count, "
                    "average_completeness_percent, status, created_at) VALUES "
                    "(:id, :dataset_id, :workspace_id, :project_id, :user_id, NULL, 1, "
                    "CAST(:task_ids AS JSON), CAST(:fields AS JSON), CAST(:script AS JSON), "
                    "CAST(:rows AS JSON), CAST(:preview AS JSON), 1, 100, 'saved', NOW())"
                ),
                {
                    "id": ids.dataset_version_id,
                    "dataset_id": ids.dataset_id,
                    "workspace_id": ids.workspace_id,
                    "project_id": ids.project_id,
                    "user_id": ids.user_id,
                    "task_ids": json.dumps([str(ids.task_run_id)]),
                    "fields": json.dumps(["legacy"]),
                    "script": json.dumps([]),
                    "rows": json.dumps([{"legacy": True}]),
                    "preview": json.dumps({"rows": 1}),
                },
            )
    finally:
        engine.dispose()
    return ids


def _legacy_snapshot(
    database_url: str,
    ids: LegacyIds,
) -> tuple[tuple[object, ...], tuple[object, ...]]:
    engine = _engine(database_url)
    try:
        with engine.connect() as connection:
            raw = tuple(
                connection.execute(
                    text(
                        "SELECT id, source_id, task_run_id, content_hash "
                        "FROM raw_records WHERE id = :id"
                    ),
                    {"id": ids.raw_record_id},
                ).one()
            )
            dataset = tuple(
                connection.execute(
                    text(
                        "SELECT id, dataset_id, source_task_run_ids, row_count "
                        "FROM dataset_versions WHERE id = :id"
                    ),
                    {"id": ids.dataset_version_id},
                ).one()
            )
    finally:
        engine.dispose()
    return raw, dataset


def test_source_has_one_head_at_034(postgres_database_url: str) -> None:
    parsed = urlsplit(str(postgres_database_url))
    assert parsed.password is not None
    assert parsed.password not in repr(postgres_database_url)
    heads = [
        line
        for line in _run_alembic(postgres_database_url, "heads").stdout.splitlines()
        if line.strip()
    ]
    assert heads == ["202607170034 (head)"]
    assert _revision(postgres_database_url) == "202607170034"


def test_033_to_034_to_033_to_034_preserves_legacy_assets(
    guarded_database_url: str,
) -> None:
    _reset_public_schema(guarded_database_url)
    _run_alembic(guarded_database_url, "upgrade", "202607160033")
    ids = _seed_legacy_state(guarded_database_url)
    before = _legacy_snapshot(guarded_database_url, ids)

    _run_alembic(guarded_database_url, "upgrade", "202607170034")
    assert _revision(guarded_database_url) == "202607170034"
    assert _legacy_snapshot(guarded_database_url, ids) == before
    assert _columns(
        guarded_database_url,
        "workflow_lineage_materialization_requests",
    )

    _run_alembic(guarded_database_url, "downgrade", "202607160033")
    assert _revision(guarded_database_url) == "202607160033"
    assert _legacy_snapshot(guarded_database_url, ids) == before
    assert not _columns(
        guarded_database_url,
        "workflow_lineage_materialization_requests",
    )

    _run_alembic(guarded_database_url, "upgrade", "202607170034")
    assert _revision(guarded_database_url) == "202607170034"
    assert _legacy_snapshot(guarded_database_url, ids) == before


def test_032_to_033_to_032_to_033_preserves_legacy_assets(
    guarded_database_url: str,
) -> None:
    _reset_public_schema(guarded_database_url)
    _run_alembic(guarded_database_url, "upgrade", "202607160032")
    ids = _seed_legacy_state(guarded_database_url)
    before = _legacy_snapshot(guarded_database_url, ids)

    _run_alembic(guarded_database_url, "upgrade", "202607160033")
    assert _revision(guarded_database_url) == "202607160033"
    assert _legacy_snapshot(guarded_database_url, ids) == before
    assert {
        "workflow_run_id",
        "workflow_step_run_id",
        "workflow_lineage_contract_version",
    } <= _columns(guarded_database_url, "raw_records")

    _run_alembic(guarded_database_url, "downgrade", "202607160032")
    assert _revision(guarded_database_url) == "202607160032"
    assert _legacy_snapshot(guarded_database_url, ids) == before
    assert "workflow_run_id" not in _columns(guarded_database_url, "raw_records")

    _run_alembic(guarded_database_url, "upgrade", "202607160033")
    assert _revision(guarded_database_url) == "202607160033"
    assert _legacy_snapshot(guarded_database_url, ids) == before


def test_downgrade_refuses_persisted_v2_lineage(
    postgres_database_url: str,
    postgres_engine: Engine,
    seeded_lineage_graph: LineageSeed,
) -> None:
    seed = seeded_lineage_graph
    with postgres_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO raw_records "
                "(id, workspace_id, project_id, source_id, task_run_id, workflow_run_id, "
                "workflow_step_run_id, workflow_lineage_contract_version, record_type, "
                "source_url, content, content_hash, screenshot_url, collected_at, created_at) "
                "VALUES (:id, :workspace_id, :project_id, NULL, NULL, :run_id, :step_id, "
                "'workflow_raw_record.v1', 'social_raw.v1', NULL, CAST(:content AS JSON), "
                ":content_hash, NULL, NOW(), NOW())"
            ),
            {
                "id": uuid.uuid4(),
                "workspace_id": seed.workspace_id,
                "project_id": seed.project_id,
                "run_id": seed.workflow_run_id,
                "step_id": seed.workflow_step_run_id,
                "content": json.dumps({"lineage": True}),
                "content_hash": "f" * 64,
            },
        )

    result = _run_alembic(
        postgres_database_url,
        "downgrade",
        "202607160032",
        check=False,
    )
    assert result.returncode != 0
    assert "202607160033 downgrade refused: V2 workflow lineage data exists" in (
        result.stdout + result.stderr
    )
    assert _revision(postgres_database_url) == "202607170034"
    assert _columns(
        postgres_database_url,
        "workflow_lineage_materialization_requests",
    )
