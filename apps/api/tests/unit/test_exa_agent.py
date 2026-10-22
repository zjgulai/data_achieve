"""Exa Agent 采集器与异步研究入队。"""

from __future__ import annotations

import json
import uuid

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.collectors import exa_agent as agent_module
from data_intelligence_hub.collectors.exa_agent import ExaAgentCollector
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.run import Run, RunStatus
from data_intelligence_hub.models.task import CollectionTask
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.services.collector_service import _agent_cost_fields
from data_intelligence_hub.services.research_service import start_research


@pytest.fixture(autouse=True)
def restricted_network_mode(monkeypatch: pytest.MonkeyPatch):
    """provider_api 在 restricted 模式放行；离线模式会拒绝。"""
    from data_intelligence_hub.core.config import get_settings

    monkeypatch.setenv("COLLECTION_NETWORK_MODE", "restricted")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _client_factory(transport: httpx.MockTransport):
    def create(_key: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url="https://api.exa.ai", transport=transport)

    return create


@pytest.mark.asyncio
async def test_agent_collector_polls_until_completed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    submitted: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.method == "POST" and request.url.path == "/agent/runs":
            submitted.update(json.loads(request.content))
        if request.method == "POST" and request.url.path == "/agent/runs":
            return httpx.Response(201, json={"id": "run-1", "status": "running"})
        if request.url.path == "/agent/runs/run-1":
            if calls.count("GET /agent/runs/run-1") < 2:
                return httpx.Response(200, json={"id": "run-1", "status": "running"})
            return httpx.Response(
                200,
                json={
                    "id": "run-1",
                    "status": "completed",
                    "output": {
                        "text": "研究结论",
                        "structured": {"answer": 42},
                        "grounding": [{"url": "https://exa.ai"}],
                    },
                    "usage": {"searches": 3},
                    "costDollars": {"total": 0.1},
                },
            )
        return httpx.Response(404)

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setenv("EXA_API_KEY", "test-key")
    monkeypatch.setattr(agent_module, "_exa_client", _client_factory(httpx.MockTransport(handler)))
    monkeypatch.setattr(agent_module.asyncio, "sleep", no_sleep)

    collector = ExaAgentCollector(
        {"query": "研究 Exa", "effort": "medium", "poll_interval_seconds": 1}
    )
    result = await collector.collect()

    assert result.errors == []
    assert len(result.raw_records) == 1
    content = result.raw_records[0].content
    assert content["status"] == "completed"
    assert content["text"] == "研究结论"
    assert content["structured"] == {"answer": 42}
    assert content["agent_run_id"] == "run-1"
    assert "budget" not in submitted  # 固定 effort 不能发送 budget


@pytest.mark.asyncio
async def test_agent_timeout_cancels_remote_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.method == "POST" and request.url.path == "/agent/runs":
            return httpx.Response(201, json={"id": "run-timeout"})
        if request.method == "POST" and request.url.path.endswith("/cancel"):
            return httpx.Response(200, json={"status": "canceled"})
        return httpx.Response(200, json={"id": "run-timeout", "status": "running"})

    async def no_sleep(_seconds: float) -> None:
        return None

    clock = {"value": 0.0}
    monkeypatch.setenv("EXA_API_KEY", "test-key")
    monkeypatch.setattr(agent_module, "_exa_client", _client_factory(httpx.MockTransport(handler)))

    async def advance(_seconds: float) -> None:
        clock["value"] = 31.0

    monkeypatch.setattr(agent_module.asyncio, "sleep", advance)
    monkeypatch.setattr(agent_module.asyncio.get_event_loop(), "time", lambda: clock["value"])

    result = await ExaAgentCollector(
        {"query": "q", "effort": "auto", "timeout_seconds": 30}
    ).collect()

    assert result.raw_records == []
    assert any("timed out" in error for error in result.errors)
    assert "POST /agent/runs/run-timeout/cancel" in calls


@pytest.mark.asyncio
async def test_agent_collector_rejects_invalid_effort() -> None:
    collector = ExaAgentCollector({"query": "q", "effort": "turbo"})
    with pytest.raises(Exception) as exc:
        collector.validate_config()
    assert "effort" in str(exc.value)


@pytest_asyncio.fixture()
async def session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user_id = uuid.uuid4()
        workspace_id = uuid.uuid4()
        project_id = uuid.uuid4()
        session.add_all(
            [
                User(
                    id=user_id,
                    email="research@example.com",
                    password_hash="x",
                    name="Research",
                    status="active",
                ),
                Workspace(
                    id=workspace_id,
                    name="Research WS",
                    slug="research-ws",
                    owner_id=user_id,
                ),
                Project(
                    id=project_id,
                    workspace_id=workspace_id,
                    name="Research Project",
                    domain="mixed",
                    status="active",
                    owner_id=user_id,
                ),
            ]
        )
        await session.commit()
    factory.ids = {"workspace": workspace_id, "project": project_id}  # type: ignore[attr-defined]
    yield factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_start_research_creates_task_and_queued_run(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    ids = session_factory.ids  # type: ignore[attr-defined]
    async with session_factory() as session:
        workspace = await session.get(Workspace, ids["workspace"])
        assert workspace is not None
        run_id = await start_research(
            session,
            workspace=workspace,
            project_id=ids["project"],
            query="研究 Exa Agent",
            effort="low",
        )

    async with session_factory() as session:
        run = await session.get(Run, run_id)
        assert run is not None
        assert run.status == RunStatus.QUEUED
        assert run.trigger == "api"
        task = await session.get(CollectionTask, run.task_id)
        assert task is not None
        assert task.collector_type == "exa_agent"
        assert task.config["endpoint_type"] == "exa_agent_research"
        assert task.config["effort"] == "low"
        assert task.config["max_cost_dollars"] == 5
        assert task.config["run_timeout_seconds"] == 630
        assert task.status == "enabled"

@pytest.mark.asyncio
async def test_agent_resumes_existing_provider_run_without_second_post(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        return httpx.Response(
            200,
            json={
                "id": "existing-run",
                "status": "completed",
                "output": {"text": "resumed"},
            },
        )

    async def no_sleep(_seconds: float) -> None:
        return None

    async def existing(_local_id: str | None, _run_id: str | None) -> str:
        return "existing-run"

    monkeypatch.setenv("EXA_API_KEY", "test-key")
    monkeypatch.setattr(agent_module, "_exa_client", _client_factory(httpx.MockTransport(handler)))
    monkeypatch.setattr(agent_module.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(agent_module, "_load_provider_run_id", existing)

    result = await ExaAgentCollector(
        {"query": "q", "local_task_run_id": str(uuid.uuid4()), "poll_interval_seconds": 1}
    ).collect()

    assert result.raw_records[0].content["text"] == "resumed"
    assert not any(call == "POST /agent/runs" for call in calls)
    assert "GET /agent/runs/existing-run" in calls

@pytest.mark.asyncio
async def test_agent_non_retryable_poll_error_fails_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.method == "POST":
            return httpx.Response(201, json={"id": "run-401"})
        return httpx.Response(401, text="unauthorized")

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setenv("EXA_API_KEY", "test-key")
    monkeypatch.setattr(agent_module, "_exa_client", _client_factory(httpx.MockTransport(handler)))
    monkeypatch.setattr(agent_module.asyncio, "sleep", no_sleep)
    result = await ExaAgentCollector({"query": "q", "poll_interval_seconds": 1}).collect()

    assert result.raw_records == []
    assert any("HTTP 401" in error for error in result.errors)
    assert calls.count("GET /agent/runs/run-401") == 1


@pytest.mark.asyncio
async def test_agent_stop_reason_marks_partial_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(201, json={"id": "run-budget"})
        return httpx.Response(
            200,
            json={
                "id": "run-budget",
                "status": "completed",
                "stopReason": "budget_exhausted",
                "output": {"text": "partial"},
            },
        )

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setenv("EXA_API_KEY", "test-key")
    monkeypatch.setattr(agent_module, "_exa_client", _client_factory(httpx.MockTransport(handler)))
    monkeypatch.setattr(agent_module.asyncio, "sleep", no_sleep)
    result = await ExaAgentCollector({"query": "q", "poll_interval_seconds": 1}).collect()

    assert len(result.raw_records) == 1
    assert result.raw_records[0].content["stop_reason"] == "budget_exhausted"
    assert any("stopped early" in error for error in result.errors)

@pytest.mark.asyncio
async def test_start_research_maps_long_timeout_to_outer_budget(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    ids = session_factory.ids  # type: ignore[attr-defined]
    async with session_factory() as session:
        workspace = await session.get(Workspace, ids["workspace"])
        assert workspace is not None
        run_id = await start_research(
            session,
            workspace=workspace,
            project_id=ids["project"],
            query="long",
            timeout_seconds=900,
        )
        run = await session.get(Run, run_id)
        task = await session.get(CollectionTask, run.task_id) if run else None
    assert task is not None
    assert task.config["timeout_seconds"] == 900
    assert task.config["run_timeout_seconds"] == 930

def test_agent_cost_fields_parse_total() -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    from data_intelligence_hub.collectors.base import CollectorRawRecord

    record = CollectorRawRecord(
        record_type="agent_research",
        source_url=None,
        content={"cost": {"total": 0.125}},
        collected_at=datetime.now(UTC),
    )
    unit, quantity, unit_price, total = _agent_cost_fields("exa_agent", [record])
    assert unit == "run"
    assert quantity == Decimal("1")
    assert unit_price == Decimal("0.125")
    assert total == Decimal("0.125")
    assert _agent_cost_fields("exa_search", [record]) == (None, None, None, None)
