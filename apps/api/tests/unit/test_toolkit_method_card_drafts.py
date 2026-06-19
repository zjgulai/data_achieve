from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.api.deps import AuthContext, get_auth_context
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.main import app
from data_intelligence_hub.models import (
    Base,
    CollectionTask,
    Project,
    RawRecord,
    Source,
    TaskRun,
    User,
    Workspace,
    WorkspaceMember,
)
from data_intelligence_hub.schemas.toolkit import (
    ToolkitMethodCardDraftRequest,
    ToolkitPreflightAuthorizationGateResponse,
    ToolkitPreflightCollectionStrategyResponse,
    ToolkitPreflightDomResponse,
    ToolkitPreflightHttpResourceResponse,
    ToolkitPreflightNetworkResponse,
    ToolkitPreflightReportResponse,
)
from data_intelligence_hub.services.toolkit_method_card_service import (
    list_method_card_drafts,
    save_method_card_draft,
)


@pytest.mark.asyncio
async def test_method_card_draft_save_is_idempotent_per_final_url() -> None:
    session_factory, engine = await _create_session_factory()
    try:
        workspace = await _create_identity(session_factory)

        async with session_factory() as session:
            first = await save_method_card_draft(
                session,
                workspace,
                ToolkitMethodCardDraftRequest(
                    preflight_report=_report("https://example.com"),
                    status="draft",
                    review_note="初稿：只允许公开页面预检。",
                ),
            )
            second = await save_method_card_draft(
                session,
                workspace,
                ToolkitMethodCardDraftRequest(
                    preflight_report=_report("https://example.com/"),
                    status="review",
                    review_note="待复核：确认 robots 和 sitemap。",
                ),
            )
            drafts = await list_method_card_drafts(session, workspace.id)

            assert first.id == second.id
            assert second.status == "review"
            assert second.method_id == "preflight-example-com"
            assert second.recommended_collector == "generic_web"
            assert second.review_note == "待复核：确认 robots 和 sitemap。"
            assert drafts == [second]
            assert await _count(session, Project) == 1
            assert await _count(session, Source) == 1
            assert await _count(session, CollectionTask) == 1
            assert await _count(session, TaskRun) == 1
            assert await _count(session, RawRecord) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_method_card_draft_routes_use_authenticated_workspace() -> None:
    session_factory, engine = await _create_session_factory()
    try:
        workspace = await _create_identity(session_factory)

        async def override_session() -> AsyncIterator[AsyncSession]:
            async with session_factory() as session:
                yield session

        async def override_auth_context() -> AuthContext:
            async with session_factory() as session:
                user = await session.get(User, workspace.owner_id)
                loaded_workspace = await session.get(Workspace, workspace.id)
                assert user is not None
                assert loaded_workspace is not None
                return AuthContext(user=user, workspace=loaded_workspace)

        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[get_auth_context] = override_auth_context
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_response = await client.post(
                "/api/toolkit/method-card-drafts",
                json={
                    "preflight_report": _report("https://example.com").model_dump(
                        mode="json"
                    ),
                    "status": "review",
                    "review_note": "API route test",
                },
            )
            list_response = await client.get("/api/toolkit/method-card-drafts")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert create_response.status_code == 201
    assert create_response.json()["status"] == "review"
    assert list_response.status_code == 200
    body = list_response.json()
    assert len(body["drafts"]) == 1
    assert body["drafts"][0]["source_url"] == "https://example.com"
    assert body["drafts"][0]["manual_confirm_state"] == "review"


def _report(final_url: str) -> ToolkitPreflightReportResponse:
    now = datetime.now(UTC)
    return ToolkitPreflightReportResponse(
        requested_url=final_url,
        final_url=final_url.rstrip("/"),
        checked_at=now,
        authorization_confirmed=True,
        headers={"content-type": "text/html; charset=utf-8"},
        redirects=[],
        robots=_resource("https://example.com/robots.txt", True),
        sitemap=_resource("https://example.com/sitemap.xml", True),
        security_txt=_resource("https://example.com/.well-known/security.txt", False),
        dom=ToolkitPreflightDomResponse(
            title="Example Domain",
            description="Example public page",
            canonical_url="https://example.com",
            meta_robots=None,
            headings=["Example Domain"],
            link_count=1,
            script_count=1,
            stylesheet_count=0,
            image_count=0,
            form_count=0,
            text_sample="Example public text",
        ),
        network=ToolkitPreflightNetworkResponse(
            request_method="GET",
            final_status_code=200,
            final_content_type="text/html; charset=utf-8",
            redirect_count=0,
            same_origin_links=1,
            external_links=0,
            script_count=1,
            stylesheet_count=0,
            image_count=0,
            form_count=0,
        ),
        authorization_gate=ToolkitPreflightAuthorizationGateResponse(
            allowed_to_continue=True,
            risk_level="low",
            blocked_reasons=[],
            required_next_actions=["可进入低风险公开页面采集实验。"],
        ),
        collection_strategy=ToolkitPreflightCollectionStrategyResponse(
            recommended_path="generic_web",
            label="静态公开页面采集",
            fit="high",
            confidence=86,
            field_stability="medium",
            reasons=["标题、链接和可见文本可从 HTML 直接读取。"],
            next_steps=["建立 DOM 字段契约，使用 generic_web 做低频公开页面采集实验。"],
            cleaning_notes=["保留 requested_url、final_url、标题、描述和正文样本。"],
        ),
        recommendations=["robots.txt 可读取，未发现全站禁止规则。"],
    )


def _resource(url: str, available: bool) -> ToolkitPreflightHttpResourceResponse:
    return ToolkitPreflightHttpResourceResponse(
        url=url,
        status_code=200 if available else 404,
        content_type="text/plain",
        content_length=24,
        available=available,
        summary="可读取" if available else "不可读取",
    )


async def _create_session_factory() -> tuple[async_sessionmaker[AsyncSession], AsyncEngine]:
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
    return async_sessionmaker(engine, expire_on_commit=False), engine


async def _create_identity(
    session_factory: async_sessionmaker[AsyncSession],
) -> Workspace:
    async with session_factory() as session:
        user = User(
            email="owner@example.com",
            password_hash="hashed-password",
            name="Data Achieve Owner",
            status="active",
        )
        session.add(user)
        await session.flush()
        workspace = Workspace(
            name="Data Achieve Intelligence Hub",
            slug="data-achieve-demo",
            owner_id=user.id,
        )
        session.add(workspace)
        await session.flush()
        session.add(
            WorkspaceMember(
                workspace_id=workspace.id,
                user_id=user.id,
                role="owner",
            )
        )
        await session.commit()
        return workspace


async def _count(session: AsyncSession, model: type[Any]) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)
