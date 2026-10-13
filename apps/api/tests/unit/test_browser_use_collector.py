"""Unit tests for BrowserUseCollector.

The collector is an HTTP client for the browser-use bridge container — the
library itself is not installed here. All tests mock httpx.AsyncClient, so no
bridge and no LLM key are required.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from data_intelligence_hub.collectors.base import CollectorError
from data_intelligence_hub.collectors.browser_use_collector import (
    BrowserUseCollector,
    _bridge_headers,
    _bridge_url,
)


def _collector(config: dict[str, Any]) -> BrowserUseCollector:
    return BrowserUseCollector(config=config)


def _fake_client(response: Any = None, error: Exception | None = None):
    client = AsyncMock()
    if error is not None:
        client.post = AsyncMock(side_effect=error)
        client.get = AsyncMock(side_effect=error)
    else:
        client.post = AsyncMock(return_value=response)
        client.get = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


def _response(body: Any, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json = MagicMock(return_value=body)
    return response


class TestValidateConfig:
    def test_missing_task_raises(self):
        with pytest.raises(CollectorError, match="task"):
            _collector({}).validate_config()

    def test_defaults(self):
        cfg = _collector({"task": "get the title"}).validate_config()
        assert cfg == {"task": "get the title", "url": "", "max_steps": 10}

    def test_max_steps_bounds(self):
        with pytest.raises(CollectorError, match="max_steps"):
            _collector({"task": "t", "max_steps": 0}).validate_config()
        with pytest.raises(CollectorError, match="max_steps"):
            _collector({"task": "t", "max_steps": 51}).validate_config()

    def test_private_url_rejected(self):
        with pytest.raises(CollectorError, match="private or loopback"):
            _collector({"task": "t", "url": "http://localhost:8000/x"}).validate_config()


class TestEnvHelpers:
    def test_bridge_url_default(self, monkeypatch):
        monkeypatch.delenv("BROWSER_USE_BRIDGE_URL", raising=False)
        assert _bridge_url() == "http://browser-use:5002"

    def test_bridge_url_override_and_trailing_slash(self, monkeypatch):
        monkeypatch.setenv("BROWSER_USE_BRIDGE_URL", "http://host:9999/")
        assert _bridge_url() == "http://host:9999"

    def test_bridge_headers(self, monkeypatch):
        monkeypatch.delenv("BROWSER_USE_BRIDGE_KEY", raising=False)
        assert _bridge_headers() == {}
        monkeypatch.setenv("BROWSER_USE_BRIDGE_KEY", "secret")
        assert _bridge_headers() == {"Authorization": "Bearer secret"}


class TestTest:
    @pytest.mark.asyncio
    async def test_bridge_unreachable(self):
        with patch(
            "data_intelligence_hub.collectors.browser_use_collector.httpx.AsyncClient",
            return_value=_fake_client(error=httpx.ConnectError("refused")),
        ):
            result = await _collector({"task": "t"}).test()
        assert result.status == "failed"
        assert "unreachable" in result.message

    @pytest.mark.asyncio
    async def test_bridge_reports_degraded(self):
        """A reachable bridge with no LLM key must not look healthy."""
        body = {"status": "degraded", "llm_error": "ANTHROPIC_API_KEY not set"}
        with patch(
            "data_intelligence_hub.collectors.browser_use_collector.httpx.AsyncClient",
            return_value=_fake_client(response=_response(body)),
        ):
            result = await _collector({"task": "t"}).test()
        assert result.status == "failed"
        assert "ANTHROPIC_API_KEY" in result.message

    @pytest.mark.asyncio
    async def test_bridge_healthy(self):
        body = {
            "status": "ok",
            "browser_use": "0.13.11",
            "provider": "anthropic",
            "model": "claude-sonnet-4-5-20250929",
            "backend": "obscura",
        }
        with patch(
            "data_intelligence_hub.collectors.browser_use_collector.httpx.AsyncClient",
            return_value=_fake_client(response=_response(body)),
        ):
            result = await _collector({"task": "t"}).test()
        assert result.status == "ok"
        assert "0.13.11" in result.message
        assert "obscura" in result.message


class TestCollect:
    @pytest.mark.asyncio
    async def test_success_maps_record_fields(self):
        body = {
            "ok": True,
            "result": "The title is Example Domain",
            "success": True,
            "steps": 3,
            "urls": ["https://example.com/"],
            "backend": "obscura",
            "provider": "anthropic",
            "model": "claude-sonnet-4-5-20250929",
            "duration_ms": 4200,
        }
        with patch(
            "data_intelligence_hub.collectors.browser_use_collector.httpx.AsyncClient",
            return_value=_fake_client(response=_response(body)),
        ):
            result = await _collector(
                {"task": "read the title", "url": "https://example.com"}
            ).collect()

        assert result.errors == []
        record = result.raw_records[0]
        assert record.record_type == "web_page"
        assert record.source_url == "https://example.com"
        content = record.content
        assert content["result"] == "The title is Example Domain"
        assert content["steps_taken"] == 3
        assert content["backend"] == "obscura"
        assert content["visited_urls"] == ["https://example.com/"]
        assert content["duration_ms"] == 4200

    @pytest.mark.asyncio
    async def test_task_failure_surfaces_error(self):
        body = {"ok": False, "error": "task_timeout: exceeded 120s", "backend": "chromium"}
        with patch(
            "data_intelligence_hub.collectors.browser_use_collector.httpx.AsyncClient",
            return_value=_fake_client(response=_response(body)),
        ):
            result = await _collector({"task": "t"}).collect()
        assert result.raw_records == []
        assert any("task_timeout" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_bridge_http_error(self):
        with patch(
            "data_intelligence_hub.collectors.browser_use_collector.httpx.AsyncClient",
            return_value=_fake_client(response=_response({}, status_code=500)),
        ):
            result = await _collector({"task": "t"}).collect()
        assert result.raw_records == []
        assert any("HTTP 500" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_transport_error(self):
        with patch(
            "data_intelligence_hub.collectors.browser_use_collector.httpx.AsyncClient",
            return_value=_fake_client(error=httpx.ReadTimeout("timed out")),
        ):
            result = await _collector({"task": "t"}).collect()
        assert result.raw_records == []
        assert any("unreachable" in e for e in result.errors)
