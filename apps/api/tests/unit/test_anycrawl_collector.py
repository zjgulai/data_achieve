"""Unit tests for AnyCrawl-based SERP collectors.

Covers:
- BaiduSearchCollector
- BingSearchCollector
- DuckDuckGoSearchCollector (including HTML fallback path)
- _normalize_result helper
- _ddg_html_fallback HTML parsing

All HTTP calls mocked — no real AnyCrawl or network required.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from data_intelligence_hub.collectors.base import CollectorError
from data_intelligence_hub.collectors.anycrawl_collector import (
    BaiduSearchCollector,
    BingSearchCollector,
    DuckDuckGoSearchCollector,
    _normalize_result,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _anycrawl_response(results: list[dict[str, Any]]) -> MagicMock:
    r = MagicMock()
    r.raise_for_status = MagicMock()
    r.json.return_value = {"results": results}
    return r


def _ddg_html_response(html: str) -> MagicMock:
    r = MagicMock()
    r.raise_for_status = MagicMock()
    r.text = html
    return r


def _patch_anycrawl(return_value: list[dict[str, Any]]):
    return patch(
        "data_intelligence_hub.collectors.anycrawl_collector._anycrawl_serp",
        new_callable=AsyncMock,
        return_value=return_value,
    )


def _patch_anycrawl_error(exc: Exception):
    return patch(
        "data_intelligence_hub.collectors.anycrawl_collector._anycrawl_serp",
        new_callable=AsyncMock,
        side_effect=exc,
    )


def _patch_ddg_fallback(items: list[dict[str, Any]]):
    return patch(
        "data_intelligence_hub.collectors.anycrawl_collector._ddg_html_fallback",
        new_callable=AsyncMock,
        return_value=items,
    )


def _patch_ddg_fallback_error(exc: Exception):
    return patch(
        "data_intelligence_hub.collectors.anycrawl_collector._ddg_html_fallback",
        new_callable=AsyncMock,
        side_effect=exc,
    )


# ---------------------------------------------------------------------------
# _normalize_result
# ---------------------------------------------------------------------------

class TestNormalizeResult:
    def test_standard_fields(self):
        item = {
            "title": "Python docs",
            "url": "https://docs.python.org",
            "snippet": "Official Python docs",
        }
        result = _normalize_result(item, 1, "baidu")
        assert result["rank"] == 1
        assert result["engine"] == "baidu"
        assert result["title"] == "Python docs"
        assert result["url"] == "https://docs.python.org"
        assert result["snippet"] == "Official Python docs"
        assert result["is_ad"] is False
        assert result["raw"] is item

    def test_fallback_field_names(self):
        item = {"name": "Alt title", "link": "https://x.com", "body": "Alt snippet"}
        result = _normalize_result(item, 2, "bing")
        assert result["title"] == "Alt title"
        assert result["url"] == "https://x.com"
        assert result["snippet"] == "Alt snippet"

    def test_is_ad_flag(self):
        result = _normalize_result({"url": "u", "sponsored": True}, 1, "bing")
        assert result["is_ad"] is True

    def test_empty_item(self):
        result = _normalize_result({}, 5, "duckduckgo")
        assert result["rank"] == 5
        assert result["title"] == ""
        assert result["url"] == ""


# ---------------------------------------------------------------------------
# validate_config (shared via _SerpCollector)
# ---------------------------------------------------------------------------

class TestValidateConfig:
    def test_missing_keyword_raises(self):
        with pytest.raises(CollectorError):
            BaiduSearchCollector(config={}).validate_config()

    def test_empty_keyword_raises(self):
        with pytest.raises(CollectorError):
            BingSearchCollector(config={"keyword": "  "}).validate_config()

    def test_max_items_bounds(self):
        with pytest.raises(CollectorError):
            DuckDuckGoSearchCollector(
                config={"keyword": "k", "max_items": 999}
            ).validate_config()

    def test_valid_defaults(self):
        cfg = BaiduSearchCollector(config={"keyword": "python"}).validate_config()
        assert cfg["keyword"] == "python"
        assert cfg["max_items"] == 10


# ---------------------------------------------------------------------------
# BaiduSearchCollector
# ---------------------------------------------------------------------------

class TestBaiduSearchCollector:
    @pytest.mark.asyncio
    async def test_no_anycrawl_url_returns_error(self, monkeypatch):
        monkeypatch.delenv("ANYCRAWL_BASE_URL", raising=False)
        result = await BaiduSearchCollector(config={"keyword": "python"}).collect()
        assert result.raw_records == []
        assert any("ANYCRAWL_BASE_URL" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_anycrawl_error_returns_error(self, monkeypatch):
        monkeypatch.setenv("ANYCRAWL_BASE_URL", "http://anycrawl:3001")
        with _patch_anycrawl_error(CollectorError("connect refused")):
            result = await BaiduSearchCollector(config={"keyword": "python"}).collect()
        assert result.raw_records == []
        assert result.errors

    @pytest.mark.asyncio
    async def test_collect_happy_path(self, monkeypatch):
        monkeypatch.setenv("ANYCRAWL_BASE_URL", "http://anycrawl:3001")
        raw = [
            {"title": "Python 官网", "url": "https://python.org", "snippet": "官方文档"},
            {"title": "Python教程", "url": "https://runoob.com/python", "snippet": "入门"},
        ]
        with _patch_anycrawl(raw):
            result = await BaiduSearchCollector(config={"keyword": "python"}).collect()
        assert len(result.raw_records) == 2
        assert result.raw_records[0].record_type == "serp_result"
        assert result.raw_records[0].content["engine"] == "baidu"
        assert result.raw_records[0].content["rank"] == 1
        assert not result.errors

    @pytest.mark.asyncio
    async def test_collect_respects_max_items(self, monkeypatch):
        monkeypatch.setenv("ANYCRAWL_BASE_URL", "http://anycrawl:3001")
        raw = [{"url": f"https://x.com/{i}", "title": f"r{i}"} for i in range(10)]
        with _patch_anycrawl(raw):
            result = await BaiduSearchCollector(
                config={"keyword": "python", "max_items": 3}
            ).collect()
        assert len(result.raw_records) == 3


# ---------------------------------------------------------------------------
# BingSearchCollector
# ---------------------------------------------------------------------------

class TestBingSearchCollector:
    @pytest.mark.asyncio
    async def test_no_anycrawl_returns_error(self, monkeypatch):
        monkeypatch.delenv("ANYCRAWL_BASE_URL", raising=False)
        result = await BingSearchCollector(config={"keyword": "openai"}).collect()
        assert result.raw_records == []
        assert result.errors

    @pytest.mark.asyncio
    async def test_collect_happy_path(self, monkeypatch):
        monkeypatch.setenv("ANYCRAWL_BASE_URL", "http://anycrawl:3001")
        raw = [{"title": "OpenAI", "url": "https://openai.com", "snippet": "AI research"}]
        with _patch_anycrawl(raw):
            result = await BingSearchCollector(config={"keyword": "openai"}).collect()
        assert len(result.raw_records) == 1
        assert result.raw_records[0].content["engine"] == "bing"
        assert not result.errors


# ---------------------------------------------------------------------------
# DuckDuckGoSearchCollector — AnyCrawl path
# ---------------------------------------------------------------------------

class TestDuckDuckGoWithAnyCrawl:
    @pytest.mark.asyncio
    async def test_collect_via_anycrawl(self, monkeypatch):
        monkeypatch.setenv("ANYCRAWL_BASE_URL", "http://anycrawl:3001")
        raw = [{"title": "DDG Result", "url": "https://r.com", "snippet": "desc"}]
        with _patch_anycrawl(raw):
            result = await DuckDuckGoSearchCollector(config={"keyword": "python"}).collect()
        assert len(result.raw_records) == 1
        assert result.raw_records[0].content["engine"] == "duckduckgo"
        assert not result.errors

    @pytest.mark.asyncio
    async def test_anycrawl_failure_falls_back_to_html(self, monkeypatch):
        monkeypatch.setenv("ANYCRAWL_BASE_URL", "http://anycrawl:3001")
        fallback_items = [
            {
                "rank": 1, "engine": "duckduckgo",
                "title": "Fallback result", "url": "https://f.com",
                "snippet": "from HTML", "domain": "", "is_ad": False, "raw": {},
            }
        ]
        with (
            _patch_anycrawl_error(CollectorError("AnyCrawl down")),
            _patch_ddg_fallback(fallback_items),
        ):
            result = await DuckDuckGoSearchCollector(config={"keyword": "python"}).collect()
        assert len(result.raw_records) == 1
        assert result.raw_records[0].content["title"] == "Fallback result"
        assert not result.errors


# ---------------------------------------------------------------------------
# DuckDuckGoSearchCollector — HTML fallback path (no AnyCrawl configured)
# ---------------------------------------------------------------------------

class TestDuckDuckGoHtmlFallback:
    @pytest.mark.asyncio
    async def test_no_anycrawl_uses_html_fallback(self, monkeypatch):
        monkeypatch.delenv("ANYCRAWL_BASE_URL", raising=False)
        fallback_items = [
            {
                "rank": 1, "engine": "duckduckgo",
                "title": "HTML Result", "url": "https://h.com",
                "snippet": "snippet", "domain": "", "is_ad": False, "raw": {},
            }
        ]
        with _patch_ddg_fallback(fallback_items):
            result = await DuckDuckGoSearchCollector(config={"keyword": "rust lang"}).collect()
        assert len(result.raw_records) == 1
        assert result.raw_records[0].content["title"] == "HTML Result"
        assert not result.errors

    @pytest.mark.asyncio
    async def test_html_fallback_error_returns_error(self, monkeypatch):
        monkeypatch.delenv("ANYCRAWL_BASE_URL", raising=False)
        with _patch_ddg_fallback_error(CollectorError("DDG blocked")):
            result = await DuckDuckGoSearchCollector(config={"keyword": "rust"}).collect()
        assert result.raw_records == []
        assert result.errors

    @pytest.mark.asyncio
    async def test_html_fallback_returns_serp_records(self, monkeypatch):
        monkeypatch.delenv("ANYCRAWL_BASE_URL", raising=False)
        fallback_items = [
            {
                "rank": i, "engine": "duckduckgo",
                "title": f"Result {i}", "url": f"https://x.com/{i}",
                "snippet": f"snip {i}", "domain": "", "is_ad": False, "raw": {},
            }
            for i in range(1, 6)
        ]
        with _patch_ddg_fallback(fallback_items):
            result = await DuckDuckGoSearchCollector(
                config={"keyword": "test", "max_items": 5}
            ).collect()
        assert len(result.raw_records) == 5
        for rec in result.raw_records:
            assert rec.record_type == "serp_result"
            assert rec.source_url is not None
