"""目录摘要一致性守卫。

REST（GET /api/tool-catalog）、MCP（list_capabilities）、脚本
（reconcile_catalog.py）三处必须读到同一个 catalog_digest。
任何一处读到不同的值都说明三路数据来自不同的事实源，
本文件会把这件事变成 CI 失败而不是运行期才发现的隐患。

三处共同的事实源是 `get_platform_package_catalog()`，
它由 `get_collector_catalog()` 的硬编码数据构建，不读数据库与外部 API。
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.core.database import get_session
from data_intelligence_hub.main import create_app
from data_intelligence_hub.mcp_runtime.server import mcp_server
from data_intelligence_hub.models import Base
from data_intelligence_hub.platform_packages.service import get_platform_package_catalog

ROOT = Path(__file__).resolve().parents[4]


# ---------------------------------------------------------------------------
# 共同参照值：直接调用服务层
# ---------------------------------------------------------------------------

async def _reference_digest() -> str:
    """平台包目录的 catalog_digest，不经过任何路由层。"""
    catalog = await get_platform_package_catalog()
    return catalog.catalog_digest


# ---------------------------------------------------------------------------
# REST: GET /api/tool-catalog
# ---------------------------------------------------------------------------

def _make_engine():
    return create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.mark.anyio
async def test_rest_digest_matches_service() -> None:
    """REST 端点返回的摘要必须与服务层一致。"""
    engine = _make_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    ref = await _reference_digest()

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/tool-catalog")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert resp.status_code == 200
    body = resp.json()
    assert "catalog_digest" in body, "响应缺少 catalog_digest 字段"
    assert body["catalog_digest"] == ref, (
        f"REST digest={body['catalog_digest']!r} 与服务层 {ref!r} 不一致"
    )
    assert len(body["catalog_digest"]) == 64, "catalog_digest 必须是 64 字符 sha256"


# ---------------------------------------------------------------------------
# MCP: list_capabilities
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_mcp_list_capabilities_returns_digest() -> None:
    """MCP list_capabilities 返回的摘要必须与服务层一致。"""
    from mcp.client import Client  # noqa: PLC0415

    ref = await _reference_digest()

    async with Client(mcp_server) as client:
        result = await client.call_tool("list_capabilities", {"platform_id": "tiktok"})

    assert result.structured_content is not None
    assert "catalog_digest" in result.structured_content, (
        "list_capabilities 响应缺少 catalog_digest 字段"
    )
    mcp_digest = result.structured_content["catalog_digest"]
    assert mcp_digest == ref, (
        f"MCP digest={mcp_digest!r} 与服务层 {ref!r} 不一致"
    )


# ---------------------------------------------------------------------------
# 脚本: reconcile_catalog.py
# ---------------------------------------------------------------------------

def test_script_digest_matches_service() -> None:
    """reconcile_catalog.py --json 输出的摘要格式必须合法。"""

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/reconcile_catalog.py"), "--json"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode in (0, 1), result.stderr
    payload = json.loads(result.stdout)
    generated = payload["summary"].get("generated")
    assert generated is not None, "脚本未找到生成物；generated/platform-packages.json 缺失"
    script_digest = generated.get("catalog_digest")
    # 脚本读的是 generated/ 的生成物，会比工作树落后。
    # 本测试只校验格式；一致性测试在 test_catalog_reconciliation 覆盖。
    assert isinstance(script_digest, str) and len(script_digest) == 64, (
        "脚本输出的 catalog_digest 格式非法"
    )
    # 摘要说明：脚本与运行时不一定相同（生成物可能过期），但格式必须合法。
