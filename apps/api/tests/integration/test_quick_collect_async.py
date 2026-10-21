"""``POST /api/quick-collect/async`` 的迁移测试。

异步路径只写一行 ``runs(status=queued)``，不在请求进程里执行采集。
同步端点 ``POST /api/quick-collect`` 的行为保持不变。
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.core.security import create_access_token
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base, Run, TaskRun
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.repositories.workspaces import DEMO_WORKSPACE_SLUG
from data_intelligence_hub.services.run_queue import claim_next_run, resolve_runs_table

_LAST_OWNER_ID: uuid.UUID | None = None


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


async def _seed_demo_workspace_and_project(client: AsyncClient) -> uuid.UUID:
    session_factory = client.session_factory  # type: ignore[attr-defined]
    async with session_factory() as session:
        owner = User(email="async-owner@example.com", password_hash="x", name="Owner")
        session.add(owner)
        await session.flush()

        workspace_id = uuid.uuid4()
        session.add(
            Workspace(
                id=workspace_id,
                name="Demo",
                slug=DEMO_WORKSPACE_SLUG,
                owner_id=owner.id,
            )
        )
        await session.flush()
        session.add(
            WorkspaceMember(workspace_id=workspace_id, user_id=owner.id, role="owner")
        )
        await session.flush()

        project = Project(
            workspace_id=workspace_id,
            name="异步采集",
            domain="osint",
            owner_id=owner.id,
        )
        session.add(project)
        await session.commit()
        global _LAST_OWNER_ID
        _LAST_OWNER_ID = owner.id
        return project.id


def _authenticate(client: AsyncClient) -> None:
    assert _LAST_OWNER_ID is not None, "seed must run before authenticate"
    client.cookies.set("access_token", create_access_token(_LAST_OWNER_ID))


@pytest.mark.asyncio
async def test_async_quick_collect_enqueues_run_without_executing(
    client: AsyncClient,
) -> None:
    project_id = await _seed_demo_workspace_and_project(client)
    _authenticate(client)

    response = await client.post(
        "/api/quick-collect/async",
        json={
            "project_id": str(project_id),
            "endpoint_type": "generic_web",
            "params": {"url": "https://example.com"},
            "label": "[test] async generic_web",
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    run_id = uuid.UUID(body["run_id"])
    task_id = uuid.UUID(body["task_id"])
    assert body["source_id"]

    session_factory = client.session_factory  # type: ignore[attr-defined]
    async with session_factory() as session:
        run = await session.get(Run, run_id)
        assert run is not None
        assert run.status == "queued"
        assert run.task_id == task_id
        assert run.lease_expires_at is None
        task_runs = list((await session.execute(select(TaskRun))).scalars().all())
        assert task_runs == []

    # 队列可以直接领取这一行。worker 用 task_id 找到待执行任务。
    async with session_factory() as session:
        claimed = await claim_next_run(
            session,
            "test-worker",
            lease_seconds=60,
            table=resolve_runs_table(),
        )
        await session.commit()
    assert claimed is not None
    assert claimed.run_id == run_id
    assert claimed.task_id == task_id


@pytest.mark.asyncio
async def test_sync_quick_collect_still_returns_task_run(client: AsyncClient) -> None:
    """同步端点仍同步返回 TaskRun。这里只验证路由仍可调用。"""
    project_id = await _seed_demo_workspace_and_project(client)
    _authenticate(client)

    response = await client.post(
        "/api/quick-collect",
        json={
            "project_id": str(project_id),
            "endpoint_type": "aliens_eye_basic",
            "params": {
                "username": "nobody",
                "schedule_policy": "auto_freshness",
                "execution_origin": "scheduler",
            },
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {
        "task_run_id",
        "task_id",
        "source_id",
        "status",
        "records_count",
        "error_message",
        "records",
        "output",
        "usage",
        "timing",
    }
