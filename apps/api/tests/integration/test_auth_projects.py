from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.core.security import hash_password
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace, WorkspaceMember
from data_intelligence_hub.repositories.workspaces import DEMO_WORKSPACE_SLUG


@pytest_asyncio.fixture()
async def client() -> AsyncIterator[AsyncClient]:
    async for async_client in _build_client():
        yield async_client


@pytest_asyncio.fixture()
async def demo_client() -> AsyncIterator[AsyncClient]:
    async for async_client in _build_client(seed_demo=True):
        yield async_client


async def _build_client(*, seed_demo: bool = False) -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    if seed_demo:
        await _seed_demo_workspace(session_factory)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client

    app.dependency_overrides.clear()
    await engine.dispose()


async def _seed_demo_workspace(session_factory: async_sessionmaker[AsyncSession]) -> None:
    owner_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    async with session_factory() as session:
        session.add_all(
            [
                User(
                    id=owner_id,
                    email="demo-owner@example.com",
                    password_hash=hash_password("strong-password"),
                    name="Demo Owner",
                    status="active",
                ),
                Workspace(
                    id=workspace_id,
                    name="Data Achieve Intelligence Hub",
                    slug=DEMO_WORKSPACE_SLUG,
                    owner_id=owner_id,
                ),
                WorkspaceMember(workspace_id=workspace_id, user_id=owner_id, role="owner"),
                Project(
                    workspace_id=workspace_id,
                    owner_id=owner_id,
                    name="Training Intelligence Corpus",
                    description=(
                        "Seeded project proving registered users do not see an empty shell."
                    ),
                    domain="osint",
                    status="active",
                ),
            ]
        )
        await session.commit()


@pytest.mark.asyncio
async def test_register_creates_user_workspace_and_cookie(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={"email": "Owner@Example.com", "password": "strong-password", "name": "Owner"},
    )

    assert response.status_code == 201
    assert "access_token" in response.cookies
    payload = response.json()
    assert payload["user"]["email"] == "owner@example.com"
    assert payload["workspace"]["slug"] == "owner"

    me_response = await client.get("/api/auth/me")

    assert me_response.status_code == 200
    assert me_response.json()["workspace"]["id"] == payload["workspace"]["id"]


@pytest.mark.asyncio
async def test_register_defaults_to_demo_workspace_when_available(
    demo_client: AsyncClient,
) -> None:
    response = await demo_client.post(
        "/api/auth/register",
        json={"email": "new-user@example.com", "password": "strong-password", "name": "New User"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["workspace"]["slug"] == DEMO_WORKSPACE_SLUG

    me_response = await demo_client.get("/api/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["workspace"]["slug"] == DEMO_WORKSPACE_SLUG

    projects_response = await demo_client.get("/api/projects")
    assert projects_response.status_code == 200
    assert [project["name"] for project in projects_response.json()] == [
        "Training Intelligence Corpus"
    ]

    notifications_response = await demo_client.get("/api/notifications")
    assert notifications_response.status_code == 200
    notification_types = [
        notification["notification_type"] for notification in notifications_response.json()
    ]
    assert notification_types == [
        "training_workspace_ready"
    ]


@pytest.mark.asyncio
async def test_login_rejects_invalid_password(client: AsyncClient) -> None:
    await client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "strong-password", "name": "Owner"},
    )

    response = await client.post(
        "/api/auth/login",
        json={"email": "owner@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_project_crud_is_scoped_to_current_workspace(client: AsyncClient) -> None:
    await client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "strong-password", "name": "Owner"},
    )

    create_response = await client.post(
        "/api/projects",
        json={
            "name": "AI Scrapy Tools",
            "description": "Track open-source scraping tools.",
            "domain": "osint",
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["status"] == "active"

    list_response = await client.get("/api/projects?domain=osint")
    assert list_response.status_code == 200
    assert [project["id"] for project in list_response.json()] == [created["id"]]

    update_response = await client.patch(
        f"/api/projects/{created['id']}",
        json={"name": "AI Scrapy Radar"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "AI Scrapy Radar"

    archive_response = await client.delete(f"/api/projects/{created['id']}")
    assert archive_response.status_code == 200
    assert archive_response.json()["status"] == "archived"


@pytest.mark.asyncio
async def test_projects_require_authentication(client: AsyncClient) -> None:
    client.cookies.clear()

    response = await client.get("/api/projects")

    assert response.status_code == 401
