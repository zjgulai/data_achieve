from __future__ import annotations

import json
import uuid
from typing import Protocol

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError


class LineageSeed(Protocol):
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    other_project_id: uuid.UUID
    workflow_run_id: uuid.UUID
    workflow_step_run_id: uuid.UUID
    dataset_id: uuid.UUID


def _sqlstate(error: DBAPIError) -> str | None:
    return getattr(error.orig, "sqlstate", None)


def _insert_raw_record(
    engine: Engine,
    seed: LineageSeed,
    *,
    project_id: uuid.UUID | None = None,
    content_hash: str = "b" * 64,
    contract_version: str | None = "workflow_raw_record.v1",
) -> uuid.UUID:
    record_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO raw_records "
                "(id, workspace_id, project_id, source_id, task_run_id, workflow_run_id, "
                "workflow_step_run_id, workflow_lineage_contract_version, record_type, "
                "source_url, content, content_hash, screenshot_url, collected_at, created_at) "
                "VALUES (:id, :workspace_id, :project_id, NULL, NULL, :run_id, :step_id, "
                ":contract_version, 'social_raw.v1', NULL, CAST(:content AS JSON), "
                ":content_hash, NULL, NOW(), NOW())"
            ),
            {
                "id": record_id,
                "workspace_id": seed.workspace_id,
                "project_id": project_id or seed.project_id,
                "run_id": seed.workflow_run_id,
                "step_id": seed.workflow_step_run_id,
                "contract_version": contract_version,
                "content": json.dumps({"id": str(record_id)}),
                "content_hash": content_hash,
            },
        )
    return record_id


def _insert_dataset_version(
    engine: Engine,
    seed: LineageSeed,
    *,
    raw_record_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    include_raw_ids: bool = True,
    contract_version: str | None = "workflow_dataset_version.v1",
) -> uuid.UUID:
    version_id = uuid.uuid4()
    raw_ids = json.dumps([str(raw_record_id)]) if include_raw_ids else None
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO dataset_versions "
                "(id, dataset_id, workspace_id, project_id, created_by_user_id, "
                "cleaning_plan_id, source_workflow_run_id, source_workflow_step_run_ids, "
                "source_raw_record_ids, lineage_contract_version, version_number, "
                "source_task_run_ids, selected_fields, cleaning_script, rows, export_preview, "
                "row_count, average_completeness_percent, status, created_at) VALUES "
                "(:id, :dataset_id, :workspace_id, :project_id, :user_id, NULL, :run_id, "
                "CAST(:step_ids AS JSON), CAST(:raw_ids AS JSON), :contract_version, "
                "1, CAST(:task_ids AS JSON), CAST(:fields AS JSON), CAST(:script AS JSON), "
                "CAST(:rows AS JSON), CAST(:preview AS JSON), 1, 100, 'saved', NOW())"
            ),
            {
                "id": version_id,
                "dataset_id": seed.dataset_id,
                "workspace_id": seed.workspace_id,
                "project_id": project_id or seed.project_id,
                "user_id": seed.user_id,
                "run_id": seed.workflow_run_id,
                "step_ids": json.dumps([str(seed.workflow_step_run_id)]),
                "raw_ids": raw_ids,
                "contract_version": contract_version,
                "task_ids": json.dumps([]),
                "fields": json.dumps(["id"]),
                "script": json.dumps([]),
                "rows": json.dumps([{"id": str(raw_record_id)}]),
                "preview": json.dumps({"rows": 1}),
            },
        )
    return version_id


def test_head_exposes_named_lineage_columns_constraints_and_indexes(
    postgres_engine: Engine,
) -> None:
    with postgres_engine.connect() as connection:
        raw_columns = set(
            connection.scalars(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'raw_records'"
                )
            )
        )
        dataset_columns = set(
            connection.scalars(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'dataset_versions'"
                )
            )
        )
        constraint_rows = [
            tuple(row)
            for row in connection.execute(
                text(
                    "SELECT conrelid::regclass::text, conname, pg_get_constraintdef(oid) "
                    "FROM pg_constraint WHERE conrelid IN ('raw_records'::regclass, "
                    "'dataset_versions'::regclass, 'step_runs'::regclass)"
                )
            )
        ]
        index_names = set(
            connection.scalars(
                text(
                    "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' "
                    "AND tablename IN ('raw_records', 'dataset_versions')"
                )
            )
        )

    assert {
        "workflow_run_id",
        "workflow_step_run_id",
        "workflow_lineage_contract_version",
    } <= raw_columns
    assert {
        "source_workflow_run_id",
        "source_workflow_step_run_ids",
        "source_raw_record_ids",
        "lineage_contract_version",
    } <= dataset_columns
    constraint_names = {str(row[1]) for row in constraint_rows}
    raw_check_definitions = {str(row[2]) for row in constraint_rows if row[0] == "raw_records"}
    dataset_check_definitions = {
        str(row[2]) for row in constraint_rows if row[0] == "dataset_versions"
    }
    assert {
        "uq_step_runs_tenant_run_id",
        "uq_raw_records_workflow_step_content_hash",
        "fk_raw_records_workflow_run_tenant",
        "fk_raw_records_workflow_step_tenant",
        "fk_dataset_versions_workflow_run_tenant",
    } <= constraint_names
    assert any(
        "task_run_id IS NOT NULL" in definition and "workflow_step_run_id IS NOT NULL" in definition
        for definition in raw_check_definitions
    )
    assert any(
        "workflow_lineage_contract_version" in definition and "workflow_raw_record.v1" in definition
        for definition in raw_check_definitions
    )
    assert any(
        "source_raw_record_ids" in definition and "workflow_dataset_version.v1" in definition
        for definition in dataset_check_definitions
    )
    assert {
        "ix_raw_records_workflow_run",
        "ix_raw_records_workflow_step",
        "ix_dataset_versions_workflow_run",
    } <= index_names


def test_workflow_template_revisions_reject_update_and_delete(
    postgres_engine: Engine,
    seeded_lineage_graph: LineageSeed,
) -> None:
    seed = seeded_lineage_graph
    template_id = uuid.uuid4()
    revision_id = uuid.uuid4()
    with postgres_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO workflow_templates "
                "(id, workspace_id, project_id, created_by_user_id, name, template_key, "
                "description, status, current_revision_id) VALUES "
                "(:id, :workspace_id, :project_id, :user_id, 'Immutable template', "
                ":template_key, NULL, 'draft', NULL)"
            ),
            {
                "id": template_id,
                "workspace_id": seed.workspace_id,
                "project_id": seed.project_id,
                "user_id": seed.user_id,
                "template_key": f"immutable-{template_id}",
            },
        )
        connection.execute(
            text(
                "INSERT INTO workflow_template_revisions "
                "(id, workspace_id, project_id, workflow_template_id, created_by_user_id, "
                "revision_number, definition, definition_fingerprint) VALUES "
                "(:id, :workspace_id, :project_id, :template_id, :user_id, 1, "
                "CAST(:definition AS JSON), :fingerprint)"
            ),
            {
                "id": revision_id,
                "workspace_id": seed.workspace_id,
                "project_id": seed.project_id,
                "template_id": template_id,
                "user_id": seed.user_id,
                "definition": json.dumps({"flow_mode": "batch_research"}),
                "fingerprint": "sha256:" + "e" * 64,
            },
        )
        connection.execute(
            text(
                "UPDATE workflow_templates SET current_revision_id = :revision_id "
                "WHERE id = :template_id"
            ),
            {"revision_id": revision_id, "template_id": template_id},
        )

    with (
        pytest.raises(DBAPIError) as update_attempt,
        postgres_engine.begin() as connection,
    ):
        connection.execute(
            text(
                "UPDATE workflow_template_revisions SET revision_number = 2 "
                "WHERE id = :revision_id"
            ),
            {"revision_id": revision_id},
        )
    assert _sqlstate(update_attempt.value) == "55000"

    with (
        pytest.raises(DBAPIError) as delete_attempt,
        postgres_engine.begin() as connection,
    ):
        connection.execute(
            text("DELETE FROM workflow_template_revisions WHERE id = :revision_id"),
            {"revision_id": revision_id},
        )
    assert _sqlstate(delete_attempt.value) == "55000"


def test_valid_v2_lineage_persists_and_duplicate_step_hash_is_rejected(
    postgres_engine: Engine,
    seeded_lineage_graph: LineageSeed,
) -> None:
    seed = seeded_lineage_graph
    raw_record_id = _insert_raw_record(postgres_engine, seed)
    dataset_version_id = _insert_dataset_version(
        postgres_engine,
        seed,
        raw_record_id=raw_record_id,
    )

    with postgres_engine.connect() as connection:
        raw_lineage = tuple(
            connection.execute(
                text(
                    "SELECT source_id, task_run_id, workflow_run_id, workflow_step_run_id, "
                    "workflow_lineage_contract_version FROM raw_records WHERE id = :id"
                ),
                {"id": raw_record_id},
            ).one()
        )
        dataset_lineage = tuple(
            connection.execute(
                text(
                    "SELECT source_task_run_ids, source_workflow_run_id, "
                    "source_workflow_step_run_ids, source_raw_record_ids, "
                    "lineage_contract_version FROM dataset_versions WHERE id = :id"
                ),
                {"id": dataset_version_id},
            ).one()
        )

    assert raw_lineage == (
        None,
        None,
        seed.workflow_run_id,
        seed.workflow_step_run_id,
        "workflow_raw_record.v1",
    )
    assert dataset_lineage == (
        [],
        seed.workflow_run_id,
        [str(seed.workflow_step_run_id)],
        [str(raw_record_id)],
        "workflow_dataset_version.v1",
    )

    with pytest.raises(IntegrityError) as duplicate:
        _insert_raw_record(postgres_engine, seed)
    assert _sqlstate(duplicate.value) == "23505"


def test_raw_record_contract_and_tenant_foreign_keys_fail_closed(
    postgres_engine: Engine,
    seeded_lineage_graph: LineageSeed,
) -> None:
    seed = seeded_lineage_graph
    with pytest.raises(IntegrityError) as missing_contract:
        _insert_raw_record(postgres_engine, seed, contract_version=None)
    assert _sqlstate(missing_contract.value) == "23514"

    with pytest.raises(IntegrityError) as cross_project:
        _insert_raw_record(
            postgres_engine,
            seed,
            project_id=seed.other_project_id,
            content_hash="c" * 64,
        )
    assert _sqlstate(cross_project.value) == "23503"


def test_dataset_contract_and_tenant_foreign_key_fail_closed(
    postgres_engine: Engine,
    seeded_lineage_graph: LineageSeed,
) -> None:
    seed = seeded_lineage_graph
    raw_record_id = _insert_raw_record(postgres_engine, seed, content_hash="d" * 64)

    with pytest.raises(IntegrityError) as missing_contract:
        _insert_dataset_version(
            postgres_engine,
            seed,
            raw_record_id=raw_record_id,
            contract_version=None,
        )
    assert _sqlstate(missing_contract.value) == "23514"

    with pytest.raises(IntegrityError) as missing_raw_ids:
        _insert_dataset_version(
            postgres_engine,
            seed,
            raw_record_id=raw_record_id,
            include_raw_ids=False,
        )
    assert _sqlstate(missing_raw_ids.value) == "23514"

    with pytest.raises(IntegrityError) as cross_project:
        _insert_dataset_version(
            postgres_engine,
            seed,
            raw_record_id=raw_record_id,
            project_id=seed.other_project_id,
        )
    assert _sqlstate(cross_project.value) == "23503"
