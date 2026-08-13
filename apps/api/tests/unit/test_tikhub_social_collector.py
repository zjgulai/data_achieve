"""Unit tests for TikHubSocialCollector.

All tests use httpx mock transports — no real network calls, no TIKHUB_API_KEY
required (except where explicitly noted with pytest.mark.skip).
"""

from __future__ import annotations

import json
from typing import Any, cast
from unittest.mock import patch

import httpx
import pytest

from data_intelligence_hub.collectors.base import CollectorRawRecord


def _c(record: CollectorRawRecord) -> dict[str, Any]:
    return cast(dict[str, Any], record.content)

from data_intelligence_hub.collectors.base import CollectorError
from data_intelligence_hub.collectors.tikhub_social import (
    TIKHUB_ENDPOINT_MAP,
    TikHubSocialCollector,
    _extract_hashtags,
    _extract_items,
    _normalize_instagram_post,
    _normalize_tiktok_video,
    _normalize_xiaohongshu_note,
    _safe_int,
    _safe_ts,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TIKTOK_VIDEO_ITEM: dict[str, Any] = {
    "aweme_id": "7123456789012345678",
    "desc": "Wearable breast pump review #momlife #breastpump",
    "create_time": 1720000000,
    "author": {
        "uid": "987654321",
        "unique_id": "momcozy_official",
        "nickname": "Momcozy Official",
    },
    "statistics": {
        "play_count": 150000,
        "digg_count": 8500,
        "comment_count": 320,
        "share_count": 1200,
        "collect_count": 450,
    },
    "video": {
        "duration": 45,
        "cover": {"url_list": ["https://p16.tiktokcdn.com/cover.jpg"]},
    },
    "music": {"title": "Original Sound"},
    "cha_list": [
        {"cha_name": "momlife"},
        {"cha_name": "breastpump"},
    ],
}

INSTAGRAM_POST_ITEM: dict[str, Any] = {
    "id": "3456789012345678901",
    "shortcode": "CxAbCdEfGhI",
    "caption": {"text": "New Momcozy S21 Pro review! #breastpump #momlife"},
    "user": {"pk": "11223344", "username": "momcozy_us"},
    "media_type": 1,
    "like_count": 2300,
    "comment_count": 87,
    "taken_at": 1720100000,
}

XIAOHONGSHU_NOTE_ITEM: dict[str, Any] = {
    "mix_track_id": "mix_001",
    "model_type": 1,
    "note": {
        "id": "note_abc123",
        "title": "Momcozy 吸奶器测评",
        "type": "normal",
        "user": {"userid": "xhs_user_001", "nickname": "奶妈日记"},
        "liked_count": 1200,
        "comments_count": 89,
        "collected_count": 340,
    },
}

TIKHUB_TIKTOK_RESPONSE: dict[str, Any] = {
    "code": 200,
    "data": {
        "aweme_list": [TIKTOK_VIDEO_ITEM],
        "has_more": 0,
        "cursor": 20,
    },
}

TIKHUB_INSTAGRAM_RESPONSE: dict[str, Any] = {
    "code": 200,
    "data": {
        "items": [INSTAGRAM_POST_ITEM],
        "end_cursor": "abc123cursor",
    },
}

TIKHUB_XHS_RESPONSE: dict[str, Any] = {
    "code": 200,
    "data": {
        "data": {
            "items": [XIAOHONGSHU_NOTE_ITEM],
        },
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok_response(body: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, json=body)


def _make_mock_transport(body: dict[str, Any]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok_response(body)

    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# validate_config
# ---------------------------------------------------------------------------


def test_validate_config_missing_endpoint_type_raises() -> None:
    collector = TikHubSocialCollector(config={})
    with pytest.raises(CollectorError, match="endpoint_type"):
        collector.validate_config()


def test_validate_config_unknown_endpoint_type_raises() -> None:
    collector = TikHubSocialCollector(config={"endpoint_type": "tikhub_unknown_platform"})
    with pytest.raises(CollectorError, match="tikhub_endpoint_type_unknown"):
        collector.validate_config()


def test_validate_config_valid_tiktok_search() -> None:
    collector = TikHubSocialCollector(
        config={"endpoint_type": "tikhub_tiktok_video_search", "keyword": "test", "max_items": 5}
    )
    cfg = collector.validate_config()
    assert cfg["endpoint_type"] == "tikhub_tiktok_video_search"
    assert cfg["max_items"] == 5


def test_validate_config_max_items_capped_at_100() -> None:
    collector = TikHubSocialCollector(
        config={"endpoint_type": "tikhub_tiktok_video_search", "max_items": 9999}
    )
    cfg = collector.validate_config()
    assert cfg["max_items"] == 100


def test_validate_config_all_endpoint_types_accepted() -> None:
    for endpoint_type in TIKHUB_ENDPOINT_MAP:
        collector = TikHubSocialCollector(config={"endpoint_type": endpoint_type})
        cfg = collector.validate_config()
        assert cfg["endpoint_type"] == endpoint_type


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def test_safe_int_conversions() -> None:
    assert _safe_int(42) == 42
    assert _safe_int("100") == 100
    assert _safe_int(True) is None   # bool excluded
    assert _safe_int(None) is None
    assert _safe_int("abc") is None


def test_safe_ts_unix_timestamp() -> None:
    result = _safe_ts(1720000000)
    assert result is not None
    assert "2024" in result or "T" in result


def test_safe_ts_iso_string_passthrough() -> None:
    assert _safe_ts("2024-07-03T12:00:00Z") == "2024-07-03T12:00:00Z"


def test_safe_ts_none_returns_none() -> None:
    assert _safe_ts(None) is None


def test_extract_hashtags() -> None:
    tags = _extract_hashtags("Hello #momlife #breastpump world #test")
    assert tags == ["momlife", "breastpump", "test"]


def test_extract_hashtags_empty() -> None:
    assert _extract_hashtags("no hashtags here") == []


# ---------------------------------------------------------------------------
# TikTok normalizer
# ---------------------------------------------------------------------------


def test_normalize_tiktok_video_full_item() -> None:
    record = _normalize_tiktok_video(TIKTOK_VIDEO_ITEM, "tikhub_tiktok_video_search")
    assert record is not None
    assert record.record_type == "tiktok_video"
    assert _c(record)["video_id"] == "7123456789012345678"
    assert _c(record)["platform"] == "tiktok"
    assert _c(record)["provider"] == "tikhub"
    assert _c(record)["play_count"] == 150000
    assert _c(record)["like_count"] == 8500
    assert _c(record)["comment_count"] == 320
    assert "momlife" in _c(record)["hashtags"]
    assert record.source_url is not None
    assert "7123456789012345678" in record.source_url


def test_normalize_tiktok_video_missing_id_returns_none() -> None:
    item = {**TIKTOK_VIDEO_ITEM, "aweme_id": None}
    assert _normalize_tiktok_video(item, "tikhub_tiktok_video_search") is None


def test_normalize_tiktok_video_empty_id_returns_none() -> None:
    item = {**TIKTOK_VIDEO_ITEM, "aweme_id": "  "}
    assert _normalize_tiktok_video(item, "tikhub_tiktok_video_search") is None


def test_normalize_tiktok_video_text_truncated_at_2000() -> None:
    long_text = "x" * 3000
    item = {**TIKTOK_VIDEO_ITEM, "desc": long_text}
    record = _normalize_tiktok_video(item, "tikhub_tiktok_video_search")
    assert record is not None
    assert len(_c(record)["text"]) <= 2000


# ---------------------------------------------------------------------------
# Instagram normalizer
# ---------------------------------------------------------------------------


def test_normalize_instagram_post_full_item() -> None:
    record = _normalize_instagram_post(INSTAGRAM_POST_ITEM, "tikhub_instagram_user_posts")
    assert record is not None
    assert record.record_type == "instagram_post"
    assert _c(record)["post_id"] == "3456789012345678901"
    assert _c(record)["shortcode"] == "CxAbCdEfGhI"
    assert _c(record)["platform"] == "instagram"
    assert _c(record)["provider"] == "tikhub"
    assert _c(record)["like_count"] == 2300
    assert "breastpump" in _c(record)["hashtags"]
    assert "instagram.com/p/CxAbCdEfGhI" in (record.source_url or "")


def test_normalize_instagram_post_missing_id_returns_none() -> None:
    item = {k: v for k, v in INSTAGRAM_POST_ITEM.items() if k not in ("id", "pk", "shortcode")}
    assert _normalize_instagram_post(item, "tikhub_instagram_user_posts") is None


def test_normalize_instagram_post_string_caption() -> None:
    item = {**INSTAGRAM_POST_ITEM, "caption": "plain string caption #test"}
    record = _normalize_instagram_post(item, "tikhub_instagram_user_posts")
    assert record is not None
    assert "test" in _c(record)["hashtags"]


# ---------------------------------------------------------------------------
# Xiaohongshu normalizer
# ---------------------------------------------------------------------------


def test_normalize_xiaohongshu_note_full_item() -> None:
    record = _normalize_xiaohongshu_note(XIAOHONGSHU_NOTE_ITEM, "tikhub_xiaohongshu_search")
    assert record is not None
    assert record.record_type == "xiaohongshu_note"
    assert _c(record)["note_id"] == "note_abc123"
    assert _c(record)["platform"] == "xiaohongshu"
    assert _c(record)["provider"] == "tikhub"
    assert _c(record)["title"] == "Momcozy 吸奶器测评"
    assert _c(record)["like_count"] == 1200
    assert _c(record)["comment_count"] == 89
    assert "xiaohongshu.com" in (record.source_url or "")


def test_normalize_xiaohongshu_note_missing_id_returns_none() -> None:
    item: dict[str, Any] = {"note": {"title": "no id here"}}
    assert _normalize_xiaohongshu_note(item, "tikhub_xiaohongshu_search") is None


# ---------------------------------------------------------------------------
# _extract_items
# ---------------------------------------------------------------------------


def test_extract_items_aweme_list() -> None:
    data = {"data": {"aweme_list": [{"id": "1"}, {"id": "2"}]}}
    items = _extract_items(data, "tiktok")
    assert len(items) == 2


def test_extract_items_direct_list() -> None:
    data = {"data": [{"id": "1"}]}
    items = _extract_items(data, "instagram")
    assert len(items) == 1


def test_extract_items_items_key() -> None:
    data = {"data": {"items": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}}
    items = _extract_items(data, "instagram")
    assert len(items) == 3


def test_extract_items_empty_response() -> None:
    assert _extract_items({}, "tiktok") == []
    assert _extract_items({"data": {}}, "tiktok") == []


# ---------------------------------------------------------------------------
# collect() — mock HTTP
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collect_tiktok_video_search_mock() -> None:
    with patch("data_intelligence_hub.collectors.tikhub_social._get_api_key", return_value="fake_key"):
        transport = _make_mock_transport(TIKHUB_TIKTOK_RESPONSE)
        collector = TikHubSocialCollector(
            config={"endpoint_type": "tikhub_tiktok_video_search", "keyword": "breast pump", "max_items": 5}
        )
        # Inject mock transport
        import httpx as _httpx
        original_client = _httpx.AsyncClient

        class MockClient:
            def __init__(self, **kwargs: Any) -> None:
                self._client = original_client(transport=transport)

            async def __aenter__(self) -> _httpx.AsyncClient:
                return await self._client.__aenter__()

            async def __aexit__(self, *args: Any) -> None:
                await self._client.__aexit__(*args)

        with patch("data_intelligence_hub.collectors.tikhub_social.httpx.AsyncClient", MockClient):
            result = await collector.collect()

    assert result.errors == []
    assert len(result.raw_records) == 1
    assert result.raw_records[0].record_type == "tiktok_video"
    assert _c(result.raw_records[0])["video_id"] == "7123456789012345678"


@pytest.mark.asyncio
async def test_collect_instagram_user_posts_mock() -> None:
    with patch("data_intelligence_hub.collectors.tikhub_social._get_api_key", return_value="fake_key"):
        transport = _make_mock_transport(TIKHUB_INSTAGRAM_RESPONSE)
        collector = TikHubSocialCollector(
            config={"endpoint_type": "tikhub_instagram_user_posts", "username": "momcozy_us"}
        )
        import httpx as _httpx
        original_client = _httpx.AsyncClient

        class MockClient:
            def __init__(self, **kwargs: Any) -> None:
                self._client = original_client(transport=transport)

            async def __aenter__(self) -> _httpx.AsyncClient:
                return await self._client.__aenter__()

            async def __aexit__(self, *args: Any) -> None:
                await self._client.__aexit__(*args)

        with patch("data_intelligence_hub.collectors.tikhub_social.httpx.AsyncClient", MockClient):
            result = await collector.collect()

    assert result.errors == []
    assert len(result.raw_records) == 1
    assert result.raw_records[0].record_type == "instagram_post"


@pytest.mark.asyncio
async def test_collect_xiaohongshu_search_mock() -> None:
    with patch("data_intelligence_hub.collectors.tikhub_social._get_api_key", return_value="fake_key"):
        transport = _make_mock_transport(TIKHUB_XHS_RESPONSE)
        collector = TikHubSocialCollector(
            config={"endpoint_type": "tikhub_xiaohongshu_search", "keyword": "吸奶器"}
        )
        import httpx as _httpx
        original_client = _httpx.AsyncClient

        class MockClient:
            def __init__(self, **kwargs: Any) -> None:
                self._client = original_client(transport=transport)

            async def __aenter__(self) -> _httpx.AsyncClient:
                return await self._client.__aenter__()

            async def __aexit__(self, *args: Any) -> None:
                await self._client.__aexit__(*args)

        with patch("data_intelligence_hub.collectors.tikhub_social.httpx.AsyncClient", MockClient):
            result = await collector.collect()

    assert result.errors == []
    assert len(result.raw_records) == 1
    assert result.raw_records[0].record_type == "xiaohongshu_note"


@pytest.mark.asyncio
async def test_collect_missing_api_key_returns_error() -> None:
    with patch.dict("os.environ", {}, clear=True):
        import os
        os.environ.pop("TIKHUB_API_KEY", None)
        collector = TikHubSocialCollector(
            config={"endpoint_type": "tikhub_tiktok_video_search", "keyword": "test"}
        )
        result = await collector.collect()

    assert len(result.errors) == 1
    assert "tikhub_api_key_missing" in result.errors[0]
    assert result.raw_records == []


@pytest.mark.asyncio
async def test_collect_http_error_returns_error_not_exception() -> None:
    with patch("data_intelligence_hub.collectors.tikhub_social._get_api_key", return_value="fake_key"):

        def error_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"error": "rate limited"})

        transport = httpx.MockTransport(error_handler)
        collector = TikHubSocialCollector(
            config={"endpoint_type": "tikhub_tiktok_video_search", "keyword": "test"}
        )
        import httpx as _httpx
        original_client = _httpx.AsyncClient

        class MockClient:
            def __init__(self, **kwargs: Any) -> None:
                self._client = original_client(transport=transport)

            async def __aenter__(self) -> _httpx.AsyncClient:
                return await self._client.__aenter__()

            async def __aexit__(self, *args: Any) -> None:
                await self._client.__aexit__(*args)

        with patch("data_intelligence_hub.collectors.tikhub_social.httpx.AsyncClient", MockClient):
            result = await collector.collect()

    assert len(result.errors) >= 1
    assert result.raw_records == []


@pytest.mark.asyncio
async def test_collect_all_items_fail_normalization_adds_error() -> None:
    bad_response = {"code": 200, "data": {"aweme_list": [{"no_id": "missing"}]}}
    with patch("data_intelligence_hub.collectors.tikhub_social._get_api_key", return_value="fake_key"):
        transport = _make_mock_transport(bad_response)
        collector = TikHubSocialCollector(
            config={"endpoint_type": "tikhub_tiktok_video_search", "keyword": "test"}
        )
        import httpx as _httpx
        original_client = _httpx.AsyncClient

        class MockClient:
            def __init__(self, **kwargs: Any) -> None:
                self._client = original_client(transport=transport)

            async def __aenter__(self) -> _httpx.AsyncClient:
                return await self._client.__aenter__()

            async def __aexit__(self, *args: Any) -> None:
                await self._client.__aexit__(*args)

        with patch("data_intelligence_hub.collectors.tikhub_social.httpx.AsyncClient", MockClient):
            result = await collector.collect()

    assert any("tikhub_normalize_all_failed" in e for e in result.errors)
    assert result.raw_records == []


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------


def test_tikhub_registered_in_registry() -> None:
    from data_intelligence_hub.collectors.registry import COLLECTOR_REGISTRY

    assert "tikhub_social" in COLLECTOR_REGISTRY
    assert COLLECTOR_REGISTRY["tikhub_social"] is TikHubSocialCollector
