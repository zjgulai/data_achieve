from __future__ import annotations

import pytest
from mcp.client import Client

from data_intelligence_hub.mcp_runtime.server import mcp_server


@pytest.mark.anyio
async def test_mcp_lists_platforms_and_describes_capability() -> None:
    async with Client(mcp_server) as client:
        platforms = await client.call_tool("list_platforms", {"query": "TikTok"})
        capability = await client.call_tool(
            "describe_capability",
            {"endpoint_type": "tikhub_tiktok_video_search"},
        )

    assert platforms.structured_content is not None
    assert len(platforms.structured_content["platforms"]) == 3
    assert capability.structured_content is not None
    assert capability.structured_content["endpoint_type"] == "tikhub_tiktok_video_search"


@pytest.mark.anyio
async def test_mcp_rejects_unknown_capability() -> None:
    async with Client(mcp_server, raise_exceptions=False) as client:
        result = await client.call_tool(
            "describe_capability",
            {"endpoint_type": "missing_endpoint"},
        )

    assert result.is_error is True
