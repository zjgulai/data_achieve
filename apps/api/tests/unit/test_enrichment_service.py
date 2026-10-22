"""列表富集：后台逐行执行与状态。"""

from __future__ import annotations

import asyncio
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
async def test_enrichment_processes_rows_in_background(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_run_row(query: str, schema: dict):
        calls.append(query)
        return {"summary": f"result for {query}"}, ["https://exa.ai"]

    monkeypatch.setattr(enrichment_service, "_run_row", fake_run_row)
    monkeypatch.setattr(enrichment_service, "_session_factory", session_factory)

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
            output_schema={"type": "object"},
        )

    for _ in range(50):
        async with session_factory() as session:
            current = await enrichment_service.get_job(session, ids["workspace"], job.id)
            if current is not None and current.status in {"completed", "partial"}:
                rows = await enrichment_service.get_rows(session, job.id)
                break
        await asyncio.sleep(0.02)
    else:  # pragma: no cover - 超时守卫
        raise AssertionError("enrichment job did not finish")

    assert current.status == "completed"
    assert current.processed == 2
    assert current.failed == 0
    assert [row.status for row in rows] == ["completed", "completed"]
    assert rows[0].output == {"summary": "result for 查询 exa.ai 的公司简介"}
    assert rows[0].citations == ["https://exa.ai"]
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_enrichment_rejects_empty_items(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    ids = session_factory.ids  # type: ignore[attr-defined]
    async with session_factory() as session:
        workspace = await session.get(Workspace, ids["workspace"])
        assert workspace is not None
        with pytest.raises(enrichment_service.EnrichmentError):
            await enrichment_service.start_enrichment(
                session,
                workspace=workspace,
                project_id=ids["project"],
                name="空",
                query_template="查询 {x}",
                items=[],
                output_schema={"type": "object"},
            )