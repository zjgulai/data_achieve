from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError

from data_intelligence_hub.models.workflow_executor import (
    WorkflowExecutionDispatchRecord,
    WorkflowExecutionEventRecord,
    WorkflowExecutionLeaseRecord,
)
from data_intelligence_hub.repositories.workflow_executor import (
    get_workflow_execution_dispatch_by_key,
    workflow_execution_lease_lock_statement,
)

NOW = datetime(2026, 7, 28, 16, 0, tzinfo=UTC)
DIGEST_A = "sha256:" + "a" * 64


def _lease(seed: Any, *, worker_id: str) -> WorkflowExecutionLeaseRecord:
    return WorkflowExecutionLeaseRecord(
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workflow_run_id=seed.run_id,
        workflow_step_run_id=seed.step_id,
        attempt_generation=0,
        dispatch_id=seed.dispatch_id,
        worker_id=worker_id,
        fencing_token=1,
        version=1,
        claimed_at=NOW,
        heartbeat_at=NOW,
        expires_at=NOW + timedelta(minutes=1),
        state="active",
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.asyncio
async def test_concurrent_claim_has_one_lease_head_winner(seeded_executor: Any) -> None:
    start = asyncio.Event()

    async def contender(worker_id: str) -> str | IntegrityError:
        await start.wait()
        try:
            async with seeded_executor.database.sessions.begin() as session:
                session.add(_lease(seeded_executor, worker_id=worker_id))
            return worker_id
        except IntegrityError as error:
            return error

    tasks = [
        asyncio.create_task(contender("worker.f2b.a")),
        asyncio.create_task(contender("worker.f2b.b")),
    ]
    start.set()
    results = await asyncio.gather(*tasks)
    assert sum(isinstance(item, str) for item in results) == 1
    assert sum(isinstance(item, IntegrityError) for item in results) == 1
    async with seeded_executor.database.sessions() as session:
        count = await session.scalar(select(func.count()).select_from(WorkflowExecutionLeaseRecord))
    assert count == 1


@pytest.mark.asyncio
async def test_takeover_advances_fence_and_stale_worker_update_loses(
    seeded_executor: Any,
) -> None:
    async with seeded_executor.database.sessions.begin() as session:
        session.add(_lease(seeded_executor, worker_id="worker.f2b.original"))

    taken_over_at = NOW + timedelta(minutes=2)
    async with seeded_executor.database.sessions.begin() as session:
        locked = (
            await session.execute(
                workflow_execution_lease_lock_statement(
                    workspace_id=seeded_executor.workspace_id,
                    project_id=seeded_executor.project_id,
                    dispatch_id=seeded_executor.dispatch_id,
                )
            )
        ).scalar_one()
        assert locked.fencing_token == 1
        assert locked.expires_at <= taken_over_at
        locked.worker_id = "worker.f2b.takeover"
        locked.fencing_token = 2
        locked.version = 1
        locked.claimed_at = taken_over_at
        locked.heartbeat_at = taken_over_at
        locked.expires_at = taken_over_at + timedelta(minutes=1)

    async with seeded_executor.database.sessions.begin() as session:
        stale = await session.execute(
            update(WorkflowExecutionLeaseRecord)
            .where(
                WorkflowExecutionLeaseRecord.dispatch_id == seeded_executor.dispatch_id,
                WorkflowExecutionLeaseRecord.fencing_token == 1,
                WorkflowExecutionLeaseRecord.version == 1,
            )
            .values(heartbeat_at=taken_over_at + timedelta(seconds=1), version=2)
        )
        assert stale.rowcount == 0

    async with seeded_executor.database.sessions() as session:
        current = await session.scalar(
            select(WorkflowExecutionLeaseRecord).where(
                WorkflowExecutionLeaseRecord.dispatch_id == seeded_executor.dispatch_id
            )
        )
    assert current is not None
    assert current.worker_id == "worker.f2b.takeover"
    assert current.fencing_token == 2


@pytest.mark.asyncio
async def test_dispatch_replay_is_tenant_scoped_and_failed_event_batch_rolls_back(
    seeded_executor: Any,
) -> None:
    async with seeded_executor.database.sessions() as session:
        replay = await get_workflow_execution_dispatch_by_key(
            session,
            workspace_id=seeded_executor.workspace_id,
            project_id=seeded_executor.project_id,
            dispatch_key=seeded_executor.dispatch_key,
        )
        hidden = await get_workflow_execution_dispatch_by_key(
            session,
            workspace_id=uuid.uuid4(),
            project_id=seeded_executor.project_id,
            dispatch_key=seeded_executor.dispatch_key,
        )
    assert replay is not None and replay.id == seeded_executor.dispatch_id
    assert hidden is None

    event_id = uuid.uuid4()
    with pytest.raises(IntegrityError):
        async with seeded_executor.database.sessions.begin() as session:
            session.add_all(
                [
                    WorkflowExecutionEventRecord(
                        id=event_id,
                        workspace_id=seeded_executor.workspace_id,
                        project_id=seeded_executor.project_id,
                        workflow_run_id=seeded_executor.run_id,
                        workflow_step_run_id=seeded_executor.step_id,
                        attempt_generation=0,
                        dispatch_id=seeded_executor.dispatch_id,
                        sequence=1,
                        event_type="dispatch_created",
                        lease_id=None,
                        fencing_token=None,
                        previous_event_digest=None,
                        event_digest=DIGEST_A,
                        occurred_at=NOW,
                        created_at=NOW,
                    ),
                    WorkflowExecutionEventRecord(
                        workspace_id=seeded_executor.workspace_id,
                        project_id=seeded_executor.project_id,
                        workflow_run_id=seeded_executor.run_id,
                        workflow_step_run_id=seeded_executor.step_id,
                        attempt_generation=0,
                        dispatch_id=seeded_executor.dispatch_id,
                        sequence=1,
                        event_type="dispatch_replayed",
                        lease_id=None,
                        fencing_token=None,
                        previous_event_digest=None,
                        event_digest="sha256:" + "b" * 64,
                        occurred_at=NOW,
                        created_at=NOW,
                    ),
                ]
            )
            await session.flush()
    async with seeded_executor.database.engine.connect() as connection:
        count = await connection.scalar(text("SELECT count(*) FROM workflow_execution_events"))
    assert count == 0
    assert replay is not None and isinstance(replay, WorkflowExecutionDispatchRecord)
