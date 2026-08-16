from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import func, select
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
    WorkflowRunActionAuditEvent,
    WorkflowRunActionReceiptRecord,
    WorkflowRunActionRequestRecord,
)
from data_intelligence_hub.models.workflow_execution import (
    StepRun,
    StepRunAttempt,
    WorkflowRun,
    WorkflowStepCheckpoint,
)
from data_intelligence_hub.models.workflow_executor import WorkflowExecutionDispatchRecord
from data_intelligence_hub.models.workflow_plan import WorkflowPlan, WorkflowVersion
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.schemas.workflow_action_command import (
    BudgetOverrideActionParameters,
    CancelActionParameters,
    ResumeActionParameters,
    RetryActionParameters,
    RouteSwitchActionParameters,
    WorkflowActionApprovalRequest,
    WorkflowRunActionRequest,
)
from data_intelligence_hub.services.workflow_execution.action_command import (
    WorkflowActionCommandError,
    WorkflowActionCommandEvidence,
    execute_workflow_run_action,
    issue_workflow_action_approval,
    verify_workflow_action_audit_chain,
)

NOW = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
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


async def _seed_failed_run(
    session: AsyncSession,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    owner_id, workspace_id, project_id, plan_id, version_id, run_id, step_id = (
        uuid.uuid4() for _ in range(7)
    )
    session.add_all(
        [
            User(
                id=owner_id,
                email=f"{owner_id}@example.com",
                password_hash="fixture-only",
                name="Phase C Owner",
                status="active",
            ),
            Workspace(
                id=workspace_id,
                name="Phase C",
                slug=f"phase-c-{workspace_id}",
                owner_id=owner_id,
            ),
            Project(
                id=project_id,
                workspace_id=workspace_id,
                owner_id=owner_id,
                name="Phase C",
                description=None,
                domain="social",
                status="active",
            ),
            WorkflowPlan(
                id=plan_id,
                workspace_id=workspace_id,
                project_id=project_id,
                created_by_user_id=owner_id,
                name="Phase C",
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
                created_by_user_id=owner_id,
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
                created_by_user_id=owner_id,
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
            StepRun(
                id=step_id,
                workflow_run_id=run_id,
                workspace_id=workspace_id,
                project_id=project_id,
                step_ref="step.youtube.search",
                requirement_ref="requirement.youtube.search",
                sequence=1,
                retry_generation=0,
                platform="youtube",
                resource_type="video",
                operation="search",
                assertion_id="assertion.youtube.search",
                implementation_id="youtube.official.search",
                route_plan_snapshot={"ordered_candidates": ["youtube.official.search"]},
                evidence_refs=["fixture:phase-c"],
                fixture_case_id=None,
                fixture_content_hash=None,
                input_digest=DIGEST_A,
                output_digest=None,
                idempotency_scope=f"step_run.v1:{run_id}:{step_id}",
                idempotency_key_hash=DIGEST_B,
                status="failed",
                records_count=0,
                started_at=NOW,
                finished_at=NOW,
                created_at=NOW,
            ),
        ]
    )
    await session.commit()
    return owner_id, workspace_id, project_id, run_id, step_id


async def _seed_pending_run(
    session: AsyncSession,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    identifiers = await _seed_failed_run(session)
    step = await session.get(StepRun, identifiers[-1])
    assert step is not None
    step.status = "pending"
    step.finished_at = None
    await session.commit()
    return identifiers


async def _approve_and_execute(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    action: Any,
    approval_kind: Any,
    reason_code: Any,
    reason: str,
    parameters: Any,
    evidence: WorkflowActionCommandEvidence,
    expected_run_status: Any = "held",
) -> tuple[Any, Any]:
    approval_request = WorkflowActionApprovalRequest(
        action=action,
        approval_kind=approval_kind,
        expected_action_context_version=1,
        expected_run_status=expected_run_status,
        action_gate_digest=evidence.action_gate_digest,
        reason_code=reason_code,
        reason=reason,
        parameters=parameters,
    )
    approval = await issue_workflow_action_approval(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
        actor_user_id=owner_id,
        idempotency_key=f"phase-c-approval-{action}-{run_id}",
        http_request_id=f"req-phase-c-approval-{run_id}",
        request=approval_request,
        evidence=evidence,
        evaluated_at=NOW,
    )
    request = WorkflowRunActionRequest(
        action=action,
        approval_receipt_id=approval.id,
        expected_action_context_version=1,
        expected_run_status=expected_run_status,
        action_gate_digest=evidence.action_gate_digest,
        reason_code=reason_code,
        reason=reason,
        parameters=parameters,
    )
    receipt = await execute_workflow_run_action(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
        actor_user_id=owner_id,
        idempotency_key=f"phase-c-action-{action}-{run_id}",
        http_request_id=f"req-phase-c-action-{run_id}",
        request=request,
        evidence=evidence,
        evaluated_at=NOW,
    )
    return approval, receipt


@pytest.mark.asyncio
async def test_retry_is_atomic_and_exact_replay_is_write_free(
    session: AsyncSession,
) -> None:
    owner_id, workspace_id, project_id, run_id, step_id = await _seed_failed_run(session)
    parameters = RetryActionParameters(
        target_step_run_ids=[step_id],
        expected_retry_generation=0,
        attempt_evidence_digest=DIGEST_A,
        retry_policy_digest=DIGEST_B,
    )
    approval_request = WorkflowActionApprovalRequest(
        action="retry",
        approval_kind="owner_confirmation",
        expected_action_context_version=1,
        expected_run_status="held",
        action_gate_digest=DIGEST_D,
        reason_code="retry_after_retryable_failure",
        reason="Owner reviewed the retry evidence.",
        parameters=parameters,
    )
    evidence = WorkflowActionCommandEvidence(
        action_gate_digest=DIGEST_D,
        evidence_digests=(DIGEST_A, DIGEST_B),
        retry_policy_available=True,
        retry_generation_limit=3,
    )
    approval = await issue_workflow_action_approval(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
        actor_user_id=owner_id,
        idempotency_key="phase-c-approval-retry-001",
        http_request_id="req-phase-c-approval-001",
        request=approval_request,
        evidence=evidence,
        evaluated_at=NOW,
    )
    request = WorkflowRunActionRequest(
        action="retry",
        approval_receipt_id=approval.id,
        expected_action_context_version=1,
        expected_run_status="held",
        action_gate_digest=DIGEST_D,
        reason_code="retry_after_retryable_failure",
        reason="Owner reviewed the retry evidence.",
        parameters=parameters,
    )
    receipt = await execute_workflow_run_action(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
        actor_user_id=owner_id,
        idempotency_key="phase-c-action-retry-001",
        http_request_id="req-phase-c-action-001",
        request=request,
        evidence=evidence,
        evaluated_at=NOW,
    )
    replay = await execute_workflow_run_action(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
        actor_user_id=owner_id,
        idempotency_key="phase-c-action-retry-001",
        http_request_id="req-phase-c-action-replay-001",
        request=request,
        evidence=evidence,
        evaluated_at=NOW,
    )

    persisted_run = await session.get(WorkflowRun, run_id)
    persisted_step = await session.get(StepRun, step_id)
    assert receipt.action == "retry"
    assert receipt.before_action_context_version == 1
    assert receipt.after_action_context_version == 2
    assert receipt.before_run_status == "held"
    assert receipt.after_run_status == "ready"
    assert receipt.state_changed is True
    assert receipt.database_write is True
    assert receipt.idempotent_replay is False
    assert replay.id == receipt.id
    assert replay.receipt_digest == receipt.receipt_digest
    assert replay.database_write is False
    assert replay.idempotent_replay is True
    assert persisted_run is not None
    assert persisted_run.status == "ready"
    assert persisted_run.status_reason_code is None
    assert persisted_run.impact_code is None
    assert persisted_run.recovery_action_codes == []
    assert persisted_step is not None
    assert persisted_step.status == "pending"
    assert persisted_step.retry_generation == 1
    assert persisted_step.finished_at is None

    counts = {}
    for model in (
        WorkflowRunActionRequestRecord,
        WorkflowRunActionReceiptRecord,
        WorkflowRunActionApprovalConsumption,
        StepRunAttempt,
    ):
        counts[model] = await session.scalar(select(func.count()).select_from(model))
    assert counts == {
        WorkflowRunActionRequestRecord: 1,
        WorkflowRunActionReceiptRecord: 1,
        WorkflowRunActionApprovalConsumption: 1,
        StepRunAttempt: 0,
    }


@pytest.mark.asyncio
async def test_retry_acceptance_creates_one_pending_dispatch_without_execution(
    session: AsyncSession,
) -> None:
    owner_id, workspace_id, project_id, run_id, step_id = await _seed_failed_run(session)
    parameters = RetryActionParameters(
        target_step_run_ids=[step_id],
        expected_retry_generation=0,
        attempt_evidence_digest=DIGEST_A,
        retry_policy_digest=DIGEST_B,
    )

    _approval, receipt = await _approve_and_execute(
        session,
        owner_id=owner_id,
        workspace_id=workspace_id,
        project_id=project_id,
        run_id=run_id,
        action="retry",
        approval_kind="owner_confirmation",
        reason_code="retry_after_retryable_failure",
        reason="Owner reviewed the retry evidence.",
        parameters=parameters,
        evidence=WorkflowActionCommandEvidence(
            action_gate_digest=DIGEST_D,
            evidence_digests=(DIGEST_A, DIGEST_B),
            retry_policy_available=True,
            retry_generation_limit=3,
        ),
    )

    dispatches = tuple(
        (
            await session.execute(
                select(WorkflowExecutionDispatchRecord).where(
                    WorkflowExecutionDispatchRecord.workspace_id == workspace_id,
                    WorkflowExecutionDispatchRecord.project_id == project_id,
                    WorkflowExecutionDispatchRecord.workflow_run_id == run_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(dispatches) == 1
    dispatch = dispatches[0]
    assert dispatch.workflow_step_run_id == step_id
    assert dispatch.attempt_generation == 1
    assert dispatch.source_action_request_id == receipt.request_id
    assert dispatch.source_action_receipt_id == receipt.id
    assert dispatch.execution_policy_digest == DIGEST_B
    assert dispatch.state == "pending"
    assert dispatch.database_write is False
    assert dispatch.credential_read_attempted is False
    assert dispatch.provider_call is False
    assert dispatch.network_call is False
    assert dispatch.production_write_allowed is False
    assert receipt.execution_started is False


@pytest.mark.asyncio
async def test_resume_cancel_budget_and_route_effects_remain_fixture_only(
    session: AsyncSession,
) -> None:
    resume_ids = await _seed_pending_run(session)
    resume_run = await session.get(WorkflowRun, resume_ids[3])
    resume_step = await session.get(StepRun, resume_ids[4])
    assert resume_run is not None and resume_step is not None
    session.add(
        WorkflowStepCheckpoint(
            execution_session_id=resume_run.id,
            workspace_id=resume_run.workspace_id,
            project_id=resume_run.project_id,
            workflow_plan_id=resume_run.workflow_plan_id,
            workflow_version_id=resume_run.workflow_version_id,
            step_ref=resume_step.step_ref,
            requirement_ref=resume_step.requirement_ref,
            implementation_id=resume_step.implementation_id,
            contract_version="workflow_step_checkpoint.v1",
            fixture_profile_id=resume_run.fixture_profile_id,
            fixture_profile_hash=resume_run.fixture_profile_hash,
            step_input_digest=resume_step.input_digest,
            page_number=1,
            cursor_before=None,
            cursor_before_digest=DIGEST_B,
            cursor_after="fixture-next-page",
            cursor_after_digest=DIGEST_C,
            side_effect_key_hash=DIGEST_D,
            page_output_digest=DIGEST_B,
            checkpoint_digest=DIGEST_A,
            records_count=1,
            terminal=False,
            evidence_refs=["fixture:phase-f3-resume"],
            provider_call_attempted=False,
            credential_read_attempted=False,
            actor_run=False,
            browser_run=False,
            llm_call=False,
            raw_record_write=False,
            dataset_write=False,
            production_write_allowed=False,
            confirmed_at=NOW,
            created_at=NOW,
        )
    )
    await session.commit()
    resume_parameters = ResumeActionParameters(
        checkpoint_digest=DIGEST_A,
        budget_policy_digest=DIGEST_B,
        budget_ledger_digest=DIGEST_C,
    )
    _, resume_receipt = await _approve_and_execute(
        session,
        owner_id=resume_ids[0],
        workspace_id=resume_ids[1],
        project_id=resume_ids[2],
        run_id=resume_ids[3],
        action="resume",
        approval_kind="owner_confirmation",
        reason_code="resume_from_confirmed_checkpoint",
        reason="Owner confirmed the frozen checkpoint and budget evidence.",
        parameters=resume_parameters,
        evidence=WorkflowActionCommandEvidence(
            action_gate_digest=DIGEST_D,
            evidence_digests=(DIGEST_A, DIGEST_B, DIGEST_C),
            checkpoint_available=True,
            budget_within_limit=True,
        ),
    )
    resume_run = await session.get(WorkflowRun, resume_ids[3])
    assert resume_receipt.after_run_status == "ready"
    assert resume_receipt.next_action_code == "await_fixture_executor"
    assert resume_run is not None and resume_run.status == "ready"
    resume_dispatches = tuple(
        (
            await session.execute(
                select(WorkflowExecutionDispatchRecord).where(
                    WorkflowExecutionDispatchRecord.workspace_id == resume_ids[1],
                    WorkflowExecutionDispatchRecord.project_id == resume_ids[2],
                    WorkflowExecutionDispatchRecord.workflow_run_id == resume_ids[3],
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(resume_dispatches) == 1
    assert resume_dispatches[0].workflow_step_run_id == resume_ids[4]
    assert resume_dispatches[0].execution_policy_digest == DIGEST_B
    assert resume_dispatches[0].state == "pending"

    cancel_ids = await _seed_pending_run(session)
    _, cancel_receipt = await _approve_and_execute(
        session,
        owner_id=cancel_ids[0],
        workspace_id=cancel_ids[1],
        project_id=cancel_ids[2],
        run_id=cancel_ids[3],
        action="cancel",
        approval_kind="owner_confirmation",
        reason_code="cancel_operator_request",
        reason="Owner requested a terminal fixture cancellation.",
        parameters=CancelActionParameters(cancel_scope="held_run"),
        evidence=WorkflowActionCommandEvidence(
            action_gate_digest=DIGEST_D,
            evidence_digests=(DIGEST_A,),
        ),
    )
    cancel_run = await session.get(WorkflowRun, cancel_ids[3])
    assert cancel_receipt.after_run_status == "cancelled"
    assert cancel_run is not None
    assert cancel_run.finished_at == NOW.replace(tzinfo=None)
    assert cancel_run.recovery_action_codes == []

    budget_ids = await _seed_pending_run(session)
    _, budget_receipt = await _approve_and_execute(
        session,
        owner_id=budget_ids[0],
        workspace_id=budget_ids[1],
        project_id=budget_ids[2],
        run_id=budget_ids[3],
        action="budget_override",
        approval_kind="owner_policy_override",
        reason_code="budget_override_business_exception",
        reason="Owner approved bounded fixture ceilings for this Run.",
        parameters=BudgetOverrideActionParameters(
            request_limit=20,
            item_limit=200,
            quota_unit_limit=1000,
            cost_limit_usd=Decimal("5.00"),
            time_limit_ms=60_000,
            expires_at=NOW.replace(hour=13),
        ),
        evidence=WorkflowActionCommandEvidence(
            action_gate_digest=DIGEST_D,
            evidence_digests=(DIGEST_A,),
            budget_held=True,
            budget_current_request_count=10,
            budget_current_item_count=100,
            budget_current_quota_units=500,
            budget_current_cost_usd=Decimal("2.50"),
            budget_current_elapsed_ms=30_000,
        ),
    )
    budget_run = await session.get(WorkflowRun, budget_ids[3])
    assert budget_receipt.after_run_status == "held"
    assert budget_receipt.state_changed is False
    assert budget_run is not None and budget_run.status == "held"

    route_ids = await _seed_failed_run(session)
    _, route_receipt = await _approve_and_execute(
        session,
        owner_id=route_ids[0],
        workspace_id=route_ids[1],
        project_id=route_ids[2],
        run_id=route_ids[3],
        action="route_switch",
        approval_kind="owner_route_override",
        reason_code="route_switch_verified_fallback",
        reason="Owner approved the verified fallback for the next retry.",
        parameters=RouteSwitchActionParameters(
            step_run_id=route_ids[4],
            primary_implementation_id="youtube.official.search",
            fallback_implementation_id="youtube.fixture.search",
            fallback_decision_digest=DIGEST_A,
            field_difference_digest=DIGEST_B,
            cost_digest=DIGEST_C,
            provider_health_digest=DIGEST_D,
        ),
        evidence=WorkflowActionCommandEvidence(
            action_gate_digest=DIGEST_D,
            evidence_digests=(DIGEST_A, DIGEST_B, DIGEST_C, DIGEST_D),
            route_switch_eligible=True,
        ),
    )
    route_run = await session.get(WorkflowRun, route_ids[3])
    route_step = await session.get(StepRun, route_ids[4])
    route_record = await session.scalar(
        select(WorkflowRunActionReceiptRecord).where(
            WorkflowRunActionReceiptRecord.id == route_receipt.id
        )
    )
    assert route_receipt.after_run_status == "held"
    assert route_receipt.state_changed is False
    assert route_run is not None and route_run.status == "held"
    assert route_step is not None
    assert route_step.implementation_id == "youtube.official.search"
    assert route_step.retry_generation == 0
    assert route_record is not None
    assert route_record.decision_refs[0]["original_route_plan_unchanged"] is True
    assert route_record.decision_refs[0]["catalog_unchanged"] is True


@pytest.mark.asyncio
async def test_wrong_tenant_non_owner_and_running_cancel_fail_without_action_write(
    session: AsyncSession,
) -> None:
    owner_id, workspace_id, project_id, run_id, _ = await _seed_pending_run(session)
    approval_request = WorkflowActionApprovalRequest(
        action="cancel",
        approval_kind="owner_confirmation",
        expected_action_context_version=1,
        expected_run_status="held",
        action_gate_digest=DIGEST_D,
        reason_code="cancel_operator_request",
        reason="Owner requested a terminal fixture cancellation.",
        parameters=CancelActionParameters(cancel_scope="held_run"),
    )
    evidence = WorkflowActionCommandEvidence(
        action_gate_digest=DIGEST_D,
        evidence_digests=(DIGEST_A,),
    )
    with pytest.raises(WorkflowActionCommandError) as wrong_tenant:
        await issue_workflow_action_approval(
            session,
            workspace_id=uuid.uuid4(),
            project_id=project_id,
            workflow_run_id=run_id,
            actor_user_id=owner_id,
            idempotency_key="phase-c-wrong-tenant",
            http_request_id="req-phase-c-wrong-tenant",
            request=approval_request,
            evidence=evidence,
            evaluated_at=NOW,
        )
    assert wrong_tenant.value.code == "workflow_run_not_found"
    assert wrong_tenant.value.status == 404

    outsider_id = uuid.uuid4()
    session.add(
        User(
            id=outsider_id,
            email=f"{outsider_id}@example.com",
            password_hash="fixture-only",
            name="Phase C Outsider",
            status="active",
        )
    )
    await session.commit()
    with pytest.raises(WorkflowActionCommandError) as non_owner:
        await issue_workflow_action_approval(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            actor_user_id=outsider_id,
            idempotency_key="phase-c-non-owner",
            http_request_id="req-phase-c-non-owner",
            request=approval_request,
            evidence=evidence,
            evaluated_at=NOW,
        )
    assert non_owner.value.code == "workflow_action_owner_required"
    assert non_owner.value.status == 403

    run = await session.get(WorkflowRun, run_id)
    assert run is not None
    run.status = "running"
    run.status_reason_code = None
    run.impact_code = None
    run.missing_fields = []
    run.recovery_action_codes = []
    await session.commit()
    running_approval_request = WorkflowActionApprovalRequest(
        action="cancel",
        approval_kind="owner_confirmation",
        expected_action_context_version=1,
        expected_run_status="running",
        action_gate_digest=DIGEST_D,
        reason_code="cancel_operator_request",
        reason="Owner requested a terminal fixture cancellation.",
        parameters=CancelActionParameters(cancel_scope="running_run"),
    )
    approval = await issue_workflow_action_approval(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
        actor_user_id=owner_id,
        idempotency_key="phase-c-running-cancel-approval",
        http_request_id="req-phase-c-running-cancel-approval",
        request=running_approval_request,
        evidence=evidence,
        evaluated_at=NOW,
    )
    running_request = WorkflowRunActionRequest(
        action="cancel",
        approval_receipt_id=approval.id,
        expected_action_context_version=1,
        expected_run_status="running",
        action_gate_digest=DIGEST_D,
        reason_code="cancel_operator_request",
        reason="Owner requested a terminal fixture cancellation.",
        parameters=CancelActionParameters(cancel_scope="running_run"),
    )
    before_request_count = await session.scalar(
        select(func.count()).select_from(WorkflowRunActionRequestRecord)
    )
    await session.rollback()
    with pytest.raises(WorkflowActionCommandError) as running_cancel:
        await execute_workflow_run_action(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            actor_user_id=owner_id,
            idempotency_key="phase-c-running-cancel-action",
            http_request_id="req-phase-c-running-cancel-action",
            request=running_request,
            evidence=evidence,
            evaluated_at=NOW,
        )
    after_request_count = await session.scalar(
        select(func.count()).select_from(WorkflowRunActionRequestRecord)
    )
    refreshed_run = await session.get(WorkflowRun, run_id)
    assert running_cancel.value.code == "workflow_action_executor_ack_unavailable"
    assert before_request_count == after_request_count
    assert refreshed_run is not None and refreshed_run.status == "running"


@pytest.mark.asyncio
async def test_conflicts_expiry_revocation_and_audit_tamper_fail_closed(
    session: AsyncSession,
) -> None:
    owner_id, workspace_id, project_id, run_id, step_id = await _seed_failed_run(session)
    parameters = RetryActionParameters(
        target_step_run_ids=[step_id],
        expected_retry_generation=0,
        attempt_evidence_digest=DIGEST_A,
        retry_policy_digest=DIGEST_B,
    )
    evidence = WorkflowActionCommandEvidence(
        action_gate_digest=DIGEST_D,
        evidence_digests=(DIGEST_A, DIGEST_B),
        retry_policy_available=True,
    )
    approval_request = WorkflowActionApprovalRequest(
        action="retry",
        approval_kind="owner_confirmation",
        expected_action_context_version=1,
        expected_run_status="held",
        action_gate_digest=DIGEST_D,
        reason_code="retry_after_retryable_failure",
        reason="Owner reviewed the retry evidence.",
        parameters=parameters,
    )
    approval = await issue_workflow_action_approval(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
        actor_user_id=owner_id,
        idempotency_key="phase-c-conflict-approval",
        http_request_id="req-phase-c-conflict-approval",
        request=approval_request,
        evidence=evidence,
        evaluated_at=NOW,
    )
    action_request = WorkflowRunActionRequest(
        action="retry",
        approval_receipt_id=approval.id,
        expected_action_context_version=1,
        expected_run_status="held",
        action_gate_digest=DIGEST_D,
        reason_code="retry_after_retryable_failure",
        reason="Owner reviewed the retry evidence.",
        parameters=parameters,
    )
    with pytest.raises(WorkflowActionCommandError) as gate_conflict:
        await execute_workflow_run_action(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            actor_user_id=owner_id,
            idempotency_key="phase-c-gate-conflict",
            http_request_id="req-phase-c-gate-conflict",
            request=action_request,
            evidence=WorkflowActionCommandEvidence(
                action_gate_digest=DIGEST_C,
                evidence_digests=(DIGEST_A, DIGEST_B),
                retry_policy_available=True,
            ),
            evaluated_at=NOW,
        )
    assert gate_conflict.value.code == "workflow_action_gate_conflict"

    with pytest.raises(WorkflowActionCommandError) as expired:
        await execute_workflow_run_action(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            actor_user_id=owner_id,
            idempotency_key="phase-c-expired",
            http_request_id="req-phase-c-expired",
            request=action_request,
            evidence=evidence,
            evaluated_at=NOW.replace(minute=11),
        )
    assert expired.value.code == "workflow_action_approval_expired"

    with pytest.raises(WorkflowActionCommandError) as revoked:
        await execute_workflow_run_action(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            actor_user_id=owner_id,
            idempotency_key="phase-c-revoked",
            http_request_id="req-phase-c-revoked",
            request=action_request,
            evidence=evidence,
            evaluated_at=NOW,
            approval_revoked=True,
        )
    assert revoked.value.code == "workflow_action_approval_revoked"

    receipt = await execute_workflow_run_action(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
        actor_user_id=owner_id,
        idempotency_key="phase-c-conflict-action",
        http_request_id="req-phase-c-conflict-action",
        request=action_request,
        evidence=evidence,
        evaluated_at=NOW,
    )
    conflicting_request = WorkflowRunActionRequest(
        action="retry",
        approval_receipt_id=approval.id,
        expected_action_context_version=1,
        expected_run_status="held",
        action_gate_digest=DIGEST_D,
        reason_code="retry_after_retryable_failure",
        reason="A different valid reason creates a different canonical request.",
        parameters=parameters,
    )
    with pytest.raises(WorkflowActionCommandError) as idempotency_conflict:
        await execute_workflow_run_action(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            actor_user_id=owner_id,
            idempotency_key="phase-c-conflict-action",
            http_request_id="req-phase-c-idempotency-conflict",
            request=conflicting_request,
            evidence=evidence,
            evaluated_at=NOW,
        )
    assert idempotency_conflict.value.code == "workflow_action_idempotency_conflict"
    assert "different valid reason" not in str(idempotency_conflict.value).lower()

    await verify_workflow_action_audit_chain(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_run_id=run_id,
    )
    events = tuple(
        (
            await session.scalars(
                select(WorkflowRunActionAuditEvent)
                .where(WorkflowRunActionAuditEvent.workflow_run_id == run_id)
                .order_by(WorkflowRunActionAuditEvent.event_number)
            )
        ).all()
    )
    assert [event.event_number for event in events] == [1, 2]
    assert events[1].previous_event_digest == events[0].event_digest
    assert events[1].action_receipt_id == receipt.id
    events[1].event_digest = DIGEST_C
    await session.commit()
    with pytest.raises(WorkflowActionCommandError) as tampered:
        await verify_workflow_action_audit_chain(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
        )
    assert tampered.value.code == "workflow_action_audit_chain_invalid"


@pytest.mark.asyncio
async def test_concurrent_exact_duplicate_persists_one_receipt(tmp_path: Any) -> None:
    database_path = tmp_path / "phase-c-concurrent.sqlite3"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path}",
        connect_args={"timeout": 30},
    )
    async with engine.begin() as connection:
        await connection.exec_driver_sql("PRAGMA journal_mode=WAL")
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as seed_session:
        owner_id, workspace_id, project_id, run_id, step_id = await _seed_failed_run(seed_session)
        parameters = RetryActionParameters(
            target_step_run_ids=[step_id],
            expected_retry_generation=0,
            attempt_evidence_digest=DIGEST_A,
            retry_policy_digest=DIGEST_B,
        )
        evidence = WorkflowActionCommandEvidence(
            action_gate_digest=DIGEST_D,
            evidence_digests=(DIGEST_A, DIGEST_B),
            retry_policy_available=True,
        )
        approval = await issue_workflow_action_approval(
            seed_session,
            workspace_id=workspace_id,
            project_id=project_id,
            workflow_run_id=run_id,
            actor_user_id=owner_id,
            idempotency_key="phase-c-concurrent-approval",
            http_request_id="req-phase-c-concurrent-approval",
            request=WorkflowActionApprovalRequest(
                action="retry",
                approval_kind="owner_confirmation",
                expected_action_context_version=1,
                expected_run_status="held",
                action_gate_digest=DIGEST_D,
                reason_code="retry_after_retryable_failure",
                reason="Owner reviewed the retry evidence.",
                parameters=parameters,
            ),
            evidence=evidence,
            evaluated_at=NOW,
        )
    request = WorkflowRunActionRequest(
        action="retry",
        approval_receipt_id=approval.id,
        expected_action_context_version=1,
        expected_run_status="held",
        action_gate_digest=DIGEST_D,
        reason_code="retry_after_retryable_failure",
        reason="Owner reviewed the retry evidence.",
        parameters=parameters,
    )

    async def submit(request_id: str) -> Any:
        async with factory() as concurrent_session:
            return await execute_workflow_run_action(
                concurrent_session,
                workspace_id=workspace_id,
                project_id=project_id,
                workflow_run_id=run_id,
                actor_user_id=owner_id,
                idempotency_key="phase-c-concurrent-action",
                http_request_id=request_id,
                request=request,
                evidence=evidence,
                evaluated_at=NOW,
            )

    first, second = await asyncio.gather(
        submit("req-phase-c-concurrent-action-a"),
        submit("req-phase-c-concurrent-action-b"),
    )
    assert first.id == second.id
    assert sorted((first.database_write, second.database_write)) == [False, True]
    assert sorted((first.idempotent_replay, second.idempotent_replay)) == [False, True]
    async with factory() as verify_session:
        assert (
            await verify_session.scalar(
                select(func.count()).select_from(WorkflowRunActionRequestRecord)
            )
            == 1
        )
        assert (
            await verify_session.scalar(
                select(func.count()).select_from(WorkflowRunActionReceiptRecord)
            )
            == 1
        )
    await engine.dispose()
