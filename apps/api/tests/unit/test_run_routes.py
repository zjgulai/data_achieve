"""``/api/runs`` 五个端点的路由级单元测试。

覆盖十一条语义：

1. 无 cookie 一律 401。
2. 跨工作区读取一律 404。
3. 创建后状态是 ``queued``。
4. 同幂等键二次创建返回同一 id。
5. 取消终态运行返回 409。
6. outcome 聚合字段齐全。
7. 缺少 ``task_id`` 返回 422 业务码，且 ``runs`` 表行数不变。
8. ``task_id`` 指向不存在的任务时返回 404，且 ``runs`` 表行数不变。
9. ``task_id`` 属于别的 workspace 时返回 404，且 ``runs`` 表行数不变。
10. ``task_id`` 属于同 workspace 的另一个 project 时返回 404，且 ``runs`` 表行数不变。
11. 采集任务未启用时返回 409，且 ``runs`` 表行数不变。
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import NamedTuple

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.core.security import create_access_token
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base, Run
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.run import (
    RunOutcome,
    RunStatus,
    RunStepStatus,
)
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.repositories.runs import add_step, create_run

_MISSING_RUN_ID = uuid.uuid4()


class SeededWorkspace(NamedTuple):
    """一个测试工作区的最小种子。"""

    user_id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    task_id: uuid.UUID


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


async def _seed_workspace(
    client: AsyncClient,
    *,
    slug: str,
    name: str,
) -> SeededWorkspace:
    """种一个用户、一个工作区与一个项目。"""
    session_factory = client.session_factory  # type: ignore[attr-defined]
    async with session_factory() as session:
        user = User(
            email=f"{slug}@example.com",
            password_hash="test-hash",
            name=name,
            status="active",
        )
        session.add(user)
        await session.flush()

        workspace = Workspace(name=name, slug=slug, owner_id=user.id)
        session.add(workspace)
        await session.flush()

        session.add(
            WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
        )
        project = Project(
            workspace_id=workspace.id,
            name=f"{name} Project",
            domain="ecommerce",
            owner_id=user.id,
        )
        session.add(project)
        await session.flush()

        source = Source(
            workspace_id=workspace.id,
            project_id=project.id,
            name=f"{name} Source",
            type="generic_web",
            url=None,
            config={"endpoint_type": "generic_web"},
            schedule_cron=None,
            enabled=True,
        )
        session.add(source)
        await session.flush()

        task = CollectionTask(
            workspace_id=workspace.id,
            project_id=project.id,
            source_id=source.id,
            collector_type="generic_web",
            name=f"{name} Task",
            schedule_cron=None,
            status="enabled",
            config={"endpoint_type": "generic_web"},
        )
        session.add(task)
        await session.commit()

        return SeededWorkspace(
            user_id=user.id,
            workspace_id=workspace.id,
            project_id=project.id,
            task_id=task.id,
        )


def _authenticate(client: AsyncClient, user_id: uuid.UUID) -> None:
    client.cookies.set("access_token", create_access_token(user_id))


async def _run_count(client: AsyncClient, workspace_id: uuid.UUID) -> int:
    """返回一个工作区的运行行数。用于断言拒绝请求没有副作用。"""
    session_factory = client.session_factory  # type: ignore[attr-defined]
    async with session_factory() as session:
        count = await session.scalar(
            select(func.count()).select_from(Run).where(Run.workspace_id == workspace_id)
        )
    return int(count or 0)


_AUTH_REQUIRED_CASES = [
    pytest.param(
        "POST",
        "/api/runs",
        {
            "json": {
                "project_id": str(uuid.uuid4()),
                "task_id": str(uuid.uuid4()),
                "endpoint_type": "generic_web",
            }
        },
        id="create",
    ),
    pytest.param("GET", f"/api/runs/{_MISSING_RUN_ID}", {}, id="detail"),
    pytest.param("POST", f"/api/runs/{_MISSING_RUN_ID}/cancel", {}, id="cancel"),
    pytest.param("GET", f"/api/runs/{_MISSING_RUN_ID}/steps", {}, id="steps"),
    pytest.param("GET", f"/api/runs/{_MISSING_RUN_ID}/outcome", {}, id="outcome"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "path", "kwargs"), _AUTH_REQUIRED_CASES)
async def test_every_endpoint_rejects_missing_cookie(
    client: AsyncClient,
    method: str,
    path: str,
    kwargs: dict[str, object],
) -> None:
    """五个端点都必须 fail-closed。无 cookie 一律 401。"""
    response = await client.request(method, path, **kwargs)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_run_starts_queued(client: AsyncClient) -> None:
    """创建后状态必须是 queued。详情端点必须返回同一行。"""
    seed = await _seed_workspace(client, slug="create-ws", name="Create")
    _authenticate(client, seed.user_id)

    response = await client.post(
        "/api/runs",
        json={
            "project_id": str(seed.project_id),
            "task_id": str(seed.task_id),
            "endpoint_type": "generic_web",
            "trigger": "api",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "queued"
    assert body["outcome"] is None
    assert body["workspace_id"] == str(seed.workspace_id)
    assert body["project_id"] == str(seed.project_id)
    assert body["task_id"] == str(seed.task_id)
    assert body["trigger"] == "api"

    run_id = uuid.UUID(body["id"])
    session_factory = client.session_factory  # type: ignore[attr-defined]
    async with session_factory() as session:
        stored = await session.get(Run, run_id)
        assert stored is not None
        assert stored.status == "queued"
        assert stored.workspace_id == seed.workspace_id
        assert stored.task_id == seed.task_id

    detail = await client.get(f"/api/runs/{run_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == str(run_id)


@pytest.mark.asyncio
async def test_idempotency_key_returns_same_run(client: AsyncClient) -> None:
    """同幂等键二次创建必须返回同一 id，且只落一行。"""
    seed = await _seed_workspace(client, slug="idem-ws", name="Idempotent")
    _authenticate(client, seed.user_id)

    payload = {
        "project_id": str(seed.project_id),
        "task_id": str(seed.task_id),
        "endpoint_type": "generic_web",
        "idempotency_key": "same-key-001",
    }

    first = await client.post("/api/runs", json=payload)
    second = await client.post("/api/runs", json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    expected_hash = hashlib.sha256(b"same-key-001").hexdigest()
    session_factory = client.session_factory  # type: ignore[attr-defined]
    async with session_factory() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(Run)
            .where(
                Run.workspace_id == seed.workspace_id,
                Run.idempotency_key_hash == expected_hash,
            )
        )
        assert count == 1


@pytest.mark.asyncio
async def test_cross_workspace_access_returns_404(client: AsyncClient) -> None:
    """跨工作区的读、取消与创建必须返回 404，不返回 403。"""
    owner = await _seed_workspace(client, slug="owner-ws", name="Owner")
    stranger = await _seed_workspace(client, slug="stranger-ws", name="Stranger")

    session_factory = client.session_factory  # type: ignore[attr-defined]
    async with session_factory() as session:
        foreign_run = await create_run(
            session,
            workspace_id=stranger.workspace_id,
            project_id=stranger.project_id,
            status=RunStatus.QUEUED,
        )
        await session.commit()
        foreign_run_id = foreign_run.id

    _authenticate(client, owner.user_id)

    detail = await client.get(f"/api/runs/{foreign_run_id}")
    steps = await client.get(f"/api/runs/{foreign_run_id}/steps")
    outcome = await client.get(f"/api/runs/{foreign_run_id}/outcome")
    cancel = await client.post(f"/api/runs/{foreign_run_id}/cancel")

    assert detail.status_code == 404
    assert steps.status_code == 404
    assert outcome.status_code == 404
    assert cancel.status_code == 404

    # 用别人的项目创建运行同样 404。
    create = await client.post(
        "/api/runs",
        json={
            "project_id": str(stranger.project_id),
            "task_id": str(stranger.task_id),
            "endpoint_type": "generic_web",
        },
    )
    assert create.status_code == 404
    assert create.json()["detail"] == "project_not_found"


@pytest.mark.asyncio
async def test_create_run_without_task_id_returns_422(client: AsyncClient) -> None:
    """缺少 task_id 必须在创建阶段拒绝。业务码必须稳定。"""
    seed = await _seed_workspace(client, slug="no-task-ws", name="No Task")
    _authenticate(client, seed.user_id)
    before = await _run_count(client, seed.workspace_id)

    response = await client.post(
        "/api/runs",
        json={
            "project_id": str(seed.project_id),
            "endpoint_type": "generic_web",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "run_binding_required"
    assert await _run_count(client, seed.workspace_id) == before


@pytest.mark.asyncio
async def test_create_run_with_unknown_task_id_returns_404(client: AsyncClient) -> None:
    """task_id 不存在必须返回 404，且 runs 表行数不变。"""
    seed = await _seed_workspace(client, slug="missing-task-ws", name="Missing Task")
    _authenticate(client, seed.user_id)
    before = await _run_count(client, seed.workspace_id)

    response = await client.post(
        "/api/runs",
        json={
            "project_id": str(seed.project_id),
            "task_id": str(uuid.uuid4()),
            "endpoint_type": "generic_web",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "task_not_found"
    assert await _run_count(client, seed.workspace_id) == before


@pytest.mark.asyncio
async def test_create_run_with_foreign_task_id_returns_404(client: AsyncClient) -> None:
    """别的 workspace 的 task_id 必须返回 404，且 runs 表行数不变。"""
    owner = await _seed_workspace(client, slug="task-owner-ws", name="Task Owner")
    stranger = await _seed_workspace(client, slug="task-stranger-ws", name="Task Stranger")
    _authenticate(client, owner.user_id)
    before = await _run_count(client, owner.workspace_id)

    response = await client.post(
        "/api/runs",
        json={
            "project_id": str(owner.project_id),
            "task_id": str(stranger.task_id),
            "endpoint_type": "generic_web",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "task_not_found"
    assert await _run_count(client, owner.workspace_id) == before


@pytest.mark.asyncio
async def test_create_run_with_task_from_other_project_returns_404(
    client: AsyncClient,
) -> None:
    """同 workspace 的另一个 project 下的 task_id 必须返回 404，且 runs 表行数不变。"""
    seed = await _seed_workspace(client, slug="task-project-ws", name="Task Project")

    session_factory = client.session_factory  # type: ignore[attr-defined]
    async with session_factory() as session:
        other_project = Project(
            workspace_id=seed.workspace_id,
            name="Other Project",
            domain="ecommerce",
            owner_id=seed.user_id,
        )
        session.add(other_project)
        await session.commit()
        other_project_id = other_project.id

    _authenticate(client, seed.user_id)
    before = await _run_count(client, seed.workspace_id)

    response = await client.post(
        "/api/runs",
        json={
            "project_id": str(other_project_id),
            "task_id": str(seed.task_id),
            "endpoint_type": "generic_web",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "task_not_found"
    assert await _run_count(client, seed.workspace_id) == before


@pytest.mark.asyncio
async def test_create_run_with_disabled_task_returns_409(client: AsyncClient) -> None:
    """未启用的任务必须在创建阶段拒绝，且 runs 表行数不变。"""
    seed = await _seed_workspace(client, slug="paused-task-ws", name="Paused Task")

    session_factory = client.session_factory  # type: ignore[attr-defined]
    async with session_factory() as session:
        task = await session.get(CollectionTask, seed.task_id)
        assert task is not None
        task.status = "paused"
        await session.commit()

    _authenticate(client, seed.user_id)
    before = await _run_count(client, seed.workspace_id)

    response = await client.post(
        "/api/runs",
        json={
            "project_id": str(seed.project_id),
            "task_id": str(seed.task_id),
            "endpoint_type": "generic_web",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "task_not_runnable"
    assert await _run_count(client, seed.workspace_id) == before


@pytest.mark.asyncio
async def test_cancel_terminal_run_returns_409(client: AsyncClient) -> None:
    """终态运行不得再取消。"""
    seed = await _seed_workspace(client, slug="cancel-ws", name="Cancel")
    _authenticate(client, seed.user_id)

    session_factory = client.session_factory  # type: ignore[attr-defined]
    async with session_factory() as session:
        terminal = await create_run(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            status=RunStatus.COMPLETED,
            outcome=RunOutcome.SUCCESS,
            finished_at=datetime(2026, 10, 20, 9, 0, tzinfo=UTC),
        )
        await session.commit()
        terminal_id = terminal.id

    response = await client.post(f"/api/runs/{terminal_id}/cancel")

    assert response.status_code == 409
    assert response.json()["detail"] == "run_not_cancellable"


@pytest.mark.asyncio
async def test_cancel_queued_run_succeeds(client: AsyncClient) -> None:
    """queued 运行必须可以取消，并写入结束时间。"""
    seed = await _seed_workspace(client, slug="cancel-ok-ws", name="Cancel OK")
    _authenticate(client, seed.user_id)

    session_factory = client.session_factory  # type: ignore[attr-defined]
    async with session_factory() as session:
        queued = await create_run(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            status=RunStatus.QUEUED,
        )
        await session.commit()
        queued_id = queued.id

    response = await client.post(f"/api/runs/{queued_id}/cancel")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cancelled"
    assert body["finished_at"] is not None


@pytest.mark.asyncio
async def test_list_steps_returns_rows_in_step_order(client: AsyncClient) -> None:
    """步骤列表必须按 step_index 升序返回。"""
    seed = await _seed_workspace(client, slug="steps-ws", name="Steps")
    _authenticate(client, seed.user_id)

    session_factory = client.session_factory  # type: ignore[attr-defined]
    async with session_factory() as session:
        run = await create_run(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            status=RunStatus.RUNNING,
        )
        await add_step(
            session,
            run_id=run.id,
            step_index=1,
            endpoint_type="tikhub_tiktok_video_search",
            collector_type="tikhub_social",
            status=RunStepStatus.PENDING,
        )
        await add_step(
            session,
            run_id=run.id,
            step_index=0,
            endpoint_type="generic_web",
            collector_type="generic_web",
            status=RunStepStatus.SUCCESS,
            outcome=RunOutcome.SUCCESS,
            records_count=2,
        )
        await session.commit()
        run_id = run.id

    response = await client.get(f"/api/runs/{run_id}/steps")

    assert response.status_code == 200
    steps = response.json()
    assert [step["step_index"] for step in steps] == [0, 1]
    assert steps[0]["status"] == "success"
    assert steps[0]["outcome"] == "success"
    assert steps[1]["status"] == "pending"


@pytest.mark.asyncio
async def test_outcome_aggregates_all_fields(client: AsyncClient) -> None:
    """outcome 必须返回全部聚合字段，包括七个步骤计数。"""
    seed = await _seed_workspace(client, slug="outcome-ws", name="Outcome")
    _authenticate(client, seed.user_id)

    finished_at = datetime(2026, 10, 20, 10, 30, tzinfo=UTC)
    session_factory = client.session_factory  # type: ignore[attr-defined]
    async with session_factory() as session:
        run = await create_run(
            session,
            workspace_id=seed.workspace_id,
            project_id=seed.project_id,
            status=RunStatus.COMPLETED,
            outcome=RunOutcome.SUCCESS,
            evidence_grade="L3_live_single",
            records_count=5,
            started_at=datetime(2026, 10, 20, 10, 0, tzinfo=UTC),
            finished_at=finished_at,
        )
        run.total_cost_usd = Decimal("1.250000")
        await session.flush()

        await add_step(
            session,
            run_id=run.id,
            step_index=0,
            endpoint_type="generic_web",
            collector_type="generic_web",
            status=RunStepStatus.SUCCESS,
            outcome=RunOutcome.SUCCESS,
            records_count=5,
            total_cost_usd=Decimal("1.250000"),
        )
        await add_step(
            session,
            run_id=run.id,
            step_index=1,
            endpoint_type="tikhub_tiktok_video_search",
            collector_type="tikhub_social",
            status=RunStepStatus.EMPTY,
            outcome=RunOutcome.EMPTY,
        )
        await add_step(
            session,
            run_id=run.id,
            step_index=2,
            endpoint_type="tikhub_instagram_search",
            collector_type="tikhub_social",
            status=RunStepStatus.FAILED,
            outcome=RunOutcome.FAILED,
            error_message="upstream_timeout",
        )
        await session.commit()
        run_id = run.id

    response = await client.get(f"/api/runs/{run_id}/outcome")

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == str(run_id)
    assert body["status"] == "completed"
    assert body["outcome"] == "success"
    assert body["records_count"] == 5
    assert body["evidence_grade"] == "L3_live_single"
    assert float(body["total_cost_usd"]) == 1.25
    assert body["finished_at"] is not None
    assert body["total_steps"] == 3
    assert set(body["step_counts"]) == {item.value for item in RunStepStatus}
    assert body["step_counts"]["success"] == 1
    assert body["step_counts"]["empty"] == 1
    assert body["step_counts"]["failed"] == 1
    assert body["step_counts"]["pending"] == 0
