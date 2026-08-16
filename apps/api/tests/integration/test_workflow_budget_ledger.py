from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.workflow_execution import WorkflowBudgetLedgerEntry
from data_intelligence_hub.schemas.workflow_budget import (
    WorkflowBudgetCharge,
    WorkflowBudgetPolicy,
)
from data_intelligence_hub.schemas.workflow_resume import (
    WorkflowCheckpointPageResult,
    WorkflowStepResumeIdentity,
)
from data_intelligence_hub.services.workflow_execution.budget import (
    WorkflowBudgetContractError,
    execute_budgeted_fixture_step_pages,
)

NOW = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64


@pytest_asyncio.fixture()
async def sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


def _identity(**changes: object) -> WorkflowStepResumeIdentity:
    payload: dict[str, object] = {
        "execution_session_id": uuid.UUID("10000000-0000-0000-0000-000000000008"),
        "workspace_id": uuid.UUID("20000000-0000-0000-0000-000000000001"),
        "project_id": uuid.UUID("30000000-0000-0000-0000-000000000001"),
        "workflow_plan_id": uuid.UUID("40000000-0000-0000-0000-000000000001"),
        "workflow_version_id": uuid.UUID("50000000-0000-0000-0000-000000000001"),
        "step_ref": "step://youtube/search",
        "requirement_ref": "requirement://youtube/search",
        "implementation_id": "fixture.youtube.search.v1",
        "fixture_profile_id": "fixture-payload-v2",
        "fixture_profile_hash": DIGEST_A,
        "step_input_digest": DIGEST_B,
    }
    payload.update(changes)
    return WorkflowStepResumeIdentity.model_validate(payload)


def _policy(**changes: object) -> WorkflowBudgetPolicy:
    payload: dict[str, object] = {
        "max_requests": 100,
        "max_items": 100,
        "quota_ceilings": {"youtube.search": 100},
        "max_cost_usd": Decimal("100"),
        "max_time_ms": 100_000,
        "evidence_refs": ["policy://fixture-budget/v1"],
    }
    payload.update(changes)
    return WorkflowBudgetPolicy.model_validate(payload)


def _charge(**changes: object) -> WorkflowBudgetCharge:
    payload: dict[str, object] = {
        "request_count": 1,
        "item_count": 2,
        "quota_units": {"youtube.search": 2},
        "estimated_cost_usd": Decimal("0.10"),
        "reserved_time_ms": 100,
    }
    payload.update(changes)
    return WorkflowBudgetCharge.model_validate(payload)


def _page_result(page_number: int) -> WorkflowCheckpointPageResult:
    terminal = page_number == 3
    return WorkflowCheckpointPageResult(
        records_count=2,
        next_cursor=None if terminal else f"cursor-{page_number}",
        output_digest=(DIGEST_A, DIGEST_B, DIGEST_C)[page_number - 1],
        terminal=terminal,
        evidence_refs=[f"fixture://page/{page_number}"],
    )


@pytest.mark.parametrize(
    ("policy_changes", "expected_code"),
    [
        ({"max_requests": 1}, "workflow_request_budget_exceeded"),
        ({"max_items": 2}, "workflow_item_budget_exceeded"),
        (
            {"quota_ceilings": {"youtube.search": 2}},
            "workflow_quota_budget_exceeded",
        ),
        ({"max_cost_usd": Decimal("0.10")}, "workflow_cost_budget_exceeded"),
        ({"max_time_ms": 100}, "workflow_time_budget_exceeded"),
    ],
)
@pytest.mark.asyncio
async def test_each_budget_dimension_holds_before_second_executor_call(
    sessions: async_sessionmaker[AsyncSession],
    policy_changes: dict[str, object],
    expected_code: str,
) -> None:
    executor_calls: list[int] = []

    async def executor(
        cursor: str | None,
        page_number: int,
        side_effect_key: str,
    ) -> WorkflowCheckpointPageResult:
        del cursor, side_effect_key
        executor_calls.append(page_number)
        return _page_result(page_number)

    async with sessions() as session:
        result = await execute_budgeted_fixture_step_pages(
            session,
            identity=_identity(),
            policy=_policy(**policy_changes),
            charge_for_page=lambda _cursor, _page: _charge(),
            executor=executor,
            clock=lambda: NOW,
        )

    assert result.status == "held"
    assert result.held_reason_code == expected_code
    assert result.held_before_executor
    assert result.next_page_number == 2
    assert result.next_cursor == "cursor-1"
    assert result.confirmed_pages == 1
    assert result.executor_calls == 1
    assert result.budget_entries_written == 2
    assert executor_calls == [1]
    assert [entry.status for entry in result.entries] == ["reserved", "blocked"]
    assert result.entries[-1].cumulative_request_count == 1
    assert result.entries[-1].cumulative_item_count == 2
    assert result.entries[-1].cumulative_quota_units == {"youtube.search": 2}
    assert result.entries[-1].cumulative_cost_usd == Decimal("0.10")
    assert result.entries[-1].cumulative_time_ms == 100


@pytest.mark.asyncio
async def test_terminal_replay_adds_no_charge_and_makes_no_executor_call(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    executor_calls: list[int] = []

    async def executor(
        cursor: str | None,
        page_number: int,
        side_effect_key: str,
    ) -> WorkflowCheckpointPageResult:
        del cursor, side_effect_key
        executor_calls.append(page_number)
        return _page_result(page_number)

    policy = _policy(
        max_requests=3,
        max_items=6,
        quota_ceilings={"youtube.search": 6},
        max_cost_usd=Decimal("0.30"),
        max_time_ms=300,
    )
    async with sessions() as first_session:
        first = await execute_budgeted_fixture_step_pages(
            first_session,
            identity=_identity(),
            policy=policy,
            charge_for_page=lambda _cursor, _page: _charge(),
            executor=executor,
            clock=lambda: NOW,
        )
    assert first.status == "completed"
    assert first.budget_entries_written == 3
    assert first.executor_calls == 3

    async with sessions() as replay_session:
        replay = await execute_budgeted_fixture_step_pages(
            replay_session,
            identity=_identity(),
            policy=policy,
            charge_for_page=lambda _cursor, _page: _charge(),
            executor=executor,
            clock=lambda: NOW,
        )
    assert replay.status == "completed"
    assert not replay.account_created
    assert replay.budget_entries_written == 0
    assert replay.reservation_replays == 0
    assert replay.executor_calls == 0
    assert len(replay.entries) == 3
    assert executor_calls == [1, 2, 3]


@pytest.mark.asyncio
async def test_crash_restart_replays_reservation_without_double_charge(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    cached_results: dict[str, WorkflowCheckpointPageResult] = {}
    physical_effects: list[str] = []
    delivered_keys: list[str] = []
    should_crash = True

    async def crash_once_executor(
        cursor: str | None,
        page_number: int,
        side_effect_key: str,
    ) -> WorkflowCheckpointPageResult:
        nonlocal should_crash
        del cursor
        delivered_keys.append(side_effect_key)
        if side_effect_key not in cached_results:
            physical_effects.append(side_effect_key)
            cached_results[side_effect_key] = _page_result(page_number)
        if should_crash:
            should_crash = False
            raise RuntimeError("simulated_process_exit_after_effect")
        return cached_results[side_effect_key]

    async with sessions() as interrupted_session:
        with pytest.raises(RuntimeError, match="simulated_process_exit_after_effect"):
            await execute_budgeted_fixture_step_pages(
                interrupted_session,
                identity=_identity(),
                policy=_policy(),
                charge_for_page=lambda _cursor, _page: _charge(),
                executor=crash_once_executor,
                max_pages=1,
                clock=lambda: NOW,
            )

    async with sessions() as restarted_session:
        recovered = await execute_budgeted_fixture_step_pages(
            restarted_session,
            identity=_identity(),
            policy=_policy(),
            charge_for_page=lambda _cursor, _page: _charge(),
            executor=crash_once_executor,
            max_pages=1,
            clock=lambda: NOW,
        )
    assert recovered.status == "in_progress"
    assert recovered.budget_entries_written == 0
    assert recovered.reservation_replays == 1
    assert recovered.executor_calls == 1
    assert len(recovered.entries) == 1
    assert recovered.entries[0].status == "reserved"
    assert recovered.entries[0].cumulative_request_count == 1
    assert delivered_keys[0] == delivered_keys[1]
    assert physical_effects == [delivered_keys[0]]


@pytest.mark.asyncio
async def test_policy_change_and_ledger_tampering_fail_closed(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async def executor(
        cursor: str | None,
        page_number: int,
        side_effect_key: str,
    ) -> WorkflowCheckpointPageResult:
        del cursor, side_effect_key
        return _page_result(page_number)

    async with sessions() as first_session:
        await execute_budgeted_fixture_step_pages(
            first_session,
            identity=_identity(),
            policy=_policy(),
            charge_for_page=lambda _cursor, _page: _charge(),
            executor=executor,
            max_pages=1,
            clock=lambda: NOW,
        )

    async with sessions() as conflict_session:
        with pytest.raises(
            WorkflowBudgetContractError,
            match="workflow_budget_account_conflict",
        ):
            await execute_budgeted_fixture_step_pages(
                conflict_session,
                identity=_identity(),
                policy=_policy(max_requests=99),
                charge_for_page=lambda _cursor, _page: _charge(),
                executor=executor,
                max_pages=1,
                clock=lambda: NOW,
            )

    async with sessions() as mutation_session, mutation_session.begin():
        await mutation_session.execute(
            update(WorkflowBudgetLedgerEntry).values(ledger_digest=DIGEST_C)
        )

    async with sessions() as tampered_session:
        with pytest.raises(
            WorkflowBudgetContractError,
            match="workflow_budget_ledger_digest_invalid",
        ):
            await execute_budgeted_fixture_step_pages(
                tampered_session,
                identity=_identity(),
                policy=_policy(),
                charge_for_page=lambda _cursor, _page: _charge(),
                executor=executor,
                max_pages=1,
                clock=lambda: NOW,
            )
        persisted = (await tampered_session.execute(select(WorkflowBudgetLedgerEntry))).scalar_one()
        assert persisted.ledger_digest == DIGEST_C
