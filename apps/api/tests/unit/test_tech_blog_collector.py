"""Unit tests for DevTo, Juejin, and Substack collectors."""
from __future__ import annotations

import textwrap
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from data_intelligence_hub.collectors.base import CollectorError
from data_intelligence_hub.collectors.tech_blog_collector import (
    DevToArticlesCollector,
    JuejinArticlesCollector,
    SubstackPostsCollector,
)


def _http_response(body: Any, status: int = 200, text: str | None = None) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.raise_for_status = MagicMock()
    r.json = MagicMock(return_value=body)
    r.text = text or ""
    return r


def _http_error_response() -> MagicMock:
    r = MagicMock()
    r.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock(status_code=404)
        )
    )
    return r


def _patch_get(return_value):
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=return_value)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return patch(
        "data_intelligence_hub.collectors.tech_blog_collector._client",
        return_value=mock_client,
    )


def _patch_post(return_value):
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=return_value)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return patch(
        "data_intelligence_hub.collectors.tech_blog_collector._client",
        return_value=mock_client,
    )


class TestDevToArticlesCollector:
    def test_no_filter_raises(self):
        with pytest.raises(CollectorError, match="tag.*username.*keyword"):
            DevToArticlesCollector(config={}).validate_config()

    def test_valid_with_tag(self):
        cfg = DevToArticlesCollector(config={"tag": "python"}).validate_config()
        assert cfg["tag"] == "python"
        assert cfg["max_items"] == 20

    def test_valid_with_keyword(self):
        cfg = DevToArticlesCollector(config={"keyword": "async"}).validate_config()
        assert cfg["keyword"] == "async"

    def test_max_items_bounds(self):
        with pytest.raises(CollectorError):
            DevToArticlesCollector(config={"tag": "t", "max_items": 999}).validate_config()

    @pytest.mark.asyncio
    async def test_collect_http_error_returns_error(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch(
            "data_intelligence_hub.collectors.tech_blog_collector._client",
            return_value=mock_client,
        ):
            result = await DevToArticlesCollector(config={"tag": "python"}).collect()
        assert result.raw_records == []
        assert result.errors

    @pytest.mark.asyncio
    async def test_collect_happy_path(self):
        articles = [
            {
                "id": 1, "title": "Intro to Python", "url": "https://dev.to/a/1",
                "description": "Learn Python", "tag_list": ["python"],
                "user": {"username": "alice"}, "published_at": "2025-01-01",
                "positive_reactions_count": 42, "comments_count": 5,
                "reading_time_minutes": 3,
            }
        ]
        resp = _http_response(articles)
        with _patch_get(resp):
            result = await DevToArticlesCollector(config={"tag": "python"}).collect()
        assert len(result.raw_records) == 1
        rec = result.raw_records[0]
        assert rec.record_type == "news"
        assert rec.content["title"] == "Intro to Python"
        assert rec.content["author"] == "alice"
        assert not result.errors

    @pytest.mark.asyncio
    async def test_collect_limits_items(self):
        articles = [{"id": i, "title": f"t{i}", "url": f"https://dev.to/{i}"} for i in range(10)]
        resp = _http_response(articles)
        with _patch_get(resp):
            result = await DevToArticlesCollector(
                config={"tag": "python", "max_items": 3}
            ).collect()
        assert len(result.raw_records) == 3


class TestJuejinArticlesCollector:
    def test_missing_keyword_raises(self):
        with pytest.raises(CollectorError):
            JuejinArticlesCollector(config={}).validate_config()

    def test_valid_config(self):
        cfg = JuejinArticlesCollector(config={"keyword": "vue"}).validate_config()
        assert cfg["keyword"] == "vue"
        assert cfg["max_items"] == 20

    @pytest.mark.asyncio
    async def test_collect_http_error_returns_error(self):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch(
            "data_intelligence_hub.collectors.tech_blog_collector._client",
            return_value=mock_client,
        ):
            result = await JuejinArticlesCollector(config={"keyword": "vue"}).collect()
        assert result.raw_records == []
        assert result.errors

    @pytest.mark.asyncio
    async def test_collect_happy_path(self):
        body = {
            "data": [
                {
                    "result_model": {
                        "article_info": {
                            "article_id": "111",
                            "title": "Vue 3 Guide",
                            "brief_content": "Learn Vue 3",
                            "view_count": 1000,
                            "digg_count": 50,
                            "comment_count": 5,
                            "collect_count": 20,
                            "rtime": 1700000000,
                        },
                        "author_user_info": {"user_name": "bob"},
                        "tags": [],
                    }
                }
            ]
        }
        resp = _http_response(body)
        with _patch_post(resp):
            result = await JuejinArticlesCollector(config={"keyword": "vue"}).collect()
        assert len(result.raw_records) == 1
        rec = result.raw_records[0]
        assert rec.record_type == "news"
        assert rec.content["title"] == "Vue 3 Guide"
        assert rec.content["author"] == "bob"
        assert not result.errors


class TestSubstackPostsCollector:
    def test_missing_publication_raises(self):
        with pytest.raises(CollectorError):
            SubstackPostsCollector(config={}).validate_config()

    def test_publication_normalised(self):
        cfg = SubstackPostsCollector(
            config={"publication": "https://platformer.substack.com/"}
        ).validate_config()
        assert cfg["publication"] == "platformer"

    def test_max_items_bounds(self):
        with pytest.raises(CollectorError):
            SubstackPostsCollector(
                config={"publication": "test", "max_items": 200}
            ).validate_config()

    @pytest.mark.asyncio
    async def test_collect_http_error_returns_error(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch(
            "data_intelligence_hub.collectors.tech_blog_collector._client",
            return_value=mock_client,
        ):
            result = await SubstackPostsCollector(config={"publication": "test"}).collect()
        assert result.raw_records == []
        assert result.errors

    @pytest.mark.asyncio
    async def test_collect_invalid_xml_returns_error(self):
        resp = _http_response({}, text="not valid xml <<>>")
        with _patch_get(resp):
            result = await SubstackPostsCollector(config={"publication": "test"}).collect()
        assert result.raw_records == []
        assert any("parse" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    async def test_collect_happy_path(self):
        xml = textwrap.dedent("""\
            <?xml version="1.0"?>
            <rss version="2.0">
              <channel>
                <title>Test Newsletter</title>
                <item>
                  <title>Post One</title>
                  <link>https://test.substack.com/p/one</link>
                  <description>First post</description>
                  <pubDate>Mon, 01 Jan 2025 00:00:00 +0000</pubDate>
                </item>
                <item>
                  <title>Post Two</title>
                  <link>https://test.substack.com/p/two</link>
                </item>
              </channel>
            </rss>
        """)
        resp = _http_response({}, text=xml)
        with _patch_get(resp):
            result = await SubstackPostsCollector(config={"publication": "test"}).collect()
        assert len(result.raw_records) == 2
        assert result.raw_records[0].record_type == "news"
        assert result.raw_records[0].content["title"] == "Post One"
        assert result.raw_records[0].source_url == "https://test.substack.com/p/one"
        assert not result.errors

    @pytest.mark.asyncio
    async def test_collect_limits_items(self):
        items_xml = "\n".join(
            f"<item><title>P{i}</title><link>https://t.com/{i}</link></item>"
            for i in range(5)
        )
        xml = f"<?xml version='1.0'?><rss><channel>{items_xml}</channel></rss>"
        resp = _http_response({}, text=xml)
        with _patch_get(resp):
            result = await SubstackPostsCollector(
                config={"publication": "test", "max_items": 2}
            ).collect()
        assert len(result.raw_records) == 2
