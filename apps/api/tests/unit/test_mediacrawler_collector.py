"""Unit tests for MediaCrawler-based collectors.

All HTTP calls are mocked via httpx.AsyncMock — no real MediaCrawler required.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from data_intelligence_hub.collectors.base import CollectorError
from data_intelligence_hub.collectors.mediacrawler_collector import (
    BilibiliUserVideosCollector,
    BilibiliVideoCommentsCollector,
    BilibiliVideoSearchCollector,
    KuaishouUserVideosCollector,
    KuaishouVideoSearchCollector,
    WeiboKeywordSearchCollector,
    WeiboTrendingTopicsCollector,
    WeiboUserPostsCollector,
    ZhihuHotListCollector,
    ZhihuKeywordSearchCollector,
    ZhihuQuestionAnswersCollector,
    _records_from,
)
from datetime import UTC, datetime


def _mc_response(data: list[dict[str, Any]], code: int = 0) -> MagicMock:
    r = MagicMock()
    r.raise_for_status = MagicMock()
    r.json.return_value = {"code": code, "data": data}
    return r


def _mc_error_response(msg: str) -> MagicMock:
    r = MagicMock()
    r.raise_for_status = MagicMock()
    r.json.return_value = {"code": 1, "msg": msg, "data": []}
    return r


def _patch_mc_get(return_value: list[dict[str, Any]]):
    return patch(
        "data_intelligence_hub.collectors.mediacrawler_collector._mc_get",
        new_callable=AsyncMock,
        return_value=return_value,
    )


def _patch_mc_get_error(exc: Exception):
    return patch(
        "data_intelligence_hub.collectors.mediacrawler_collector._mc_get",
        new_callable=AsyncMock,
        side_effect=exc,
    )


class TestRecordsFrom:
    def test_creates_records_with_source_url(self):
        items = [{"url": "https://b.com/1", "title": "t1"}, {"url": "https://b.com/2"}]
        now = datetime.now(UTC)
        records = _records_from(items, "post", "url", now)
        assert len(records) == 2
        assert records[0].source_url == "https://b.com/1"
        assert records[0].record_type == "post"
        assert records[0].content["title"] == "t1"

    def test_none_source_url_key(self):
        items = [{"text": "hello"}]
        now = datetime.now(UTC)
        records = _records_from(items, "comment", None, now)
        assert records[0].source_url is None


class TestBilibiliVideoSearch:
    def test_missing_keyword_raises(self):
        with pytest.raises(CollectorError):
            BilibiliVideoSearchCollector(config={}).validate_config()

    def test_max_items_bounds(self):
        with pytest.raises(CollectorError):
            BilibiliVideoSearchCollector(config={"keyword": "k", "max_items": 999}).validate_config()

    def test_valid_config(self):
        cfg = BilibiliVideoSearchCollector(config={"keyword": "python"}).validate_config()
        assert cfg["keyword"] == "python"
        assert cfg["max_items"] == 20

    @pytest.mark.asyncio
    async def test_collect_returns_records(self):
        items = [{"url": "https://bilibili.com/1", "title": "v1"}]
        with _patch_mc_get(items):
            result = await BilibiliVideoSearchCollector(
                config={"keyword": "python"}
            ).collect()
        assert len(result.raw_records) == 1
        assert result.raw_records[0].record_type == "post"
        assert not result.errors

    @pytest.mark.asyncio
    async def test_collect_error_returns_error(self):
        with _patch_mc_get_error(CollectorError("MediaCrawler down")):
            result = await BilibiliVideoSearchCollector(
                config={"keyword": "python"}
            ).collect()
        assert result.raw_records == []
        assert result.errors


class TestBilibiliUserVideos:
    def test_missing_uid_raises(self):
        with pytest.raises(CollectorError):
            BilibiliUserVideosCollector(config={}).validate_config()

    @pytest.mark.asyncio
    async def test_collect_happy_path(self):
        items = [{"url": "https://bilibili.com/v/1", "bvid": "BV1xx"}]
        with _patch_mc_get(items):
            result = await BilibiliUserVideosCollector(
                config={"uid": "123456"}
            ).collect()
        assert len(result.raw_records) == 1
        assert not result.errors


class TestBilibiliVideoComments:
    def test_missing_bvid_raises(self):
        with pytest.raises(CollectorError):
            BilibiliVideoCommentsCollector(config={}).validate_config()

    @pytest.mark.asyncio
    async def test_collect_returns_comment_records(self):
        items = [{"content": "great video!"}]
        with _patch_mc_get(items):
            result = await BilibiliVideoCommentsCollector(
                config={"bvid": "BV1xx411c7mD"}
            ).collect()
        assert result.raw_records[0].record_type == "comment"
        assert result.raw_records[0].source_url is None


class TestWeiboKeywordSearch:
    def test_missing_keyword_raises(self):
        with pytest.raises(CollectorError):
            WeiboKeywordSearchCollector(config={}).validate_config()

    @pytest.mark.asyncio
    async def test_collect_returns_post_records(self):
        items = [{"url": "https://weibo.com/1", "text": "hello"}]
        with _patch_mc_get(items):
            result = await WeiboKeywordSearchCollector(
                config={"keyword": "AI"}
            ).collect()
        assert len(result.raw_records) == 1
        assert result.raw_records[0].record_type == "post"


class TestWeiboUserPosts:
    def test_missing_user_id_raises(self):
        with pytest.raises(CollectorError):
            WeiboUserPostsCollector(config={}).validate_config()

    @pytest.mark.asyncio
    async def test_collect_happy_path(self):
        items = [{"id": "w1", "text": "post1"}]
        with _patch_mc_get(items):
            result = await WeiboUserPostsCollector(config={"uid": "uid123"}).collect()
        assert len(result.raw_records) == 1
        assert not result.errors


class TestWeiboTrendingTopics:
    @pytest.mark.asyncio
    async def test_collect_returns_trend_record(self):
        items = [{"name": "#热搜1#", "hotness": 100}]
        with _patch_mc_get(items):
            result = await WeiboTrendingTopicsCollector(config={}).collect()
        assert len(result.raw_records) == 1
        assert result.raw_records[0].record_type == "trend"

    @pytest.mark.asyncio
    async def test_collect_error(self):
        with _patch_mc_get_error(CollectorError("network error")):
            result = await WeiboTrendingTopicsCollector(config={}).collect()
        assert result.raw_records == []
        assert result.errors


class TestZhihuQuestionAnswers:
    def test_missing_question_id_raises(self):
        with pytest.raises(CollectorError):
            ZhihuQuestionAnswersCollector(config={}).validate_config()

    @pytest.mark.asyncio
    async def test_collect_returns_records(self):
        items = [{"id": "a1", "content": "answer"}]
        with _patch_mc_get(items):
            result = await ZhihuQuestionAnswersCollector(
                config={"question_id": "123456"}
            ).collect()
        assert len(result.raw_records) == 1
        assert result.raw_records[0].record_type == "post"


class TestZhihuKeywordSearch:
    def test_missing_keyword_raises(self):
        with pytest.raises(CollectorError):
            ZhihuKeywordSearchCollector(config={}).validate_config()

    @pytest.mark.asyncio
    async def test_collect_happy_path(self):
        items = [{"url": "https://zhihu.com/q/1", "title": "Q1"}]
        with _patch_mc_get(items):
            result = await ZhihuKeywordSearchCollector(
                config={"keyword": "机器学习"}
            ).collect()
        assert len(result.raw_records) == 1


class TestZhihuHotList:
    @pytest.mark.asyncio
    async def test_collect_returns_trend_record(self):
        items = [{"title": "热榜1", "url": "https://zhihu.com/hot/1"}]
        with _patch_mc_get(items):
            result = await ZhihuHotListCollector(config={}).collect()
        assert result.raw_records[0].record_type == "trend"


class TestKuaishouVideoSearch:
    def test_missing_keyword_raises(self):
        with pytest.raises(CollectorError):
            KuaishouVideoSearchCollector(config={}).validate_config()

    @pytest.mark.asyncio
    async def test_collect_returns_records(self):
        items = [{"url": "https://ks.com/v/1", "title": "k1"}]
        with _patch_mc_get(items):
            result = await KuaishouVideoSearchCollector(
                config={"keyword": "搞笑"}
            ).collect()
        assert len(result.raw_records) == 1
        assert result.raw_records[0].record_type == "post"


class TestKuaishouUserVideos:
    def test_missing_user_id_raises(self):
        with pytest.raises(CollectorError):
            KuaishouUserVideosCollector(config={}).validate_config()

    @pytest.mark.asyncio
    async def test_collect_happy_path(self):
        items = [{"id": "v1", "caption": "test"}]
        with _patch_mc_get(items):
            result = await KuaishouUserVideosCollector(
                config={"user_id": "ks_user_1"}
            ).collect()
        assert len(result.raw_records) == 1
        assert not result.errors
