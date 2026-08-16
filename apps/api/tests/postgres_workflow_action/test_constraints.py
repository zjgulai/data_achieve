from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from data_intelligence_hub.services.workflow_execution.action_command import (
    execute_workflow_run_action,
)

EXPECTED_CONSTRAINTS = {
    "ck_step_runs_retry_generation",
    "ck_step_run_attempts_retry_generation",
    "uq_workflow_run_action_contexts_run",
    "fk_workflow_run_action_contexts_run_tenant",
    "uq_workflow_run_action_approvals_actor_key",
    "fk_workflow_run_action_requests_approval_tenant",
    "ck_workflow_run_action_requests_context_version",
    "uq_workflow_run_action_receipts_request",
    "ck_workflow_run_action_receipts_outcome",
    "ck_workflow_run_action_receipts_write_replay",
    "uq_workflow_run_action_consumptions_approval",
    "uq_workflow_run_action_consumptions_request",
    "uq_workflow_run_action_audit_events_run_number",
    "fk_workflow_run_action_audit_events_predecessor_tenant",
}


def _sqlstate(error: DBAPIError) -> str | None:
    origin = error.orig
    if origin is None:
        return None
    cause = origin.__cause__
    for candidate in (origin, cause):
        value = getattr(candidate, "sqlstate", None) or getattr(candidate, "pgcode", None)
        if isinstance(value, str):
            return value
    return None


async def _assert_rejected(
    database: Any,
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
async def test_catalog_contains_workflow_action_postgresql_constraints(
    postgres_database: Any,
) -> None:
    async with postgres_database.engine.connect() as connection:
        actual = {
            str(value)
            for value in (
                await connection.scalars(
                    text(
                        "SELECT conname FROM pg_catalog.pg_constraint "
                        "JOIN pg_catalog.pg_namespace ON pg_namespace.oid = connamespace "
                        "WHERE pg_namespace.nspname = 'public'"
                    )
                )
            )
        }
    assert actual >= EXPECTED_CONSTRAINTS


@pytest.mark.asyncio
async def test_tenant_context_receipt_consumption_and_audit_constraints_fail_closed(
    retry_command: Any,
) -> None:
    seed = retry_command.seed
    async with seed.database.sessions() as session:
        receipt = await execute_workflow_run_action(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workflow_run_id=seed.run_id,
            actor_user_id=seed.owner_id,
            idempotency_key=retry_command.idempotency_key,
            http_request_id="req-phase-e-constraint-seed",
            request=retry_command.request,
            evidence=retry_command.evidence,
            evaluated_at=datetime(2026, 7, 28, 12, 0, tzinfo=UTC),
        )

    await _assert_rejected(
        seed.database,
        "UPDATE workflow_run_action_contexts SET action_context_version = 0 "
        "WHERE workflow_run_id = :run_id",
        {"run_id": seed.run_id},
        sqlstate="23514",
    )
    await _assert_rejected(
        seed.database,
        "UPDATE workflow_run_action_requests SET project_id = :project_id "
        "WHERE workflow_run_id = :run_id",
        {"project_id": uuid.uuid4(), "run_id": seed.run_id},
        sqlstate="23503",
    )
    await _assert_rejected(
        seed.database,
        "UPDATE workflow_run_action_receipts SET outcome = 'rejected_conflict' "
        "WHERE id = :receipt_id",
        {"receipt_id": receipt.id},
        sqlstate="23514",
    )
    await _assert_rejected(
        seed.database,
        "UPDATE workflow_run_action_receipts SET database_write = false WHERE id = :receipt_id",
        {"receipt_id": receipt.id},
        sqlstate="23514",
    )
    await _assert_rejected(
        seed.database,
        "INSERT INTO workflow_run_action_approval_consumptions "
        "(id, workspace_id, project_id, workflow_run_id, approval_receipt_id, "
        "action_request_id, consumed_at) "
        "SELECT :id, workspace_id, project_id, workflow_run_id, "
        "approval_receipt_id, action_request_id, consumed_at "
        "FROM workflow_run_action_approval_consumptions LIMIT 1",
        {"id": uuid.uuid4()},
        sqlstate="23505",
    )
    await _assert_rejected(
        seed.database,
        "UPDATE workflow_run_action_audit_events SET previous_event_digest = :digest "
        "WHERE workflow_run_id = :run_id AND event_number = 2",
        {"digest": "sha256:" + "f" * 64, "run_id": seed.run_id},
        sqlstate="23503",
    )
