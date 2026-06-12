from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base


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
        yield async_client

    app.dependency_overrides.clear()
    await engine.dispose()


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
