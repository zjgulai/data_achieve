from __future__ import annotations

import hashlib
import io
import zipfile
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
    """平台包列表/详情读取实时证据，因此显式注入测试数据库。"""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncGenerator[object, None]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_platform_package_routes_list_detail_and_playbook(
    client: AsyncClient,
) -> None:
    listing = await client.get("/api/platform-packages", params={"query": "TikTok"})
    detail = await client.get("/api/platform-packages/tiktok")
    playbook = await client.get("/api/platform-packages/tiktok/playbook")
    download = await client.get("/api/platform-packages/tiktok/download")
    release = await client.get("/api/platform-packages/tiktok/release")

    assert listing.status_code == 200
    assert listing.json()["platform_count"] == 3
    assert detail.status_code == 200
    assert detail.json()["platform_id"] == "tiktok"
    assert playbook.status_code == 200
    assert playbook.json()["platform_id"] == "tiktok"
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        assert set(archive.namelist()) == {
            "SKILL.md",
            "README.md",
            "manifest.json",
            "references/playbook.md",
            "evals/trigger_cases.json",
        }
    assert release.status_code == 200
    assert release.json()["version"].startswith("1.0.0+")
    assert len(release.json()["archive_sha256"]) == 64
    assert release.json()["archive_sha256"] == hashlib.sha256(download.content).hexdigest()


@pytest.mark.asyncio
async def test_platform_package_route_returns_stable_not_found() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/platform-packages/missing-platform")

    assert response.status_code == 404
    assert response.json()["detail"] == "platform_package_not_found"
