from __future__ import annotations

import asyncio
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from data_intelligence_hub.models.workflow_execution import (
    StepRun,
    WorkflowRun,
    WorkflowRunRequest,
)
from data_intelligence_hub.repositories.workflow_execution import (
    add_step_runs as repository_add_step_runs,
)
from data_intelligence_hub.schemas.workflow_execution import (
    WorkflowFixtureRunCreateRequest,
    WorkflowFixtureRunCreateResponse,
)
from data_intelligence_hub.services.workflow_execution import execution
from data_intelligence_hub.services.workflow_execution.execution import (
    WorkflowExecutionIdempotencyConflictError,
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


def _payload(
    seed: SeededWorkflowVersion,
    *,
    fingerprint: str | None = None,
) -> WorkflowFixtureRunCreateRequest:
    return WorkflowFixtureRunCreateRequest(
        expected_preview_fingerprint=fingerprint or seed.preview_fingerprint,
        fixture_profile_id="fixture-primary-v1",
    )


async def _run(
    seed: SeededWorkflowVersion,
    *,
    key: str,
    payload: WorkflowFixtureRunCreateRequest | None = None,
) -> WorkflowFixtureRunCreateResponse:
    async with seed.database.sessions() as session:
        return await create_workflow_fixture_run(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workflow_plan_id=seed.plan_id,
            workflow_version_id=seed.version_id,
            created_by_user_id=seed.user_id,
            payload=payload or _payload(seed),
            idempotency_key=key,
            request_id=f"postgres-concurrency-{key}",
        )


async def _count(database: PostgresDatabase, model: type[object]) -> int:
    async with database.sessions() as session:
        result = await session.execute(select(func.count()).select_from(model))
        return int(result.scalar_one())


@pytest.mark.asyncio
async def test_concurrent_same_key_same_request_has_one_run_and_one_replay(
    seeded_workflow_version: SeededWorkflowVersion,
) -> None:
    seed = seeded_workflow_version
    start = asyncio.Event()

    async def contender() -> WorkflowFixtureRunCreateResponse:
        await start.wait()
        return await _run(seed, key="postgres-concurrent-same-key-0001")

    tasks = [asyncio.create_task(contender()) for _ in range(2)]
    start.set()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    responses = [item for item in results if isinstance(item, WorkflowFixtureRunCreateResponse)]

    assert len(responses) == 2, results
    assert sum(item.database_write for item in responses) == 1
    assert sum(item.idempotent_replay for item in responses) == 1
    assert len({item.run.id for item in responses}) == 1
    assert await _count(seed.database, WorkflowRun) == 1
    assert await _count(seed.database, StepRun) == 3
    assert await _count(seed.database, WorkflowRunRequest) == 1


@pytest.mark.asyncio
async def test_same_key_different_request_delayed_contender_gets_stable_conflict(
    seeded_workflow_version: SeededWorkflowVersion,
) -> None:
    seed = seeded_workflow_version
    winner_finished = asyncio.Event()

    async def winner() -> WorkflowFixtureRunCreateResponse:
        try:
            return await _run(seed, key="postgres-concurrent-conflict-key-0001")
        finally:
            winner_finished.set()

    async def delayed_contender() -> WorkflowFixtureRunCreateResponse:
        await winner_finished.wait()
        return await _run(
            seed,
            key="postgres-concurrent-conflict-key-0001",
            payload=_payload(seed, fingerprint="sha256:" + "f" * 64),
        )

    results = await asyncio.gather(
        asyncio.create_task(winner()),
        asyncio.create_task(delayed_contender()),
        return_exceptions=True,
    )
    responses = [item for item in results if isinstance(item, WorkflowFixtureRunCreateResponse)]
    conflicts = [
        item for item in results if isinstance(item, WorkflowExecutionIdempotencyConflictError)
    ]

    assert len(responses) == 1, results
    assert len(conflicts) == 1, results
    assert str(conflicts[0]) == "idempotency_conflict"
    assert await _count(seed.database, WorkflowRun) == 1
    assert await _count(seed.database, StepRun) == 3
    assert await _count(seed.database, WorkflowRunRequest) == 1


@pytest.mark.asyncio
async def test_injected_step_failure_rolls_back_run_steps_and_request(
    seeded_workflow_version: SeededWorkflowVersion,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = seeded_workflow_version
    flush_count = 0

    async def fail_on_second_step(
        session: AsyncSession,
        steps: Sequence[StepRun],
    ) -> tuple[StepRun, ...]:
        nonlocal flush_count
        persisted = await repository_add_step_runs(session, steps)
        flush_count += 1
        if flush_count == 2:
            raise RuntimeError("injected_postgres_step_failure")
        return persisted

    monkeypatch.setattr(execution, "add_step_runs", fail_on_second_step)
    with pytest.raises(RuntimeError, match="injected_postgres_step_failure"):
        await _run(seed, key="postgres-rollback-key-0001")

    assert flush_count == 2
    assert await _count(seed.database, WorkflowRun) == 0
    assert await _count(seed.database, StepRun) == 0
    assert await _count(seed.database, WorkflowRunRequest) == 0
