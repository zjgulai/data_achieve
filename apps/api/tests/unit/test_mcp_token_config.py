from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.types import Receive, Scope, Send

from data_intelligence_hub.core import config
from data_intelligence_hub.mcp_runtime.auth import BearerTokenMiddleware


async def _ok_app(scope: Scope, receive: Receive, send: Send) -> None:
    del scope, receive
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def test_blank_env_token_is_treated_as_unset() -> None:
    """`SCRAPY_MCP_TOKEN=`（空串，compose 默认注入）不得被当作有效 token。

    否则 accepted_mcp_tokens 非空 → 中间件对所有人 401，且没有任何 token 能通过。
    """
    settings = config.Settings(SCRAPY_MCP_TOKEN="")
    assert settings.mcp_token is None
    assert settings.accepted_mcp_tokens == ()


def test_blank_tokens_json_entries_are_ignored() -> None:
    settings = config.Settings(SCRAPY_MCP_TOKENS_JSON={"claude": "", "codex": "  "})
    assert settings.accepted_mcp_tokens == ()


@pytest.mark.asyncio
async def test_blank_token_env_allows_unauthenticated_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = config.Settings(SCRAPY_MCP_TOKEN="")
    import data_intelligence_hub.mcp_runtime.auth as auth_module

    monkeypatch.setattr(auth_module, "get_settings", lambda: settings)
    transport = ASGITransport(app=BearerTokenMiddleware(_ok_app))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/")

    assert response.status_code == 200
