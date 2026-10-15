"""外访策略在路由层的回归：被禁/未批准/已停用一律零联网。

三条边界，全部走真实 ASGI app + SQLite（内存）+ 默认 offline 策略：
1. manual task run：generic_web 在离线模式下被拒，TaskRun 落 policy_denied，
   records_count == 0，审计日志 http_requests_sent == 0（拒绝先于任何请求），
   且拒绝发生在 collection_scope 之前（无 outbound_policy_checked 审计）；
2. quick-collect：params.safe_approved 之类的调用方自报批准不解锁任何出口；
3. 已停用 source：run 直接 409，连 run 行都不创建。
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.workspaces import DEMO_WORKSPACE_SLUG


@pytest.fixture(autouse=True)
def offline_policy(monkeypatch: pytest.MonkeyPatch):
    """固定为默认 offline：不设 COLLECTION_NETWORK_MODE / COLLECTION_HTTP_GRANTS。

    这正是生产本地的默认形态；用例要证明的就是"这个形态下没有任何出口"。
    """
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("COLLECTION_NETWORK_MODE", raising=False)
    monkeypatch.delenv("COLLECTION_HTTP_GRANTS", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


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


async def seed_demo_workspace_and_project(client: AsyncClient) -> uuid.UUID:
    """直接落最小合法的 User + demo Workspace + Project（不依赖注册流程）。"""
    session_factory = client.session_factory  # type: ignore[attr-defined]
    async with session_factory() as session:
        owner = User(email="policy-owner@example.com", password_hash="x", name="Policy Owner")
        session.add(owner)
        await session.flush()
        workspace = Workspace(name="Demo", slug=DEMO_WORKSPACE_SLUG, owner_id=owner.id)
        session.add(workspace)
        await session.flush()
        project = Project(
            workspace_id=workspace.id,
            name="Outbound Policy",
            domain="osint",
            owner_id=owner.id,
        )
        session.add(project)
        await session.commit()
        return project.id


async def create_enabled_generic_web_task(client: AsyncClient, project_id: uuid.UUID) -> uuid.UUID:
    """走公开路由：建 source -> enable 生成 task，返回 task_id。"""
    source_response = await client.post(
        "/api/sources",
        json={
            "project_id": str(project_id),
            "name": "policy-probe-generic-web",
            "type": "generic_web",
            "config": {"url": "https://example.com"},
        },
    )
    assert source_response.status_code == 201, source_response.text
    source_id = source_response.json()["id"]

    enable_response = await client.post(f"/api/sources/{source_id}/enable")
    assert enable_response.status_code == 200, enable_response.text
    return uuid.UUID(enable_response.json()["id"])


def _failed_log(run_logs: list[dict[str, object]]) -> dict[str, object]:
    failed = [log for log in run_logs if log.get("step") == "collector_failed"]
    assert failed, f"expected collector_failed log in {run_logs}"
    return failed[0]


@pytest.mark.asyncio
async def test_manual_task_run_denied_offline_without_network(client: AsyncClient) -> None:
    """离线默认下 manual run 被策略拒绝：run=failed、0 记录、无预算审计。"""
    project_id = await seed_demo_workspace_and_project(client)
    task_id = await create_enabled_generic_web_task(client, project_id)

    run_response = await client.post(f"/api/tasks/{task_id}/run")
    assert run_response.status_code == 201, run_response.text
    run = run_response.json()

    assert run["status"] == "failed"
    assert run["records_count"] == 0
    assert run["entities_count"] == 0
    assert (run["error_message"] or "").startswith("collection_policy_denied")

    failed_log = _failed_log(run["logs"])
    assert failed_log["failure_reason"] == "policy_denied"
    # 策略拒绝发生在任何 HTTP 出口之前：实测请求数必须是 0（不是 None）。
    assert failed_log.get("http_requests_sent") == 0

    # 拒绝发生在 collection_scope 之前：不存在 outbound_policy_checked 审计。
    policy_audits = [log for log in run["logs"] if log.get("step") == "outbound_policy_checked"]
    assert policy_audits == []

    runs_response = await client.get(f"/api/tasks/{task_id}/runs")
    assert runs_response.status_code == 200
    assert len(runs_response.json()) == 1


@pytest.mark.asyncio
async def test_quick_collect_caller_approval_cannot_unlock_offline(
    client: AsyncClient,
) -> None:
    """params 里的 safe_approved/approved 是调用方自报，绝不能解锁离线模式。"""
    project_id = await seed_demo_workspace_and_project(client)

    response = await client.post(
        "/api/quick-collect",
        json={
            "project_id": str(project_id),
            "endpoint_type": "generic_web",
            "params": {
                "url": "https://example.com",
                "safe_approved": True,
                "approved": True,
                "safety_approved": True,
            },
            "label": "[test] policy-approval-bypass",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["status"] == "failed"
    assert body["records_count"] == 0
    assert (body["error_message"] or "").startswith("collection_policy_denied")

    session_factory = client.session_factory  # type: ignore[attr-defined]
    from data_intelligence_hub.models.task import TaskRun

    async with session_factory() as session:
        run = await session.get(TaskRun, uuid.UUID(body["task_run_id"]))
        assert run is not None
        assert run.status == "failed"
        assert run.records_count == 0
        failed_log = _failed_log(run.logs)
        assert failed_log["failure_reason"] == "policy_denied"
        assert failed_log.get("http_requests_sent") == 0
        # 预算构造前的拒绝没有 budget：不存在 outbound_policy_checked 审计。
        audits = [log for log in run.logs if log.get("step") == "outbound_policy_checked"]
        assert audits == []


@pytest.mark.asyncio
async def test_disabled_source_run_is_rejected_without_run_creation(
    client: AsyncClient,
) -> None:
    """已停用 source：run 409，不创建 TaskRun，更没有网络。"""
    project_id = await seed_demo_workspace_and_project(client)
    task_id = await create_enabled_generic_web_task(client, project_id)

    runs_before = (await client.get(f"/api/tasks/{task_id}/runs")).json()
    assert runs_before == []

    tasks_response = await client.get("/api/tasks")
    assert tasks_response.status_code == 200
    task_payload = next(item for item in tasks_response.json() if item["id"] == str(task_id))
    source_id = task_payload["source_id"]

    disable_response = await client.post(f"/api/sources/{source_id}/disable")
    assert disable_response.status_code == 200, disable_response.text
    assert disable_response.json()["enabled"] is False

    run_response = await client.post(f"/api/tasks/{task_id}/run")
    assert run_response.status_code == 409
    assert run_response.json()["detail"] == "Task is not enabled"

    runs_after = (await client.get(f"/api/tasks/{task_id}/runs")).json()
    assert runs_after == []


@pytest.mark.asyncio
async def test_editing_quick_source_cannot_remove_one_shot_origin(client: AsyncClient) -> None:
    project_id = await seed_demo_workspace_and_project(client)
    created = await client.post(
        "/api/quick-collect",
        json={
            "project_id": str(project_id),
            "endpoint_type": "aliens_eye_basic",
            "params": {"username": "nobody"},
        },
    )
    assert created.status_code == 201
    source_id = created.json()["source_id"]
    updated = await client.patch(
        f"/api/sources/{source_id}",
        json={
            "config": {
                "username": "another",
                "execution_origin": "scheduler",
                "schedule_policy": "auto_freshness",
            },
            "schedule_cron": "30 12 * * *",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["config"]["execution_origin"] == "quick_collect"
    assert updated.json()["config"]["schedule_policy"] == "manual_refresh_only"
    assert updated.json()["schedule_cron"] is None
    tested = await client.post(f"/api/sources/{source_id}/test")
    assert tested.status_code == 200
    current = (await client.get(f"/api/sources/{source_id}")).json()
    assert current["config"]["execution_origin"] == "quick_collect"


@pytest.mark.asyncio
async def test_mcp_collection_uses_the_same_denial(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from data_intelligence_hub.mcp_runtime import collect_service

    project_id = await seed_demo_workspace_and_project(client)
    monkeypatch.setattr(collect_service, "async_session_factory", client.session_factory)
    result = await collect_service.collect_capability(
        "aliens_eye_basic",
        project_id,
        {"username": "nobody", "approved": True},
    )
    assert result.status == "failed"
    assert result.records_count == 0
    assert result.error_message.startswith("collection_policy_denied:")


@pytest.mark.asyncio
async def test_scheduler_does_not_retry_a_policy_denied_cron(client: AsyncClient) -> None:
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from data_intelligence_hub.models import CollectionTask, TaskRun
    from data_intelligence_hub.scheduler.service import CollectionScheduler

    project_id = await seed_demo_workspace_and_project(client)
    task_id = await create_enabled_generic_web_task(client, project_id)
    async with client.session_factory() as session:
        task = await session.get(CollectionTask, task_id)
        task.schedule_cron = "30 12 * * *"
        await session.commit()
    now = datetime.now(UTC)
    scheduler = CollectionScheduler(
        session_factory=client.session_factory, poll_interval_seconds=60, clock=lambda: now
    )
    first = await scheduler.tick()
    assert first.started == 1
    scheduler._clock = lambda: now + timedelta(days=2)
    second = await scheduler.tick()
    assert second.started == 0
    async with client.session_factory() as session:
        runs = list((await session.execute(select(TaskRun))).scalars())
        assert len(runs) == 1
        assert runs[0].error_message.startswith("collection_policy_denied:")
        assert _failed_log(runs[0].logs)["http_requests_sent"] == 0
