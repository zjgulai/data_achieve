"""TikTok Phase 1 content endpoint contract tests."""

from __future__ import annotations

import asyncio

from data_intelligence_hub.collectors.tikhub_social import (
    TIKHUB_CONTENT_ENDPOINT_MAP,
    TikHubSocialCollector,
    _build_params,
    _extract_content_items,
    _normalize_content_item,
)
from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.services.collector_catalog import validate_collector_config


def _video_item() -> dict:
    return {
        "id": "v1",
        "desc": "hello",
        "createTime": 1790000000,
        "author": {"uid": "u1", "unique_id": "alice", "nickname": "Alice"},
        "stats": {
            "playCount": 100,
            "diggCount": 10,
            "commentCount": 2,
            "shareCount": 1,
            "collectCount": 3,
        },
        "video": {"duration": 15, "cover": {"url_list": ["https://cover"]}},
        "music": {"id": "m1", "title": "song", "author": "artist"},
        "challenges": [{"cid": "h1", "cha_name": "newborn"}],
    }


def test_content_endpoint_map_has_phase1_endpoints() -> None:
    expected = {
        "tikhub_tiktok_video_detail",
        "tikhub_tiktok_user_posts_web",
        "tikhub_tiktok_search_web",
        "tikhub_tiktok_comments_app",
        "tikhub_tiktok_comment_replies_app",
        "tikhub_tiktok_user_profile_web",
        "tikhub_tiktok_user_fans_web",
        "tikhub_tiktok_hashtag_detail_app",
        "tikhub_tiktok_tag_posts_web",
        "tikhub_tiktok_trending_searchwords",
        "tikhub_tiktok_music_chart",
        "tikhub_tiktok_fake_views",
        "tikhub_tiktok_comment_keywords",
        "tikhub_tiktok_ads_trends",
        "tikhub_tiktok_sec_uid",
        "tikhub_tiktok_user_id",
        "tikhub_tiktok_identity_by_username",
    }
    assert expected <= set(TIKHUB_CONTENT_ENDPOINT_MAP)


def test_video_detail_extracts_item_struct() -> None:
    data = {"data": {"itemInfo": {"itemStruct": _video_item()}}}
    items = _extract_content_items(data, "video_detail")
    assert len(items) == 1
    record = _normalize_content_item(items[0], "video_detail", "tikhub_tiktok_video_detail")
    assert record is not None
    assert record.record_type == "tiktok_video"
    assert record.content["video_id"] == "v1"
    assert record.content["play_count"] == 100
    assert record.content["hashtags"] == ["newborn"]


def test_search_extracts_item_from_rows() -> None:
    data = {"data": {"data": [{"type": 1, "item": _video_item()}]}}
    items = _extract_content_items(data, "search")
    assert len(items) == 1
    record = _normalize_content_item(items[0], "search", "tikhub_tiktok_search_web")
    assert record is not None
    assert record.content["video_id"] == "v1"


def test_comments_normalize_reply_and_interaction() -> None:
    data = {
        "data": {
            "comments": [
                {
                    "cid": "c1",
                    "aweme_id": "v1",
                    "reply_id": "0",
                    "reply_to_reply_id": "0",
                    "text": "nice",
                    "comment_language": "en",
                    "digg_count": 7,
                    "reply_comment_total": 2,
                    "author_pin": True,
                    "is_author_digged": True,
                    "is_high_purchase_intent": True,
                    "create_time": 1790000000,
                    "user": {"uid": "u2", "unique_id": "bob", "nickname": "Bob"},
                }
            ]
        }
    }
    items = _extract_content_items(data, "comments")
    record = _normalize_content_item(items[0], "comments", "tikhub_tiktok_comments_app")
    assert record is not None
    assert record.record_type == "tiktok_comment"
    assert record.content["comment_id"] == "c1"
    assert record.content["parent_comment_id"] is None
    assert record.content["is_pinned"] is True
    assert record.content["creator_interacted"] is True
    assert record.content["is_high_purchase_intent"] is True
    assert record.content["author_unique_id"] == "bob"


def test_profile_normalizes_user_and_stats() -> None:
    data = {
        "data": {
            "userInfo": {
                "user": {
                    "id": "u1",
                    "uniqueId": "alice",
                    "secUid": "MS4w",
                    "nickname": "Alice",
                    "signature": "bio",
                    "verified": True,
                },
                "stats": {
                    "followerCount": 10,
                    "followingCount": 2,
                    "videoCount": 3,
                    "heartCount": 100,
                },
            }
        }
    }
    items = _extract_content_items(data, "profile")
    record = _normalize_content_item(items[0], "profile", "tikhub_tiktok_user_profile_web")
    assert record is not None
    assert record.record_type == "tiktok_user"
    assert record.content["uid"] == "u1"
    assert record.content["unique_id"] == "alice"
    assert record.content["follower_count"] == 10
    assert record.content["heart_count"] == 100


def test_fans_normalizes_user_list() -> None:
    data = {
        "data": {
            "userList": [
                {
                    "user": {"id": "u2", "uniqueId": "bob", "nickname": "Bob"},
                    "stats": {"followerCount": 5},
                }
            ]
        }
    }
    items = _extract_content_items(data, "fans")
    record = _normalize_content_item(items[0], "fans", "tikhub_tiktok_user_fans_web")
    assert record is not None
    assert record.content["uid"] == "u2"
    assert record.content["follower_count"] == 5


def test_hashtag_detail_normalizes_ch_info() -> None:
    data = {
        "data": {
            "ch_info": {
                "cid": "h1",
                "cha_name": "newborn",
                "desc": "desc",
                "use_count": 10,
                "user_count": 5,
                "view_count": 1000,
                "is_commerce": False,
            }
        }
    }
    items = _extract_content_items(data, "hashtag_detail")
    record = _normalize_content_item(items[0], "hashtag_detail", "tikhub_tiktok_hashtag_detail_app")
    assert record is not None
    assert record.record_type == "tiktok_hashtag"
    assert record.content["hashtag_id"] == "h1"
    assert record.content["video_count"] == 10
    assert record.content["view_count"] == 1000


def test_ads_trends_normalizes_items() -> None:
    data = {
        "data": {
            "items": [
                {
                    "hashtagID": "h1",
                    "hashtagName": "newborn",
                    "rankIndex": 1,
                    "publishCnt": 10,
                    "vv": 1000,
                }
            ]
        }
    }
    items = _extract_content_items(data, "ads_trends")
    record = _normalize_content_item(items[0], "ads_trends", "tikhub_tiktok_ads_trends")
    assert record is not None
    assert record.record_type == "tiktok_trend"
    assert record.content["entity_id"] == "h1"
    assert record.content["rank"] == 1
    assert record.content["view_count"] == 1000


def test_analytics_normalizes_fake_views() -> None:
    data = {"data": {"video_id": "v1", "view_pattern_type": "organic"}}
    items = _extract_content_items(data, "fake_views")
    record = _normalize_content_item(items[0], "fake_views", "tikhub_tiktok_fake_views")
    assert record is not None
    assert record.record_type == "tiktok_analytics"
    assert record.content["video_id"] == "v1"
    assert record.content["analytics_type"] == "fake_views"


def test_identity_normalizes_string_and_dict() -> None:
    string_items = _extract_content_items({"data": "MS4wABC"}, "sec_uid")
    string_record = _normalize_content_item(string_items[0], "sec_uid", "tikhub_tiktok_sec_uid")
    assert string_record is not None
    assert string_record.content["value"] == "MS4wABC"

    dict_items = _extract_content_items(
        {"data": {"user_id": "u1", "sec_user_id": "MS4wABC"}},
        "identity",
    )
    dict_record = _normalize_content_item(
        dict_items[0], "identity", "tikhub_tiktok_identity_by_username"
    )
    assert dict_record is not None
    assert dict_record.content["user_id"] == "u1"
    assert dict_record.content["sec_user_id"] == "MS4wABC"


def test_build_params_for_phase1_endpoints() -> None:
    detail = _build_params(
        {"endpoint_type": "tikhub_tiktok_video_detail", "item_id": "v1"}, 5
    )
    assert detail == {"itemId": "v1", "region": "US"}

    comments = _build_params(
        {"endpoint_type": "tikhub_tiktok_comments_app", "aweme_id": "v1"}, 5
    )
    assert comments["aweme_id"] == "v1"
    assert comments["count"] == 5

    trends = _build_params(
        {"endpoint_type": "tikhub_tiktok_ads_trends", "period": 30}, 5
    )
    assert trends == {"time_range": 30, "country_code": "US", "page": 1, "limit": 5}


class _FakeResponse:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self._payload


class _FakeClient:
    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False

    async def get(self, *args: object, **kwargs: object) -> _FakeResponse:
        return _FakeResponse({"code": 200, "data": {"itemInfo": {"itemStruct": _video_item()}}})

    async def post(self, *args: object, **kwargs: object) -> _FakeResponse:
        return _FakeResponse({"code": 200, "data": {"items": []}})


def test_collector_end_to_end_video_detail(monkeypatch) -> None:
    monkeypatch.setenv("TIKHUB_API_KEY", "test-key")
    monkeypatch.setenv("COLLECTION_NETWORK_MODE", "restricted")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "data_intelligence_hub.collectors.tikhub_social.httpx.AsyncClient",
        _FakeClient,
    )
    collector = TikHubSocialCollector(
        config={
            "endpoint_type": "tikhub_tiktok_video_detail",
            "item_id": "v1",
            "max_items": 5,
        }
    )
    try:
        result = asyncio.run(collector.collect())
    finally:
        get_settings.cache_clear()
    assert result.errors == []
    assert len(result.raw_records) == 1
    assert result.raw_records[0].content["video_id"] == "v1"


def test_validator_accepts_phase1_params() -> None:
    out = validate_collector_config(
        "tikhub_social",
        {
            "endpoint_type": "tikhub_tiktok_comment_replies_app",
            "item_id": "v1",
            "comment_id": "c1",
            "region": "US",
            "max_items": 5,
        },
    )
    assert out["endpoint_type"] == "tikhub_tiktok_comment_replies_app"
    assert out["item_id"] == "v1"
    assert out["comment_id"] == "c1"
    assert out["region"] == "US"
