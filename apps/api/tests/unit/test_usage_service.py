"""用量与成本汇总的隔离与估算口径。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.services.usage_service import get_usage_summary


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
    await _seed(factory)
    yield factory
    await engine.dispose()


async def _seed(factory: async_sessionmaker[AsyncSession]) -> None:
    now = datetime.now(UTC)
    ids = {
        "user": uuid.uuid4(),
        "workspace": uuid.uuid4(),
        "project": uuid.uuid4(),
        "task": uuid.uuid4(),
        "source": uuid.uuid4(),
        "other_workspace": uuid.uuid4(),
        "other_project": uuid.uuid4(),
        "other_task": uuid.uuid4(),
        "other_source": uuid.uuid4(),
    }
    async with factory() as session:
        session.add_all(
            [
                User(
                    id=ids["user"],
                    email="usage@example.com",
                    password_hash="x",
                    name="Usage",
                    status="active",
                ),
                Workspace(
                    id=ids["workspace"],
                    name="Usage WS",
                    slug="usage-ws",
                    owner_id=ids["user"],
                ),
                Project(
                    id=ids["project"],
                    workspace_id=ids["workspace"],
                    name="Usage Project",
                    domain="mixed",
                    status="active",
                    owner_id=ids["user"],
                ),
                Source(
                    id=ids["source"],
                    workspace_id=ids["workspace"],
                    project_id=ids["project"],
                    name="usage source",
                    type="exa_search",
                    url=None,
                    config={},
                    schedule_cron=None,
                    enabled=True,
                ),
                CollectionTask(
                    id=ids["task"],
                    workspace_id=ids["workspace"],
                    project_id=ids["project"],
                    source_id=ids["source"],
                    collector_type="exa_search",
                    name="usage task",
                    status="enabled",
                    config={"endpoint_type": "exa_search_lite"},
                ),
                Workspace(
                    id=ids["other_workspace"],
                    name="Other",
                    slug="usage-other",
                    owner_id=ids["user"],
                ),
                Project(
                    id=ids["other_project"],
                    workspace_id=ids["other_workspace"],
                    name="Other Project",
                    domain="mixed",
                    status="active",
                    owner_id=ids["user"],
                ),
                Source(
                    id=ids["other_source"],
                    workspace_id=ids["other_workspace"],
                    project_id=ids["other_project"],
                    name="other source",
                    type="exa_search",
                    url=None,
                    config={},
                    schedule_cron=None,
                    enabled=True,
                ),
                CollectionTask(
                    id=ids["other_task"],
                    workspace_id=ids["other_workspace"],
                    project_id=ids["other_project"],
                    source_id=ids["other_source"],
                    collector_type="exa_search",
                    name="other task",
                    status="enabled",
                    config={"endpoint_type": "exa_search_lite"},
                ),
            ]
        )
        await session.flush()

        def run(task_id: uuid.UUID, ws: uuid.UUID, records: int, when: datetime, cost=None):
            return TaskRun(
                task_id=task_id,
                workspace_id=ws,
                status="success",
                started_at=when,
                finished_at=when,
                records_count=records,
                entities_count=0,
                logs=[],
                created_at=when,
                endpoint_type="exa_search_lite",
                provider="exa_search",
                total_cost_usd=cost,
            )

        session.add_all(
            [
                run(ids["task"], ids["workspace"], 2, now - timedelta(hours=2)),
                run(ids["task"], ids["workspace"], 3, now - timedelta(days=2)),
                run(
                    ids["task"],
                    ids["workspace"],
                    1,
                    now - timedelta(days=3),
                    cost=Decimal("0.5"),
                ),
                run(ids["other_task"], ids["other_workspace"], 9, now),
            ]
        )
        await session.commit()
    _seed.ids = ids  # type: ignore[attr-defined]


def _ids() -> dict[str, uuid.UUID]:
    return _seed.ids  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_usage_summary_isolates_workspace_and_estimates_cost(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        summary = await get_usage_summary(
            session, workspace_id=_ids()["workspace"], days=30
        )

    assert summary["totals"]["runs"] == 3
    assert summary["totals"]["records"] == 6
    # 两次估算各 $0.004（per_query 按次），一次实际成本 $0.5。
    assert summary["totals"]["cost_usd"] == "0.508000"
    assert summary["by_provider"][0]["provider"] == "exa_search"
    assert summary["by_provider"][0]["runs"] == 3
    assert len(summary["by_day"]) == 3


@pytest.mark.asyncio
async def test_usage_summary_filters_by_project(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        summary = await get_usage_summary(
            session,
            workspace_id=_ids()["workspace"],
            days=30,
            project_id=_ids()["project"],
        )
        empty = await get_usage_summary(
            session,
            workspace_id=_ids()["workspace"],
            days=30,
            project_id=_ids()["other_project"],
        )

    assert summary["totals"]["runs"] == 3
    assert empty["totals"]["runs"] == 0
    assert empty["totals"]["cost_usd"] == "0.000000"


@pytest.mark.asyncio
async def test_usage_summary_respects_day_window(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        summary = await get_usage_summary(
            session, workspace_id=_ids()["workspace"], days=1
        )
    # 只有 2 小时前的运行落在 1 天窗口内。
    assert summary["totals"]["runs"] == 1