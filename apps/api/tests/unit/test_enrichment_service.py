"""列表富集：持久队列、逐行执行与恢复。"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.services import enrichment_service
from data_intelligence_hub.services.enrichment_worker import EnrichmentWorkerRuntime


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
                    email="enrich@example.com",
                    password_hash="x",
                    name="Enrich",
                    status="active",
                ),
                Workspace(
                    id=workspace_id,
                    name="Enrich WS",
                    slug="enrich-ws",
                    owner_id=user_id,
                ),
                Project(
                    id=project_id,
                    workspace_id=workspace_id,
                    name="Enrich Project",
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
async def test_enrichment_worker_processes_queued_rows(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_run_row(query: str, schema: dict):
        calls.append(query)
        return {"summary": f"result for {query}"}, [{"url": "https://exa.ai"}]

    monkeypatch.setattr(enrichment_service, "_run_row", fake_run_row)
    ids = session_factory.ids  # type: ignore[attr-defined]
    async with session_factory() as session:
        workspace = await session.get(Workspace, ids["workspace"])
        assert workspace is not None
        job = await enrichment_service.start_enrichment(
            session,
            workspace=workspace,
            project_id=ids["project"],
            name="公司富集",
            query_template="查询 {domain} 的公司简介",
            items=[{"domain": "exa.ai"}, {"domain": "openai.com"}],
            output_schema={"type": "object", "properties": {"summary": {"type": "string"}}},
        )
        assert job.status == "queued"

    worker = EnrichmentWorkerRuntime(session_factory, poll_interval_seconds=0.01)
    assert await worker.run_once() is True

    async with session_factory() as session:
        current = await enrichment_service.get_job(session, ids["workspace"], job.id)
        rows = await enrichment_service.get_rows(session, job.id)
    assert current is not None
    assert current.status == "completed"
    assert current.processed == 2
    assert current.failed == 0
    assert [row.status for row in rows] == ["completed", "completed"]
    assert rows[0].output == {"summary": "result for 查询 exa.ai 的公司简介"}
    assert rows[0].citations == [{"url": "https://exa.ai"}]
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_worker_recovers_interrupted_jobs(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    ids = session_factory.ids  # type: ignore[attr-defined]
    async with session_factory() as session:
        workspace = await session.get(Workspace, ids["workspace"])
        assert workspace is not None
        job = await enrichment_service.start_enrichment(
            session,
            workspace=workspace,
            project_id=ids["project"],
            name="恢复测试",
            query_template="查询 {domain}",
            items=[{"domain": "exa.ai"}],
            output_schema={"type": "object"},
        )
        job.status = "running"
        await session.commit()

    worker = EnrichmentWorkerRuntime(session_factory)
    assert await worker.recover_interrupted() == 1
    async with session_factory() as session:
        recovered = await enrichment_service.get_job(session, ids["workspace"], job.id)
    assert recovered is not None
    assert recovered.status == "queued"


@pytest.mark.asyncio
async def test_enrichment_rejects_pii_schema_and_bad_template(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    ids = session_factory.ids  # type: ignore[attr-defined]
    async with session_factory() as session:
        workspace = await session.get(Workspace, ids["workspace"])
        assert workspace is not None
        with pytest.raises(enrichment_service.EnrichmentError, match="pii"):
            await enrichment_service.start_enrichment(
                session,
                workspace=workspace,
                project_id=ids["project"],
                name="PII",
                query_template="查询 {domain}",
                items=[{"domain": "exa.ai"}],
                output_schema={"type": "object", "properties": {"email": {"type": "string"}}},
            )
        with pytest.raises(enrichment_service.EnrichmentError, match="placeholder"):
            await enrichment_service.start_enrichment(
                session,
                workspace=workspace,
                project_id=ids["project"],
                name="坏模板",
                query_template="查询 {{domain}}",
                items=[{"domain": "exa.ai"}],
                output_schema={"type": "object"},
            )
