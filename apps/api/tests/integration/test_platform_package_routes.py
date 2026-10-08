from __future__ import annotations

import io
import zipfile

import pytest
from httpx import ASGITransport, AsyncClient

from data_intelligence_hub.main import app


@pytest.mark.asyncio
async def test_platform_package_routes_list_detail_and_playbook() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        listing = await client.get("/api/platform-packages", params={"query": "TikTok"})
        detail = await client.get("/api/platform-packages/tiktok")
        playbook = await client.get("/api/platform-packages/tiktok/playbook")
        download = await client.get("/api/platform-packages/tiktok/download")

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


@pytest.mark.asyncio
async def test_platform_package_route_returns_stable_not_found() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/platform-packages/missing-platform")

    assert response.status_code == 404
    assert response.json()["detail"] == "platform_package_not_found"
