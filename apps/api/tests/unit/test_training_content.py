from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import (
    Base,
    CollectionTask,
    Entity,
    IntelligenceItem,
    Project,
    RawRecord,
    Report,
    Source,
    User,
    Workspace,
    WorkspaceMember,
)
from data_intelligence_hub.seed import training_content
from data_intelligence_hub.seed.demo_data import cleanup_demo_noise
from data_intelligence_hub.seed.training_content import (
    _demo_id,
    curated_training_ids,
    seed_training_content,
)

ROOT_DIR = Path(__file__).resolve().parents[4]
CURATION_PATH = ROOT_DIR / "tmp" / "outputs" / "training-content-curation-20260615.json"
SNAPSHOT_PATH = ROOT_DIR / "tmp" / "outputs" / "training-content-snapshot-20260615.json"


def test_curated_training_ids_cover_seed_graph() -> None:
    ids = curated_training_ids()

    assert len(ids["projects"]) == 4
    assert len(ids["sources"]) == 44
    assert len(ids["tasks"]) == 44
    assert len(ids["task_runs"]) == 44
    assert len(ids["raw_records"]) == 44
    assert len(ids["entities"]) == 44
    assert len(ids["signals"]) == 13
    assert len(ids["intelligence"]) == 14
    assert len(ids["reports"]) == 1
    assert len(ids["alert_rules"]) == 3
    assert len(ids["alert_events"]) == 3
    assert len(ids["notifications"]) == 3


@pytest.mark.asyncio
async def test_training_content_seed_execute_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = await _create_session_factory()
    monkeypatch.setattr(training_content, "async_session_factory", session_factory)
    await _create_demo_identity(session_factory)
    await _create_existing_demo_entity(session_factory)

    first_report = await seed_training_content(
        curation_path=CURATION_PATH,
        snapshot_path=SNAPSHOT_PATH,
        execute=True,
    )
    second_report = await seed_training_content(
        curation_path=CURATION_PATH,
        snapshot_path=SNAPSHOT_PATH,
        execute=True,
    )

    assert first_report.counts == second_report.counts
    async with session_factory() as session:
        assert await _count(session, Project) == 5
        assert await _count(session, Source) == 44
        assert await _count(session, CollectionTask) == 44
        assert await _count(session, RawRecord) == 44
        assert await _count(session, Entity) == 45
        assert await _count(session, IntelligenceItem) == 14
        weekly_report = await session.scalar(
            select(Report).where(Report.report_type == "weekly_training")
        )
        assert weekly_report is not None
        included_intelligence = int(
            await session.scalar(
                select(func.count())
                .select_from(IntelligenceItem)
                .where(
                    IntelligenceItem.created_at >= weekly_report.period_start,
                    IntelligenceItem.created_at <= weekly_report.period_end,
                )
            )
            or 0
        )
        assert included_intelligence == 14


@pytest.mark.asyncio
async def test_demo_noise_cleanup_preserves_curated_training(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = await _create_session_factory()
    monkeypatch.setattr(training_content, "async_session_factory", session_factory)
    await _create_demo_identity(session_factory)
    await seed_training_content(
        curation_path=CURATION_PATH,
        snapshot_path=SNAPSHOT_PATH,
        execute=True,
    )

    async with session_factory() as session:
        report = await cleanup_demo_noise(session, dry_run=True)

    assert all(count == 0 for count in report.counts.values())


async def _create_session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


async def _create_demo_identity(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        user = User(
            id=_demo_id("user-owner"),
            email="owner@example.com",
            password_hash="hashed-password",
            name="Data Achieve Owner",
            status="active",
        )
        workspace = Workspace(
            id=_demo_id("workspace-main"),
            name="Data Achieve Intelligence Hub",
            slug="data-achieve-demo",
            owner_id=user.id,
        )
        member = WorkspaceMember(
            id=_demo_id("workspace-member-owner"),
            workspace_id=workspace.id,
            user_id=user.id,
            role="owner",
        )
        session.add_all([user, workspace, member])
        await session.commit()


async def _create_existing_demo_entity(session_factory: async_sessionmaker[AsyncSession]) -> None:
    now = datetime.now(UTC)
    async with session_factory() as session:
        project = Project(
            id=_demo_id("project-osint"),
            workspace_id=_demo_id("workspace-main"),
            name="开源采集工具雷达",
            description="Existing curated demo project.",
            domain="osint",
            status="active",
            owner_id=_demo_id("user-owner"),
        )
        entity = Entity(
            id=_demo_id("entity-osint-repo"),
            workspace_id=_demo_id("workspace-main"),
            project_id=project.id,
            entity_type="github_repo",
            external_id="scrapy/scrapy",
            canonical_url="https://github.com/scrapy/scrapy",
            name="scrapy/scrapy",
            domain="osint",
            latest_snapshot_id=None,
            first_seen_at=now,
            last_seen_at=now,
        )
        session.add_all([project, entity])
        await session.commit()


async def _count(session: AsyncSession, model: type[Any]) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)
