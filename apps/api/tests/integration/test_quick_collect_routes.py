"""/api/quick-collect 路由契约测试。

quick-collect 是公开（免鉴权）的"一键采集"入口，控制台与 Skill 示例都直接打它，
此前**零测试覆盖**。这里守住两条边界：未知端点、未知 project_id 必须返回 400，
而不是 500 + 原始 SQL 栈（2026-10-09 生产实测：demo 项目被删后 quick-collect 500）。
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.workspaces import DEMO_WORKSPACE_SLUG


@pytest_asyncio.fixture()
async def client() -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncGenerator[object, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        async_client.session_factory = session_factory  # type: ignore[attr-defined]
        yield async_client

    app.dependency_overrides.clear()
    await engine.dispose()


async def _seed_demo_workspace_and_project(
    client: AsyncClient,
    *,
    with_workspace: bool = True,
) -> uuid.UUID:
    """建一个 demo workspace + 一个属于它的 project，返回 project_id。"""
    session_factory = client.session_factory  # type: ignore[attr-defined]
    async with session_factory() as session:
        owner = User(email="owner@example.com", password_hash="x", name="Owner")
        session.add(owner)
        await session.flush()

        workspace_id = uuid.uuid4()
        if with_workspace:
            session.add(
                Workspace(
                    id=workspace_id,
                    name="Demo",
                    slug=DEMO_WORKSPACE_SLUG,
                    owner_id=owner.id,
                )
            )
            await session.flush()

        project = Project(
            workspace_id=workspace_id,
            name="采集验证",
            domain="osint",
            owner_id=owner.id,
        )
        session.add(project)
        await session.commit()
        return project.id


@pytest.mark.asyncio
async def test_quick_collect_rejects_unknown_project_id(client: AsyncClient) -> None:
    await _seed_demo_workspace_and_project(client)

    response = await client.post(
        "/api/quick-collect",
        json={
            "project_id": str(uuid.uuid4()),
            "endpoint_type": "tikhub_youtube_search",
            "params": {"keyword": "python"},
        },
    )

    assert response.status_code == 400
    assert "Unknown project_id" in response.json()["detail"]


@pytest.mark.asyncio
async def test_quick_collect_project_check_runs_before_endpoint_lookup(
    client: AsyncClient,
) -> None:
    project_id = await _seed_demo_workspace_and_project(client)

    response = await client.post(
        "/api/quick-collect",
        json={
            "project_id": str(project_id),
            "endpoint_type": "not_a_real_endpoint",
            "params": {},
        },
    )

    # 既有项目通过了 project 校验，才会走到端点查表并报未知端点。
    assert response.status_code == 400
    assert "Unknown endpoint_type" in response.json()["detail"]


@pytest.mark.asyncio
async def test_quick_collect_without_demo_workspace_returns_503(
    client: AsyncClient,
) -> None:
    project_id = await _seed_demo_workspace_and_project(client, with_workspace=False)

    response = await client.post(
        "/api/quick-collect",
        json={"project_id": str(project_id), "endpoint_type": "tikhub_youtube_search"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "demo_workspace_unavailable"
