from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.api.deps import AuthContext, get_auth_context
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.main import app
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
from data_intelligence_hub.services.toolkit_service import get_toolkit_overview

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


@pytest.mark.asyncio
async def test_toolkit_overview_reads_curated_training(
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
        overview = await get_toolkit_overview(session, _demo_id("workspace-main"))

    assert overview.dataset == "curated_training"
    assert overview.metrics.source_count == 44
    assert overview.metrics.tool_count >= 10
    assert overview.metrics.method_count >= 8
    assert overview.metrics.intelligence_count == 14
    assert overview.metrics.evidence_count == 40
    assert overview.tools[0].stars is not None
    assert overview.tools[0].source_credibility_score >= 60
    assert overview.tools[0].source_credibility_level in {"high", "medium", "review"}
    assert overview.tools[0].source_credibility_factors
    assert any(tool.name == "firecrawl/firecrawl" for tool in overview.tools)
    assert any(method.platform == "GitHub" for method in overview.methods)
    assert all(item.evidence_count > 0 for item in overview.intelligence_items)
    assert len(overview.lecture_playbooks) == 14
    assert len(overview.image_anchor_diagnostics) == 6
    assert len(overview.browser_labs) == 5
    assert len(overview.authorization_checklists) == 3
    assert any(
        diagnostic.source_title == "lissy93/web-check"
        for diagnostic in overview.image_anchor_diagnostics
    )
    assert any(lab.id == "browser-fingerprint-risk-diagnostics" for lab in overview.browser_labs)
    assert all(lab.acceptance_criteria for lab in overview.browser_labs)
    assert all(checklist.blocked_conditions for checklist in overview.authorization_checklists)
    assert all(
        diagnostic.evidence_urls
        for diagnostic in overview.image_anchor_diagnostics
    )
    assert all(playbook.audience for playbook in overview.lecture_playbooks)
    assert all(playbook.hands_on_steps for playbook in overview.lecture_playbooks)
    assert all(playbook.verification_steps for playbook in overview.lecture_playbooks)
    assert all(playbook.risk_boundaries for playbook in overview.lecture_playbooks)
    assert all(playbook.evidence_urls for playbook in overview.lecture_playbooks)
    assert len(overview.learning_paths) == 5
    path_by_id = {path.id: path for path in overview.learning_paths}
    assert path_by_id["github-api-baseline"].tool_count > 0
    assert path_by_id["github-api-baseline"].method_count > 0
    assert path_by_id["github-api-baseline"].evidence_count > 0
    assert path_by_id["agent-mcp-orchestration"].tool_count > 0
    assert path_by_id["agent-mcp-orchestration"].method_count > 0
    assert path_by_id["platform-sop-governance"].method_count > 0
    assert path_by_id["platform-sop-governance"].risk_level == "high"


@pytest.mark.asyncio
async def test_toolkit_route_uses_authenticated_workspace_id(
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

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    async def override_auth_context() -> AuthContext:
        async with session_factory() as session:
            user = await session.get(User, _demo_id("user-owner"))
            workspace = await session.get(Workspace, _demo_id("workspace-main"))
            assert user is not None
            assert workspace is not None
            return AuthContext(user=user, workspace=workspace)

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_auth_context] = override_auth_context
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/toolkit")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["dataset"] == "curated_training"
    assert body["metrics"]["source_count"] == 44
    assert body["metrics"]["evidence_count"] == 40
    assert len(body["learning_paths"]) == 5
    assert len(body["lecture_playbooks"]) == 14
    assert len(body["image_anchor_diagnostics"]) == 6
    assert len(body["browser_labs"]) == 5
    assert len(body["authorization_checklists"]) == 3
    assert body["tools"][0]["source_credibility_score"] >= 60
    assert body["tools"][0]["source_credibility_factors"]
    assert body["image_anchor_diagnostics"][0]["evidence_urls"]
    assert body["browser_labs"][0]["playwright_checks"]
    assert body["authorization_checklists"][0]["required_checks"]
    assert body["lecture_playbooks"][0]["hands_on_steps"]
    assert body["learning_paths"][0]["acceptance_criteria"]
    assert len(body["intelligence_items"]) == 14


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
