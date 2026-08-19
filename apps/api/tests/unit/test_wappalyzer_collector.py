"""Unit tests for TechStackDetectCollector and _detect fingerprinting."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from data_intelligence_hub.collectors.base import CollectorError
from data_intelligence_hub.collectors.wappalyzer_collector import (
    TechStackDetectCollector,
    _detect,
)


def _fake_response(html: str, headers: dict[str, str] = {}, status: int = 200):
    r = MagicMock()
    r.text = html
    r.status_code = status
    r.url = MagicMock()
    r.url.__str__ = lambda _: "https://example.com"
    r.headers = {**headers, "server": headers.get("server", "")}
    r.raise_for_status = MagicMock()
    return r


def _patch_client(response):
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return patch(
        "data_intelligence_hub.collectors.wappalyzer_collector._client",
        return_value=mock_client,
    )


class TestDetect:
    def test_detects_react(self):
        html = '<div id="root" data-reactroot __reactFiber></div>'
        result = _detect(html, {})
        names = [t["name"] for t in result]
        assert "React" in names

    def test_detects_nextjs(self):
        html = '<script id="__NEXT_DATA__"></script>'
        result = _detect(html, {})
        names = [t["name"] for t in result]
        assert "Next.js" in names

    def test_detects_wordpress(self):
        html = '<link rel="stylesheet" href="/wp-content/themes/main.css">'
        result = _detect(html, {})
        names = [t["name"] for t in result]
        assert "WordPress" in names

    def test_detects_cloudflare_via_header(self):
        result = _detect("", {"cf-ray": "abc123"})
        names = [t["name"] for t in result]
        assert "Cloudflare" in names

    def test_detects_nginx_via_server_header(self):
        result = _detect("", {"server": "nginx/1.24.0"})
        names = [t["name"] for t in result]
        assert "Nginx" in names

    def test_no_false_positives_on_empty(self):
        result = _detect("", {})
        assert result == []

    def test_no_duplicate_entries(self):
        html = '<div class="btn-primary col-md-6"><link href="/wp-content/x.css">'
        result = _detect(html, {"cf-ray": "x", "server": "nginx"})
        names = [t["name"] for t in result]
        assert len(names) == len(set(names))

    def test_result_sorted_by_category(self):
        html = (
            '<script src="react.js"></script>'
            '<link href="/wp-content/x.css">'
        )
        result = _detect(html, {})
        categories = [t["category"] for t in result]
        assert categories == sorted(categories)


class TestValidateConfig:
    def test_missing_url_raises(self):
        with pytest.raises(CollectorError):
            TechStackDetectCollector(config={}).validate_config()

    def test_non_http_scheme_raises(self):
        with pytest.raises(CollectorError):
            TechStackDetectCollector(config={"url": "ftp://x.com"}).validate_config()

    def test_valid_url(self):
        cfg = TechStackDetectCollector(config={"url": "https://example.com"}).validate_config()
        assert cfg["url"] == "https://example.com"


class TestCollect:
    @pytest.mark.asyncio
    async def test_collect_http_error_returns_error(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch(
            "data_intelligence_hub.collectors.wappalyzer_collector._client",
            return_value=mock_client,
        ):
            result = await TechStackDetectCollector(
                config={"url": "https://example.com"}
            ).collect()
        assert result.raw_records == []
        assert result.errors

    @pytest.mark.asyncio
    async def test_collect_detects_technologies(self):
        html = (
            '<script src="/_next/static/chunks/main.js"></script>'
            '<meta name="generator" content="Next.js">'
        )
        resp = _fake_response(html, {"cf-ray": "abc", "server": "nginx"})
        with _patch_client(resp):
            result = await TechStackDetectCollector(
                config={"url": "https://example.com"}
            ).collect()
        assert len(result.raw_records) == 1
        rec = result.raw_records[0]
        assert rec.record_type == "web_page"
        content = rec.content
        assert content["tech_count"] > 0
        tech_names = [t["name"] for t in content["technologies"]]
        assert "Nginx" in tech_names
        assert "Cloudflare" in tech_names
        assert not result.errors

    @pytest.mark.asyncio
    async def test_collect_empty_page_returns_record(self):
        resp = _fake_response("<html></html>", {})
        with _patch_client(resp):
            result = await TechStackDetectCollector(
                config={"url": "https://example.com"}
            ).collect()
        assert len(result.raw_records) == 1
        assert result.raw_records[0].content["tech_count"] == 0
