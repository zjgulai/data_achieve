from __future__ import annotations

import hmac

from starlette.types import ASGIApp, Receive, Scope, Send

from data_intelligence_hub.core.config import get_settings


class BearerTokenMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        tokens = get_settings().accepted_mcp_tokens
        if not tokens or scope.get("type") != "http":
            await self._app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        provided = headers.get(b"authorization", b"").decode()
        if any(hmac.compare_digest(provided, f"Bearer {token}") for token in tokens):
            await self._app(scope, receive, send)
            return
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b'{"detail":"mcp_authentication_required"}',
            }
        )
