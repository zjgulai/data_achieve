"""Unit tests for AutoScraperEnhancedWebCollector.

All HTTP and AutoScraper calls are mocked — no real network and no real
extraction.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from data_intelligence_hub.collectors.autoscraper_collector import (
    AutoScraperEnhancedWebCollector,
)

_PATCH_ALLOWED = (
    "data_intelligence_hub.collectors.autoscraper_collector.assert_collector_allowed"
)
_PATCH_CLIENT = "data_intelligence_hub.collectors.autoscraper_collector._client"
_PATCH_SCRAPER = "data_intelligence_hub.collectors.autoscraper_collector.AutoScraper"


class _FakeResponse:
    status_code = 200
    text = "<html><body>example</body></html>"

    def raise_for_status(self) -> None:
        return None


class _FakeClient:
    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def get(self, url: str) -> _FakeResponse:
        return _FakeResponse()


class _FakeScraper:
    def __init__(self, results: list[str]) -> None:
        self._results = results

    def build(self, **_kwargs: Any) -> None:
        return None

    def get_result_exact(self, html: str) -> list[str]:
        return self._results

    def get_result_similar(self, html: str) -> list[str]:
        return self._results


def _config(**overrides: Any) -> dict[str, Any]:
    config: dict[str, Any] = {
        "url": "https://example.com",
        "wanted_list": ["example"],
    }
    config.update(overrides)
    return config


async def _collect(config: dict[str, Any], results: list[str]) -> Any:
    with (
        patch(_PATCH_ALLOWED),
        patch(_PATCH_CLIENT, return_value=_FakeClient()),
        patch(_PATCH_SCRAPER, return_value=_FakeScraper(results)),
    ):
        return await AutoScraperEnhancedWebCollector(config=config).collect()


@pytest.mark.asyncio
async def test_zero_extraction_returns_no_raw_records() -> None:
    result = await _collect(_config(), [])
    assert result.raw_records == []
    assert result.errors == []


@pytest.mark.asyncio
async def test_zero_extraction_with_allow_empty_false_reports_error() -> None:
    result = await _collect(_config(allow_empty=False), [])
    assert result.raw_records == []
    assert any(
        e.startswith("collector_empty_result: expected >= 1 record(s), got 0")
        for e in result.errors
    )


@pytest.mark.asyncio
async def test_non_empty_extraction_keeps_single_record() -> None:
    result = await _collect(_config(), ["example"])
    assert result.errors == []
    assert len(result.raw_records) == 1
    content = result.raw_records[0].content
    assert content["extraction_count"] == 1
    assert content["extracted_data"] == ["example"]
