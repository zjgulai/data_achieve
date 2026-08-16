from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError

from data_intelligence_hub.models.workflow_executor import (
    WorkflowCancellationAcknowledgementRecord,
    WorkflowCancellationRequestRecord,
    WorkflowExecutionEventRecord,
    WorkflowExecutionLeaseRecord,
    WorkflowProviderCallAuditRecord,
)

NOW = datetime(2026, 7, 28, 16, 0, tzinfo=UTC)
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64
DIGEST_D = "sha256:" + "d" * 64


async def _seed_lease(seed: Any) -> WorkflowExecutionLeaseRecord:
    lease = WorkflowExecutionLeaseRecord(
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workflow_run_id=seed.run_id,
        workflow_step_run_id=seed.step_id,
        attempt_generation=0,
        dispatch_id=seed.dispatch_id,
        worker_id="worker.f2b.evidence",
        fencing_token=1,
        version=1,
        claimed_at=NOW,
        heartbeat_at=NOW,
        expires_at=NOW + timedelta(minutes=1),
        state="active",
        created_at=NOW,
        updated_at=NOW,
    )
    async with seed.database.sessions.begin() as session:
        session.add(lease)
    return lease


@pytest.mark.asyncio
async def test_provider_call_audit_is_bound_to_hash_chained_events(
    seeded_executor: Any,
) -> None:
    lease = await _seed_lease(seeded_executor)
    async with seeded_executor.database.sessions.begin() as session:
        session.add_all(
            [
                WorkflowExecutionEventRecord(
                    workspace_id=seeded_executor.workspace_id,
                    project_id=seeded_executor.project_id,
                    workflow_run_id=seeded_executor.run_id,
                    workflow_step_run_id=seeded_executor.step_id,
                    attempt_generation=0,
                    dispatch_id=seeded_executor.dispatch_id,
                    sequence=1,
                    event_type="provider_attempting",
                    lease_id=lease.id,
                    fencing_token=1,
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
                    sequence=2,
                    event_type="provider_succeeded",
                    lease_id=lease.id,
                    fencing_token=1,
                    previous_event_digest=DIGEST_A,
                    event_digest=DIGEST_B,
                    occurred_at=NOW + timedelta(seconds=1),
                    created_at=NOW,
                ),
                WorkflowProviderCallAuditRecord(
                    workspace_id=seeded_executor.workspace_id,
                    project_id=seeded_executor.project_id,
                    workflow_run_id=seeded_executor.run_id,
                    workflow_step_run_id=seeded_executor.step_id,
                    attempt_generation=0,
                    dispatch_id=seeded_executor.dispatch_id,
                    lease_id=lease.id,
                    fencing_token=1,
                    provider_id="youtube",
                    operation_id="search",
                    preflight_id=DIGEST_C,
                    policy_digest=DIGEST_D,
                    side_effect_key=DIGEST_B,
                    environment="test",
                    attempt_ordinal=1,
                    transport_state="succeeded",
                    outcome_code="provider_succeeded",
                    started_at=NOW,
                    finished_at=NOW + timedelta(seconds=1),
                    created_at=NOW,
                ),
            ]
        )

    with pytest.raises(IntegrityError):
        async with seeded_executor.database.sessions.begin() as session:
            session.add(
                WorkflowExecutionEventRecord(
                    workspace_id=seeded_executor.workspace_id,
                    project_id=seeded_executor.project_id,
                    workflow_run_id=seeded_executor.run_id,
                    workflow_step_run_id=seeded_executor.step_id,
                    attempt_generation=0,
                    dispatch_id=seeded_executor.dispatch_id,
                    sequence=3,
                    event_type="terminal_committed",
                    lease_id=lease.id,
                    fencing_token=1,
                    previous_event_digest="sha256:" + "f" * 64,
                    event_digest=DIGEST_C,
                    occurred_at=NOW + timedelta(seconds=2),
                    created_at=NOW,
                )
            )
            await session.flush()


@pytest.mark.asyncio
async def test_cancellation_acknowledgement_is_exactly_once(seeded_executor: Any) -> None:
    lease = await _seed_lease(seeded_executor)
    request = WorkflowCancellationRequestRecord(
        workspace_id=seeded_executor.workspace_id,
        project_id=seeded_executor.project_id,
        workflow_run_id=seeded_executor.run_id,
        workflow_step_run_id=seeded_executor.step_id,
        attempt_generation=0,
        dispatch_id=seeded_executor.dispatch_id,
        requested_by_user_id=seeded_executor.owner_id,
        request_key=DIGEST_C,
        reason_code="owner_cancelled",
        requested_at=NOW,
        created_at=NOW,
    )
    async with seeded_executor.database.sessions.begin() as session:
        session.add(request)
    acknowledgement = WorkflowCancellationAcknowledgementRecord(
        workspace_id=seeded_executor.workspace_id,
        project_id=seeded_executor.project_id,
        workflow_run_id=seeded_executor.run_id,
        workflow_step_run_id=seeded_executor.step_id,
        attempt_generation=0,
        request_id=request.id,
        dispatch_id=seeded_executor.dispatch_id,
        lease_id=lease.id,
        fencing_token=1,
        safe_point="before.provider.call",
        outcome="cancelled_before_effect",
        acknowledged_at=NOW + timedelta(seconds=1),
        created_at=NOW,
    )
    async with seeded_executor.database.sessions.begin() as session:
        session.add(acknowledgement)

    with pytest.raises(IntegrityError):
        async with seeded_executor.database.sessions.begin() as session:
            session.add(
                WorkflowCancellationAcknowledgementRecord(
                    id=uuid.uuid4(),
                    workspace_id=seeded_executor.workspace_id,
                    project_id=seeded_executor.project_id,
                    workflow_run_id=seeded_executor.run_id,
                    workflow_step_run_id=seeded_executor.step_id,
                    attempt_generation=0,
                    request_id=request.id,
                    dispatch_id=seeded_executor.dispatch_id,
                    lease_id=lease.id,
                    fencing_token=1,
                    safe_point="after.provider.call",
                    outcome="cancelled_after_current_effect",
                    acknowledged_at=NOW + timedelta(seconds=2),
                    created_at=NOW,
                )
            )
            await session.flush()
