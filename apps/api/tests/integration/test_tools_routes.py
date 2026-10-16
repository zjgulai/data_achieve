"""/api/tools 只读路由契约测试。

这是工具目录唯一的对外暴露面。两条边界必须守住：

1. 只读：不接受执行请求，不引入绕过执行鉴权的路径。
2. 不泄漏治理字段：`authorization` 与策略拒绝原文留在服务端。
   把它们发布到匿名可读的端点上等于对外公告自身弱点。
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.workspaces import DEMO_WORKSPACE_SLUG

# 治理字段：出现在对外响应里即为泄漏。
_FORBIDDEN_KEYS = ("authorization", "reachability", "block_reason")


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
        async_client.session_factory = session_factory  # type: ignore[attr-defined]
        yield async_client

    app.dependency_overrides.clear()
    await engine.dispose()


async def _seed_demo_workspace(client: AsyncClient) -> None:
    """建一个 demo workspace + 一个属于它的 project。

    provider 状态查询需要一个可归属的工作区，缺它接口会 503。
    """
    session_factory = client.session_factory  # type: ignore[attr-defined]
    async with session_factory() as session:
        owner = User(email="owner@example.com", password_hash="x", name="Owner")
        session.add(owner)
        await session.flush()

        workspace_id = uuid.uuid4()
        session.add(
            Workspace(
                id=workspace_id,
                name="Demo",
                slug=DEMO_WORKSPACE_SLUG,
                owner_id=owner.id,
            )
        )
        await session.flush()
        session.add(
            Project(
                workspace_id=workspace_id,
                name="采集验证",
                domain="osint",
                owner_id=owner.id,
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_list_tools_returns_the_catalog(client: AsyncClient) -> None:
    await _seed_demo_workspace(client)
    response = await client.get("/api/tools")

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_count"] > 0
    assert payload["tool_count"] == len(payload["tools"])
    assert payload["schema_version"] == "tool-catalog.v1"
    # 目录摘要必须有值，它是这棵树的版本锚。
    assert payload["catalog_digest"]


@pytest.mark.asyncio
async def test_list_tools_does_not_leak_governance_fields(client: AsyncClient) -> None:
    """对外响应不得含授权现状与策略拒绝原文。

    内部契约里 258 条都带 block_reason（策略拒绝文案），
    对外响应里一条都不能有。
    """
    await _seed_demo_workspace(client)
    response = await client.get("/api/tools")
    assert response.status_code == 200

    raw = response.text
    for forbidden in _FORBIDDEN_KEYS:
        assert f'"{forbidden}"' not in raw, f"对外响应泄漏了 {forbidden}"
    assert "collection_policy_denied" not in raw
    assert "demo_workspace" not in raw


@pytest.mark.asyncio
async def test_read_tool_exposes_types_but_not_governance(client: AsyncClient) -> None:
    await _seed_demo_workspace(client)
    listed = (await client.get("/api/tools")).json()
    tool_id = listed["tools"][0]["tool_id"]

    response = await client.get(f"/api/tools/{tool_id}")
    assert response.status_code == 200
    tool = response.json()
    assert tool["tool_id"] == tool_id
    # 参数只保留发现所需字段，不带治理判断。
    for parameter in tool["parameters"]:
        assert set(parameter) & {"authorization", "block_reason"} == set()


@pytest.mark.asyncio
async def test_read_tool_carries_execution_reachability(client: AsyncClient) -> None:
    """可执行性要能查，但只给布尔，不给策略原文。"""
    await _seed_demo_workspace(client)
    response = await client.get("/api/tools")
    assert response.status_code == 200

    tools = response.json()["tools"]
    assert tools
    for tool in tools:
        assert isinstance(tool["executable_now"], bool)
        assert isinstance(tool["permanently_blocked"], bool)
        assert tool["execution_kind"] in {
            "offline",
            "guarded_http",
            "provider_api",
            "unsupported",
        }
        # 永久拒绝的必然当前不可执行。
        if tool["permanently_blocked"]:
            assert tool["executable_now"] is False


@pytest.mark.asyncio
async def test_unknown_tool_returns_404(client: AsyncClient) -> None:
    await _seed_demo_workspace(client)
    response = await client.get("/api/tools/definitely_not_a_real_tool_id")
    assert response.status_code == 404
    assert response.json()["detail"] == "tool_not_found"


@pytest.mark.asyncio
async def test_query_filter_narrows_the_result(client: AsyncClient) -> None:
    await _seed_demo_workspace(client)
    full = (await client.get("/api/tools")).json()["tool_count"]

    filtered = await client.get("/api/tools", params={"query": "tiktok"})
    assert filtered.status_code == 200
    payload = filtered.json()
    assert payload["tool_count"] < full
    assert payload["tool_count"] == len(payload["tools"])
    assert all("tiktok" in tool["tool_id"].casefold() or
               "tiktok" in tool["label"].casefold() or
               "tiktok" in tool["description"].casefold() or
               "tiktok" in tool["platform"].casefold() for tool in payload["tools"])


@pytest.mark.asyncio
async def test_invalid_risk_class_is_rejected(client: AsyncClient) -> None:
    await _seed_demo_workspace(client)
    response = await client.get("/api/tools", params={"risk_class": "bogus"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_route_is_read_only(client: AsyncClient) -> None:
    """这条路由不接受任何写方法。

    执行仍走既有 quick-collect 与 MCP 入口；本路由不得成为新旁路。
    """
    await _seed_demo_workspace(client)
    for method in ("post", "put", "patch"):
        response = await getattr(client, method)("/api/tools", json={})
        assert response.status_code == 405, f"{method.upper()} 竟然被接受"
    # delete 不接受请求体，单独调用。
    response = await client.delete("/api/tools")
    assert response.status_code == 405, "DELETE 竟然被接受"
