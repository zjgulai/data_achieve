from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workflow_execution import StepRun, WorkflowRun
from data_intelligence_hub.models.workflow_executor import (
    WorkflowCancellationAcknowledgementRecord,
    WorkflowCancellationRequestRecord,
    WorkflowCredentialResolutionPermitRecord,
    WorkflowExecutionDispatchRecord,
    WorkflowExecutionEventRecord,
    WorkflowExecutionLeaseRecord,
    WorkflowProviderCallAuditRecord,
    WorkflowProviderCallPermitRecord,
)
from data_intelligence_hub.models.workflow_plan import WorkflowPlan, WorkflowVersion
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.workflow_executor import (
    add_workflow_cancellation_acknowledgement,
    add_workflow_cancellation_request,
    add_workflow_credential_resolution_permit,
    add_workflow_execution_dispatch,
    add_workflow_execution_event,
    add_workflow_execution_lease,
    add_workflow_provider_call_audit,
    add_workflow_provider_call_permit,
    consume_workflow_credential_resolution_permit,
    consume_workflow_provider_call_permit,
    get_workflow_cancellation_acknowledgement,
    get_workflow_cancellation_request_by_key,
    get_workflow_execution_dispatch_by_key,
    list_workflow_cancellation_acknowledgements_for_run,
    list_workflow_cancellation_requests_for_run,
    list_workflow_execution_dispatches_for_run,
    list_workflow_execution_events,
    list_workflow_execution_events_for_run,
    list_workflow_execution_leases_for_run,
    list_workflow_provider_call_audits,
    list_workflow_provider_call_audits_for_run,
    workflow_execution_lease_lock_statement,
)
from data_intelligence_hub.services.workflow_execution.executor_evidence import (
    load_workflow_executor_evidence,
)

NOW = datetime(2026, 7, 28, 8, 0, tzinfo=UTC)
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64
DIGEST_D = "sha256:" + "d" * 64


@pytest_asyncio.fixture()
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as value:
        yield value
    await engine.dispose()


async def _seed_step(session: AsyncSession) -> tuple[uuid.UUID, ...]:
    user_id, workspace_id, project_id, plan_id, version_id, run_id, step_id = (
        uuid.uuid4() for _ in range(7)
    )
    session.add_all(
        [
            User(
                id=user_id,
                email=f"{user_id}@example.com",
                password_hash="fixture-only",
                name="Phase F Owner",
                status="active",
            ),
            Workspace(
                id=workspace_id,
                name="Phase F",
                slug=f"phase-f-{workspace_id}",
                owner_id=user_id,
            ),
            Project(
                id=project_id,
                workspace_id=workspace_id,
                owner_id=user_id,
                name="Phase F",
                description=None,
                domain="social",
                status="active",
            ),
            WorkflowPlan(
                id=plan_id,
                workspace_id=workspace_id,
                project_id=project_id,
                created_by_user_id=user_id,
                name="Phase F",
                flow_mode="periodic_monitoring",
                status="previewed",
                current_version_id=None,
                created_at=NOW,
                updated_at=NOW,
            ),
            WorkflowVersion(
                id=version_id,
                workspace_id=workspace_id,
                project_id=project_id,
                workflow_plan_id=plan_id,
                created_by_user_id=user_id,
                version_number=1,
                planning_status="resolved",
                planner_contract_version="workflow_planner.v1",
                catalog_snapshot_id=DIGEST_A,
                policy_version="policy.v1",
                mode_template_version="periodic.v1",
                query_versions={"youtube": "youtube.v1"},
                fingerprint_payload={},
                normalized_input={},
                plan_payload={},
                preview_fingerprint=DIGEST_B,
                created_at=NOW,
            ),
            WorkflowRun(
                id=run_id,
                workspace_id=workspace_id,
                project_id=project_id,
                workflow_plan_id=plan_id,
                workflow_version_id=version_id,
                created_by_user_id=user_id,
                execution_contract_version="workflow_execution_fixture.v1",
                execution_mode="fixture",
                status="running",
                planner_contract_version="workflow_planner.v1",
                preview_fingerprint=DIGEST_B,
                catalog_snapshot_id=DIGEST_A,
                policy_version="policy.v1",
                mode_template_version="periodic.v1",
                query_versions={"youtube": "youtube.v1"},
                fixture_profile_id="fixture-primary-v1",
                fixture_profile_hash=DIGEST_C,
                total_steps=1,
                completed_steps=0,
                records_count=0,
                status_reason_code=None,
                impact_code=None,
                missing_fields=[],
                recovery_action_codes=[],
                started_at=NOW,
                finished_at=None,
                created_at=NOW,
            ),
            StepRun(
                id=step_id,
                workflow_run_id=run_id,
                workspace_id=workspace_id,
                project_id=project_id,
                step_ref="collect.youtube.v1",
                requirement_ref="youtube.search.v1",
                sequence=1,
                retry_generation=0,
                platform="youtube",
                resource_type="video",
                operation="search",
                assertion_id="youtube.search.v1",
                implementation_id="fixture.youtube.search.v1",
                route_plan_snapshot={},
                evidence_refs=[],
                fixture_case_id=None,
                fixture_content_hash=None,
                input_digest=DIGEST_A,
                output_digest=None,
                idempotency_scope=f"step.v1:{run_id}:{step_id}",
                idempotency_key_hash=DIGEST_B,
                status="pending",
                records_count=0,
                started_at=NOW,
                finished_at=None,
                created_at=NOW,
            ),
        ]
    )
    await session.commit()
    return user_id, workspace_id, project_id, plan_id, version_id, run_id, step_id


def _dispatch(
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    version_id: uuid.UUID,
    run_id: uuid.UUID,
    step_id: uuid.UUID,
) -> WorkflowExecutionDispatchRecord:
    return WorkflowExecutionDispatchRecord(
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_plan_id=plan_id,
        workflow_version_id=version_id,
        workflow_run_id=run_id,
        workflow_step_run_id=step_id,
        attempt_generation=0,
        source_action_request_id=None,
        source_action_receipt_id=None,
        workflow_version_digest=DIGEST_A,
        execution_policy_digest=DIGEST_B,
        dispatch_key=DIGEST_C,
        provider_side_effect_key=DIGEST_D,
        state="claimable",
        created_at=NOW,
    )


def test_lease_lock_is_only_postgresql_shape_not_sqlite_concurrency_evidence() -> None:
    statement = workflow_execution_lease_lock_statement(
        workspace_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        dispatch_id=uuid.uuid4(),
    )
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),  # type: ignore[no-untyped-call]
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "workflow_execution_leases.workspace_id" in sql
    assert "workflow_execution_leases.project_id" in sql
    assert "workflow_execution_leases.dispatch_id" in sql
    assert "FOR UPDATE" in sql
    assert statement.get_execution_options()["populate_existing"] is True


@pytest.mark.asyncio
async def test_executor_evidence_is_tenant_scoped_replayable_and_single_use(
    session: AsyncSession,
) -> None:
    user_id, workspace_id, project_id, plan_id, version_id, run_id, step_id = await _seed_step(
        session
    )
    dispatch = await add_workflow_execution_dispatch(
        session,
        _dispatch(
            workspace_id=workspace_id,
            project_id=project_id,
            plan_id=plan_id,
            version_id=version_id,
            run_id=run_id,
            step_id=step_id,
        ),
    )
    lease = await add_workflow_execution_lease(
        session,
        WorkflowExecutionLeaseRecord(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            workflow_step_run_id=step_id,
            attempt_generation=0,
            dispatch_id=dispatch.id,
            worker_id="worker.local.f1",
            fencing_token=1,
            version=1,
            claimed_at=NOW,
            heartbeat_at=NOW,
            expires_at=NOW + timedelta(minutes=1),
            state="active",
            created_at=NOW,
            updated_at=NOW,
        ),
    )
    await add_workflow_execution_event(
        session,
        WorkflowExecutionEventRecord(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            workflow_step_run_id=step_id,
            attempt_generation=0,
            dispatch_id=dispatch.id,
            sequence=1,
            event_type="dispatch_created",
            lease_id=None,
            fencing_token=None,
            previous_event_digest=None,
            event_digest=DIGEST_A,
            occurred_at=NOW,
            created_at=NOW,
        ),
    )
    credential_permit = await add_workflow_credential_resolution_permit(
        session,
        WorkflowCredentialResolutionPermitRecord(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            workflow_step_run_id=step_id,
            attempt_generation=0,
            dispatch_id=dispatch.id,
            provider_id="youtube",
            operation_id="search",
            environment="local",
            purpose="provider.search",
            credential_reference_fingerprint=DIGEST_B,
            issued_at=NOW,
            expires_at=NOW + timedelta(minutes=5),
            created_at=NOW,
        ),
    )
    provider_permit = await add_workflow_provider_call_permit(
        session,
        WorkflowProviderCallPermitRecord(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            workflow_step_run_id=step_id,
            attempt_generation=0,
            dispatch_id=dispatch.id,
            provider_id="youtube",
            operation_id="search",
            environment="local",
            preflight_id=DIGEST_A,
            policy_digest=DIGEST_B,
            side_effect_key=DIGEST_D,
            max_cost_usd=Decimal("0"),
            max_quota_units=0,
            issued_at=NOW,
            expires_at=NOW + timedelta(minutes=5),
            created_at=NOW,
        ),
    )
    consumed_credential = await consume_workflow_credential_resolution_permit(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        permit_id=credential_permit.id,
        consumed_at=NOW + timedelta(seconds=1),
    )
    consumed_provider = await consume_workflow_provider_call_permit(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        permit_id=provider_permit.id,
        consumed_at=NOW + timedelta(seconds=1),
    )
    assert consumed_credential is not None
    assert consumed_provider is not None
    assert (
        await consume_workflow_credential_resolution_permit(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            permit_id=credential_permit.id,
            consumed_at=NOW + timedelta(seconds=2),
        )
        is None
    )
    audit = await add_workflow_provider_call_audit(
        session,
        WorkflowProviderCallAuditRecord(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            workflow_step_run_id=step_id,
            attempt_generation=0,
            dispatch_id=dispatch.id,
            lease_id=lease.id,
            fencing_token=1,
            provider_id="youtube",
            operation_id="search",
            preflight_id=DIGEST_A,
            policy_digest=DIGEST_B,
            side_effect_key=DIGEST_D,
            environment="local",
            attempt_ordinal=1,
            transport_state="not_attempted",
            outcome_code=None,
            started_at=None,
            finished_at=None,
            created_at=NOW,
        ),
    )
    request = await add_workflow_cancellation_request(
        session,
        WorkflowCancellationRequestRecord(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            workflow_step_run_id=step_id,
            attempt_generation=0,
            dispatch_id=dispatch.id,
            requested_by_user_id=user_id,
            request_key=DIGEST_C,
            reason_code="owner_cancelled",
            requested_at=NOW + timedelta(seconds=2),
            created_at=NOW,
        ),
    )
    acknowledgement = await add_workflow_cancellation_acknowledgement(
        session,
        WorkflowCancellationAcknowledgementRecord(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            workflow_step_run_id=step_id,
            attempt_generation=0,
            request_id=request.id,
            dispatch_id=dispatch.id,
            lease_id=lease.id,
            fencing_token=1,
            safe_point="before.provider.call",
            outcome="cancelled_before_effect",
            acknowledged_at=NOW + timedelta(seconds=3),
            created_at=NOW,
        ),
    )
    await session.commit()

    replay = await get_workflow_execution_dispatch_by_key(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        dispatch_key=dispatch.dispatch_key,
    )
    hidden = await get_workflow_execution_dispatch_by_key(
        session,
        workspace_id=uuid.uuid4(),
        project_id=project_id,
        dispatch_key=dispatch.dispatch_key,
    )
    cancellation_replay = await get_workflow_cancellation_request_by_key(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        request_key=request.request_key,
    )
    acknowledgement_replay = await get_workflow_cancellation_acknowledgement(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        request_id=request.id,
    )
    assert replay is not None and replay.id == dispatch.id
    assert hidden is None
    assert [
        item.event_digest
        for item in await list_workflow_execution_events(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            dispatch_id=dispatch.id,
        )
    ] == [DIGEST_A]
    assert [
        item.id
        for item in await list_workflow_provider_call_audits(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            dispatch_id=dispatch.id,
        )
    ] == [audit.id]
    assert cancellation_replay is not None and cancellation_replay.id == request.id
    assert acknowledgement_replay is not None
    assert acknowledgement_replay.id == acknowledgement.id


@pytest.mark.asyncio
async def test_run_evidence_reads_are_tenant_scoped_and_empty_safe(
    session: AsyncSession,
) -> None:
    _, workspace_id, project_id, plan_id, version_id, run_id, step_id = await _seed_step(
        session
    )
    dispatch = await add_workflow_execution_dispatch(
        session,
        _dispatch(
            workspace_id=workspace_id,
            project_id=project_id,
            plan_id=plan_id,
            version_id=version_id,
            run_id=run_id,
            step_id=step_id,
        ),
    )
    await session.commit()

    assert [
        item.id
        for item in await list_workflow_execution_dispatches_for_run(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
        )
    ] == [dispatch.id]
    assert (
        await list_workflow_execution_dispatches_for_run(
            session,
            workspace_id=uuid.uuid4(),
            project_id=project_id,
            workflow_run_id=run_id,
        )
        == ()
    )
    assert (
        await list_workflow_execution_leases_for_run(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
        )
        == ()
    )
    assert (
        await list_workflow_execution_events_for_run(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
        )
        == ()
    )
    assert (
        await list_workflow_provider_call_audits_for_run(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
        )
        == ()
    )
    assert (
        await list_workflow_cancellation_requests_for_run(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
        )
        == ()
    )
    assert (
        await list_workflow_cancellation_acknowledgements_for_run(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
        )
        == ()
    )


@pytest.mark.asyncio
async def test_run_evidence_exposes_only_opaque_permit_ids(
    session: AsyncSession,
) -> None:
    _, workspace_id, project_id, plan_id, version_id, run_id, step_id = await _seed_step(
        session
    )
    dispatch = await add_workflow_execution_dispatch(
        session,
        _dispatch(
            workspace_id=workspace_id,
            project_id=project_id,
            plan_id=plan_id,
            version_id=version_id,
            run_id=run_id,
            step_id=step_id,
        ),
    )
    credential_permit = await add_workflow_credential_resolution_permit(
        session,
        WorkflowCredentialResolutionPermitRecord(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            workflow_step_run_id=step_id,
            attempt_generation=0,
            dispatch_id=dispatch.id,
            provider_id="youtube.fixture",
            operation_id="search",
            environment="local",
            purpose="fixture.search",
            credential_reference_fingerprint=DIGEST_A,
            issued_at=NOW,
            expires_at=NOW + timedelta(minutes=5),
            created_at=NOW,
        ),
    )
    provider_permit = await add_workflow_provider_call_permit(
        session,
        WorkflowProviderCallPermitRecord(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            workflow_step_run_id=step_id,
            attempt_generation=0,
            dispatch_id=dispatch.id,
            provider_id="youtube.fixture",
            operation_id="search",
            environment="local",
            preflight_id=DIGEST_A,
            policy_digest=DIGEST_B,
            side_effect_key=DIGEST_D,
            max_cost_usd=Decimal("0"),
            max_quota_units=0,
            issued_at=NOW,
            expires_at=NOW + timedelta(minutes=5),
            created_at=NOW,
        ),
    )
    await session.commit()

    evidence = await load_workflow_executor_evidence(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
        evaluated_at=NOW,
    )

    assert evidence.dispatches[0].credential_permit_ids == [credential_permit.id]
    assert evidence.dispatches[0].provider_permit_ids == [provider_permit.id]
    assert evidence.credential_read_attempted is False
    assert evidence.provider_call is False
    assert evidence.network_call is False
    assert "fingerprint" not in evidence.model_dump_json()


@pytest.mark.asyncio
async def test_semantic_duplicate_rolls_back_without_partial_event(
    session: AsyncSession,
) -> None:
    _, workspace_id, project_id, plan_id, version_id, run_id, step_id = await _seed_step(session)
    first = await add_workflow_execution_dispatch(
        session,
        _dispatch(
            workspace_id=workspace_id,
            project_id=project_id,
            plan_id=plan_id,
            version_id=version_id,
            run_id=run_id,
            step_id=step_id,
        ),
    )
    await session.commit()
    first_id = first.id

    duplicate = _dispatch(
        workspace_id=workspace_id,
        project_id=project_id,
        plan_id=plan_id,
        version_id=version_id,
        run_id=run_id,
        step_id=step_id,
    )
    session.add_all(
        [
            duplicate,
            WorkflowExecutionEventRecord(
                workspace_id=workspace_id,
                project_id=project_id,
                workflow_run_id=run_id,
                workflow_step_run_id=step_id,
                attempt_generation=0,
                dispatch_id=duplicate.id,
                sequence=1,
                event_type="dispatch_replayed",
                lease_id=None,
                fencing_token=None,
                previous_event_digest=None,
                event_digest=DIGEST_B,
                occurred_at=NOW,
                created_at=NOW,
            ),
        ]
    )
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()

    assert (
        await list_workflow_execution_events(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            dispatch_id=first_id,
        )
        == ()
    )


@pytest.mark.asyncio
async def test_permit_consumption_obeys_caller_owned_rollback(session: AsyncSession) -> None:
    _, workspace_id, project_id, plan_id, version_id, run_id, step_id = await _seed_step(session)
    dispatch = await add_workflow_execution_dispatch(
        session,
        _dispatch(
            workspace_id=workspace_id,
            project_id=project_id,
            plan_id=plan_id,
            version_id=version_id,
            run_id=run_id,
            step_id=step_id,
        ),
    )
    permit = await add_workflow_credential_resolution_permit(
        session,
        WorkflowCredentialResolutionPermitRecord(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            workflow_step_run_id=step_id,
            attempt_generation=0,
            dispatch_id=dispatch.id,
            provider_id="youtube",
            operation_id="search",
            environment="local",
            purpose="provider.search",
            credential_reference_fingerprint=DIGEST_B,
            issued_at=NOW,
            expires_at=NOW + timedelta(minutes=5),
            created_at=NOW,
        ),
    )
    await session.commit()

    consumed = await consume_workflow_credential_resolution_permit(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        permit_id=permit.id,
        consumed_at=NOW + timedelta(seconds=1),
    )
    assert consumed is not None and consumed.consumed_at is not None
    await session.rollback()
    await session.refresh(permit)
    assert permit.consumed_at is None
