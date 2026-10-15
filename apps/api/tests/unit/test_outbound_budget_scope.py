"""A parent collection and nested page fetches must consume the same budget."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import httpx
import pytest

from data_intelligence_hub.collectors.base import CollectorError
from data_intelligence_hub.collectors.ecommerce_product_page import EcommerceProductPageCollector
from data_intelligence_hub.collectors.generic_web import GenericWebCollector
from data_intelligence_hub.collectors.guarded_http import collection_scope
from data_intelligence_hub.core.config import get_settings


@pytest.mark.asyncio
async def test_ecommerce_uses_its_grant_without_generic_web_grant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COLLECTION_NETWORK_MODE", "restricted")
    monkeypatch.setenv(
        "COLLECTION_HTTP_GRANTS",
        json.dumps(
            [
                {
                    "collector_type": "ecommerce_product_page",
                    "hosts": ["example.com"],
                    "expires_at": "2099-01-01T00:00:00Z",
                    "max_requests": 2,
                }
            ]
        ),
    )
    get_settings.cache_clear()
    from data_intelligence_hub.collectors import generic_web

    monkeypatch.setattr(generic_web, "_assert_public_http_url", AsyncMock())
    try:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, text="<html><title>Item</title></html>")
            )
        ) as client:
            result = await EcommerceProductPageCollector(
                {"url": "https://example.com/p"}, client
            ).collect()
        assert len(result.raw_records) == 1
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_nested_requests_share_run_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLLECTION_NETWORK_MODE", "restricted")
    monkeypatch.setenv(
        "COLLECTION_HTTP_GRANTS",
        json.dumps(
            [
                {
                    "collector_type": "ecommerce_product_page",
                    "hosts": ["example.com"],
                    "expires_at": "2099-01-01T00:00:00Z",
                    "max_requests": 2,
                }
            ]
        ),
    )
    get_settings.cache_clear()
    from data_intelligence_hub.collectors import generic_web

    monkeypatch.setattr(generic_web, "_assert_public_http_url", AsyncMock())
    sent: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        sent.append(request.url.path)
        return httpx.Response(200, text="<p>Item</p>")

    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with collection_scope("ecommerce_product_page"):
                await EcommerceProductPageCollector(
                    {"url": "https://example.com/1"}, client
                ).collect()
                await GenericWebCollector({"url": "https://example.com/2"}, client).collect()
                with pytest.raises(CollectorError, match="outbound_budget_exceeded"):
                    await GenericWebCollector({"url": "https://example.com/3"}, client).collect()
        assert sent == ["/1", "/2"]
    finally:
        get_settings.cache_clear()
