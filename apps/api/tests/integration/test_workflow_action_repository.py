from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workflow_action import (
    WorkflowRunActionApprovalConsumption,
    WorkflowRunActionApprovalReceiptRecord,
    WorkflowRunActionAuditEvent,
    WorkflowRunActionContext,
    WorkflowRunActionReceiptRecord,
    WorkflowRunActionRequestRecord,
)
from data_intelligence_hub.models.workflow_execution import WorkflowRun
from data_intelligence_hub.models.workflow_plan import WorkflowPlan, WorkflowVersion
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.workflow_action import (
    add_workflow_run_action_approval_consumption,
    add_workflow_run_action_approval_receipt,
    add_workflow_run_action_audit_event,
    add_workflow_run_action_context,
    add_workflow_run_action_receipt,
    add_workflow_run_action_request,
    get_workflow_run_action_approval_by_idempotency,
    get_workflow_run_action_request_by_idempotency,
    workflow_run_action_context_lock_statement,
)

NOW = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64


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


async def _seed_run(session: AsyncSession) -> tuple[uuid.UUID, ...]:
    user_id, workspace_id, project_id, plan_id, version_id, run_id = (
        uuid.uuid4() for _ in range(6)
    )
    session.add_all(
        [
            User(
                id=user_id,
                email=f"{user_id}@example.com",
                password_hash="fixture-only",
                name="Phase B Owner",
                status="active",
            ),
            Workspace(
                id=workspace_id,
                name="Phase B",
                slug=f"phase-b-{workspace_id}",
                owner_id=user_id,
            ),
            Project(
                id=project_id,
                workspace_id=workspace_id,
                owner_id=user_id,
                name="Phase B",
                description=None,
                domain="social",
                status="active",
            ),
            WorkflowPlan(
                id=plan_id,
                workspace_id=workspace_id,
                project_id=project_id,
                created_by_user_id=user_id,
                name="Phase B",
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
                status="held",
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
                status_reason_code="workflow_step_retry_exhausted",
                impact_code="workflow_run_incomplete",
                missing_fields=[],
                recovery_action_codes=["retry_failed_steps"],
                started_at=NOW,
                finished_at=None,
                created_at=NOW,
            ),
        ]
    )
    await session.commit()
    return user_id, workspace_id, project_id, run_id


def _approval(
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
) -> WorkflowRunActionApprovalReceiptRecord:
    return WorkflowRunActionApprovalReceiptRecord(
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
        approver_user_id=user_id,
        action="retry",
        approval_kind="owner_confirmation",
        proposal_digest=DIGEST_A,
        idempotency_scope=f"workflow_action_approval.v1:{project_id}:{run_id}",
        idempotency_key_hash=DIGEST_B,
        canonical_request_hash=DIGEST_C,
        expected_action_context_version=1,
        expected_run_status="held",
        action_gate_digest=DIGEST_B,
        evidence_digests=[DIGEST_C],
        reason_code="retry_after_retryable_failure",
        reason="Owner reviewed the retry evidence.",
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=10),
    )


def _request(
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    approval_id: uuid.UUID,
) -> WorkflowRunActionRequestRecord:
    return WorkflowRunActionRequestRecord(
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
        actor_user_id=user_id,
        action="retry",
        schema_version="workflow_run_action_request.v1",
        idempotency_scope=f"workflow_run_action.v1:{project_id}:{run_id}",
        idempotency_key_hash=DIGEST_A,
        canonical_request_hash=DIGEST_B,
        expected_action_context_version=1,
        accepted_action_context_version=2,
        expected_run_status="held",
        observed_run_status="held",
        action_gate_digest=DIGEST_C,
        approval_receipt_id=approval_id,
        reason_code="retry_after_retryable_failure",
        reason="Owner reviewed the retry evidence.",
        parameters={"action": "retry"},
        outcome="accepted",
        response_status=201,
        response_payload={"outcome": "accepted"},
    )


def test_context_lock_statement_is_tenant_scoped_and_postgresql_locking() -> None:
    workspace_id, project_id, run_id = (uuid.uuid4() for _ in range(3))
    statement = workflow_run_action_context_lock_statement(
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
    )
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),  # type: ignore[no-untyped-call]
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "workflow_run_action_contexts.workspace_id" in sql
    assert "workflow_run_action_contexts.project_id" in sql
    assert "workflow_run_action_contexts.workflow_run_id" in sql
    assert "FOR UPDATE" in sql
    assert statement.get_execution_options()["populate_existing"] is True


@pytest.mark.asyncio
async def test_action_rows_are_tenant_scoped_and_exactly_replayable(
    session: AsyncSession,
) -> None:
    user_id, workspace_id, project_id, run_id = await _seed_run(session)
    context = await add_workflow_run_action_context(
        session,
        WorkflowRunActionContext(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            action_context_version=1,
        ),
    )
    approval = await add_workflow_run_action_approval_receipt(
        session,
        _approval(
            user_id=user_id,
            workspace_id=workspace_id,
            project_id=project_id,
            run_id=run_id,
        ),
    )
    request = await add_workflow_run_action_request(
        session,
        _request(
            user_id=user_id,
            workspace_id=workspace_id,
            project_id=project_id,
            run_id=run_id,
            approval_id=approval.id,
        ),
    )
    receipt = await add_workflow_run_action_receipt(
        session,
        WorkflowRunActionReceiptRecord(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            request_id=request.id,
            action="retry",
            outcome="accepted",
            before_action_context_version=1,
            after_action_context_version=2,
            before_run_status="held",
            after_run_status="ready",
            before_step_snapshots=[],
            after_step_snapshots=[],
            decision_refs=[],
            state_changed=True,
            database_write=True,
            idempotent_replay=False,
            next_action_code="await_fixture_executor",
            receipt_digest=DIGEST_C,
        ),
    )
    await add_workflow_run_action_approval_consumption(
        session,
        WorkflowRunActionApprovalConsumption(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            approval_receipt_id=approval.id,
            action_request_id=request.id,
            consumed_at=NOW,
        ),
    )
    await add_workflow_run_action_audit_event(
        session,
        WorkflowRunActionAuditEvent(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            event_number=1,
            previous_event_digest=None,
            event_digest=DIGEST_A,
            action_request_id=request.id,
            approval_receipt_id=approval.id,
            action_receipt_id=receipt.id,
            actor_user_id=user_id,
            event_type="action_accepted",
            reason_code="retry_after_retryable_failure",
            before_action_context_version=1,
            after_action_context_version=2,
            before_state_digest=DIGEST_B,
            after_state_digest=DIGEST_C,
            http_request_id="req-phase-b-001",
            occurred_at=NOW,
        ),
    )
    await session.commit()

    replay = await get_workflow_run_action_request_by_idempotency(
        session,
        workspace_id=workspace_id,
        actor_user_id=user_id,
        idempotency_scope=request.idempotency_scope,
        idempotency_key_hash=request.idempotency_key_hash,
    )
    hidden = await get_workflow_run_action_request_by_idempotency(
        session,
        workspace_id=uuid.uuid4(),
        actor_user_id=user_id,
        idempotency_scope=request.idempotency_scope,
        idempotency_key_hash=request.idempotency_key_hash,
    )
    approval_replay = await get_workflow_run_action_approval_by_idempotency(
        session,
        workspace_id=workspace_id,
        approver_user_id=user_id,
        idempotency_scope=approval.idempotency_scope,
        idempotency_key_hash=approval.idempotency_key_hash,
    )
    assert replay is not None and replay.id == request.id
    assert hidden is None
    assert approval_replay is not None and approval_replay.id == approval.id
    assert context.action_context_version == 1


@pytest.mark.asyncio
async def test_duplicate_approval_consumption_rolls_back_without_partial_audit(
    session: AsyncSession,
) -> None:
    user_id, workspace_id, project_id, run_id = await _seed_run(session)
    approval = await add_workflow_run_action_approval_receipt(
        session,
        _approval(
            user_id=user_id,
            workspace_id=workspace_id,
            project_id=project_id,
            run_id=run_id,
        ),
    )
    first = await add_workflow_run_action_request(
        session,
        _request(
            user_id=user_id,
            workspace_id=workspace_id,
            project_id=project_id,
            run_id=run_id,
            approval_id=approval.id,
        ),
    )
    await add_workflow_run_action_approval_consumption(
        session,
        WorkflowRunActionApprovalConsumption(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            approval_receipt_id=approval.id,
            action_request_id=first.id,
            consumed_at=NOW,
        ),
    )
    await session.commit()

    duplicate_request = _request(
        user_id=user_id,
        workspace_id=workspace_id,
        project_id=project_id,
        run_id=run_id,
        approval_id=approval.id,
    )
    duplicate_request.idempotency_key_hash = DIGEST_C
    await add_workflow_run_action_request(session, duplicate_request)
    with pytest.raises(IntegrityError):
        await add_workflow_run_action_approval_consumption(
            session,
            WorkflowRunActionApprovalConsumption(
                workspace_id=workspace_id,
                project_id=project_id,
                workflow_run_id=run_id,
                approval_receipt_id=approval.id,
                action_request_id=duplicate_request.id,
                consumed_at=NOW,
            ),
        )
    await session.rollback()
    assert await session.get(WorkflowRunActionRequestRecord, duplicate_request.id) is None


@pytest.mark.asyncio
async def test_approval_request_and_audit_uniqueness_fail_closed(
    session: AsyncSession,
) -> None:
    user_id, workspace_id, project_id, run_id = await _seed_run(session)
    approval = await add_workflow_run_action_approval_receipt(
        session,
        _approval(
            user_id=user_id,
            workspace_id=workspace_id,
            project_id=project_id,
            run_id=run_id,
        ),
    )
    approval_id = approval.id
    await session.commit()

    with pytest.raises(IntegrityError):
        await add_workflow_run_action_approval_receipt(
            session,
            _approval(
                user_id=user_id,
                workspace_id=workspace_id,
                project_id=project_id,
                run_id=run_id,
            ),
        )
    await session.rollback()

    request = await add_workflow_run_action_request(
        session,
        _request(
            user_id=user_id,
            workspace_id=workspace_id,
            project_id=project_id,
            run_id=run_id,
            approval_id=approval_id,
        ),
    )
    request_id = request.id
    await session.commit()

    with pytest.raises(IntegrityError):
        await add_workflow_run_action_request(
            session,
            _request(
                user_id=user_id,
                workspace_id=workspace_id,
                project_id=project_id,
                run_id=run_id,
                approval_id=approval_id,
            ),
        )
    await session.rollback()

    first_event = await add_workflow_run_action_audit_event(
        session,
        WorkflowRunActionAuditEvent(
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            event_number=1,
            previous_event_digest=None,
            event_digest=DIGEST_A,
            action_request_id=request_id,
            approval_receipt_id=approval_id,
            action_receipt_id=None,
            actor_user_id=user_id,
            event_type="action_accepted",
            reason_code="retry_after_retryable_failure",
            before_action_context_version=1,
            after_action_context_version=2,
            before_state_digest=DIGEST_B,
            after_state_digest=DIGEST_C,
            http_request_id="req-phase-b-unique-001",
            occurred_at=NOW,
        ),
    )
    first_event_number = first_event.event_number
    await session.commit()

    with pytest.raises(IntegrityError):
        await add_workflow_run_action_audit_event(
            session,
            WorkflowRunActionAuditEvent(
                workspace_id=workspace_id,
                project_id=project_id,
                workflow_run_id=run_id,
                event_number=first_event_number,
                previous_event_digest=None,
                event_digest=DIGEST_B,
                action_request_id=request_id,
                approval_receipt_id=approval_id,
                action_receipt_id=None,
                actor_user_id=user_id,
                event_type="action_accepted",
                reason_code="retry_after_retryable_failure",
                before_action_context_version=1,
                after_action_context_version=2,
                before_state_digest=DIGEST_B,
                after_state_digest=DIGEST_C,
                http_request_id="req-phase-b-unique-002",
                occurred_at=NOW,
            ),
        )
    await session.rollback()


@pytest.mark.asyncio
async def test_request_version_and_audit_predecessor_constraints_fail_closed(
    session: AsyncSession,
) -> None:
    user_id, workspace_id, project_id, run_id = await _seed_run(session)
    approval = await add_workflow_run_action_approval_receipt(
        session,
        _approval(
            user_id=user_id,
            workspace_id=workspace_id,
            project_id=project_id,
            run_id=run_id,
        ),
    )
    approval_id = approval.id
    await session.commit()

    accepted_without_version = _request(
        user_id=user_id,
        workspace_id=workspace_id,
        project_id=project_id,
        run_id=run_id,
        approval_id=approval_id,
    )
    accepted_without_version.accepted_action_context_version = None
    with pytest.raises(IntegrityError):
        await add_workflow_run_action_request(session, accepted_without_version)
    await session.rollback()

    rejected_with_version = _request(
        user_id=user_id,
        workspace_id=workspace_id,
        project_id=project_id,
        run_id=run_id,
        approval_id=approval_id,
    )
    rejected_with_version.outcome = "rejected_conflict"
    rejected_with_version.response_status = 409
    with pytest.raises(IntegrityError):
        await add_workflow_run_action_request(session, rejected_with_version)
    await session.rollback()

    await session.execute(text("PRAGMA foreign_keys = ON"))
    with pytest.raises(IntegrityError):
        await add_workflow_run_action_audit_event(
            session,
            WorkflowRunActionAuditEvent(
                workspace_id=workspace_id,
                project_id=project_id,
                workflow_run_id=run_id,
                event_number=2,
                previous_event_digest=DIGEST_A,
                event_digest=DIGEST_B,
                action_request_id=None,
                approval_receipt_id=None,
                action_receipt_id=None,
                actor_user_id=user_id,
                event_type="action_rejected",
                reason_code="workflow_action_context_conflict",
                before_action_context_version=1,
                after_action_context_version=1,
                before_state_digest=DIGEST_B,
                after_state_digest=DIGEST_B,
                http_request_id="req-phase-b-predecessor-001",
                occurred_at=NOW,
            ),
        )
    await session.rollback()
