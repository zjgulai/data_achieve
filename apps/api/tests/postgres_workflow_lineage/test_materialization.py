from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Protocol

import pytest
from sqlalchemy import Connection, Engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from data_intelligence_hub.models.dataset import DatasetVersion
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.workflow_execution import (
    StepRun,
    WorkflowRun,
)
from data_intelligence_hub.models.workflow_execution import (
    WorkflowLineageMaterializationRequest as MaterializationLedger,
)
from data_intelligence_hub.schemas.workflow_execution import (
    WorkflowRunResponse,
    WorkflowStepRunResponse,
)
from data_intelligence_hub.schemas.workflow_lineage import (
    WorkflowLineageMaterializationRequest,
    WorkflowLineageMaterializationResponse,
)
from data_intelligence_hub.services.workflow_execution.fixtures import (
    execute_workflow_fixture_step,
    load_workflow_fixture_profile,
)
from data_intelligence_hub.services.workflow_execution.lineage_preview import (
    build_workflow_lineage_preview,
)
from data_intelligence_hub.services.workflow_execution.materialization import (
    materialize_workflow_lineage,
)
from tests.unit.test_workflow_execution_fixtures import _resolved_contracts

API_ROOT = Path(__file__).resolve().parents[2]


class LineageSeed(Protocol):
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    other_project_id: uuid.UUID
    workflow_run_id: uuid.UUID
    workflow_step_run_id: uuid.UUID
    dataset_id: uuid.UUID


def _sqlstate(error: IntegrityError) -> str | None:
    return getattr(error.orig, "sqlstate", None)


def _constraint_name(error: IntegrityError) -> str | None:
    return getattr(getattr(error.orig, "diag", None), "constraint_name", None)


def _insert_materialized_assets(
    connection: Connection,
    seed: LineageSeed,
) -> tuple[uuid.UUID, uuid.UUID]:
    raw_record_id = uuid.uuid4()
    dataset_version_id = uuid.uuid4()
    row = {"provider_record_id": str(raw_record_id)}
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
            "id": raw_record_id,
            "workspace_id": seed.workspace_id,
            "project_id": seed.project_id,
            "run_id": seed.workflow_run_id,
            "step_id": seed.workflow_step_run_id,
            "content": json.dumps(row),
            "content_hash": "b" * 64,
        },
    )
    connection.execute(
        text(
            "INSERT INTO dataset_versions "
            "(id, dataset_id, workspace_id, project_id, created_by_user_id, "
            "cleaning_plan_id, source_workflow_run_id, source_workflow_step_run_ids, "
            "source_raw_record_ids, lineage_contract_version, version_number, "
            "source_task_run_ids, selected_fields, cleaning_script, rows, export_preview, "
            "row_count, average_completeness_percent, status, created_at) VALUES "
            "(:id, :dataset_id, :workspace_id, :project_id, :user_id, NULL, :run_id, "
            "CAST(:step_ids AS JSON), CAST(:raw_ids AS JSON), "
            "'workflow_dataset_version.v1', 1, CAST(:task_ids AS JSON), "
            "CAST(:fields AS JSON), CAST(:script AS JSON), CAST(:rows AS JSON), "
            "CAST(:preview AS JSON), 1, 100, 'saved', NOW())"
        ),
        {
            "id": dataset_version_id,
            "dataset_id": seed.dataset_id,
            "workspace_id": seed.workspace_id,
            "project_id": seed.project_id,
            "user_id": seed.user_id,
            "run_id": seed.workflow_run_id,
            "step_ids": json.dumps([str(seed.workflow_step_run_id)]),
            "raw_ids": json.dumps([str(raw_record_id)]),
            "task_ids": json.dumps([]),
            "fields": json.dumps(["provider_record_id"]),
            "script": json.dumps([]),
            "rows": json.dumps([row]),
            "preview": json.dumps({"row_count": 1}),
        },
    )
    return raw_record_id, dataset_version_id


def _insert_ledger(
    connection: Connection,
    seed: LineageSeed,
    *,
    dataset_version_id: uuid.UUID,
    ledger_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    key_hash: str | None = None,
) -> None:
    connection.execute(
        text(
            "INSERT INTO workflow_lineage_materialization_requests "
            "(id, workspace_id, project_id, created_by_user_id, workflow_run_id, "
            "dataset_id, dataset_version_id, idempotency_scope, idempotency_key_hash, "
            "request_hash, outcome, response_status, response_payload, created_at) VALUES "
            "(:id, :workspace_id, :project_id, :user_id, :run_id, :dataset_id, "
            ":dataset_version_id, :scope, :key_hash, :request_hash, 'completed', 201, "
            "CAST(:response AS JSON), NOW())"
        ),
        {
            "id": ledger_id,
            "workspace_id": seed.workspace_id,
            "project_id": project_id or seed.project_id,
            "user_id": seed.user_id,
            "run_id": seed.workflow_run_id,
            "dataset_id": seed.dataset_id,
            "dataset_version_id": dataset_version_id,
            "scope": f"materialization:{seed.workflow_run_id}",
            "key_hash": key_hash or "sha256:" + "c" * 64,
            "request_hash": "sha256:" + "d" * 64,
            "response": json.dumps({"materialization_id": str(ledger_id)}),
        },
    )


def test_head_exposes_materialization_constraints_and_tenant_fks(
    postgres_engine: Engine,
    seeded_lineage_graph: LineageSeed,
) -> None:
    seed = seeded_lineage_graph
    with postgres_engine.connect() as connection:
        constraint_names = set(
            connection.scalars(
                text(
                    "SELECT conname FROM pg_constraint WHERE conrelid IN "
                    "('workflow_lineage_materialization_requests'::regclass, "
                    "'datasets'::regclass, 'dataset_versions'::regclass)"
                )
            )
        )
    assert {
        "uq_datasets_tenant_id",
        "uq_dataset_versions_tenant_dataset_id",
        "uq_dataset_versions_source_workflow_run",
        "uq_workflow_lineage_materializations_idempotency",
        "uq_workflow_lineage_materializations_run",
        "fk_workflow_lineage_materializations_run_tenant",
        "fk_workflow_lineage_materializations_dataset_tenant",
        "fk_workflow_lineage_materializations_version_tenant",
    } <= constraint_names

    with postgres_engine.begin() as connection:
        _, version_id = _insert_materialized_assets(connection, seed)
    with (
        pytest.raises(IntegrityError) as cross_project,
        postgres_engine.begin() as connection,
    ):
        _insert_ledger(
            connection,
            seed,
            dataset_version_id=version_id,
            ledger_id=uuid.uuid4(),
            project_id=seed.other_project_id,
        )
    assert _sqlstate(cross_project.value) == "23503"


def test_concurrent_materialization_ledger_has_exactly_one_winner(
    postgres_engine: Engine,
    seeded_lineage_graph: LineageSeed,
) -> None:
    seed = seeded_lineage_graph
    with postgres_engine.begin() as connection:
        _, version_id = _insert_materialized_assets(connection, seed)
    barrier = threading.Barrier(2)

    def contender(index: int) -> tuple[str, str | None]:
        try:
            with postgres_engine.begin() as connection:
                barrier.wait(timeout=10)
                _insert_ledger(
                    connection,
                    seed,
                    dataset_version_id=version_id,
                    ledger_id=uuid.uuid4(),
                    key_hash="sha256:" + str(index) * 64,
                )
            return "committed", None
        except IntegrityError as exc:
            return _sqlstate(exc) or "unknown", _constraint_name(exc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(contender, (1, 2)))

    assert sorted(item[0] for item in outcomes) == ["23505", "committed"]
    loser = next(item for item in outcomes if item[0] == "23505")
    assert loser[1] == "uq_workflow_lineage_materializations_run"
    with postgres_engine.connect() as connection:
        count = connection.scalar(
            text("SELECT COUNT(*) FROM workflow_lineage_materialization_requests")
        )
    assert count == 1


def test_transaction_failure_rolls_back_all_materialized_assets(
    postgres_engine: Engine,
    seeded_lineage_graph: LineageSeed,
) -> None:
    seed = seeded_lineage_graph
    with (
        pytest.raises(RuntimeError, match="injected_failure"),
        postgres_engine.begin() as connection,
    ):
        _, version_id = _insert_materialized_assets(connection, seed)
        _insert_ledger(
            connection,
            seed,
            dataset_version_id=version_id,
            ledger_id=uuid.uuid4(),
        )
        raise RuntimeError("injected_failure")

    with postgres_engine.connect() as connection:
        counts = {
            "raw_records": connection.scalar(text("SELECT COUNT(*) FROM raw_records")),
            "dataset_versions": connection.scalar(text("SELECT COUNT(*) FROM dataset_versions")),
            "workflow_lineage_materialization_requests": connection.scalar(
                text("SELECT COUNT(*) FROM workflow_lineage_materialization_requests")
            ),
        }
    assert counts == {
        "raw_records": 0,
        "dataset_versions": 0,
        "workflow_lineage_materialization_requests": 0,
    }


def test_downgrade_refuses_nonempty_materialization_ledger(
    postgres_database_url: str,
    postgres_engine: Engine,
    seeded_lineage_graph: LineageSeed,
) -> None:
    seed = seeded_lineage_graph
    with postgres_engine.begin() as connection:
        _, version_id = _insert_materialized_assets(connection, seed)
        _insert_ledger(
            connection,
            seed,
            dataset_version_id=version_id,
            ledger_id=uuid.uuid4(),
        )

    environment = os.environ.copy()
    environment["DATABASE_URL"] = postgres_database_url
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "202607160033"],
        cwd=API_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert (
        "202607170034 downgrade refused: workflow lineage materialization data exists"
        in result.stdout + result.stderr
    )
    with postgres_engine.connect() as connection:
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
    assert revision == "202607170034"


@pytest.mark.asyncio
async def test_concurrent_service_calls_return_one_write_and_one_exact_replay(
    postgres_database_url: str,
    postgres_engine: Engine,
    seeded_lineage_graph: LineageSeed,
) -> None:
    seed = seeded_lineage_graph
    loaded = load_workflow_fixture_profile("fixture-primary-payload-v1")
    contract = _resolved_contracts()[0]
    receipt = execute_workflow_fixture_step(loaded, contract)
    candidate = contract.route_plan.primary_implementation
    assert candidate is not None
    with postgres_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE workflow_runs SET fixture_profile_id = :profile_id, "
                "fixture_profile_hash = :profile_hash, total_steps = 1, "
                "completed_steps = 1, records_count = :records_count "
                "WHERE id = :run_id"
            ),
            {
                "profile_id": loaded.profile.profile_id,
                "profile_hash": loaded.profile_hash,
                "records_count": receipt.records_count,
                "run_id": seed.workflow_run_id,
            },
        )
        connection.execute(
            text(
                "UPDATE step_runs SET step_ref = :step_ref, "
                "requirement_ref = :requirement_ref, sequence = :sequence, "
                "platform = :platform, resource_type = :resource_type, "
                "operation = :operation, assertion_id = :assertion_id, "
                "implementation_id = :implementation_id, "
                "route_plan_snapshot = CAST(:route AS JSON), "
                "evidence_refs = CAST(:evidence AS JSON), "
                "fixture_case_id = :case_id, fixture_content_hash = :fixture_hash, "
                "output_digest = :output_digest, status = 'completed', "
                "records_count = :records_count WHERE id = :step_id"
            ),
            {
                "step_ref": contract.step.step_ref,
                "requirement_ref": contract.requirement.requirement_ref,
                "sequence": contract.step.sequence,
                "platform": contract.requirement.platform.value,
                "resource_type": contract.requirement.resource_type.value,
                "operation": contract.requirement.operation.value,
                "assertion_id": candidate.assertion_id,
                "implementation_id": candidate.implementation_id,
                "route": json.dumps(contract.route_plan.model_dump(mode="json")),
                "evidence": json.dumps(candidate.evidence_refs),
                "case_id": receipt.fixture_case_id,
                "fixture_hash": receipt.fixture_content_hash,
                "output_digest": receipt.output_digest,
                "records_count": receipt.records_count,
                "step_id": seed.workflow_step_run_id,
            },
        )

    async_engine = create_async_engine(postgres_database_url)
    sessions = async_sessionmaker(async_engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            run = await session.get(WorkflowRun, seed.workflow_run_id)
            step = await session.get(StepRun, seed.workflow_step_run_id)
            assert run is not None and step is not None
            preview = build_workflow_lineage_preview(
                WorkflowRunResponse.model_validate(run),
                [WorkflowStepRunResponse.model_validate(step)],
                payload_bound=True,
            )
        request = WorkflowLineageMaterializationRequest(
            dataset_name="postgres-concurrent-materialization",
            expected_lineage_digest=preview.lineage_digest,
        )

        async def contender(
            request_id: str,
        ) -> WorkflowLineageMaterializationResponse:
            async with sessions() as session:
                return await materialize_workflow_lineage(
                    session,
                    workspace_id=seed.workspace_id,
                    project_id=seed.project_id,
                    workflow_run_id=seed.workflow_run_id,
                    created_by_user_id=seed.user_id,
                    payload=request,
                    idempotency_key="postgres-concurrent-materialization-key-0001",
                    request_id=request_id,
                )

        results = await asyncio.gather(contender("winner-a"), contender("winner-b"))
        assert sorted(item.database_write for item in results) == [False, True]
        assert sorted(item.idempotent_replay for item in results) == [False, True]
        assert results[0].dataset_version_id == results[1].dataset_version_id
        assert results[0].raw_record_ids == results[1].raw_record_ids
        async with sessions() as session:
            counts = [
                int((await session.execute(select(func.count()).select_from(model))).scalar_one())
                for model in (
                    RawRecord,
                    DatasetVersion,
                    MaterializationLedger,
                )
            ]
        assert counts == [receipt.records_count, 1, 1]
    finally:
        await async_engine.dispose()
