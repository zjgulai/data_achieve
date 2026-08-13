"""Unit tests for ApifyActorCollector.

All tests use httpx mock transports — no real network calls, no APIFY_API_TOKEN
required.
"""

from __future__ import annotations

import json
from typing import Any, Union, cast
from unittest.mock import patch

import httpx
import pytest

from data_intelligence_hub.collectors.apify_actor import (
    APIFY_TERMINAL_STATUSES,
    ApifyActorCollector,
    _actor_id_to_path,
    _extract_source_url,
    _extract_text,
    _infer_platform,
    _infer_record_type,
    normalize_apify_item,
)
from data_intelligence_hub.collectors.base import CollectorError, CollectorRawRecord


def _c(record: CollectorRawRecord) -> dict[str, Any]:
    return cast(dict[str, Any], record.content)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

INSTAGRAM_POST_ITEM: dict[str, Any] = {
    "id": "3456789012",
    "shortCode": "CxAbCdEfGhI",
    "url": "https://www.instagram.com/p/CxAbCdEfGhI/",
    "caption": "Momcozy S21 Pro review #breastpump",
    "likesCount": 2300,
    "commentsCount": 87,
    "timestamp": "2024-07-03T12:00:00.000Z",
    "ownerUsername": "momcozy_us",
}

TIKTOK_VIDEO_ITEM: dict[str, Any] = {
    "id": "7123456789012345678",
    "webVideoUrl": "https://www.tiktok.com/@momcozy_official/video/7123456789012345678",
    "text": "Wearable breast pump review #momlife",
    "createTime": "2024-07-03T10:00:00.000Z",
    "authorMeta": {"name": "Momcozy Official", "id": "987654321"},
    "diggCount": 8500,
    "shareCount": 1200,
    "playCount": 150000,
    "commentCount": 320,
}

YOUTUBE_VIDEO_ITEM: dict[str, Any] = {
    "id": "yt_video_abc123",
    "url": "https://www.youtube.com/watch?v=yt_video_abc123",
    "title": "Momcozy S21 Pro Full Review",
    "description": "In-depth review of the Momcozy S21 Pro wearable breast pump",
    "viewCount": 45000,
    "likeCount": 1200,
    "commentCount": 234,
    "publishedAt": "2024-07-01T00:00:00.000Z",
}

REDDIT_POST_ITEM: dict[str, Any] = {
    "id": "reddit_post_xyz",
    "url": "https://www.reddit.com/r/breastfeeding/comments/xyz/momcozy_review/",
    "title": "Momcozy S21 Pro - 3 month review",
    "body": "I've been using the S21 Pro for 3 months now...",
    "score": 87,
    "numComments": 23,
}


# ---------------------------------------------------------------------------
# Mock transport helpers
# ---------------------------------------------------------------------------

def _run_response(run_id: str, status: str = "SUCCEEDED", dataset_id: str = "ds_abc123") -> dict[str, Any]:
    return {
        "data": {
            "id": run_id,
            "status": status,
            "defaultDatasetId": dataset_id,
        }
    }


_ResponseBody = Union[dict[str, Any], list[dict[str, Any]]]


def _make_sequence_transport(
    responses: list[tuple[str, _ResponseBody]],
) -> httpx.MockTransport:
    queue: list[tuple[str, _ResponseBody]] = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        for pattern, body in queue:
            if pattern in path:
                return httpx.Response(200, json=body)
        return httpx.Response(404, json={"error": "not found"})

    return httpx.MockTransport(handler)


def _patched_client(transport: httpx.MockTransport) -> Any:
    real = httpx.AsyncClient(transport=transport)

    class _Ctx:
        async def __aenter__(self) -> httpx.AsyncClient:
            return await real.__aenter__()

        async def __aexit__(self, *a: Any) -> None:
            await real.__aexit__(*a)

    return lambda **_kw: _Ctx()


# ---------------------------------------------------------------------------
# Pure helper tests
# ---------------------------------------------------------------------------


def test_actor_id_to_path() -> None:
    assert _actor_id_to_path("apify/instagram-scraper") == "apify~instagram-scraper"
    assert _actor_id_to_path("clockworks/tiktok-scraper") == "clockworks~tiktok-scraper"


def test_infer_platform() -> None:
    assert _infer_platform("apify/instagram-scraper") == "instagram"
    assert _infer_platform("clockworks/tiktok-scraper") == "tiktok"
    assert _infer_platform("streamers/youtube-scraper") == "youtube"
    assert _infer_platform("trudax/reddit-scraper-lite") == "reddit"
    assert _infer_platform("apify/facebook-posts-scraper") == "facebook"
    assert _infer_platform("junglee/amazon-crawler") == "amazon"
    assert _infer_platform("some/unknown-scraper") == "web"


def test_infer_record_type() -> None:
    assert _infer_record_type("apify/instagram-scraper") == "instagram_post"
    assert _infer_record_type("apify/instagram-profile-scraper") == "instagram_profile"
    assert _infer_record_type("clockworks/tiktok-scraper") == "tiktok_video"
    assert _infer_record_type("streamers/youtube-scraper") == "youtube_video"
    assert _infer_record_type("streamers/youtube-comments-scraper") == "youtube_comment"
    assert _infer_record_type("trudax/reddit-scraper-lite") == "reddit_post"
    assert _infer_record_type("apify/facebook-posts-scraper") == "facebook_post"
    assert _infer_record_type("apify/facebook-comments-scraper") == "facebook_comment"


def test_extract_source_url_url_key() -> None:
    item = {"url": "https://www.instagram.com/p/abc/", "other": "field"}
    assert _extract_source_url(item) == "https://www.instagram.com/p/abc/"


def test_extract_source_url_postUrl_key() -> None:
    item = {"postUrl": "https://www.facebook.com/post/123"}
    assert _extract_source_url(item) == "https://www.facebook.com/post/123"


def test_extract_source_url_none_when_missing() -> None:
    assert _extract_source_url({"no_url": "here"}) is None


def test_extract_text_prefers_text_key() -> None:
    item = {"text": "hello world", "title": "ignored"}
    assert _extract_text(item) == "hello world"


def test_extract_text_falls_back_to_title() -> None:
    item = {"title": "My Title"}
    assert _extract_text(item) == "My Title"


def test_extract_text_truncates_at_2000() -> None:
    item = {"text": "x" * 3000}
    assert len(_extract_text(item)) == 2000


def test_extract_text_empty_when_no_text_field() -> None:
    assert _extract_text({"count": 42}) == ""


# ---------------------------------------------------------------------------
# normalize_apify_item
# ---------------------------------------------------------------------------


def test_normalize_instagram_item() -> None:
    record = normalize_apify_item(INSTAGRAM_POST_ITEM, "apify/instagram-scraper")
    assert record is not None
    assert record.record_type == "instagram_post"
    assert _c(record)["provider"] == "apify"
    assert _c(record)["platform"] == "instagram"
    assert _c(record)["actor_id"] == "apify/instagram-scraper"
    assert record.source_url == "https://www.instagram.com/p/CxAbCdEfGhI/"
    assert "breastpump" in _c(record)["text"]
    assert _c(record)["raw"] == INSTAGRAM_POST_ITEM


def test_normalize_tiktok_item() -> None:
    record = normalize_apify_item(TIKTOK_VIDEO_ITEM, "clockworks/tiktok-scraper")
    assert record is not None
    assert record.record_type == "tiktok_video"
    assert _c(record)["platform"] == "tiktok"
    assert "momlife" in _c(record)["text"]


def test_normalize_youtube_item() -> None:
    record = normalize_apify_item(YOUTUBE_VIDEO_ITEM, "streamers/youtube-scraper")
    assert record is not None
    assert record.record_type == "youtube_video"
    assert _c(record)["platform"] == "youtube"
    assert "Momcozy" in _c(record)["text"]


def test_normalize_reddit_item() -> None:
    record = normalize_apify_item(REDDIT_POST_ITEM, "trudax/reddit-scraper-lite")
    assert record is not None
    assert record.record_type == "reddit_post"
    assert _c(record)["platform"] == "reddit"


def test_normalize_empty_item_returns_none() -> None:
    assert normalize_apify_item({}, "apify/instagram-scraper") is None


def test_normalize_non_dict_returns_none() -> None:
    assert normalize_apify_item("not a dict", "apify/instagram-scraper") is None  # type: ignore[arg-type]


def test_normalize_with_explicit_record_type_override() -> None:
    record = normalize_apify_item(INSTAGRAM_POST_ITEM, "apify/instagram-scraper", record_type="custom_type")
    assert record is not None
    assert record.record_type == "custom_type"


# ---------------------------------------------------------------------------
# validate_config
# ---------------------------------------------------------------------------


def test_validate_config_missing_actor_id_raises() -> None:
    collector = ApifyActorCollector(config={"actor_input": {}})
    with pytest.raises(CollectorError, match="actor_id"):
        collector.validate_config()


def test_validate_config_actor_id_without_slash_raises() -> None:
    collector = ApifyActorCollector(config={"actor_id": "instagramscraper", "actor_input": {}})
    with pytest.raises(CollectorError, match="apify_actor_id_invalid"):
        collector.validate_config()


def test_validate_config_missing_actor_input_raises() -> None:
    collector = ApifyActorCollector(config={"actor_id": "apify/instagram-scraper"})
    with pytest.raises(CollectorError, match="apify_actor_input_missing"):
        collector.validate_config()


def test_validate_config_actor_input_not_dict_raises() -> None:
    collector = ApifyActorCollector(
        config={"actor_id": "apify/instagram-scraper", "actor_input": "not_a_dict"}
    )
    with pytest.raises(CollectorError, match="apify_actor_input_missing"):
        collector.validate_config()


def test_validate_config_valid() -> None:
    collector = ApifyActorCollector(
        config={
            "actor_id": "apify/instagram-scraper",
            "actor_input": {"search": "test"},
            "max_items": 10,
            "max_total_charge_usd": 0.5,
        }
    )
    cfg = collector.validate_config()
    assert cfg["actor_id"] == "apify/instagram-scraper"
    assert cfg["max_items"] == 10
    assert cfg["max_total_charge_usd"] == 0.5


def test_validate_config_max_items_capped_at_1000() -> None:
    collector = ApifyActorCollector(
        config={"actor_id": "apify/instagram-scraper", "actor_input": {}, "max_items": 99999}
    )
    cfg = collector.validate_config()
    assert cfg["max_items"] == 1000


# ---------------------------------------------------------------------------
# collect() — mock HTTP (full async flow)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collect_succeeds_end_to_end_mock() -> None:
    run_id = "run_test_001"
    dataset_id = "ds_test_001"
    dataset_items = [INSTAGRAM_POST_ITEM]

    transport = _make_sequence_transport([
        ("/runs", _run_response(run_id, "SUCCEEDED", dataset_id)),
        (f"/actor-runs/{run_id}", _run_response(run_id, "SUCCEEDED", dataset_id)),
        (f"/datasets/{dataset_id}/items", dataset_items),
    ])

    collector = ApifyActorCollector(
        config={
            "actor_id": "apify/instagram-scraper",
            "actor_input": {"search": "breast pump", "resultsLimit": 3},
            "max_items": 5,
        }
    )

    with patch("data_intelligence_hub.collectors.apify_actor._get_api_token", return_value="fake_token"):
        with patch("data_intelligence_hub.collectors.apify_actor.httpx.AsyncClient", _patched_client(transport)):
            result = await collector.collect()

    assert result.errors == []
    assert len(result.raw_records) == 1
    assert result.raw_records[0].record_type == "instagram_post"
    assert _c(result.raw_records[0])["actor_id"] == "apify/instagram-scraper"


@pytest.mark.asyncio
async def test_collect_actor_run_failed_returns_error() -> None:
    run_id = "run_fail_001"
    dataset_id = "ds_fail_001"

    transport = _make_sequence_transport([
        ("/runs", _run_response(run_id, "FAILED", dataset_id)),
        (f"/actor-runs/{run_id}", _run_response(run_id, "FAILED", dataset_id)),
    ])

    collector = ApifyActorCollector(
        config={
            "actor_id": "apify/instagram-scraper",
            "actor_input": {"search": "test"},
        }
    )

    with patch("data_intelligence_hub.collectors.apify_actor._get_api_token", return_value="fake_token"):
        with patch("data_intelligence_hub.collectors.apify_actor.httpx.AsyncClient", _patched_client(transport)):
            result = await collector.collect()

    assert len(result.errors) == 1
    assert "FAILED" in result.errors[0]
    assert result.raw_records == []


@pytest.mark.asyncio
async def test_collect_missing_api_token_returns_error() -> None:
    with patch.dict("os.environ", {}, clear=True):
        import os
        os.environ.pop("APIFY_API_TOKEN", None)
        collector = ApifyActorCollector(
            config={"actor_id": "apify/instagram-scraper", "actor_input": {}}
        )
        result = await collector.collect()

    assert len(result.errors) == 1
    assert "apify_token_missing" in result.errors[0]
    assert result.raw_records == []


@pytest.mark.asyncio
async def test_collect_http_error_returns_error_not_exception() -> None:
    def error_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "internal server error"})

    transport = httpx.MockTransport(error_handler)
    collector = ApifyActorCollector(
        config={"actor_id": "apify/instagram-scraper", "actor_input": {"search": "test"}}
    )

    with patch("data_intelligence_hub.collectors.apify_actor._get_api_token", return_value="fake_token"):
        with patch("data_intelligence_hub.collectors.apify_actor.httpx.AsyncClient", _patched_client(transport)):
            result = await collector.collect()

    assert len(result.errors) >= 1
    assert result.raw_records == []


@pytest.mark.asyncio
async def test_collect_empty_dataset_returns_zero_records() -> None:
    run_id = "run_empty_001"
    dataset_id = "ds_empty_001"

    transport = _make_sequence_transport([
        ("/runs", _run_response(run_id, "SUCCEEDED", dataset_id)),
        (f"/actor-runs/{run_id}", _run_response(run_id, "SUCCEEDED", dataset_id)),
        (f"/datasets/{dataset_id}/items", []),
    ])

    collector = ApifyActorCollector(
        config={"actor_id": "apify/instagram-scraper", "actor_input": {"search": "test"}}
    )

    with patch("data_intelligence_hub.collectors.apify_actor._get_api_token", return_value="fake_token"):
        with patch("data_intelligence_hub.collectors.apify_actor.httpx.AsyncClient", _patched_client(transport)):
            result = await collector.collect()

    assert result.errors == []
    assert result.raw_records == []


@pytest.mark.asyncio
async def test_collect_all_items_unnormalizable_adds_error() -> None:
    """Items that can't be normalized (empty dicts) should trigger error."""
    run_id = "run_bad_001"
    dataset_id = "ds_bad_001"
    bad_items: list[dict[str, Any]] = [{}, {}, {}]

    transport = _make_sequence_transport([
        ("/runs", _run_response(run_id, "SUCCEEDED", dataset_id)),
        (f"/actor-runs/{run_id}", _run_response(run_id, "SUCCEEDED", dataset_id)),
        (f"/datasets/{dataset_id}/items", bad_items),
    ])

    collector = ApifyActorCollector(
        config={"actor_id": "apify/instagram-scraper", "actor_input": {"search": "test"}}
    )

    with patch("data_intelligence_hub.collectors.apify_actor._get_api_token", return_value="fake_token"):
        with patch("data_intelligence_hub.collectors.apify_actor.httpx.AsyncClient", _patched_client(transport)):
            result = await collector.collect()

    assert any("apify_normalize_all_failed" in e for e in result.errors)
    assert result.raw_records == []


# ---------------------------------------------------------------------------
# test() — mock HTTP
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_test_valid_token_returns_ok() -> None:
    me_response = {"data": {"username": "testuser", "plan": "FREE"}}
    transport = _make_sequence_transport([("/users/me", me_response)])

    collector = ApifyActorCollector(
        config={"actor_id": "apify/instagram-scraper", "actor_input": {}}
    )

    with patch("data_intelligence_hub.collectors.apify_actor._get_api_token", return_value="fake_token"):
        with patch("data_intelligence_hub.collectors.apify_actor.httpx.AsyncClient", _patched_client(transport)):
            result = await collector.test()

    assert result.status == "ok"
    assert "testuser" in result.message


@pytest.mark.asyncio
async def test_test_missing_token_returns_failed() -> None:
    with patch.dict("os.environ", {}, clear=True):
        import os
        os.environ.pop("APIFY_API_TOKEN", None)
        collector = ApifyActorCollector(
            config={"actor_id": "apify/instagram-scraper", "actor_input": {}}
        )
        result = await collector.test()

    assert result.status == "failed"
    assert "apify_token_missing" in result.message


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------


def test_apify_registered_in_registry() -> None:
    from data_intelligence_hub.collectors.registry import COLLECTOR_REGISTRY

    assert "apify_actor" in COLLECTOR_REGISTRY
    assert COLLECTOR_REGISTRY["apify_actor"] is ApifyActorCollector
