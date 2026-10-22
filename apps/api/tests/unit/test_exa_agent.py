"""Exa Agent 采集器与异步研究入队。"""

from __future__ import annotations

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

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
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
        assert run.trigger == "mcp"
        task = await session.get(CollectionTask, run.task_id)
        assert task is not None
        assert task.collector_type == "exa_agent"
        assert task.config["endpoint_type"] == "exa_agent_research"
        assert task.config["effort"] == "low"
        assert task.config["max_cost_dollars"] == 5
        assert task.status == "enabled"