"""GET /api/tasks/runs/{run_id} 的路由级单元测试。"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun
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

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        async_client.session_factory = session_factory  # type: ignore[attr-defined]
        yield async_client

    app.dependency_overrides.clear()
    await engine.dispose()


async def _seed_run(
    session: AsyncSession,
    *,
    workspace_slug: str,
    workspace_name: str,
) -> TaskRun:
    user = User(
        email=f"{workspace_slug}@example.com",
        password_hash="test-hash",
        name=workspace_name,
    )
    session.add(user)
    await session.flush()

    workspace = Workspace(name=workspace_name, slug=workspace_slug, owner_id=user.id)
    session.add(workspace)
    await session.flush()

    project = Project(
        workspace_id=workspace.id,
        name=f"{workspace_name} Project",
        domain="ecommerce",
        owner_id=user.id,
    )
    session.add(project)
    await session.flush()

    source = Source(
        workspace_id=workspace.id,
        project_id=project.id,
        name=f"{workspace_name} Source",
        type="manual_json",
        config={},
    )
    session.add(source)
    await session.flush()

    task = CollectionTask(
        workspace_id=workspace.id,
        project_id=project.id,
        source_id=source.id,
        collector_type="manual_json",
        name=f"{workspace_name} Task",
        status="active",
    )
    session.add(task)
    await session.flush()

    run = TaskRun(
        task_id=task.id,
        workspace_id=workspace.id,
        status="success",
        started_at=datetime(2026, 10, 19, 8, 0, tzinfo=UTC),
        finished_at=datetime(2026, 10, 19, 8, 1, tzinfo=UTC),
        records_count=3,
        entities_count=2,
        error_message=None,
        error_traceback=None,
        logs=[
            {
                "step": "idempotency_key_recorded",
                "scope": "task_manual_run",
                "idempotency_key_hash": "hash-abc",
            }
        ],
        created_at=datetime(2026, 10, 19, 8, 0, tzinfo=UTC),
    )
    session.add(run)
    await session.commit()
    return run


@pytest.mark.asyncio
async def test_get_task_run_returns_matching_run(client: AsyncClient) -> None:
    async with client.session_factory() as session:  # type: ignore[attr-defined]
        run = await _seed_run(
            session,
            workspace_slug=DEMO_WORKSPACE_SLUG,
            workspace_name="Demo",
        )

    response = await client.get(f"/api/tasks/runs/{run.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(run.id)
    assert body["task_id"] == str(run.task_id)
    assert body["workspace_id"] == str(run.workspace_id)
    assert body["status"] == "success"
    assert body["records_count"] == 3
    assert body["entities_count"] == 2
    assert body["idempotency_scope"] == "task_manual_run"
    assert body["idempotency_key_hash"] == "hash-abc"

    # 与列表端点同形状：字段集合必须一致。
    list_response = await client.get("/api/tasks/runs")
    assert list_response.status_code == 200
    listed = [item for item in list_response.json() if item["id"] == str(run.id)]
    assert len(listed) == 1
    assert set(body) == set(listed[0])


@pytest.mark.asyncio
async def test_get_task_run_returns_404_for_unknown_run(client: AsyncClient) -> None:
    # demo workspace 必须存在，否则端点在查询前就返回 503。
    async with client.session_factory() as session:  # type: ignore[attr-defined]
        await _seed_run(
            session,
            workspace_slug=DEMO_WORKSPACE_SLUG,
            workspace_name="Demo",
        )

    response = await client.get(f"/api/tasks/runs/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "task_run_not_found"}


@pytest.mark.asyncio
async def test_get_task_run_returns_404_for_other_workspace(client: AsyncClient) -> None:
    async with client.session_factory() as session:  # type: ignore[attr-defined]
        await _seed_run(
            session,
            workspace_slug=DEMO_WORKSPACE_SLUG,
            workspace_name="Demo",
        )
        run = await _seed_run(
            session,
            workspace_slug="other-workspace",
            workspace_name="Other",
        )

    response = await client.get(f"/api/tasks/runs/{run.id}")

    # 跨 workspace 与不存在使用同一个 404，避免泄露 run 的存在性。
    assert response.status_code == 404
    assert response.json() == {"detail": "task_run_not_found"}

    # 证明该 run 实际存在，404 来自 workspace 过滤而不是行缺失。
    async with client.session_factory() as session:  # type: ignore[attr-defined]
        persisted = await session.get(TaskRun, run.id)
    assert persisted is not None
