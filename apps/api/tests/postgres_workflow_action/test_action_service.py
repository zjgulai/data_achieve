from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import func, select

from data_intelligence_hub.models.workflow_action import (
    WorkflowRunActionApprovalConsumption,
    WorkflowRunActionAuditEvent,
    WorkflowRunActionReceiptRecord,
    WorkflowRunActionRequestRecord,
)
from data_intelligence_hub.models.workflow_execution import StepRun, WorkflowRun
from data_intelligence_hub.services.workflow_execution import action_command
from data_intelligence_hub.services.workflow_execution.action_command import (
    execute_workflow_run_action,
    verify_workflow_action_audit_chain,
)


async def _submit(command: Any, request_id: str) -> Any:
    seed = command.seed
    async with seed.database.sessions() as session:
        return await execute_workflow_run_action(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workflow_run_id=seed.run_id,
            actor_user_id=seed.owner_id,
            idempotency_key=command.idempotency_key,
            http_request_id=request_id,
            request=command.request,
            evidence=command.evidence,
            evaluated_at=datetime(2026, 7, 28, 12, 0, tzinfo=UTC),
        )


@pytest.mark.asyncio
async def test_retry_exact_replay_tenant_scope_and_audit_chain(retry_command: Any) -> None:
    first = await _submit(retry_command, "req-phase-e-action-first")
    replay = await _submit(retry_command, "req-phase-e-action-replay")
    seed = retry_command.seed

    assert first.id == replay.id
    assert first.database_write is True and first.idempotent_replay is False
    assert replay.database_write is False and replay.idempotent_replay is True
    assert first.before_action_context_version == 1
    assert first.after_action_context_version == 2
    assert first.before_run_status == "held"
    assert first.after_run_status == "ready"

    async with seed.database.sessions() as session:
        run = await session.get(WorkflowRun, seed.run_id)
        step = await session.get(StepRun, seed.step_id)
        counts = {
            model: await session.scalar(select(func.count()).select_from(model))
            for model in (
                WorkflowRunActionRequestRecord,
                WorkflowRunActionReceiptRecord,
                WorkflowRunActionApprovalConsumption,
            )
        }
        events = tuple(
            (
                await session.scalars(
                    select(WorkflowRunActionAuditEvent).order_by(
                        WorkflowRunActionAuditEvent.event_number
                    )
                )
            ).all()
        )
        await verify_workflow_action_audit_chain(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workflow_run_id=seed.run_id,
        )

    assert run is not None and run.status == "ready"
    assert step is not None and step.status == "pending" and step.retry_generation == 1
    assert all(value == 1 for value in counts.values())
    assert [event.event_number for event in events] == [1, 2]
    assert events[0].previous_event_digest is None
    assert events[1].previous_event_digest == events[0].event_digest
    assert all(not event.provider_call_attempted for event in events)
    assert all(not event.credential_read_attempted for event in events)
    assert all(not event.execution_started for event in events)
    assert all(not event.production_write_allowed for event in events)


@pytest.mark.asyncio
async def test_concurrent_exact_duplicate_persists_one_receipt(retry_command: Any) -> None:
    start = asyncio.Event()

    async def contender(request_id: str) -> Any:
        await start.wait()
        return await _submit(retry_command, request_id)

    tasks = (
        asyncio.create_task(contender("req-phase-e-concurrent-a")),
        asyncio.create_task(contender("req-phase-e-concurrent-b")),
    )
    start.set()
    first, second = await asyncio.gather(*tasks)

    assert first.id == second.id
    assert sorted((first.database_write, second.database_write)) == [False, True]
    assert sorted((first.idempotent_replay, second.idempotent_replay)) == [False, True]
    seed = retry_command.seed
    async with seed.database.sessions() as session:
        assert (
            await session.scalar(select(func.count()).select_from(WorkflowRunActionRequestRecord))
            == 1
        )
        assert (
            await session.scalar(select(func.count()).select_from(WorkflowRunActionReceiptRecord))
            == 1
        )


@pytest.mark.asyncio
async def test_injected_audit_failure_rolls_back_action_atomically(
    retry_command: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_audit(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise RuntimeError("injected_phase_e_audit_failure")

    monkeypatch.setattr(action_command, "_append_audit_event", fail_audit)
    with pytest.raises(RuntimeError, match="injected_phase_e_audit_failure"):
        await _submit(retry_command, "req-phase-e-rollback")

    seed = retry_command.seed
    async with seed.database.sessions() as session:
        run = await session.get(WorkflowRun, seed.run_id)
        step = await session.get(StepRun, seed.step_id)
        request_count = await session.scalar(
            select(func.count()).select_from(WorkflowRunActionRequestRecord)
        )
        receipt_count = await session.scalar(
            select(func.count()).select_from(WorkflowRunActionReceiptRecord)
        )
        consumption_count = await session.scalar(
            select(func.count()).select_from(WorkflowRunActionApprovalConsumption)
        )

    assert run is not None and run.status == "held"
    assert step is not None and step.status == "failed" and step.retry_generation == 0
    assert request_count == 0
    assert receipt_count == 0
    assert consumption_count == 0
