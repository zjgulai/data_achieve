from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import NoReturn, cast

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workflow_execution import (
    StepRun,
    StepRunAttempt,
    WorkflowFallbackDecision,
    WorkflowRun,
    WorkflowRunRequest,
    WorkflowShadowComparison,
)
from data_intelligence_hub.models.workflow_plan import WorkflowPlan, WorkflowVersion
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.workflow_execution import (
    add_step_runs as repository_add_step_runs,
)
from data_intelligence_hub.repositories.workflow_execution import (
    add_workflow_run as repository_add_workflow_run,
)
from data_intelligence_hub.repositories.workflow_execution import (
    get_workflow_run,
    list_step_runs,
)
from data_intelligence_hub.schemas.capability_catalog import CapabilityCatalog
from data_intelligence_hub.schemas.workflow_execution import (
    WorkflowFixtureRunCreateRequest,
    WorkflowFixtureRunCreateResponse,
    WorkflowRunStatus,
    WorkflowStepRunStatus,
)
from data_intelligence_hub.schemas.workflow_plan_persistence import (
    serialize_preview_snapshot,
)
from data_intelligence_hub.schemas.workflow_planner import PlanningInput, WorkflowPlanPreview
from data_intelligence_hub.services.workflow_execution import execution
from data_intelligence_hub.services.workflow_execution.eligibility import (
    PrimaryExecutionContract,
    WorkflowVersionNotFixtureRunnableError,
    build_primary_execution_contracts,
)
from data_intelligence_hub.services.workflow_execution.execution import (
    WorkflowExecutionIdempotencyConflictError,
    WorkflowExecutionProjectNotActiveError,
    WorkflowExecutionTransactionStateError,
    create_workflow_fixture_run,
)
from data_intelligence_hub.services.workflow_execution.fixtures import (
    LoadedWorkflowFixtureProfile,
    WorkflowFixtureAdapterUnavailableError,
    WorkflowFixtureProfileUnknownError,
    WorkflowFixtureStepReceipt,
)
from data_intelligence_hub.services.workflow_execution.fixtures import (
    execute_workflow_fixture_step as execute_registered_fixture_step,
)
from data_intelligence_hub.services.workflow_execution.fixtures import (
    load_workflow_fixture_profile as load_registered_fixture_profile,
)
from data_intelligence_hub.services.workflow_execution.integrity import (
    WorkflowVersionExpectedFingerprintConflictError,
    WorkflowVersionSnapshotInvalidError,
)
from data_intelligence_hub.services.workflow_execution.retry import (
    WorkflowStepRetryableError,
    WorkflowStepTerminalError,
)
from data_intelligence_hub.services.workflow_execution.shadow import (
    compile_workflow_fixture_shadow_comparison,
)
from data_intelligence_hub.services.workflow_planner.planner import (
    build_workflow_plan_result,
)

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "workflow_planner"
PERIODIC_FIXTURE = FIXTURE_DIR / "periodic_monitoring_request_v1.json"
SYNTHETIC_CATALOG_FIXTURE = FIXTURE_DIR / "synthetic_capability_catalog_v1.json"
NOW = datetime(2026, 7, 15, 13, 0, tzinfo=UTC)
RAW_IDEMPOTENCY_KEY = "workflow-fixture-key-0001"


@dataclass(frozen=True, slots=True)
class SeededVersion:
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    plan_id: uuid.UUID
    version_id: uuid.UUID
    template_id: uuid.UUID
    template_revision_id: uuid.UUID
    version: WorkflowVersion
    preview: WorkflowPlanPreview


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


def _planning_input(
    required_fields: list[str] | None = None,
) -> PlanningInput:
    payload = cast(
        dict[str, object],
        json.loads(PERIODIC_FIXTURE.read_text(encoding="utf-8")),
    )
    payload["required_fields"] = required_fields or ["id", "url", "text"]
    return PlanningInput.model_validate(payload)


def _catalog() -> CapabilityCatalog:
    return CapabilityCatalog.model_validate_json(
        SYNTHETIC_CATALOG_FIXTURE.read_text(encoding="utf-8")
    )


async def _seed_resolved_version(
    session: AsyncSession,
    *,
    required_fields: list[str] | None = None,
) -> SeededVersion:
    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    version_id = uuid.uuid4()
    template_id = uuid.uuid4()
    template_revision_id = uuid.uuid4()
    result = build_workflow_plan_result(
        project_id=project_id,
        planning_input=_planning_input(required_fields),
        catalog=_catalog(),
        generated_at=NOW,
        request_id="workflow-execution-service-fixture",
    )
    preview = result.preview
    plan = WorkflowPlan(
        id=plan_id,
        workspace_id=workspace_id,
        project_id=project_id,
        created_by_user_id=user_id,
        name="Fixture Plan",
        flow_mode=preview.flow_mode.value,
        status="active",
        current_version_id=None,
        workflow_template_id=template_id,
        workflow_template_revision_id=template_revision_id,
        created_at=NOW,
        updated_at=NOW,
    )
    version = WorkflowVersion(
        id=version_id,
        workspace_id=workspace_id,
        project_id=project_id,
        workflow_plan_id=plan_id,
        workflow_template_id=template_id,
        workflow_template_revision_id=template_revision_id,
        created_by_user_id=user_id,
        version_number=1,
        planning_status=preview.planning_status.value,
        planner_contract_version=preview.planner_contract_version,
        catalog_snapshot_id=preview.catalog_snapshot_id,
        policy_version=preview.policy_version,
        mode_template_version=preview.mode_template_version,
        query_versions={key.value: value for key, value in preview.query_versions.items()},
        fingerprint_payload=result.fingerprint_payload.model_dump(mode="json"),
        normalized_input=preview.normalized_input.model_dump(mode="json"),
        plan_payload=serialize_preview_snapshot(preview),
        preview_fingerprint=preview.preview_fingerprint,
        created_at=NOW,
    )
    session.add_all(
        [
            User(
                id=user_id,
                email="workflow-execution-service@example.com",
                password_hash="not-a-real-secret",
                name="Workflow Execution Service",
                status="active",
            ),
            Workspace(
                id=workspace_id,
                name="Workflow Execution Service",
                slug=f"workflow-execution-service-{workspace_id.hex[:8]}",
                owner_id=user_id,
            ),
            Project(
                id=project_id,
                workspace_id=workspace_id,
                owner_id=user_id,
                name="Workflow Execution Service",
                description=None,
                domain="social",
                status="active",
            ),
            plan,
            version,
        ]
    )
    await session.flush()
    plan.current_version_id = version_id
    await session.commit()
    return SeededVersion(
        user_id=user_id,
        workspace_id=workspace_id,
        project_id=project_id,
        plan_id=plan_id,
        version_id=version_id,
        template_id=template_id,
        template_revision_id=template_revision_id,
        version=version,
        preview=preview,
    )


async def _row_count(session: AsyncSession, model: type[Base]) -> int:
    result = await session.execute(select(func.count()).select_from(model))
    return int(result.scalar_one())


def _request(seed: SeededVersion) -> WorkflowFixtureRunCreateRequest:
    return WorkflowFixtureRunCreateRequest(
        expected_preview_fingerprint=seed.version.preview_fingerprint,
        fixture_profile_id="fixture-primary-v1",
    )


async def _create_run(
    session: AsyncSession,
    seed: SeededVersion,
    *,
    idempotency_key: str = RAW_IDEMPOTENCY_KEY,
    payload: WorkflowFixtureRunCreateRequest | None = None,
) -> WorkflowFixtureRunCreateResponse:
    return await create_workflow_fixture_run(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workflow_plan_id=seed.plan_id,
        workflow_version_id=seed.version_id,
        created_by_user_id=seed.user_id,
        payload=payload or _request(seed),
        idempotency_key=idempotency_key,
        request_id="workflow-execution-task8",
        generated_at=NOW + timedelta(minutes=1),
    )


@pytest.mark.asyncio
async def test_active_frozen_version_creates_one_exact_completed_fixture_run(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = await _seed_resolved_version(session)
    await session.execute(select(Project).where(Project.id == seed.project_id))
    assert session.in_transaction()

    original = execute_registered_fixture_step
    calls: list[PrimaryExecutionContract] = []

    def spy(
        loaded: LoadedWorkflowFixtureProfile,
        contract: PrimaryExecutionContract,
    ) -> WorkflowFixtureStepReceipt:
        calls.append(contract)
        return original(loaded, contract)

    monkeypatch.setattr(execution, "execute_workflow_fixture_step", spy)
    response = await create_workflow_fixture_run(
        session,
        workspace_id=seed.workspace_id,
        project_id=seed.project_id,
        workflow_plan_id=seed.plan_id,
        workflow_version_id=seed.version_id,
        created_by_user_id=seed.user_id,
        payload=_request(seed),
        idempotency_key=RAW_IDEMPOTENCY_KEY,
        request_id="workflow-execution-service-create",
        generated_at=NOW + timedelta(minutes=1),
    )

    assert response.database_write is True
    assert response.idempotent_replay is False
    assert response.run.status is WorkflowRunStatus.COMPLETED
    assert response.run.preview_fingerprint == seed.version.preview_fingerprint
    assert response.run.workflow_template_id == seed.template_id
    assert response.run.workflow_template_revision_id == seed.template_revision_id
    assert response.run.catalog_snapshot_id == seed.version.catalog_snapshot_id
    assert response.run.query_versions == seed.preview.query_versions
    assert response.run.total_steps == response.run.completed_steps == len(calls) == 3
    assert response.run.records_count == sum(item.records_count for item in response.steps)
    assert [item.sequence for item in response.steps] == [3, 4, 5]
    assert all(item.status is WorkflowStepRunStatus.COMPLETED for item in response.steps)
    assert all(item.primary.implementation_id == "fixture.primary" for item in calls)
    assert all(len(item.route_plan.fallback_implementations) == 1 for item in calls)
    assert all(item.provider_call_attempted is False for item in response.steps)
    assert response.provider_call is False
    assert response.credential_read_attempted is False
    assert response.raw_record_write is False
    assert response.dataset_write is False

    runs = list((await session.execute(select(WorkflowRun))).scalars().all())
    steps = list(
        (await session.execute(select(StepRun).order_by(StepRun.sequence, StepRun.step_ref)))
        .scalars()
        .all()
    )
    requests = list((await session.execute(select(WorkflowRunRequest))).scalars().all())
    assert len(runs) == len(requests) == 1
    assert len(steps) == 3
    assert [item.step_ref for item in steps] == [item.step_ref for item in response.steps]
    assert [item.route_plan_snapshot for item in steps] == [
        item.route_plan.model_dump(mode="json") for item in calls
    ]
    assert [item.assertion_id for item in steps] == [item.primary.assertion_id for item in calls]
    assert [item.evidence_refs for item in steps] == [item.primary.evidence_refs for item in calls]
    assert requests[0].response_payload == response.model_dump(mode="json")
    persisted_text = json.dumps(
        {
            "request": requests[0].response_payload,
            "scope": requests[0].idempotency_scope,
            "steps": [
                {
                    "scope": item.idempotency_scope,
                    "hash": item.idempotency_key_hash,
                }
                for item in steps
            ],
        },
        sort_keys=True,
    )
    assert RAW_IDEMPOTENCY_KEY not in persisted_text


@pytest.mark.parametrize(
    ("plan_status", "clear_current_version", "expected_reason"),
    [
        ("previewed", False, "workflow_plan_not_active"),
        ("active", True, "workflow_version_not_current"),
    ],
)
@pytest.mark.asyncio
async def test_product_run_gate_rejects_inactive_plan_or_noncurrent_version_before_write(
    plan_status: str,
    clear_current_version: bool,
    expected_reason: str,
    session: AsyncSession,
) -> None:
    seed = await _seed_resolved_version(session)
    plan = await session.get(WorkflowPlan, seed.plan_id)
    assert plan is not None
    plan.status = plan_status
    if clear_current_version:
        plan.current_version_id = None
    await session.commit()

    with pytest.raises(
        WorkflowVersionNotFixtureRunnableError,
        match=f"workflow_version_not_fixture_runnable:{expected_reason}",
    ):
        await _create_run(session, seed)

    assert await _row_count(session, WorkflowRun) == 0
    assert await _row_count(session, StepRun) == 0
    assert await _row_count(session, WorkflowRunRequest) == 0


@pytest.mark.asyncio
async def test_shadow_fixture_profile_persists_bounded_equivalence_evidence(
    session: AsyncSession,
) -> None:
    seed = await _seed_resolved_version(session)
    payload = WorkflowFixtureRunCreateRequest(
        expected_preview_fingerprint=seed.version.preview_fingerprint,
        fixture_profile_id="fixture-shadow-v1",
    )

    response = await _create_run(session, seed, payload=payload)

    comparisons = list(
        (
            await session.execute(
                select(WorkflowShadowComparison).order_by(WorkflowShadowComparison.requirement_ref)
            )
        )
        .scalars()
        .all()
    )
    assert response.run.status is WorkflowRunStatus.COMPLETED
    assert len(comparisons) == response.run.completed_steps == 3
    assert all(item.sample_rate == 0.05 for item in comparisons)
    assert all(item.max_items == 10 for item in comparisons)
    assert all(item.sampled_items == 1 for item in comparisons)
    assert all(item.matched_items == 1 for item in comparisons)
    assert all(item.equivalence_status == "equivalent" for item in comparisons)
    assert all(
        item.routing_recommendation == "eligible_for_governance_review" for item in comparisons
    )
    assert all(item.catalog_mutation_applied is False for item in comparisons)
    assert all(item.route_ranking_mutation_applied is False for item in comparisons)
    assert all(item.provider_call_attempted is False for item in comparisons)
    assert all(item.credential_read_attempted is False for item in comparisons)

    replay = await _create_run(session, seed, payload=payload)

    assert replay.idempotent_replay is True
    assert await _row_count(session, WorkflowShadowComparison) == 3


@pytest.mark.asyncio
async def test_shadow_kernel_retains_required_field_difference_and_safe_recommendation(
    session: AsyncSession,
) -> None:
    seed = await _seed_resolved_version(session)
    contract = build_primary_execution_contracts(seed.preview)[0]
    loaded = load_registered_fixture_profile("fixture-shadow-v1")
    primary_receipt = execute_registered_fixture_step(loaded, contract)
    shadow_case = next(
        item
        for item in loaded.profile.cases
        if item.implementation_id == "fixture.fallback"
        and item.operation == contract.requirement.operation
    )
    assert shadow_case.records is not None
    shadow_case.records[0].content["text"] = "semantically different fixture text"

    comparison = compile_workflow_fixture_shadow_comparison(
        loaded,
        contract,
        primary_receipt,
    )

    assert comparison is not None
    assert comparison.sampled_items == 1
    assert comparison.matched_items == 0
    assert comparison.mismatched_items == 1
    assert comparison.equivalence_status == "different"
    assert comparison.routing_recommendation == "keep_primary_investigate_shadow"
    assert comparison.difference_evidence.mismatched_record_keys == ["id:fixture-shadow-search-001"]


@pytest.mark.asyncio
async def test_verified_zero_receipts_create_empty_valid_run(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = await _seed_resolved_version(session)
    original = execute_registered_fixture_step

    def return_verified_zero(
        loaded: LoadedWorkflowFixtureProfile,
        contract: PrimaryExecutionContract,
    ) -> WorkflowFixtureStepReceipt:
        return original(loaded, contract).model_copy(update={"records_count": 0})

    monkeypatch.setattr(execution, "execute_workflow_fixture_step", return_verified_zero)

    response = await _create_run(session, seed)

    assert response.run.status is WorkflowRunStatus.EMPTY_VALID
    assert response.run.status_reason_code == "verified_zero_result"
    assert response.run.impact_code == "no_records_in_scope"
    assert response.run.missing_fields == []
    assert response.run.recovery_action_codes == []
    assert response.run.completed_steps == response.run.total_steps == 3
    assert response.run.records_count == 0
    assert response.run.finished_at is not None
    assert len(response.steps) == 3
    assert all(item.status is WorkflowStepRunStatus.COMPLETED for item in response.steps)
    assert all(item.records_count == 0 for item in response.steps)


@pytest.mark.asyncio
async def test_dirty_session_is_rejected_before_fixture_or_database_write(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = await _seed_resolved_version(session)
    calls = 0
    original = execute_registered_fixture_step

    def spy(
        loaded: LoadedWorkflowFixtureProfile,
        contract: PrimaryExecutionContract,
    ) -> WorkflowFixtureStepReceipt:
        nonlocal calls
        calls += 1
        return original(loaded, contract)

    monkeypatch.setattr(execution, "execute_workflow_fixture_step", spy)
    session.add(
        User(
            email="pending-user@example.com",
            password_hash="not-a-real-secret",
            name="Pending",
            status="active",
        )
    )

    with pytest.raises(
        WorkflowExecutionTransactionStateError,
        match="workflow_execution_transaction_state_invalid",
    ):
        await create_workflow_fixture_run(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workflow_plan_id=seed.plan_id,
            workflow_version_id=seed.version_id,
            created_by_user_id=seed.user_id,
            payload=_request(seed),
            idempotency_key=RAW_IDEMPOTENCY_KEY,
            request_id="workflow-execution-service-dirty",
            generated_at=NOW + timedelta(minutes=1),
        )

    assert calls == 0
    await session.rollback()
    assert await _row_count(session, WorkflowRun) == 0
    assert await _row_count(session, StepRun) == 0
    assert await _row_count(session, WorkflowRunRequest) == 0


@pytest.mark.asyncio
async def test_all_fixture_receipts_preflight_before_first_durable_row(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = await _seed_resolved_version(session)
    calls = 0
    original = execute_registered_fixture_step

    def fail_second(
        loaded: LoadedWorkflowFixtureProfile,
        contract: PrimaryExecutionContract,
    ) -> WorkflowFixtureStepReceipt:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise WorkflowFixtureAdapterUnavailableError("workflow_fixture_adapter_unavailable")
        return original(loaded, contract)

    monkeypatch.setattr(execution, "execute_workflow_fixture_step", fail_second)

    with pytest.raises(WorkflowFixtureAdapterUnavailableError):
        await create_workflow_fixture_run(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            workflow_plan_id=seed.plan_id,
            workflow_version_id=seed.version_id,
            created_by_user_id=seed.user_id,
            payload=_request(seed),
            idempotency_key=RAW_IDEMPOTENCY_KEY,
            request_id="workflow-execution-service-preflight",
            generated_at=NOW + timedelta(minutes=1),
        )

    assert calls == 2
    assert await _row_count(session, WorkflowRun) == 0
    assert await _row_count(session, StepRun) == 0
    assert await _row_count(session, WorkflowRunRequest) == 0


@pytest.mark.asyncio
async def test_same_key_same_request_replays_without_adapter_or_database_write(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = await _seed_resolved_version(session)
    calls = 0
    original = execute_registered_fixture_step

    def spy(
        loaded: LoadedWorkflowFixtureProfile,
        contract: PrimaryExecutionContract,
    ) -> WorkflowFixtureStepReceipt:
        nonlocal calls
        calls += 1
        return original(loaded, contract)

    monkeypatch.setattr(execution, "execute_workflow_fixture_step", spy)
    created = await _create_run(session, seed)
    replay = await _create_run(session, seed)

    assert created.database_write is True
    assert replay.database_write is False
    assert replay.idempotent_replay is True
    assert replay.run == created.run
    assert replay.steps == created.steps
    assert calls == len(created.steps) == 3
    assert await _row_count(session, WorkflowRun) == 1
    assert await _row_count(session, StepRun) == 3
    assert await _row_count(session, WorkflowRunRequest) == 1


@pytest.mark.asyncio
async def test_retryable_step_persists_attempts_once_and_replay_does_not_reexecute(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = await _seed_resolved_version(session)
    calls = 0
    original = execute_registered_fixture_step

    def retry_first_attempt(
        loaded: LoadedWorkflowFixtureProfile,
        contract: PrimaryExecutionContract,
    ) -> WorkflowFixtureStepReceipt:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise WorkflowStepRetryableError("step_network_unavailable")
        return original(loaded, contract)

    monkeypatch.setattr(
        execution,
        "execute_workflow_fixture_step",
        retry_first_attempt,
    )
    created = await _create_run(session, seed)
    attempts_before_replay = list(
        (
            await session.execute(
                select(StepRunAttempt).order_by(
                    StepRunAttempt.step_run_id,
                    StepRunAttempt.attempt_number,
                )
            )
        )
        .scalars()
        .all()
    )

    replayed = await _create_run(session, seed)
    attempts_after_replay = list((await session.execute(select(StepRunAttempt))).scalars().all())

    first_step_attempts = sorted(
        (item for item in attempts_before_replay if item.step_run_id == created.steps[0].id),
        key=lambda item: item.attempt_number,
    )
    assert [item.status for item in first_step_attempts] == [
        "retryable_error",
        "succeeded",
    ]
    assert [item.backoff_ms for item in first_step_attempts] == [10, 0]
    assert len(attempts_before_replay) == len(attempts_after_replay) == 4
    assert len({item.attempt_key_hash for item in attempts_before_replay}) == 4
    assert calls == 4
    assert replayed.idempotent_replay is True
    assert replayed.database_write is False


@pytest.mark.parametrize(
    ("failure", "expected_calls", "expected_failure_code"),
    [
        (WorkflowStepRetryableError("step_rate_limited"), 3, "step_rate_limited"),
        (WorkflowStepTerminalError("step_request_rejected"), 1, "step_request_rejected"),
    ],
)
@pytest.mark.asyncio
async def test_recognized_step_failure_persists_held_run_and_attempt_ledger(
    failure: Exception,
    expected_calls: int,
    expected_failure_code: str,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = await _seed_resolved_version(session)
    calls = 0

    def fail_step(
        loaded: LoadedWorkflowFixtureProfile,
        contract: PrimaryExecutionContract,
    ) -> WorkflowFixtureStepReceipt:
        nonlocal calls
        _ = (loaded, contract)
        calls += 1
        raise failure

    monkeypatch.setattr(execution, "execute_workflow_fixture_step", fail_step)

    response = await _create_run(session, seed)
    decision = (await session.execute(select(WorkflowFallbackDecision))).scalar_one()

    assert calls == expected_calls
    assert response.run.status is WorkflowRunStatus.HELD
    assert response.steps[0].status is WorkflowStepRunStatus.FAILED
    assert decision.primary_failure_code == expected_failure_code
    assert await _row_count(session, WorkflowRun) == 1
    assert await _row_count(session, StepRun) == 1
    assert await _row_count(session, StepRunAttempt) == expected_calls
    assert await _row_count(session, WorkflowRunRequest) == 1


@pytest.mark.asyncio
async def test_same_key_different_request_conflicts_before_adapter(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = await _seed_resolved_version(session)
    calls = 0
    original = execute_registered_fixture_step

    def spy(
        loaded: LoadedWorkflowFixtureProfile,
        contract: PrimaryExecutionContract,
    ) -> WorkflowFixtureStepReceipt:
        nonlocal calls
        calls += 1
        return original(loaded, contract)

    monkeypatch.setattr(execution, "execute_workflow_fixture_step", spy)
    await _create_run(session, seed)
    conflicting = WorkflowFixtureRunCreateRequest(
        expected_preview_fingerprint=seed.version.preview_fingerprint,
        fixture_profile_id="different-registered-profile",
    )

    with pytest.raises(
        WorkflowExecutionIdempotencyConflictError,
        match="idempotency_conflict",
    ):
        await _create_run(session, seed, payload=conflicting)

    assert calls == 3
    assert await _row_count(session, WorkflowRun) == 1
    assert await _row_count(session, StepRun) == 3
    assert await _row_count(session, WorkflowRunRequest) == 1


@pytest.mark.asyncio
async def test_archived_project_replays_and_reads_but_rejects_new_run(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = await _seed_resolved_version(session)
    calls = 0
    original = execute_registered_fixture_step

    def spy(
        loaded: LoadedWorkflowFixtureProfile,
        contract: PrimaryExecutionContract,
    ) -> WorkflowFixtureStepReceipt:
        nonlocal calls
        calls += 1
        return original(loaded, contract)

    monkeypatch.setattr(execution, "execute_workflow_fixture_step", spy)
    created = await _create_run(session, seed)
    project = await session.get(Project, seed.project_id)
    assert project is not None
    project.status = "archived"
    await session.commit()

    replay = await _create_run(session, seed)
    assert replay.idempotent_replay is True
    assert replay.run.id == created.run.id
    assert calls == 3
    assert await get_workflow_run(
        session,
        seed.workspace_id,
        seed.project_id,
        created.run.id,
    )
    assert (
        len(
            await list_step_runs(
                session,
                seed.workspace_id,
                seed.project_id,
                created.run.id,
            )
        )
        == 3
    )

    with pytest.raises(
        WorkflowExecutionProjectNotActiveError,
        match="project_not_active",
    ):
        await _create_run(
            session,
            seed,
            idempotency_key="workflow-fixture-key-new-0002",
        )
    assert calls == 3


@pytest.mark.parametrize(
    "phase",
    [
        "after_run",
        "after_step_1",
        "after_step_2",
        "after_step_3",
        "before_response",
        "before_ledger",
    ],
)
@pytest.mark.asyncio
async def test_injected_persistence_phase_failure_rolls_back_every_row(
    phase: str,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = await _seed_resolved_version(session)
    step_call_count = 0

    async def add_run_then_fail(
        target_session: AsyncSession,
        run: WorkflowRun,
    ) -> WorkflowRun:
        await repository_add_workflow_run(target_session, run)
        raise RuntimeError("injected_after_run")

    async def add_steps_with_injection(
        target_session: AsyncSession,
        steps: Sequence[StepRun],
    ) -> tuple[StepRun, ...]:
        nonlocal step_call_count
        step_call_count += 1
        result = await repository_add_step_runs(target_session, steps)
        if phase == f"after_step_{step_call_count}":
            raise RuntimeError(phase)
        return result

    def fail_before_response(
        run: WorkflowRun,
        steps: tuple[StepRun, ...],
        **lineage: object,
    ) -> NoReturn:
        assert lineage["workflow_template_id"] == seed.template_id
        assert lineage["workflow_template_revision_id"] == seed.template_revision_id
        if run not in session or not all(step in session for step in steps):
            raise AssertionError("response_snapshot_created_before_persistence_phase")
        raise RuntimeError("before_response")

    async def fail_before_ledger(
        target_session: AsyncSession,
        request: WorkflowRunRequest,
    ) -> WorkflowRunRequest:
        assert request.workflow_run_id is not None
        raise RuntimeError("before_ledger")

    if phase == "after_run":
        monkeypatch.setattr(execution, "add_workflow_run", add_run_then_fail)
    elif phase.startswith("after_step_"):
        monkeypatch.setattr(execution, "add_step_runs", add_steps_with_injection)
    elif phase == "before_response":
        monkeypatch.setattr(execution, "_create_response", fail_before_response)
    else:
        monkeypatch.setattr(
            execution,
            "add_workflow_run_request",
            fail_before_ledger,
        )

    with pytest.raises(RuntimeError, match=phase):
        await _create_run(session, seed)

    assert await _row_count(session, WorkflowRun) == 0
    assert await _row_count(session, StepRun) == 0
    assert await _row_count(session, WorkflowRunRequest) == 0


@pytest.mark.parametrize(
    ("failure_kind", "expected_error"),
    [
        ("fingerprint", WorkflowVersionExpectedFingerprintConflictError),
        ("tampered", WorkflowVersionSnapshotInvalidError),
        ("unknown_profile", WorkflowFixtureProfileUnknownError),
        ("missing_case", WorkflowFixtureAdapterUnavailableError),
        ("non_runnable", WorkflowVersionNotFixtureRunnableError),
    ],
)
@pytest.mark.asyncio
async def test_preflight_failures_leave_zero_durable_rows(
    failure_kind: str,
    expected_error: type[Exception],
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    required_fields = None
    if failure_kind == "non_runnable":
        required_fields = ["id", "url", "text", "impossible_field"]
    seed = await _seed_resolved_version(
        session,
        required_fields=required_fields,
    )
    payload = _request(seed)
    if failure_kind == "fingerprint":
        payload = payload.model_copy(update={"expected_preview_fingerprint": "sha256:" + "f" * 64})
    elif failure_kind == "tampered":
        tampered = deepcopy(seed.version.plan_payload)
        tampered["unexpected"] = "tampered"
        seed.version.plan_payload = tampered
        await session.commit()
    elif failure_kind == "unknown_profile":
        payload = payload.model_copy(update={"fixture_profile_id": "not-registered"})
    elif failure_kind == "missing_case":
        loaded = load_registered_fixture_profile("fixture-primary-v1")
        loaded.profile.cases = [
            item
            for item in loaded.profile.cases
            if not (
                item.implementation_id == "fixture.primary"
                and item.platform.value == "youtube"
                and item.resource_type.value == "content"
                and item.operation.value == "search_discover"
            )
        ]

        def load_missing_case(profile_id: str) -> LoadedWorkflowFixtureProfile:
            del profile_id
            return loaded

        monkeypatch.setattr(
            execution,
            "load_workflow_fixture_profile",
            load_missing_case,
        )

    with pytest.raises(expected_error):
        await _create_run(session, seed, payload=payload)

    assert await _row_count(session, WorkflowRun) == 0
    assert await _row_count(session, StepRun) == 0
    assert await _row_count(session, WorkflowRunRequest) == 0


@pytest.mark.asyncio
async def test_primary_failure_persists_blocked_fallback_decision_and_replays_without_adapter(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = await _seed_resolved_version(session)
    request_payload = _request(seed)
    calls = 0

    def fail_primary(
        loaded: LoadedWorkflowFixtureProfile,
        contract: PrimaryExecutionContract,
    ) -> WorkflowFixtureStepReceipt:
        nonlocal calls
        _ = (loaded, contract)
        calls += 1
        raise WorkflowStepRetryableError("step_network_unavailable")

    monkeypatch.setattr(execution, "execute_workflow_fixture_step", fail_primary)

    response = await _create_run(session, seed, payload=request_payload)

    decisions = list((await session.execute(select(WorkflowFallbackDecision))).scalars().all())
    assert calls == 3
    assert len(decisions) == 1
    decision = decisions[0]
    gates = {item["gate"]: item for item in decision.gate_snapshot}
    assert decision.outcome == "blocked"
    assert decision.primary_failure_code == "step_network_unavailable"
    assert decision.primary_implementation_id == "fixture.primary"
    assert decision.fallback_implementation_id == "fixture.fallback"
    assert gates["trigger"]["status"] == "passed"
    assert gates["policy"]["status"] == "passed"
    assert gates["credential"]["status"] == "passed"
    assert gates["budget"]["code"] == "fallback_budget_not_applicable"
    assert gates["fields"]["code"] == "fallback_field_evidence_unavailable"
    assert gates["evidence"]["status"] == "passed"
    assert gates["approval"]["status"] == "passed"
    assert decision.switch_executed is False
    assert decision.provider_call_attempted is False
    assert decision.credential_read_attempted is False
    assert response.database_write is True
    assert response.idempotent_replay is False
    assert response.run.status.value == "held"
    assert response.run.status_reason_code == "fallback_blocked"
    assert response.run.impact_code == "step_not_completed_following_steps_not_started"
    assert response.run.finished_at is None
    assert response.run.completed_steps == 0
    assert response.run.records_count == 0
    assert response.run.recovery_action_codes == [
        "inspect_fallback_gate_evidence",
        "resolve_primary_failure",
    ]
    assert len(response.steps) == 1
    assert response.steps[0].status.value == "failed"
    assert response.steps[0].records_count == 0
    assert response.steps[0].fixture_case_id is None
    assert decision.workflow_run_id == response.run.id
    assert decision.step_run_id == response.steps[0].id
    assert await _row_count(session, WorkflowRun) == 1
    assert await _row_count(session, StepRun) == 1
    assert await _row_count(session, StepRunAttempt) == 3
    assert await _row_count(session, WorkflowRunRequest) == 1

    replay = await _create_run(session, seed, payload=request_payload)

    assert calls == 3
    assert replay.database_write is False
    assert replay.idempotent_replay is True
    assert replay.run.id == response.run.id
    assert await _row_count(session, WorkflowFallbackDecision) == 1
    assert await _row_count(session, WorkflowRun) == 1
    assert await _row_count(session, StepRunAttempt) == 3

    conflicting = WorkflowFixtureRunCreateRequest(
        expected_preview_fingerprint=request_payload.expected_preview_fingerprint,
        fixture_profile_id="different-registered-profile",
    )
    with pytest.raises(
        WorkflowExecutionIdempotencyConflictError,
        match="idempotency_conflict",
    ):
        await _create_run(session, seed, payload=conflicting)

    assert calls == 3
    assert await _row_count(session, WorkflowFallbackDecision) == 1


@pytest.mark.asyncio
async def test_non_idempotency_integrity_error_never_enters_replay_recovery(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = await _seed_resolved_version(session)
    recovery_calls = 0

    class OtherUniqueViolation(Exception):
        sqlstate = "23505"
        constraint_name = "uq_step_runs_run_step_ref"

    error = IntegrityError("INSERT step_runs", {}, OtherUniqueViolation())

    async def fail_attempt(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        raise error

    async def unexpected_recovery(*args: object, **kwargs: object) -> NoReturn:
        nonlocal recovery_calls
        del args, kwargs
        recovery_calls += 1
        raise AssertionError("non_idempotency_error_entered_recovery")

    monkeypatch.setattr(
        execution,
        "_create_workflow_fixture_run_attempt",
        fail_attempt,
    )
    monkeypatch.setattr(
        execution,
        "get_completed_workflow_run_request",
        unexpected_recovery,
    )

    with pytest.raises(IntegrityError) as captured:
        await _create_run(session, seed)

    assert captured.value is error
    assert recovery_calls == 0
