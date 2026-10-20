from __future__ import annotations

import json
from pathlib import Path

import pytest

from data_intelligence_hub.collectors.endpoint_catalog import _ENDPOINT_TO_COLLECTOR
from data_intelligence_hub.collectors.outbound_policy import execution_kind
from data_intelligence_hub.tool_catalog import fixtures

ENTRY_KEYS = {"unit", "unit_price", "quantity_basis", "source", "confidence"}
CONFIDENCE_VALUES = {"high", "medium", "low", "unknown"}


def _active_endpoints() -> dict[str, str]:
    return {
        endpoint: collector
        for endpoint, collector in _ENDPOINT_TO_COLLECTOR.items()
        if execution_kind(collector) != "unsupported"
    }


def _provider_prefix(endpoint_type: str) -> str:
    return endpoint_type.split("_", 1)[0]


def test_fixture_files_are_parseable_json_with_expected_versions() -> None:
    price_book = json.loads(fixtures.PRICE_BOOK_PATH.read_text(encoding="utf-8"))
    output_schemas = json.loads(fixtures.OUTPUT_SCHEMAS_PATH.read_text(encoding="utf-8"))

    assert price_book["schema_version"] == "price_book.v1"
    assert output_schemas["schema_version"] == "output_schemas.v1"


def test_price_book_header_is_complete() -> None:
    price_book = fixtures.load_price_book()

    assert price_book["currency"] == "USD"
    assert isinstance(price_book["updated_at"], str) and price_book["updated_at"]


def test_price_book_covers_every_non_unsupported_endpoint() -> None:
    expected = set(_active_endpoints())
    entries = fixtures.load_price_book()["entries"]

    assert set(entries) == expected


def test_price_book_entries_have_valid_shape() -> None:
    entries = fixtures.load_price_book()["entries"]

    for endpoint, entry in entries.items():
        assert set(entry) == ENTRY_KEYS, endpoint
        assert entry["confidence"] in CONFIDENCE_VALUES, endpoint
        assert isinstance(entry["source"], str) and entry["source"], endpoint
        if entry["confidence"] == "unknown":
            assert entry["unit_price"] is None, endpoint
        else:
            assert isinstance(entry["unit_price"], (int, float)), endpoint
            assert not isinstance(entry["unit_price"], bool), endpoint
            assert entry["unit_price"] >= 0, endpoint


def test_price_book_records_documented_apify_prices() -> None:
    entries = fixtures.load_price_book()["entries"]

    assert entries["apify_amazon_product_scraper"]["unit_price"] == 0.005
    assert entries["apify_tiktok_scraper"]["unit_price"] == 0.0037
    assert entries["apify_trustpilot_reviews_scraper"]["unit_price"] == 0.0029
    assert entries["apify_trustpilot_reviews_scraper"]["confidence"] == "high"


def test_output_schemas_cover_every_non_unsupported_endpoint() -> None:
    missing = [
        endpoint
        for endpoint in _active_endpoints()
        if fixtures.family_for_endpoint(endpoint) is None
    ]

    assert missing == []


def test_output_schema_families_cover_all_provider_prefixes() -> None:
    active_prefixes = {_provider_prefix(endpoint) for endpoint in _active_endpoints()}
    family_prefixes = {
        _provider_prefix(name) for name in fixtures.load_output_schemas()["families"]
    }

    assert active_prefixes <= family_prefixes


def test_output_schema_families_have_fields_and_description() -> None:
    families = fixtures.load_output_schemas()["families"]

    for name, family in families.items():
        assert isinstance(family.get("description"), str), name
        assert family["description"], name
        fields = family.get("fields")
        assert isinstance(fields, list) and fields, name
        assert all(isinstance(field, str) and field for field in fields), name


def test_every_output_schema_family_matches_an_active_endpoint() -> None:
    active = set(_active_endpoints())
    families = fixtures.load_output_schemas()["families"]

    for name in families:
        assert any(
            endpoint == name or endpoint.startswith(f"{name}_") for endpoint in active
        ), name


def test_loaders_cache_results() -> None:
    assert fixtures.load_price_book() is fixtures.load_price_book()
    assert fixtures.load_output_schemas() is fixtures.load_output_schemas()


def test_missing_price_book_raises_clear_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(fixtures, "PRICE_BOOK_PATH", tmp_path / "missing.json")
    fixtures.load_price_book.cache_clear()
    try:
        with pytest.raises(fixtures.ToolCatalogFixtureError, match="缺少价格簿夹具"):
            fixtures.load_price_book()
    finally:
        fixtures.load_price_book.cache_clear()


def test_missing_output_schemas_raises_clear_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(fixtures, "OUTPUT_SCHEMAS_PATH", tmp_path / "missing.json")
    fixtures.load_output_schemas.cache_clear()
    try:
        with pytest.raises(fixtures.ToolCatalogFixtureError, match="缺少输出 schema 夹具"):
            fixtures.load_output_schemas()
    finally:
        fixtures.load_output_schemas.cache_clear()
