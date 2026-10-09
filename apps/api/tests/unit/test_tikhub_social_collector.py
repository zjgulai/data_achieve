"""Unit tests for TikHubSocialCollector.

All tests use httpx mock transports — no real network calls, no TIKHUB_API_KEY
required (except where explicitly noted with pytest.mark.skip).
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import patch

import httpx
import pytest

from data_intelligence_hub.collectors.base import CollectorError, CollectorRawRecord
from data_intelligence_hub.collectors.tikhub_social import (
    TIKHUB_ENDPOINT_MAP,
    TikHubSocialCollector,
    _extract_hashtags,
    _extract_items,
    _normalize_instagram_post,
    _normalize_item,
    _normalize_reddit_post,
    _normalize_tiktok_video,
    _normalize_xiaohongshu_note,
    _normalize_youtube_video,
    _safe_int,
    _safe_ts,
)


def _c(record: CollectorRawRecord) -> dict[str, Any]:
    return cast(dict[str, Any], record.content)

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
# Regression: 2026-10-09 生产实测发现 youtube/reddit 归一化形状过时
# （data.contents / data.search 由 list 变成 dict），线上端点静默返回空记录。
# ---------------------------------------------------------------------------

YOUTUBE_SEARCH_RESPONSE: dict[str, Any] = {
    "data": {
        "contents": {
            "twoColumnSearchResultsRenderer": {
                "primaryContents": {
                    "sectionListRenderer": {
                        "contents": [
                            {
                                "itemSectionRenderer": {
                                    "contents": [
                                        {
                                            "videoRenderer": {
                                                "videoId": "K5KVEU3aaeQ",
                                                "title": {"runs": [{"text": "Python Full Course"}]},
                                                "ownerText": {"runs": [{"text": "Programming with Mosh"}]},
                                                "viewCountText": {"simpleText": "7,823,573 views"},
                                            }
                                        },
                                        {
                                            "videoRenderer": {
                                                "videoId": "fWjsdhR3z3c",
                                                "title": {"runs": [{"text": "Learn Python Fast"}]},
                                            }
                                        },
                                    ]
                                }
                            }
                        ]
                    }
                }
            }
        }
    }
}


def test_extract_items_youtube_nested_video_renderers() -> None:
    items = _extract_items(YOUTUBE_SEARCH_RESPONSE, "youtube")
    assert [item["videoId"] for item in items] == ["K5KVEU3aaeQ", "fWjsdhR3z3c"]


def test_extract_items_youtube_prefers_flat_videos_list() -> None:
    data = {"data": {"videos": [{"id": "1"}, {"id": "2"}]}}
    assert len(_extract_items(data, "youtube")) == 2


def test_normalize_youtube_video_full_item() -> None:
    item = _extract_items(YOUTUBE_SEARCH_RESPONSE, "youtube")[0]
    record = _normalize_youtube_video(item, "tikhub_youtube_search")
    assert record is not None
    assert record.source_url == "https://www.youtube.com/watch?v=K5KVEU3aaeQ"
    content = _c(record)
    assert content["text"] == "Python Full Course"
    assert content["channel"] == "Programming with Mosh"
    assert content["view_count_text"] == "7,823,573 views"


def test_normalize_youtube_video_without_id_falls_back_to_generic() -> None:
    record = _normalize_youtube_video({"title": "flat item"}, "tikhub_youtube_search")
    assert record is not None
    assert _c(record)["text"] == "flat item"


REDDIT_SEARCH_RESPONSE: dict[str, Any] = {
    "data": {
        "search": {
            "dynamic": {
                "components": {
                    "main": {
                        "edges": [
                            {
                                "node": {
                                    "children": [
                                        {
                                            "__typename": "SearchPost",
                                            "post": {
                                                "__typename": "Post",
                                                "postTitle": "My Python magic is gone",
                                                "permalink": "/r/Python/comments/1wwv97o/my_python_magic_is_gone/",
                                                "score": 837,
                                                "commentCount": 296,
                                                "createdAt": "2026-10-03T19:08:43.382000+0000",
                                                "authorInfo": {"__typename": "Redditor", "name": "RedYad2"},
                                                "subreddit": {"__typename": "Subreddit", "name": "Python"},
                                                "content": {"markdown": "I've been coding for a long time."},
                                            },
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
            }
        }
    }
}


def test_extract_items_reddit_dynamic_search_posts() -> None:
    items = _extract_items(REDDIT_SEARCH_RESPONSE, "reddit")
    assert len(items) == 1
    assert items[0]["postTitle"] == "My Python magic is gone"


def test_normalize_reddit_post_full_item() -> None:
    item = _extract_items(REDDIT_SEARCH_RESPONSE, "reddit")[0]
    record = _normalize_reddit_post(item, "tikhub_reddit_search")
    assert record is not None
    assert record.source_url == "https://www.reddit.com/r/Python/comments/1wwv97o/my_python_magic_is_gone/"
    content = _c(record)
    assert content["text"] == "My Python magic is gone"
    assert content["subreddit"] == "Python"
    assert content["author"] == "RedYad2"
    assert content["score"] == 837


def test_normalize_reddit_post_without_title_falls_back_to_generic() -> None:
    record = _normalize_reddit_post({"text": "flat"}, "tikhub_reddit_search")
    assert record is not None
    assert _c(record)["text"] == "flat"


def test_normalize_item_routes_youtube_and_reddit() -> None:
    youtube_item = _extract_items(YOUTUBE_SEARCH_RESPONSE, "youtube")[0]
    reddit_item = _extract_items(REDDIT_SEARCH_RESPONSE, "reddit")[0]
    youtube_record = _normalize_item(youtube_item, "youtube", "tikhub_youtube_search")
    reddit_record = _normalize_item(reddit_item, "reddit", "tikhub_reddit_search")
    assert youtube_record is not None
    assert reddit_record is not None
    assert _c(youtube_record)["platform"] == "youtube"
    assert _c(reddit_record)["platform"] == "reddit"


# ---------------------------------------------------------------------------
# collect() — mock HTTP
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collect_tiktok_video_search_mock() -> None:
    with patch(
        "data_intelligence_hub.collectors.tikhub_social._get_api_key",
        return_value="fake_key",
    ):
        transport = _make_mock_transport(TIKHUB_TIKTOK_RESPONSE)
        collector = TikHubSocialCollector(
            config={
                "endpoint_type": "tikhub_tiktok_video_search",
                "keyword": "breast pump",
                "max_items": 5,
            }
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
    with patch(
        "data_intelligence_hub.collectors.tikhub_social._get_api_key",
        return_value="fake_key",
    ):
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
    with patch(
        "data_intelligence_hub.collectors.tikhub_social._get_api_key",
        return_value="fake_key",
    ):
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
    with patch(
        "data_intelligence_hub.collectors.tikhub_social._get_api_key",
        return_value="fake_key",
    ):

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
    with patch(
        "data_intelligence_hub.collectors.tikhub_social._get_api_key",
        return_value="fake_key",
    ):
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


SUBREDDIT_FEED_RESPONSE: dict[str, Any] = {
    "code": 200,
    "data": {
        "subredditV3": {
            "elements": {
                "dist": None,
                "edges": [
                    {
                        "__typename": "FeedElementEdge",
                        "node": {
                            "__typename": "CellGroup",
                            "groupId": "t3_1wxjay5",
                            "cells": [
                                {
                                    "__typename": "MetadataCell",
                                    "authorName": "AutoModerator",
                                    "createdAt": "2026-10-04T16:05:17.397000+0000",
                                },
                                {"__typename": "TitleCell", "title": "Showcase Thread"},
                                {
                                    "__typename": "ActionCell",
                                    "score": 17,
                                    "commentCount": 4,
                                },
                            ],
                        },
                    },
                    {
                        "__typename": "FeedElementEdge",
                        "node": {
                            "__typename": "CellGroup",
                            "groupId": "t3_1x16rfy",
                            "cells": [
                                {
                                    "__typename": "MetadataCell",
                                    "authorName": "u/someone",
                                    "createdAt": "2026-10-09T00:00:32.357000+0000",
                                },
                                {
                                    "__typename": "TitleCell",
                                    "title": "Friday Daily Thread",
                                },
                                {
                                    "__typename": "PreviewTextCell",
                                    "text": "weekly free-talk",
                                },
                                {"__typename": "ActionCell", "score": 3, "commentCount": 12},
                            ],
                        },
                    },
                ],
            }
        }
    },
}


def test_extract_items_reddit_subreddit_feed_returns_cell_groups() -> None:
    """fetch_subreddit_feed 返回的是 UI 结构（CellGroup），不是 SearchPost。"""
    items = _extract_items(SUBREDDIT_FEED_RESPONSE, "reddit")
    assert len(items) == 2
    assert items[0]["__typename"] == "CellGroup"


def test_normalize_reddit_subreddit_post_reads_cells() -> None:
    items = _extract_items(SUBREDDIT_FEED_RESPONSE, "reddit")
    record = _normalize_item(items[0], "reddit", "tikhub_reddit_subreddit_posts")
    assert record is not None
    content = record.content
    assert content["post_id"] == "1wxjay5"
    assert content["text"] == "Showcase Thread"
    assert content["author"] == "AutoModerator"
    assert content["score"] == 17
    assert content["url"] == "https://www.reddit.com/comments/1wxjay5"


def test_normalize_reddit_subreddit_post_carries_preview_text() -> None:
    items = _extract_items(SUBREDDIT_FEED_RESPONSE, "reddit")
    record = _normalize_item(items[1], "reddit", "tikhub_reddit_subreddit_posts")
    assert record is not None
    assert record.content["body"] == "weekly free-talk"


YOUTUBE_COMMENTS_RESPONSE: dict[str, Any] = {
    "code": 200,
    "data": {
        "comments": [
            {
                "comment_id": "Ugzge340dBgB75hWBm54AaABAg",
                "content": "can confirm: he never gave us up",
                "published_time": "1 year ago",
                "like_count": "12K",
                "reply_count": 3,
                "reply_level": 0,
            }
        ],
        "continuation_token": "tok",
    },
}

REDDIT_POPULAR_FEED_RESPONSE: dict[str, Any] = {
    "code": 200,
    "data": {
        "popularfeed": {
            "postsInfoByIds": [
                {
                    "__typename": "Post",
                    "id": "1o8v3kd",
                    "createdAt": "2026-10-08T12:05:42.883000+0000",
                    "subreddit": {"name": "AskReddit"},
                    "postTitle": "Bartender threatened to kick me out",
                }
            ]
        },
        "after": "t3_next",
    },
}

X_TRENDING_RESPONSE: dict[str, Any] = {
    "code": 200,
    "data": {
        "trends": [
            {"name": "New Yorker", "description": None, "context": "Trending in United States"}
        ]
    },
}

LINKEDIN_COMPANY_PROFILE_RESPONSE: dict[str, Any] = {
    "code": 200,
    "data": {
        "id": "1035",
        "name": "Microsoft",
        "followers": 29258099,
        "about": "Every company has a mission.",
        "url": "https://www.linkedin.com/company/microsoft",
        "description": "Microsoft | 29,258,099 followers on LinkedIn.",
        "specialties": ["Cloud", "AI"],
    },
}


def test_extract_items_youtube_video_comments() -> None:
    items = _extract_items(YOUTUBE_COMMENTS_RESPONSE, "youtube")
    assert len(items) == 1
    record = _normalize_item(items[0], "youtube", "tikhub_youtube_video_comments")
    assert record is not None
    assert record.record_type == "youtube_comment"
    assert record.content["comment_id"] == "Ugzge340dBgB75hWBm54AaABAg"
    assert record.content["text"] == "can confirm: he never gave us up"


def test_extract_items_reddit_popular_feed() -> None:
    items = _extract_items(REDDIT_POPULAR_FEED_RESPONSE, "reddit")
    assert len(items) == 1
    record = _normalize_item(items[0], "reddit", "tikhub_reddit_trending")
    assert record is not None
    assert record.content["text"] == "Bartender threatened to kick me out"
    # 只有 id，没有 permalink / url，必须能从 id 拼出链接
    assert record.source_url == "https://www.reddit.com/comments/1o8v3kd"


def test_extract_items_x_trending() -> None:
    items = _extract_items(X_TRENDING_RESPONSE, "x")
    assert len(items) == 1
    record = _normalize_item(items[0], "x", "tikhub_x_trending")
    assert record is not None
    assert record.record_type == "trend"
    assert record.content["text"] == "New Yorker"
    assert record.content["context"] == "Trending in United States"


def test_extract_items_linkedin_company_profile() -> None:
    items = _extract_items(LINKEDIN_COMPANY_PROFILE_RESPONSE, "linkedin")
    assert len(items) == 1
    record = _normalize_item(items[0], "linkedin", "tikhub_linkedin_company_profile")
    assert record is not None
    assert "Microsoft" in record.content["text"]
    assert record.source_url == "https://www.linkedin.com/company/microsoft"


TIKTOK_LIVE_SEARCH_RESPONSE: dict[str, Any] = {
    "code": 200,
    "data": {
        "status_code": 0,
        "data": [
            {"type": 1, "lives": {"aweme_id": "7694578771533351710", "author": {"uid": "693", "nickname": "Kwood"}}},
            {"type": 2, "anchor": {"owner_user_info": {"uid": "720", "nickname": "music"}, "live_info": {}}},
        ],
        "has_more": 1,
    },
}

TIKTOK_SHOP_PRODUCTS_RESPONSE: dict[str, Any] = {
    "code": 200,
    "data": {
        "code": 0,
        "message": "ok",
        "data": {
            "products": [
                {
                    "product_id": "1731987113638072822",
                    "title": "junk phone case",
                    "seo_url": "https://shop.tiktok.com/us/pdp/x/1731987113638072822",
                    "product_price_info": {"sale_price": "9.99"},
                }
            ]
        },
    },
}

TIKTOK_TOP_ADS_RESPONSE: dict[str, Any] = {
    "code": 200,
    "data": {
        "code": 0,
        "msg": "ok",
        "data": {
            "materials": [
                {"id": "7182310470102122497", "highlight": "Showcase a comparison", "ctr": 0.21, "like": 33506}
            ]
        },
    },
}


def test_extract_items_tiktok_live_search() -> None:
    items = _extract_items(TIKTOK_LIVE_SEARCH_RESPONSE, "tiktok")
    assert len(items) == 2
    records = [_normalize_item(i, "tiktok", "tikhub_tiktok_live_search") for i in items]
    assert all(r is not None for r in records)
    assert records[0].record_type == "tiktok_live"
    assert records[0].content["nickname"] == "Kwood"
    assert records[0].content["room_id"] == "7694578771533351710"
    assert records[1].content["nickname"] == "music"


def test_extract_items_tiktok_shop_products() -> None:
    # platform 是 "tiktok_shop"，不是 "tiktok"（TIKHUB_ENDPOINT_MAP 里就是这样）
    items = _extract_items(TIKTOK_SHOP_PRODUCTS_RESPONSE, "tiktok_shop")
    assert len(items) == 1
    record = _normalize_item(items[0], "tiktok_shop", "tikhub_tiktok_shop_products")
    assert record is not None
    assert record.record_type == "tiktok_shop_product"
    assert record.content["text"] == "junk phone case"
    assert record.content["product_id"] == "1731987113638072822"


def test_extract_items_tiktok_top_ads() -> None:
    items = _extract_items(TIKTOK_TOP_ADS_RESPONSE, "tiktok")
    assert len(items) == 1
    record = _normalize_item(items[0], "tiktok", "tikhub_tiktok_top_ads")
    assert record is not None
    assert record.record_type == "tiktok_ad"
    assert record.content["material_id"] == "7182310470102122497"
    assert record.content["text"] == "Showcase a comparison"


THREADS_USER_POSTS_RESPONSE: dict[str, Any] = {
    "code": 200,
    "data": {
        "mediaData": {
            "edges": [
                {
                    "node": {
                        "__typename": "ThreadItem",
                        "id": "111",
                        "thread_items": [
                            {
                                "post": {
                                    "id": "222",
                                    "code": "Cxyz",
                                    "user": {"username": "zuck"},
                                    "caption": {"text": "hello threads"},
                                }
                            }
                        ],
                    }
                }
            ],
            "page_info": {"has_next_page": False},
        }
    },
}

THREADS_POST_COMMENTS_RESPONSE: dict[str, Any] = {
    "code": 200,
    "data": {
        "edges": [
            {
                "node": {
                    "id": "333",
                    "thread_items": [
                        {"post": {"id": "444", "code": "Dabc", "caption": {"text": "a reply"}}}
                    ],
                }
            }
        ],
        "page_info": {},
    },
}


def test_extract_items_threads_user_posts() -> None:
    items = _extract_items(THREADS_USER_POSTS_RESPONSE, "threads")
    assert len(items) == 1
    record = _normalize_item(items[0], "threads", "tikhub_threads_user_posts")
    assert record is not None
    assert record.record_type == "threads_post"
    assert record.content["text"] == "hello threads"
    assert record.content["author"] == "zuck"


def test_extract_items_threads_post_comments() -> None:
    items = _extract_items(THREADS_POST_COMMENTS_RESPONSE, "threads")
    assert len(items) == 1
    record = _normalize_item(items[0], "threads", "tikhub_threads_post_comments")
    assert record is not None
    assert record.content["text"] == "a reply"


TIKTOK_LIVE_ROOM_RESPONSE: dict[str, Any] = {
    "code": 200,
    "data": {
        "status_code": 0,
        "data": {
            "id_str": "7694650101042170654",
            "id": "7694650101042170654",
            "title": "Morning Worship Prayer",
            "owner": {"nickname": "Full Soul", "id_str": "7001"},
        },
        "extra": {},
    },
}

X_FOLLOWERS_RESPONSE: dict[str, Any] = {
    "code": 200,
    "data": {
        "followers_count": 1,
        "followers": [{"user_id": "1153803242", "screen_name": "0xOrionVega", "description": "hi"}],
        "next_cursor": "",
    },
}


def test_extract_items_tiktok_live_room_detail() -> None:
    """fetch_live_room_info 的 data.data 是单个直播间对象，不是列表。"""
    items = _extract_items(TIKTOK_LIVE_ROOM_RESPONSE, "tiktok")
    assert len(items) == 1
    record = _normalize_item(items[0], "tiktok", "tikhub_tiktok_live_room_detail")
    assert record is not None
    assert record.record_type == "tiktok_live"
    assert record.content["room_id"] == "7694650101042170654"
    assert record.content["nickname"] == "Full Soul"


def test_extract_items_x_user_followers() -> None:
    items = _extract_items(X_FOLLOWERS_RESPONSE, "x")
    assert len(items) == 1
    record = _normalize_item(items[0], "x", "tikhub_x_user_followers")
    assert record is not None


TIKTOK_FOLLOWERS_RESPONSE: dict[str, Any] = {
    "code": 200,
    "data": {
        "followers": [
            {
                "uid": "7001",
                "sec_uid": "MS4wLjABAAAA",
                "unique_id": "someuser",
                "nickname": "Some User",
                "signature": "hi",
                "follower_count": 12,
                "item_list": [],
                "cha_list": [],
            }
        ],
        "has_more": 1,
    },
}


def test_extract_items_tiktok_followers() -> None:
    """粉丝条目是完整用户对象，没有 aweme_id，不能走视频归一化。"""
    items = _extract_items(TIKTOK_FOLLOWERS_RESPONSE, "tiktok")
    assert len(items) == 1
    record = _normalize_item(items[0], "tiktok", "tikhub_tiktok_user_followers")
    assert record is not None
    assert record.record_type == "tiktok_user"
    assert record.content["text"] == "Some User"
    assert record.content["unique_id"] == "someuser"
    assert record.source_url == "https://www.tiktok.com/@someuser"


NESTED_DOMESTIC_RESPONSES: dict[str, tuple[str, dict[str, Any]]] = {
    "bilibili": (
        "bilibili",
        {"data": {"code": 0, "data": {"item": [{"title": "v1", "bvid": "BV1"}]}}},
    ),
    "douyin_hot": (
        "douyin",
        {"data": {"data": {"word_list": [{"word": "w1", "hot_value": 1}]}}},
    ),
    "weibo": (
        "weibo",
        {"data": {"data": {"list": [{"idstr": "1", "text_raw": "hello"}]}}},
    ),
    "wechat": (
        "wechat",
        {"data": {"results": {"data": [{"type": "article", "title": "t"}]}}},
    ),
}


@pytest.mark.parametrize("key,expected", [("bilibili", 1), ("douyin_hot", 1), ("weibo", 1), ("wechat", 1)])
def test_extract_items_nested_domestic_scopes(key: str, expected: int) -> None:
    platform, payload = NESTED_DOMESTIC_RESPONSES[key]
    items = _extract_items(payload, platform)
    assert len(items) == expected


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------


def test_tikhub_registered_in_registry() -> None:
    from data_intelligence_hub.collectors.registry import COLLECTOR_REGISTRY

    assert "tikhub_social" in COLLECTOR_REGISTRY
    assert COLLECTOR_REGISTRY["tikhub_social"] is TikHubSocialCollector
