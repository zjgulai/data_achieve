from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.api.deps import AuthContext, get_auth_context
from data_intelligence_hub.api.routes import platform_credentials as credential_routes
from data_intelligence_hub.core.config import Settings
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.capability_governance import CapabilityCatalogHead


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
    async with session_factory() as session:
        session.add(
            CapabilityCatalogHead(
                singleton_key="global",
                current_revision_id=None,
                head_version=0,
            )
        )
        await session.commit()

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client

    app.dependency_overrides.clear()
    await engine.dispose()


async def register_owner(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "credential-owner@example.com",
            "password": "StrongPassword123!",
            "name": "Credential Owner",
        },
    )
    assert response.status_code == 201


async def _deny_authentication() -> AuthContext:
    """注入拒绝鉴权的 auth 依赖替身。

    get_auth_context 对匿名请求走 demo workspace 回退（无 demo 工作区时
    503），永不 401；「鉴权被拒 -> 401」这条契约只能靠依赖替身演练，
    与 test_workflow_plan_persistence_routes.py 的 deny_authentication 同法。
    """
    raise HTTPException(status_code=401, detail="Authentication required")


@pytest.mark.asyncio
async def test_platform_credential_routes_require_authentication(
    client: AsyncClient,
) -> None:
    app.dependency_overrides[get_auth_context] = _deny_authentication
    try:
        response = await client.get("/api/settings/platform-credentials")
    finally:
        app.dependency_overrides.pop(get_auth_context, None)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_owner_can_store_list_and_remove_without_secret_echo(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await register_owner(client)
    settings = Settings(platform_credential_master_key=Fernet.generate_key().decode())
    monkeypatch.setattr(credential_routes, "get_settings", lambda: settings)

    initial = await client.get("/api/settings/platform-credentials")
    assert initial.status_code == 200
    assert len(initial.json()["platforms"]) == 7
    assert initial.json()["credential_read_attempted"] is False

    fixture_value = "route-fixture-value-never-returned"
    saved = await client.put(
        "/api/settings/platform-credentials/youtube",
        json={"values": {"api_key": fixture_value}},
    )
    assert saved.status_code == 200
    assert saved.json()["configured"] is True
    assert fixture_value not in saved.text

    listed = await client.get("/api/settings/platform-credentials")
    assert listed.status_code == 200
    assert fixture_value not in listed.text
    youtube = next(item for item in listed.json()["platforms"] if item["platform"] == "youtube")
    assert youtube["configured"] is True

    removed = await client.delete("/api/settings/platform-credentials/youtube")
    assert removed.status_code == 200
    assert removed.json()["configured"] is False
    assert fixture_value not in removed.text
