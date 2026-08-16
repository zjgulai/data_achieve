from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.schemas.workflow_resume import (
    WorkflowCheckpointPageResult,
    WorkflowStepResumeIdentity,
)
from data_intelligence_hub.services.workflow_execution.resume import (
    WorkflowCheckpointChainInvalidError,
    resume_fixture_step_pages,
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
        "execution_session_id": uuid.UUID("10000000-0000-0000-0000-000000000001"),
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


def _page_result(page_number: int) -> WorkflowCheckpointPageResult:
    terminal = page_number == 3
    return WorkflowCheckpointPageResult(
        records_count=2,
        next_cursor=None if terminal else f"cursor-{page_number}",
        output_digest=(DIGEST_A, DIGEST_B, DIGEST_C)[page_number - 1],
        terminal=terminal,
        evidence_refs=[f"fixture://page/{page_number}"],
    )


def test_page_result_rejects_any_live_or_persistence_boundary_claim() -> None:
    with pytest.raises(ValidationError):
        WorkflowCheckpointPageResult(
            records_count=1,
            next_cursor=None,
            output_digest=DIGEST_A,
            terminal=True,
            evidence_refs=["fixture://page/1"],
            provider_call_attempted=True,  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_resume_starts_after_latest_confirmed_cursor_and_terminal_replay_is_read_only(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    physical_effects: list[str] = []
    cached_results: dict[str, WorkflowCheckpointPageResult] = {}
    observed_cursors: list[tuple[int, str | None]] = []

    async def executor(
        cursor: str | None,
        page_number: int,
        side_effect_key: str,
    ) -> WorkflowCheckpointPageResult:
        observed_cursors.append((page_number, cursor))
        if side_effect_key not in cached_results:
            physical_effects.append(side_effect_key)
            cached_results[side_effect_key] = _page_result(page_number)
        return cached_results[side_effect_key]

    async with sessions() as first_session:
        first = await resume_fixture_step_pages(
            first_session,
            identity=_identity(),
            executor=executor,
            max_pages=1,
            clock=lambda: NOW,
        )
    assert not first.terminal
    assert first.next_cursor == "cursor-1"
    assert first.pages_executed == first.database_writes == 1
    assert first.resumed_from_page == 0

    async with sessions() as restarted_session:
        resumed = await resume_fixture_step_pages(
            restarted_session,
            identity=_identity(),
            executor=executor,
            clock=lambda: NOW,
        )
    assert resumed.terminal
    assert resumed.next_cursor is None
    assert resumed.resumed_from_page == 1
    assert resumed.pages_executed == resumed.database_writes == 2
    assert resumed.records_count == 6
    assert [item.page_number for item in resumed.checkpoints] == [1, 2, 3]
    assert observed_cursors == [(1, None), (2, "cursor-1"), (3, "cursor-2")]
    assert len(physical_effects) == 3

    async with sessions() as replay_session:
        replay = await resume_fixture_step_pages(
            replay_session,
            identity=_identity(),
            executor=executor,
            clock=lambda: NOW,
        )
    assert replay.terminal
    assert replay.checkpoint_replay
    assert replay.pages_executed == replay.database_writes == 0
    assert len(physical_effects) == 3
    assert observed_cursors == [(1, None), (2, "cursor-1"), (3, "cursor-2")]


@pytest.mark.asyncio
async def test_restart_reuses_same_side_effect_key_after_crash_before_checkpoint(
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
            await resume_fixture_step_pages(
                interrupted_session,
                identity=_identity(),
                executor=crash_once_executor,
                max_pages=1,
                clock=lambda: NOW,
            )

    async with sessions() as restarted_session:
        recovered = await resume_fixture_step_pages(
            restarted_session,
            identity=_identity(),
            executor=crash_once_executor,
            max_pages=1,
            clock=lambda: NOW,
        )
    assert recovered.pages_executed == 1
    assert delivered_keys[0] == delivered_keys[1]
    assert physical_effects == [delivered_keys[0]]


@pytest.mark.asyncio
async def test_persisted_checkpoint_identity_conflict_fails_closed(
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
        await resume_fixture_step_pages(
            first_session,
            identity=_identity(),
            executor=executor,
            max_pages=1,
            clock=lambda: NOW,
        )

    async with sessions() as conflicting_session:
        with pytest.raises(
            WorkflowCheckpointChainInvalidError,
            match="workflow_checkpoint_identity_conflict",
        ):
            await resume_fixture_step_pages(
                conflicting_session,
                identity=_identity(implementation_id="fixture.youtube.search.v2"),
                executor=executor,
                max_pages=1,
                clock=lambda: NOW,
            )
