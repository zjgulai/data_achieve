"""MCP 运行查询服务测试。使用临时 SQLite，不联网。"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.mcp_runtime import run_service
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.run import Run, RunStep
from data_intelligence_hub.models.task import TaskRun


@pytest_asyncio.fixture()
async def factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _seed(factory: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    now = datetime.now(UTC)
    run_id = uuid.uuid4()
    task_run_id = uuid.uuid4()
    async with factory() as session:
        session.add(
            Run(
                id=run_id,
                workspace_id=uuid.uuid4(),
                project_id=uuid.uuid4(),
                status="completed",
                outcome="success",
                execution_mode="live",
                trigger="api",
                records_count=2,
                started_at=now,
                finished_at=now,
                created_at=now,
            )
        )
        session.add(
            TaskRun(
                id=task_run_id,
                task_id=uuid.uuid4(),
                workspace_id=uuid.uuid4(),
                status="success",
                records_count=2,
                logs=[],
                created_at=now,
                run_id=run_id,
            )
        )
        session.add(
            RunStep(
                run_id=run_id,
                step_index=0,
                endpoint_type="tikhub_tiktok_search_web",
                collector_type="tikhub_social",
                task_run_id=task_run_id,
                status="success",
                outcome="success",
                records_count=2,
            )
        )
        for index in range(2):
            session.add(
                RawRecord(
                    id=uuid.uuid4(),
                    workspace_id=uuid.uuid4(),
                    project_id=uuid.uuid4(),
                    source_id=uuid.uuid4(),
                    task_run_id=task_run_id,
                    record_type="tiktok_video",
                    content={"index": index},
                    content_hash=f"hash-{index}",
                    collected_at=now,
                    created_at=now,
                )
            )
        await session.commit()
    return run_id


def test_get_run_detail_and_list_records(
    factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = asyncio.run(_seed(factory))
    monkeypatch.setattr(run_service, "async_session_factory", factory)

    detail = asyncio.run(run_service.get_run_detail(run_id))
    assert detail["status"] == "completed"
    assert detail["records_count"] == 2
    assert len(detail["steps"]) == 1

    page = asyncio.run(run_service.list_run_records(run_id, limit=1))
    assert page["records_total"] == 2
    assert len(page["items"]) == 1
    assert page["items"][0]["content"]
    assert page["next_cursor"] == "1"

    next_page = asyncio.run(
        run_service.list_run_records(run_id, limit=1, cursor="1")
    )
    assert len(next_page["items"]) == 1
    assert next_page["next_cursor"] is None


def test_record_preview_truncates_long_content() -> None:
    from data_intelligence_hub.services.raw_record_service import build_record_preview

    now = datetime.now(UTC)
    record = RawRecord(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        task_run_id=uuid.uuid4(),
        record_type="tiktok_video",
        source_url=None,
        content={"text": "a" * 5000},
        content_hash="long-content",
        collected_at=now,
        created_at=now,
    )
    preview = build_record_preview(record)
    assert preview["content_truncated"] is True
    assert preview["content"].endswith("[truncated]")


def test_list_records_rejects_invalid_limit(
    factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = asyncio.run(_seed(factory))
    monkeypatch.setattr(run_service, "async_session_factory", factory)
    with pytest.raises(ValueError, match="limit_invalid"):
        asyncio.run(run_service.list_run_records(run_id, limit=0))
