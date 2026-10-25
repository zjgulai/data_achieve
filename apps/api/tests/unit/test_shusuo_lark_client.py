from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest

from data_intelligence_hub.agents.shusuo import lark_client


@pytest.fixture(autouse=True)
def _reset_bot_cache() -> Iterator[None]:
    lark_client._bot_cache["open_id"] = ""
    yield
    lark_client._bot_cache["open_id"] = ""


@pytest.mark.asyncio
async def test_get_bot_open_id_caches_success(monkeypatch: pytest.MonkeyPatch) -> None:
    token_calls = 0
    request_calls = 0

    async def fake_token() -> str:
        nonlocal token_calls
        token_calls += 1
        return "token"

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"code": 0, "bot": {"open_id": "ou_bot"}}

    class Client:
        async def __aenter__(self) -> Client:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def get(self, *args: object, **kwargs: object) -> Response:
            nonlocal request_calls
            request_calls += 1
            return Response()

    monkeypatch.setattr(lark_client, "get_tenant_token", fake_token)
    monkeypatch.setattr(lark_client.httpx, "AsyncClient", lambda **kwargs: Client())

    assert await lark_client.get_bot_open_id() == "ou_bot"
    assert await lark_client.get_bot_open_id() == "ou_bot"
    assert token_calls == 1
    assert request_calls == 1


@pytest.mark.asyncio
async def test_get_bot_open_id_does_not_cache_feishu_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token_calls = 0
    request_calls = 0

    async def fake_token() -> str:
        nonlocal token_calls
        token_calls += 1
        return "token"

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"code": 99991663, "msg": "internal error"}

    class Client:
        async def __aenter__(self) -> Client:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def get(self, *args: object, **kwargs: object) -> Response:
            nonlocal request_calls
            request_calls += 1
            return Response()

    monkeypatch.setattr(lark_client, "get_tenant_token", fake_token)
    monkeypatch.setattr(lark_client.httpx, "AsyncClient", lambda **kwargs: Client())

    assert await lark_client.get_bot_open_id() == ""
    assert await lark_client.get_bot_open_id() == ""
    assert token_calls == 2
    assert request_calls == 2


@pytest.mark.asyncio
async def test_get_bot_open_id_propagates_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_token() -> str:
        return "token"

    request = httpx.Request("GET", "https://open.feishu.cn/open-apis/bot/v3/info")
    response = httpx.Response(503, request=request)
    expected_error = httpx.HTTPStatusError(
        "service unavailable",
        request=request,
        response=response,
    )

    class Response:
        def raise_for_status(self) -> None:
            raise expected_error

        def json(self) -> dict[str, object]:
            raise AssertionError("json must not be read after an HTTP error")

    class Client:
        async def __aenter__(self) -> Client:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def get(self, *args: object, **kwargs: object) -> Response:
            return Response()

    monkeypatch.setattr(lark_client, "get_tenant_token", fake_token)
    monkeypatch.setattr(lark_client.httpx, "AsyncClient", lambda **kwargs: Client())

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await lark_client.get_bot_open_id()

    assert exc_info.value is expected_error


@pytest.mark.asyncio
async def test_reply_card_propagates_lark_api_error(monkeypatch) -> None:
    """卡片请求失败抛结构化错误，由调用方降级文本。"""

    async def fail_request(*args: object, **kwargs: object) -> dict[str, object]:
        raise lark_client.LarkAPIError(99991672, "card send denied")

    monkeypatch.setattr(lark_client, "_request", fail_request)

    with pytest.raises(lark_client.LarkAPIError):
        await lark_client.reply_card("om-source", {"schema": "2.0"})
