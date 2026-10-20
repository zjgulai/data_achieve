"""写端点 fail-closed 鉴权守卫。

守一件事：B1 之后，所有写端点在没有登录凭据时一律返回 401。

背景：B1-07 之前，`get_auth_context` 在无 token 时回退到共享 demo workspace。
匿名请求因此能以 demo 业主身份写数据。B1-08 把写路径切到
`get_authenticated_context`，本文件把这件事固定下来。

选 6 个代表端点，覆盖 5 个路由模块。逐个断言 401，不依赖响应体文案。
读接口不在此列：它们暂留 `get_auth_context`，见 ADR-007 D2。
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.main import app
from data_intelligence_hub.models import Base

# (方法, 路径, 请求体)。路径里的 id 用随机 uuid，避免命中已有数据。
WRITE_ENDPOINTS: tuple[tuple[str, str, dict[str, object]], ...] = (
    ("post", "/api/quick-collect", {"project_id": str(uuid.uuid4()), "endpoint_type": "x"}),
    ("post", f"/api/reports/{uuid.uuid4()}/send", {"channel": "email"}),
    ("post", "/api/automation/site-analysis", {"url": "https://example.com"}),
    ("put", "/api/settings/platform-credentials/tikhub", {"api_key": "x"}),
    ("post", "/api/projects", {"name": "x", "domain": "ecommerce"}),
    ("post", f"/api/projects/{uuid.uuid4()}/workflow-plans", {"name": "x"}),
)


@pytest_asyncio.fixture()
async def client() -> AsyncIterator[AsyncClient]:
    """无 cookie 的测试客户端。

    显式关掉 demo 回退，模拟生产行为（APP_ENV=production）。
    这样即使读接口的回退还在，本文件也只测写接口的拒绝。
    """
    settings = get_settings()
    original = settings.demo_mode
    settings.demo_mode = False

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
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        settings.demo_mode = original
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "path", "body"), WRITE_ENDPOINTS)
async def test_write_endpoint_rejects_anonymous(
    client: AsyncClient,
    method: str,
    path: str,
    body: dict[str, object],
) -> None:
    """无 cookie 的写请求必须返回 401，不得回退 demo workspace。"""
    response = await client.request(method, path, json=body)

    assert response.status_code == 401, (
        f"{method.upper()} {path} 返回 {response.status_code}，"
        f"期望 401；响应体 {response.text[:200]}"
    )
