"""只读接口 GET /api/settings/mcp-tool-policies 的路由测试。

该接口把 Task 1 的策略注册表原样暴露给 Console 密钥页：
registry_version、tool_count、每个工具的策略字段、Console 预设。
注册表是静态事实源，不落库；测试用 ASGITransport 打真实路由。
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from data_intelligence_hub.api.deps import get_authenticated_context, get_session
from data_intelligence_hub.api.routes.mcp_tool_policies import router
from data_intelligence_hub.core.database import get_session as core_get_session
from data_intelligence_hub.mcp_runtime.tool_registry import (
    PRESETS,
    REGISTRY_VERSION,
    TOOL_POLICIES,
)


async def _noop_session() -> AsyncIterator[None]:
    yield None  # pragma: no cover - 本路由不触库，仅防依赖解析失败


@pytest.fixture()
def client() -> AsyncClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/settings")

    async def override_session() -> AsyncIterator[None]:
        yield None

    async def override_auth() -> None:
        return None

    app.dependency_overrides[core_get_session] = override_session
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_authenticated_context] = override_auth
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.anyio
async def test_returns_registry_summary(client: AsyncClient) -> None:
    response = await client.get("/api/settings/mcp-tool-policies")
    assert response.status_code == 200
    body = response.json()
    assert body["registry_version"] == REGISTRY_VERSION == "n1.v1"
    assert body["tool_count"] == len(TOOL_POLICIES) == 39
    assert set(body["presets"].keys()) == set(PRESETS.keys())
    for name, members in PRESETS.items():
        assert sorted(body["presets"][name]) == sorted(members)


@pytest.mark.anyio
async def test_tool_entries_carry_policy_fields(client: AsyncClient) -> None:
    response = await client.get("/api/settings/mcp-tool-policies")
    body = response.json()
    names = [entry["name"] for entry in body["tools"]]
    assert sorted(names) == sorted(TOOL_POLICIES)

    by_name = {entry["name"]: entry for entry in body["tools"]}
    web_search = by_name["web_search"]
    assert web_search["access_mode"] == "execute"
    assert web_search["requires_project"] is True
    assert web_search["project_scope"] == "bound_project"
    assert web_search["consumes_quota"] == "per_call"
    assert web_search["run_mode"] == "both"
    assert web_search["cancellable"] is False
    assert sorted(web_search["preset_groups"]) == sorted(
        TOOL_POLICIES["web_search"].preset_groups
    )

    list_platforms = by_name["list_platforms"]
    assert list_platforms["access_mode"] == "read"
    assert list_platforms["requires_project"] is False
    assert list_platforms["consumes_quota"] == "none"


@pytest.mark.anyio
async def test_unauthenticated_request_is_rejected() -> None:
    """fail-closed：不注入鉴权依赖时必须 401，注册表不匿名开放。"""
    app = FastAPI()
    app.include_router(router, prefix="/api/settings")

    async def override_session() -> AsyncIterator[None]:
        yield None

    app.dependency_overrides[core_get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/settings/mcp-tool-policies")
    assert response.status_code == 401
