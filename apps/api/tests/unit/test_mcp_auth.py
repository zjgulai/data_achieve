from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from starlette.types import Receive, Scope, Send

from data_intelligence_hub.core import config
from data_intelligence_hub.mcp_runtime.auth import BearerTokenMiddleware


async def _ok_app(scope: Scope, receive: Receive, send: Send) -> None:
    del scope, receive
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


@pytest.mark.asyncio
async def test_mcp_auth_rejects_missing_bearer_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = config.Settings(SCRAPY_MCP_TOKEN=SecretStr("test-token"))
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    import data_intelligence_hub.mcp_runtime.auth as auth_module

    monkeypatch.setattr(auth_module, "get_settings", lambda: settings)
    transport = ASGITransport(app=BearerTokenMiddleware(_ok_app))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/")

    assert response.status_code == 401
    assert response.json()["detail"] == "mcp_authentication_required"


@pytest.mark.asyncio
async def test_mcp_auth_accepts_matching_bearer_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = config.Settings(SCRAPY_MCP_TOKEN=SecretStr("test-token"))
    import data_intelligence_hub.mcp_runtime.auth as auth_module

    monkeypatch.setattr(auth_module, "get_settings", lambda: settings)
    transport = ASGITransport(app=BearerTokenMiddleware(_ok_app))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/",
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    assert response.text == "ok"


def test_settings_support_multiple_client_tokens() -> None:
    settings = config.Settings(
        SCRAPY_MCP_TOKENS_JSON={
            "claude": SecretStr("token-a"),
            "codex": SecretStr("token-b"),
        },
    )

    assert set(settings.accepted_mcp_tokens) == {"token-a", "token-b"}
