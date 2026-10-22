"""工作区问答：本地检索与引用。"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.services import answer_service


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
    now = datetime.now(UTC)
    async with factory() as session:
        user_id = uuid.uuid4()
        workspace_id = uuid.uuid4()
        project_id = uuid.uuid4()
        other_project = uuid.uuid4()
        source_id = uuid.uuid4()
        task_id = uuid.uuid4()
        run_id = uuid.uuid4()
        session.add_all(
            [
                User(
                    id=user_id,
                    email="answer@example.com",
                    password_hash="x",
                    name="Answer",
                    status="active",
                ),
                Workspace(
                    id=workspace_id,
                    name="Answer WS",
                    slug="answer-ws",
                    owner_id=user_id,
                ),
                Project(
                    id=project_id,
                    workspace_id=workspace_id,
                    name="Answer Project",
                    domain="mixed",
                    status="active",
                    owner_id=user_id,
                ),
                Project(
                    id=other_project,
                    workspace_id=workspace_id,
                    name="Other Project",
                    domain="mixed",
                    status="active",
                    owner_id=user_id,
                ),
                Source(
                    id=source_id,
                    workspace_id=workspace_id,
                    project_id=project_id,
                    name="answer source",
                    type="exa_search",
                    url=None,
                    config={},
                    schedule_cron=None,
                    enabled=True,
                ),
                CollectionTask(
                    id=task_id,
                    workspace_id=workspace_id,
                    project_id=project_id,
                    source_id=source_id,
                    collector_type="exa_search",
                    name="answer task",
                    schedule_cron=None,
                    status="enabled",
                    config={"endpoint_type": "exa_search_lite"},
                ),
                TaskRun(
                    id=run_id,
                    task_id=task_id,
                    workspace_id=workspace_id,
                    status="success",
                    started_at=now,
                    finished_at=now,
                    records_count=2,
                    entities_count=0,
                    logs=[],
                    created_at=now,
                ),
                RawRecord(
                    workspace_id=workspace_id,
                    project_id=project_id,
                    source_id=source_id,
                    task_run_id=run_id,
                    record_type="search_result",
                    source_url="https://example.com/exa-pricing",
                    content={
                        "title": "Exa pricing",
                        "text": "Exa lite search costs four dollars per thousand queries.",
                    },
                    content_hash=hashlib.sha256(b"a").hexdigest(),
                    collected_at=now,
                    created_at=now,
                ),
                RawRecord(
                    workspace_id=workspace_id,
                    project_id=other_project,
                    source_id=source_id,
                    task_run_id=run_id,
                    record_type="search_result",
                    source_url="https://example.com/unrelated",
                    content={"title": "Cooking", "text": "How to bake bread."},
                    content_hash=hashlib.sha256(b"b").hexdigest(),
                    collected_at=now,
                    created_at=now,
                ),
            ]
        )
        await session.commit()
    factory.ids = {  # type: ignore[attr-defined]
        "workspace": workspace_id,
        "project": project_id,
        "other_project": other_project,
    }
    yield factory
    await engine.dispose()


def _ids(factory) -> dict[str, uuid.UUID]:
    return factory.ids  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_workspace_answer_returns_local_citations(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        result = await answer_service.workspace_answer(
            session,
            workspace_id=_ids(session_factory)["workspace"],
            project_id=_ids(session_factory)["project"],
            query="exa pricing lite",
        )
    assert result["source"] == "workspace"
    assert len(result["citations"]) == 1
    assert "[1]" in result["answer"]
    assert "four dollars" in result["citations"][0]["snippet"]


@pytest.mark.asyncio
async def test_workspace_answer_respects_project_filter(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        result = await answer_service.workspace_answer(
            session,
            workspace_id=_ids(session_factory)["workspace"],
            project_id=_ids(session_factory)["other_project"],
            query="exa pricing",
        )
    assert result["citations"] == []
    assert result["source"] == "none"


@pytest.mark.asyncio
async def test_workspace_answer_matches_chinese_bigrams(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        # 写一条中文证据，证明连续中文不会被当作一个不可匹配的大词。
        record = (
            await session.execute(
                select(RawRecord).where(
                    RawRecord.project_id == _ids(session_factory)["project"]
                )
            )
        ).scalars().first()
        assert record is not None
        record.content = {"title": "价格", "text": "轻量搜索每千次四美元"}
        await session.commit()
        result = await answer_service.workspace_answer(
            session,
            workspace_id=_ids(session_factory)["workspace"],
            project_id=_ids(session_factory)["project"],
            query="轻量搜索价格",
        )
    assert result["source"] == "workspace"
    assert len(result["citations"]) == 1
    assert "轻量搜索" in result["citations"][0]["snippet"]
