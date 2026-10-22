"""持久富集 worker 的领取、恢复与项目密钥额度。"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.enrichment import EnrichmentJob, EnrichmentRow
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.project_api_key import ProjectApiKey
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.services import enrichment_service
from data_intelligence_hub.services.enrichment_worker import EnrichmentWorkerRuntime


@pytest_asyncio.fixture()
async def factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        user_id = uuid.uuid4()
        workspace_id = uuid.uuid4()
        project_id = uuid.uuid4()
        session.add_all(
            [
                User(
                    id=user_id,
                    email="ew@example.com",
                    password_hash="x",
                    name="EW",
                    status="active",
                ),
                Workspace(id=workspace_id, name="EW", slug="ew", owner_id=user_id),
                Project(
                    id=project_id,
                    workspace_id=workspace_id,
                    name="P",
                    domain="mixed",
                    status="active",
                    owner_id=user_id,
                ),
            ]
        )
        await session.commit()
    session_factory.ids = {"user": user_id, "workspace": workspace_id, "project": project_id}  # type: ignore[attr-defined]
    yield session_factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_project_key_quota_is_consumed_per_row(
    factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ids = factory.ids  # type: ignore[attr-defined]
    async with factory() as session:
        workspace = await session.get(Workspace, ids["workspace"])
        assert workspace is not None
        key = ProjectApiKey(
            workspace_id=ids["workspace"], project_id=ids["project"], label="k",
            key_prefix="dih_q", key_hash="q" * 64, created_by_user_id=ids["user"],
            tool_allowlist=["enrich_list"], daily_collect_quota=1,
        )
        session.add(key)
        await session.flush()
        job = await enrichment_service.start_enrichment(
            session,
            workspace=workspace,
            project_id=ids["project"],
            name="j",
            query_template="查询 {domain}",
            items=[{"domain": "a.com"}, {"domain": "b.com"}],
            output_schema={"type": "object"},
            project_key_id=key.id,
        )

    async def fake_row(query: str, schema: dict):
        return {"query": query}, []

    monkeypatch.setattr(enrichment_service, "_run_row", fake_row)
    worker = EnrichmentWorkerRuntime(factory)
    assert await worker.run_once() is True
    async with factory() as session:
        current = await session.get(EnrichmentJob, job.id)
        rows = (
            await session.execute(
                select(EnrichmentRow)
                .where(EnrichmentRow.job_id == job.id)
                .order_by(EnrichmentRow.row_index)
            )
        ).scalars().all()
        stored_key = await session.get(ProjectApiKey, key.id)
    assert current is not None and current.status == "partial"
    assert [row.status for row in rows] == ["completed", "failed"]
    assert rows[1].error and "quota_exceeded" in rows[1].error
    assert stored_key is not None and stored_key.quota_used == 1

@pytest.mark.asyncio
async def test_worker_recovers_running_job_after_restart(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    ids = factory.ids  # type: ignore[attr-defined]
    async with factory() as session:
        job = EnrichmentJob(
            workspace_id=ids["workspace"],
            project_id=ids["project"],
            name="interrupted",
            query_template="查询 {domain}",
            output_schema={"type": "object"},
            status="running",
            total=1,
        )
        session.add(job)
        await session.commit()
        job_id = job.id

    worker = EnrichmentWorkerRuntime(factory)
    assert await worker.recover_interrupted() == 1
    async with factory() as session:
        recovered = await session.get(EnrichmentJob, job_id)
    assert recovered is not None
    assert recovered.status == "queued"
