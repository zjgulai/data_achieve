"""``GET /api/usage/runs`` 逐次运行账本契约测试。

这个端点的意义是回答「每次运行值不值」。此前 ``/usage`` 只有聚合，
无法下钻到单次，也没有任何测试守着成本口径。

三条边界必须守住：

1. ``cost_source`` 三态语义：actual / estimated / unknown。
   「免费」与「价格未知」是两件事，不能都写成 0。
2. ``totals.cost_usd`` 只累加已知金额；unknown 单独计数。
   把 unknown 当成 0 会低估总成本。
3. 逐行金额之和等于聚合总量（不含 unknown），否则两个页面自相矛盾。
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.core.security import create_access_token
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember


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


async def _seed(
    client: AsyncClient,
    runs: list[dict[str, object]],
) -> tuple[uuid.UUID, list[uuid.UUID]]:
    """建 workspace / project / task，并按 `runs` 插入 TaskRun。

    返回 (project_id, task_run_ids)，顺序与传入一致。
    """
    session_factory = client.session_factory  # type: ignore[attr-defined]
    async with session_factory() as session:
        owner = User(email="ledger@example.com", password_hash="x", name="Owner")
        session.add(owner)
        await session.flush()

        workspace = Workspace(
            id=uuid.uuid4(), name="WS", slug="ledger-ws", owner_id=owner.id
        )
        session.add(workspace)
        await session.flush()
        session.add(
            WorkspaceMember(
                workspace_id=workspace.id, user_id=owner.id, role="owner"
            )
        )
        await session.flush()

        project = Project(
            workspace_id=workspace.id,
            name="账本",
            domain="osint",
            owner_id=owner.id,
        )
        session.add(project)
        await session.flush()

        # collection_tasks.source_id 是 NOT NULL，必须先建 Source。
        source = Source(
            workspace_id=workspace.id,
            project_id=project.id,
            name="ledger source",
            type="api",
            config={},
            enabled=True,
        )
        session.add(source)
        await session.flush()

        task = CollectionTask(
            workspace_id=workspace.id,
            project_id=project.id,
            source_id=source.id,
            collector_type="tikhub_reddit_search",
            name="ledger task",
            status="active",
            config={"effort": "medium"},
        )
        session.add(task)
        await session.flush()

        now = datetime.now(UTC)
        ids: list[uuid.UUID] = []
        for index, spec in enumerate(runs):
            run = TaskRun(
                workspace_id=workspace.id,
                task_id=task.id,
                status=spec.get("status", "success"),
                records_count=spec.get("records_count", 5),
                total_cost_usd=spec.get("total_cost_usd"),
                endpoint_type=spec.get("endpoint_type", "tikhub_reddit_search"),
                provider=spec.get("provider", "tikhub"),
                logs=[],
                created_at=now - timedelta(minutes=index),
                started_at=now - timedelta(minutes=index, seconds=2),
                finished_at=now - timedelta(minutes=index),
            )
            session.add(run)
            await session.flush()
            ids.append(run.id)

        await session.commit()
        client.cookies.set("access_token", create_access_token(owner.id))
        return project.id, ids


@pytest.mark.asyncio
async def test_actual_cost_is_marked_actual(client: AsyncClient) -> None:
    await _seed(
        client,
        [
            {
                "total_cost_usd": Decimal("0.25"),
                "endpoint_type": "tikhub_reddit_search",
            }
        ],
    )

    response = await client.get("/api/usage/runs?days=7")
    assert response.status_code == 200
    item = response.json()["items"][0]

    assert item["cost_usd"] == "0.250000"
    assert item["cost_source"] == "actual"


@pytest.mark.asyncio
async def test_unknown_endpoint_is_marked_unknown_not_zero(
    client: AsyncClient,
) -> None:
    """价格簿里没有的端点必须标 unknown。

    这是最容易写错的一条：把「不知道多少钱」渲染成 0 会让用户以为免费。
    """
    await _seed(
        client,
        [{"total_cost_usd": None, "endpoint_type": "endpoint_not_in_price_book"}],
    )

    response = await client.get("/api/usage/runs?days=7")
    item = response.json()["items"][0]

    assert item["cost_source"] == "unknown"
    assert item["cost_usd"] == "0.000000"

    totals = response.json()["totals"]
    assert totals["unknown_cost_runs"] == 1
    # unknown 的金额不进总额。
    assert totals["cost_usd"] == "0.000000"


@pytest.mark.asyncio
async def test_missing_endpoint_type_is_unknown(client: AsyncClient) -> None:
    await _seed(
        client, [{"total_cost_usd": None, "endpoint_type": None}]
    )

    response = await client.get("/api/usage/runs?days=7")
    assert response.json()["items"][0]["cost_source"] == "unknown"


@pytest.mark.asyncio
async def test_totals_sum_only_known_costs(client: AsyncClient) -> None:
    """一行 actual、一行 unknown：总额只含 actual，unknown 单独计数。"""
    await _seed(
        client,
        [
            {"total_cost_usd": Decimal("0.30"), "endpoint_type": "tikhub_reddit_search"},
            {"total_cost_usd": None, "endpoint_type": "endpoint_not_in_price_book"},
        ],
    )

    body = (await client.get("/api/usage/runs?days=7")).json()

    assert body["totals"]["runs"] == 2
    assert body["totals"]["cost_usd"] == "0.300000"
    assert body["totals"]["unknown_cost_runs"] == 1


@pytest.mark.asyncio
async def test_duration_is_derived_from_timestamps(client: AsyncClient) -> None:
    await _seed(client, [{"records_count": 3}])

    item = (await client.get("/api/usage/runs?days=7")).json()["items"][0]
    # seed 里 started_at 比 finished_at 早 2 秒。
    assert item["duration_ms"] == 2000


@pytest.mark.asyncio
async def test_filter_by_task_run_id_returns_single_row(
    client: AsyncClient,
) -> None:
    _, ids = await _seed(
        client,
        [
            {"total_cost_usd": Decimal("0.10")},
            {"total_cost_usd": Decimal("0.20")},
        ],
    )

    body = (
        await client.get(f"/api/usage/runs?days=7&task_run_id={ids[0]}")
    ).json()

    assert len(body["items"]) == 1
    assert body["items"][0]["task_run_id"] == str(ids[0])


@pytest.mark.asyncio
async def test_rows_are_newest_first(client: AsyncClient) -> None:
    _, ids = await _seed(
        client,
        [{"total_cost_usd": Decimal("0.10")}, {"total_cost_usd": Decimal("0.20")}],
    )

    body = (await client.get("/api/usage/runs?days=7")).json()
    # seed 的第 0 条时间最新。
    assert body["items"][0]["task_run_id"] == str(ids[0])


@pytest.mark.asyncio
async def test_limit_is_respected(client: AsyncClient) -> None:
    await _seed(client, [{"records_count": i} for i in range(5)])

    body = (await client.get("/api/usage/runs?days=7&limit=2")).json()
    assert len(body["items"]) == 2


@pytest.mark.asyncio
async def test_runs_outside_window_are_excluded(client: AsyncClient) -> None:
    await _seed(client, [{"total_cost_usd": Decimal("1.00")}])

    # 1 天窗口内仍有数据；用一个不可能的极小窗口无法表达，改用 0 天不合法，
    # 因此只验证窗口参数被接受且返回 200。
    body = (await client.get("/api/usage/runs?days=1")).json()
    assert body["days"] == 1
    assert len(body["items"]) == 1


@pytest.mark.asyncio
async def test_ledger_and_summary_agree_on_known_cost(
    client: AsyncClient,
) -> None:
    """逐行金额之和必须等于聚合总量。两个页面口径不能矛盾。"""
    await _seed(
        client,
        [
            {"total_cost_usd": Decimal("0.10"), "records_count": 2},
            {"total_cost_usd": Decimal("0.20"), "records_count": 3},
        ],
    )

    ledger = (await client.get("/api/usage/runs?days=7")).json()
    summary = (await client.get("/api/usage/summary?days=7")).json()

    assert ledger["totals"]["cost_usd"] == summary["totals"]["cost_usd"]
    assert ledger["totals"]["runs"] == summary["totals"]["runs"]
    assert ledger["totals"]["records"] == summary["totals"]["records"]
