from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from data_intelligence_hub.schemas.workflow_execution import (
    WorkflowFixtureRunCreateRequest,
    WorkflowFixtureRunCreateResponse,
)
from data_intelligence_hub.services.workflow_execution.execution import (
    create_workflow_fixture_run,
)


@dataclass(frozen=True, slots=True)
class PostgresDatabase:
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]


@dataclass(frozen=True, slots=True)
class SeededWorkflowVersion:
    database: PostgresDatabase
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    plan_id: uuid.UUID
    version_id: uuid.UUID
    preview_fingerprint: str


EXPECTED_CONSTRAINTS = {
    "workflow_runs": {
        "pk_workflow_runs",
        "uq_workflow_runs_tenant_id",
        "fk_workflow_runs_version_tenant",
        "fk_workflow_runs_created_by_user",
        "ck_workflow_runs_execution_contract",
        "ck_workflow_runs_execution_mode",
        "ck_workflow_runs_status",
        "ck_workflow_runs_counts",
        "ck_workflow_runs_completed_snapshot",
        "ck_workflow_runs_fixture_boundaries",
    },
    "step_runs": {
        "pk_step_runs",
        "uq_step_runs_tenant_id",
        "uq_step_runs_tenant_run_id",
        "uq_step_runs_run_step_ref",
        "uq_step_runs_run_requirement_implementation",
        "fk_step_runs_run_tenant",
        "ck_step_runs_sequence",
        "ck_step_runs_status",
        "ck_step_runs_records_count",
        "ck_step_runs_completed_snapshot",
        "ck_step_runs_fixture_boundaries",
    },
    "workflow_run_requests": {
        "pk_workflow_run_requests",
        "uq_workflow_run_requests_idempotency",
        "fk_workflow_run_requests_run_tenant",
        "fk_workflow_run_requests_created_by_user",
        "ck_workflow_run_requests_outcome",
        "ck_workflow_run_requests_response_status",
    },
}


def _sqlstate(error: DBAPIError) -> str | None:
    origin = error.orig
    if origin is None:
        return None
    cause = origin.__cause__
    return cast_sqlstate(origin) or (cast_sqlstate(cause) if cause is not None else None)


def cast_sqlstate(error: object) -> str | None:
    value = getattr(error, "sqlstate", None) or getattr(error, "pgcode", None)
    return value if isinstance(value, str) else None


async def _create(
    seed: SeededWorkflowVersion,
    *,
    key: str,
) -> WorkflowFixtureRunCreateResponse:
    async with seed.database.sessions() as session:
        return await create_workflow_fixture_run(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workflow_plan_id=seed.plan_id,
            workflow_version_id=seed.version_id,
            created_by_user_id=seed.user_id,
            payload=WorkflowFixtureRunCreateRequest(
                expected_preview_fingerprint=seed.preview_fingerprint,
                fixture_profile_id="fixture-primary-v1",
            ),
            idempotency_key=key,
            request_id=f"postgres-constraint-{key}",
        )


async def _assert_rejected(
    database: PostgresDatabase,
    statement: str,
    parameters: dict[str, object],
    *,
    sqlstate: str,
) -> None:
    with pytest.raises(DBAPIError) as captured:
        async with database.engine.begin() as connection:
            await connection.execute(text(statement), parameters)
    assert _sqlstate(captured.value) == sqlstate


@pytest.mark.asyncio
async def test_database_catalog_has_exact_named_execution_constraints(
    postgres_database: PostgresDatabase,
) -> None:
    async with postgres_database.engine.connect() as connection:
        rows = (
            await connection.execute(
                text(
                    "SELECT pg_class.relname, pg_constraint.conname "
                    "FROM pg_catalog.pg_constraint "
                    "JOIN pg_catalog.pg_class "
                    "ON pg_class.oid = pg_constraint.conrelid "
                    "JOIN pg_catalog.pg_namespace "
                    "ON pg_namespace.oid = pg_class.relnamespace "
                    "WHERE pg_namespace.nspname = 'public' "
                    "AND pg_class.relname IN "
                    "('workflow_runs', 'step_runs', 'workflow_run_requests')"
                )
            )
        ).all()
    actual: dict[str, set[str]] = {table_name: set() for table_name in EXPECTED_CONSTRAINTS}
    for table_name, constraint_name in rows:
        actual[str(table_name)].add(str(constraint_name))
    assert actual == EXPECTED_CONSTRAINTS


@pytest.mark.asyncio
async def test_composite_checks_flags_counts_and_uniqueness_fail_closed(
    seeded_workflow_version: SeededWorkflowVersion,
) -> None:
    seed = seeded_workflow_version
    first = await _create(seed, key="postgres-constraint-key-0001")
    second = await _create(seed, key="postgres-constraint-key-0002")
    async with seed.database.sessions() as session:
        first_steps = list(
            (
                await session.execute(
                    text(
                        "SELECT id, step_ref, requirement_ref, implementation_id "
                        "FROM step_runs WHERE workflow_run_id = :run_id "
                        "ORDER BY sequence"
                    ),
                    {"run_id": first.run.id},
                )
            ).mappings()
        )
        requests = list(
            (
                await session.execute(
                    text(
                        "SELECT id, idempotency_scope, idempotency_key_hash "
                        "FROM workflow_run_requests ORDER BY created_at, id"
                    )
                )
            ).mappings()
        )
    assert len(first_steps) == 3
    assert len(requests) == 2

    await _assert_rejected(
        seed.database,
        "UPDATE workflow_runs SET status = 'unknown' WHERE id = :id",
        {"id": first.run.id},
        sqlstate="23514",
    )
    await _assert_rejected(
        seed.database,
        "UPDATE workflow_runs SET provider_call_attempted = true WHERE id = :id",
        {"id": first.run.id},
        sqlstate="23514",
    )
    await _assert_rejected(
        seed.database,
        "UPDATE workflow_runs SET completed_steps = 0 WHERE id = :id",
        {"id": first.run.id},
        sqlstate="23514",
    )
    await _assert_rejected(
        seed.database,
        "UPDATE step_runs SET workspace_id = :workspace_id WHERE id = :id",
        {"workspace_id": uuid.uuid4(), "id": first_steps[0]["id"]},
        sqlstate="23503",
    )
    await _assert_rejected(
        seed.database,
        "UPDATE step_runs SET sequence = 0 WHERE id = :id",
        {"id": first_steps[0]["id"]},
        sqlstate="23514",
    )
    await _assert_rejected(
        seed.database,
        "UPDATE step_runs SET step_ref = :step_ref WHERE id = :id",
        {"step_ref": first_steps[0]["step_ref"], "id": first_steps[1]["id"]},
        sqlstate="23505",
    )
    await _assert_rejected(
        seed.database,
        "UPDATE step_runs SET requirement_ref = :requirement_ref, "
        "implementation_id = :implementation_id WHERE id = :id",
        {
            "requirement_ref": first_steps[0]["requirement_ref"],
            "implementation_id": first_steps[0]["implementation_id"],
            "id": first_steps[1]["id"],
        },
        sqlstate="23505",
    )
    await _assert_rejected(
        seed.database,
        "UPDATE workflow_run_requests SET response_status = 199 WHERE id = :id",
        {"id": requests[0]["id"]},
        sqlstate="23514",
    )
    await _assert_rejected(
        seed.database,
        "UPDATE workflow_run_requests SET idempotency_key_hash = :key_hash WHERE id = :id",
        {"key_hash": requests[0]["idempotency_key_hash"], "id": requests[1]["id"]},
        sqlstate="23505",
    )
    await _assert_rejected(
        seed.database,
        "UPDATE workflow_run_requests SET project_id = :project_id WHERE id = :id",
        {"project_id": uuid.uuid4(), "id": requests[1]["id"]},
        sqlstate="23503",
    )
    assert second.run.id != first.run.id


@pytest.mark.asyncio
async def test_step_and_request_rows_remain_owned_by_created_runs(
    seeded_workflow_version: SeededWorkflowVersion,
) -> None:
    seed = seeded_workflow_version
    response = await _create(seed, key="postgres-owner-key-0001")
    async with seed.database.sessions() as session:
        steps = list(
            (
                await session.execute(
                    text("SELECT * FROM step_runs WHERE workflow_run_id = :run_id"),
                    {"run_id": response.run.id},
                )
            ).mappings()
        )
        request = (
            (
                await session.execute(
                    text("SELECT * FROM workflow_run_requests WHERE workflow_run_id = :run_id"),
                    {"run_id": response.run.id},
                )
            )
            .mappings()
            .one()
        )
    assert len(steps) == 3
    assert all(item["workspace_id"] == seed.workspace_id for item in steps)
    assert all(item["project_id"] == seed.project_id for item in steps)
    assert request["workspace_id"] == seed.workspace_id
    assert request["project_id"] == seed.project_id
    assert request["workflow_run_id"] == response.run.id
