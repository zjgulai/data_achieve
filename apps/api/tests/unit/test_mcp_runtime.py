from __future__ import annotations

import pytest
from mcp.client import Client
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.mcp_runtime import capability_service
from data_intelligence_hub.mcp_runtime.server import mcp_server
from data_intelligence_hub.models import Base


@pytest.mark.anyio
async def test_mcp_lists_platforms_and_describes_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(
        capability_service,
        "async_session_factory",
        async_sessionmaker(engine, expire_on_commit=False),
    )
    try:
        async with Client(mcp_server) as client:
            platforms = await client.call_tool("list_platforms", {"query": "TikTok"})
            capability = await client.call_tool(
                "describe_capability",
                {"endpoint_type": "tikhub_tiktok_video_search"},
            )
    finally:
        await engine.dispose()

    assert platforms.structured_content is not None
    assert len(platforms.structured_content["platforms"]) == 3
    assert capability.structured_content is not None
    assert capability.structured_content["tool_id"] == "tikhub_tiktok_video_search"
    assert capability.structured_content["input_schema"]["type"] == "object"
    output_schema = capability.structured_content["output_schema"]
    assert output_schema["type"] == "object"
    assert output_schema["$schema"]
    assert "policy_block_reason" not in capability.structured_content
    assert "authorization" not in capability.structured_content


@pytest.mark.anyio
async def test_mcp_registers_run_query_tools() -> None:
    tools = await mcp_server.list_tools()
    names = {tool.name for tool in tools}
    assert {"get_run", "list_records"} <= names


@pytest.mark.anyio
async def test_mcp_tools_have_descriptions_and_annotations() -> None:
    tools = await mcp_server.list_tools()
    assert tools
    for tool in tools:
        assert tool.description, tool.name
        assert tool.annotations is not None, tool.name
        assert tool.annotations.read_only_hint is not None, tool.name
        assert tool.annotations.open_world_hint is not None, tool.name


@pytest.mark.anyio
async def test_mcp_rejects_unknown_capability() -> None:
    async with Client(mcp_server, raise_exceptions=False) as client:
        result = await client.call_tool(
            "describe_capability",
            {"endpoint_type": "missing_endpoint"},
        )

    assert result.is_error is True
