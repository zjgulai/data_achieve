from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

EXPECTED_CONSTRAINTS = {
    "uq_workflow_execution_dispatches_semantic_key",
    "ck_workflow_execution_dispatches_local_boundaries",
    "uq_workflow_execution_leases_dispatch_head",
    "ck_workflow_execution_leases_fencing_token",
    "uq_workflow_execution_events_dispatch_sequence",
    "fk_workflow_execution_events_previous_digest",
    "ck_workflow_credential_resolution_permits_single_terminal_state",
    "uq_workflow_provider_call_permits_authority",
    "uq_workflow_provider_call_audits_dispatch_ordinal",
    "uq_workflow_cancellation_requests_semantic_key",
    "uq_workflow_cancellation_acknowledgements_request",
}


def _sqlstate(error: DBAPIError) -> str | None:
    origin = error.orig
    cause = None if origin is None else origin.__cause__
    for candidate in (origin, cause):
        value = getattr(candidate, "sqlstate", None) or getattr(candidate, "pgcode", None)
        if isinstance(value, str):
            return value
    return None


@pytest.mark.asyncio
async def test_catalog_contains_executor_coordination_constraints(
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
async def test_tenant_and_fail_closed_dispatch_constraints_reject_drift(
    seeded_executor: Any,
) -> None:
    with pytest.raises(DBAPIError) as tenant_error:
        async with seeded_executor.database.engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE workflow_execution_dispatches SET project_id = :project_id "
                    "WHERE id = :dispatch_id"
                ),
                {
                    "project_id": uuid.uuid4(),
                    "dispatch_id": seeded_executor.dispatch_id,
                },
            )
    assert _sqlstate(tenant_error.value) == "23503"

    with pytest.raises(DBAPIError) as boundary_error:
        async with seeded_executor.database.engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE workflow_execution_dispatches SET network_call = true "
                    "WHERE id = :dispatch_id"
                ),
                {"dispatch_id": seeded_executor.dispatch_id},
            )
    assert _sqlstate(boundary_error.value) == "23514"
