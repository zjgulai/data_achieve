"""Unit tests for Firecrawl collectors.

All HTTP calls mocked — no real Firecrawl API key required.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from data_intelligence_hub.collectors.base import CollectorError
from data_intelligence_hub.collectors.firecrawl_collector import (
    FirecrawlBatchScrapeCollector,
    FirecrawlCrawlCollector,
    FirecrawlExtractCollector,
)


def _post(return_value: dict[str, Any]):
    return patch(
        "data_intelligence_hub.collectors.firecrawl_collector._post",
        new_callable=AsyncMock,
        return_value=return_value,
    )


def _post_error(exc: Exception):
    return patch(
        "data_intelligence_hub.collectors.firecrawl_collector._post",
        new_callable=AsyncMock,
        side_effect=exc,
    )


def _poll(return_value: dict[str, Any]):
    return patch(
        "data_intelligence_hub.collectors.firecrawl_collector._poll_job",
        new_callable=AsyncMock,
        return_value=return_value,
    )


class TestFirecrawlCrawlCollector:
    def test_missing_url_raises(self):
        with pytest.raises(CollectorError):
            FirecrawlCrawlCollector(config={}).validate_config()

    def test_max_pages_bounds(self):
        with pytest.raises(CollectorError):
            FirecrawlCrawlCollector(config={"url": "https://x.com", "max_pages": 999}).validate_config()

    def test_valid_config_defaults(self):
        cfg = FirecrawlCrawlCollector(config={"url": "https://example.com"}).validate_config()
        assert cfg["url"] == "https://example.com"
        assert cfg["max_pages"] == 10

    @pytest.mark.asyncio
    async def test_test_fails_without_api_key(self, monkeypatch):
        monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
        monkeypatch.delenv("FIRECRAWL_BASE_URL", raising=False)
        result = await FirecrawlCrawlCollector(config={"url": "https://x.com"}).test()
        assert result.status == "failed"
        assert "FIRECRAWL_API_KEY" in result.message

    @pytest.mark.asyncio
    async def test_collect_post_error_returns_error(self, monkeypatch):
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
        with _post_error(CollectorError("connect error")):
            result = await FirecrawlCrawlCollector(
                config={"url": "https://example.com"}
            ).collect()
        assert result.raw_records == []
        assert result.errors

    @pytest.mark.asyncio
    async def test_collect_post_rejected_returns_error(self, monkeypatch):
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
        with _post({"success": False, "error": "rate limited"}):
            result = await FirecrawlCrawlCollector(
                config={"url": "https://example.com"}
            ).collect()
        assert result.raw_records == []
        assert result.errors

    @pytest.mark.asyncio
    async def test_collect_job_failed_returns_error(self, monkeypatch):
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
        with (
            _post({"success": True, "id": "job-1"}),
            _poll({"status": "failed", "data": []}),
        ):
            result = await FirecrawlCrawlCollector(
                config={"url": "https://example.com"}
            ).collect()
        assert result.raw_records == []
        assert result.errors

    @pytest.mark.asyncio
    async def test_collect_happy_path(self, monkeypatch):
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
        pages = [
            {"metadata": {"sourceURL": "https://example.com/", "title": "Home"}, "markdown": "# Home"},
            {"metadata": {"sourceURL": "https://example.com/about"}, "markdown": "# About"},
        ]
        with (
            _post({"success": True, "id": "job-1"}),
            _poll({"status": "completed", "data": pages}),
        ):
            result = await FirecrawlCrawlCollector(
                config={"url": "https://example.com"}
            ).collect()
        assert len(result.raw_records) == 2
        assert result.raw_records[0].record_type == "web_page_markdown"
        assert result.raw_records[0].content["markdown"] == "# Home"
        assert not result.errors


class TestFirecrawlExtractCollector:
    def test_missing_url_raises(self):
        with pytest.raises(CollectorError):
            FirecrawlExtractCollector(config={}).validate_config()

    def test_missing_schema_and_prompt_raises(self):
        with pytest.raises(CollectorError, match="schema.*prompt"):
            FirecrawlExtractCollector(config={"url": "https://x.com"}).validate_config()

    def test_valid_with_prompt(self):
        cfg = FirecrawlExtractCollector(
            config={"url": "https://x.com", "prompt": "extract title"}
        ).validate_config()
        assert cfg["prompt"] == "extract title"

    def test_valid_with_schema(self):
        cfg = FirecrawlExtractCollector(
            config={"url": "https://x.com", "schema": {"title": "string"}}
        ).validate_config()
        assert cfg["schema"] == {"title": "string"}

    @pytest.mark.asyncio
    async def test_collect_post_error_returns_error(self, monkeypatch):
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
        with _post_error(CollectorError("timeout")):
            result = await FirecrawlExtractCollector(
                config={"url": "https://x.com", "prompt": "extract price"}
            ).collect()
        assert result.raw_records == []
        assert result.errors

    @pytest.mark.asyncio
    async def test_collect_happy_path(self, monkeypatch):
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
        resp = {
            "success": True,
            "data": {"extract": {"title": "Product X", "price": "$99"}},
        }
        with _post(resp):
            result = await FirecrawlExtractCollector(
                config={"url": "https://shop.com/p/1", "prompt": "extract product info"}
            ).collect()
        assert len(result.raw_records) == 1
        rec = result.raw_records[0]
        assert rec.record_type == "structured_data"
        assert rec.content["extracted"] == {"title": "Product X", "price": "$99"}
        assert not result.errors


class TestFirecrawlBatchScrapeCollector:
    def test_empty_urls_raises(self):
        with pytest.raises(CollectorError):
            FirecrawlBatchScrapeCollector(config={"urls": []}).validate_config()

    def test_non_list_raises(self):
        with pytest.raises(CollectorError):
            FirecrawlBatchScrapeCollector(config={"urls": "https://x.com"}).validate_config()

    def test_too_many_urls_raises(self):
        with pytest.raises(CollectorError):
            FirecrawlBatchScrapeCollector(
                config={"urls": [f"https://x.com/{i}" for i in range(101)]}
            ).validate_config()

    def test_empty_string_url_raises(self):
        with pytest.raises(CollectorError):
            FirecrawlBatchScrapeCollector(
                config={"urls": ["https://x.com", ""]}
            ).validate_config()

    def test_valid_urls_stripped(self):
        cfg = FirecrawlBatchScrapeCollector(
            config={"urls": ["  https://a.com  ", "https://b.com"]}
        ).validate_config()
        assert cfg["urls"] == ["https://a.com", "https://b.com"]

    @pytest.mark.asyncio
    async def test_collect_post_error_returns_error(self, monkeypatch):
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
        with _post_error(CollectorError("network error")):
            result = await FirecrawlBatchScrapeCollector(
                config={"urls": ["https://a.com"]}
            ).collect()
        assert result.raw_records == []
        assert result.errors

    @pytest.mark.asyncio
    async def test_collect_happy_path(self, monkeypatch):
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
        pages = [
            {"metadata": {"sourceURL": "https://a.com", "title": "A"}, "markdown": "# A"},
            {"metadata": {"sourceURL": "https://b.com", "title": "B"}, "markdown": "# B"},
        ]
        with _post({"success": True, "data": pages}):
            result = await FirecrawlBatchScrapeCollector(
                config={"urls": ["https://a.com", "https://b.com"]}
            ).collect()
        assert len(result.raw_records) == 2
        assert result.raw_records[1].content["markdown"] == "# B"
        assert not result.errors

    @pytest.mark.asyncio
    async def test_collect_rejected_returns_error(self, monkeypatch):
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
        with _post({"success": False}):
            result = await FirecrawlBatchScrapeCollector(
                config={"urls": ["https://a.com"]}
            ).collect()
        assert result.raw_records == []
        assert result.errors
