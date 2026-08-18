"""Unit tests for TwscrapeSearchCollector, TwscrapeUserTweetsCollector,
and TwscrapeTrendsCollector.

All tests mock twscrape internals — no real Twitter accounts required.
"""
from __future__ import annotations

import json
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from data_intelligence_hub.collectors.twscrape_collector import (
    TwscrapeTrendsCollector,
    TwscrapeSearchCollector,
    TwscrapeUserTweetsCollector,
    _load_accounts,
)
from data_intelligence_hub.collectors.base import CollectorError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _search(config: dict[str, Any]) -> TwscrapeSearchCollector:
    return TwscrapeSearchCollector(config=config)


def _user_tweets(config: dict[str, Any]) -> TwscrapeUserTweetsCollector:
    return TwscrapeUserTweetsCollector(config=config)


def _trends(config: dict[str, Any]) -> TwscrapeTrendsCollector:
    return TwscrapeTrendsCollector(config=config)


def _fake_tweet(idx: int = 1) -> MagicMock:
    t = MagicMock()
    t.id = 1000 + idx
    t.url = f"https://x.com/user/status/{1000 + idx}"
    t.rawContent = f"tweet content {idx}"
    t.user = MagicMock()
    t.user.username = "testuser"
    t.user.id = 99
    t.replyCount = 1
    t.retweetCount = 2
    t.likeCount = 3
    t.viewCount = 100
    t.date = None
    t.lang = "en"
    t.retweetedTweet = None
    return t


def _fake_trend(name: str) -> MagicMock:
    t = MagicMock()
    t.name = name
    t.tweetCount = 5000
    t.url = f"https://x.com/search?q={name}"
    return t


# ---------------------------------------------------------------------------
# _load_accounts
# ---------------------------------------------------------------------------


def test_load_accounts_empty_env(monkeypatch):
    monkeypatch.delenv("TWITTER_ACCOUNTS_JSON", raising=False)
    monkeypatch.delenv("TWITTER_ACCOUNTS_FILE", raising=False)
    assert _load_accounts() == []


def test_load_accounts_from_json_env(monkeypatch):
    accounts = [{"username": "u1", "cookies": "auth_token=abc"}]
    monkeypatch.setenv("TWITTER_ACCOUNTS_JSON", json.dumps(accounts))
    monkeypatch.delenv("TWITTER_ACCOUNTS_FILE", raising=False)
    result = _load_accounts()
    assert result == accounts


def test_load_accounts_invalid_json_raises(monkeypatch):
    monkeypatch.setenv("TWITTER_ACCOUNTS_JSON", "not-json")
    with pytest.raises(CollectorError, match="not valid JSON"):
        _load_accounts()


# ---------------------------------------------------------------------------
# validate_config — TwscrapeSearchCollector
# ---------------------------------------------------------------------------


class TestSearchValidateConfig:
    def test_missing_query_raises(self):
        with pytest.raises(CollectorError, match="query"):
            _search({}).validate_config()

    def test_defaults(self):
        cfg = _search({"query": "hello"}).validate_config()
        assert cfg["query"] == "hello"
        assert cfg["limit"] == 20
        assert cfg["product"] == "Latest"

    def test_invalid_product_raises(self):
        with pytest.raises(CollectorError, match="product"):
            _search({"query": "q", "product": "BadProduct"}).validate_config()

    def test_limit_out_of_range_raises(self):
        with pytest.raises(CollectorError, match="limit"):
            _search({"query": "q", "limit": 9999}).validate_config()

    def test_valid_product_top(self):
        cfg = _search({"query": "q", "product": "Top"}).validate_config()
        assert cfg["product"] == "Top"


# ---------------------------------------------------------------------------
# validate_config — TwscrapeUserTweetsCollector
# ---------------------------------------------------------------------------


class TestUserTweetsValidateConfig:
    def test_missing_username_raises(self):
        with pytest.raises(CollectorError, match="username"):
            _user_tweets({}).validate_config()

    def test_defaults(self):
        cfg = _user_tweets({"username": "alice"}).validate_config()
        assert cfg["username"] == "alice"
        assert cfg["limit"] == 50

    def test_limit_out_of_range_raises(self):
        with pytest.raises(CollectorError, match="limit"):
            _user_tweets({"username": "u", "limit": 9999}).validate_config()


# ---------------------------------------------------------------------------
# validate_config — TwscrapeTrendsCollector
# ---------------------------------------------------------------------------


class TestTrendsValidateConfig:
    def test_defaults_to_news(self):
        cfg = _trends({}).validate_config()
        assert cfg["category"] == "news"

    def test_invalid_category_raises(self):
        with pytest.raises(CollectorError, match="category"):
            _trends({"category": "badcat"}).validate_config()

    def test_valid_categories(self):
        for cat in ("news", "sport", "entertainment", "trending"):
            cfg = _trends({"category": cat}).validate_config()
            assert cfg["category"] == cat


# ---------------------------------------------------------------------------
# test() — twscrape not installed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_test_fails_when_twscrape_missing():
    with patch(
        "data_intelligence_hub.collectors.twscrape_collector._get_api",
        side_effect=CollectorError("twscrape not installed"),
    ):
        result = await _search({"query": "q"}).test()
    assert result.status == "failed"
    assert "twscrape" in result.message.lower()


@pytest.mark.asyncio
async def test_search_test_fails_no_accounts(monkeypatch):
    monkeypatch.delenv("TWITTER_ACCOUNTS_JSON", raising=False)
    monkeypatch.delenv("TWITTER_ACCOUNTS_FILE", raising=False)

    fake_api = MagicMock()
    with patch(
        "data_intelligence_hub.collectors.twscrape_collector._get_api",
        return_value=fake_api,
    ):
        result = await _search({"query": "q"}).test()
    assert result.status == "failed"
    assert "account" in result.message.lower()


@pytest.mark.asyncio
async def test_search_test_ok_with_accounts(monkeypatch):
    monkeypatch.setenv(
        "TWITTER_ACCOUNTS_JSON",
        json.dumps([{"username": "u1", "cookies": "auth_token=x"}]),
    )
    fake_api = MagicMock()
    with patch(
        "data_intelligence_hub.collectors.twscrape_collector._get_api",
        return_value=fake_api,
    ):
        result = await _search({"query": "q"}).test()
    assert result.status == "ok"


# ---------------------------------------------------------------------------
# collect() — TwscrapeSearchCollector
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_collect_no_accounts_returns_error(monkeypatch):
    monkeypatch.delenv("TWITTER_ACCOUNTS_JSON", raising=False)
    monkeypatch.delenv("TWITTER_ACCOUNTS_FILE", raising=False)

    with patch(
        "data_intelligence_hub.collectors.twscrape_collector._get_api",
        side_effect=CollectorError("twscrape not installed"),
    ):
        result = await _search({"query": "test"}).collect()

    assert result.raw_records == []
    assert len(result.errors) > 0


@pytest.mark.asyncio
async def test_search_collect_returns_tweet_records(monkeypatch):
    monkeypatch.setenv(
        "TWITTER_ACCOUNTS_JSON",
        json.dumps([{"username": "u1", "cookies": "auth_token=x"}]),
    )
    tweets = [_fake_tweet(i) for i in range(3)]
    fake_api = MagicMock()
    fake_api.pool = AsyncMock()
    fake_api.search = MagicMock()

    fake_twscrape = MagicMock()
    fake_twscrape.gather = AsyncMock(return_value=tweets)
    fake_twscrape.API = MagicMock(return_value=fake_api)

    with (
        patch(
            "data_intelligence_hub.collectors.twscrape_collector._get_api",
            return_value=fake_api,
        ),
        patch(
            "data_intelligence_hub.collectors.twscrape_collector._ensure_accounts",
            new_callable=AsyncMock,
        ),
        patch.dict("sys.modules", {"twscrape": fake_twscrape}),
    ):
        result = await _search({"query": "openai", "limit": 3}).collect()

    assert len(result.raw_records) == 3
    assert all(r.record_type == "post" for r in result.raw_records)


# ---------------------------------------------------------------------------
# collect() — TwscrapeUserTweetsCollector
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_tweets_collect_user_not_found_returns_error(monkeypatch):
    monkeypatch.setenv(
        "TWITTER_ACCOUNTS_JSON",
        json.dumps([{"username": "u1", "cookies": "auth_token=x"}]),
    )
    fake_api = AsyncMock()
    fake_api.pool = AsyncMock()
    fake_api.user_by_login = AsyncMock(return_value=None)

    fake_twscrape = MagicMock()
    fake_twscrape.API = MagicMock(return_value=fake_api)
    fake_twscrape.gather = AsyncMock(return_value=[])

    with (
        patch(
            "data_intelligence_hub.collectors.twscrape_collector._get_api",
            return_value=fake_api,
        ),
        patch(
            "data_intelligence_hub.collectors.twscrape_collector._ensure_accounts",
            new_callable=AsyncMock,
        ),
        patch.dict("sys.modules", {"twscrape": fake_twscrape}),
    ):
        with pytest.raises(CollectorError, match="User not found"):
            await _user_tweets({"username": "ghost_user"}).collect()


@pytest.mark.asyncio
async def test_user_tweets_collect_returns_records(monkeypatch):
    monkeypatch.setenv(
        "TWITTER_ACCOUNTS_JSON",
        json.dumps([{"username": "u1", "cookies": "auth_token=x"}]),
    )
    tweets = [_fake_tweet(i) for i in range(5)]
    fake_user = MagicMock()
    fake_user.id = 42

    fake_api = AsyncMock()
    fake_api.pool = AsyncMock()
    fake_api.user_by_login = AsyncMock(return_value=fake_user)
    fake_api.user_tweets = MagicMock(return_value=iter([]))

    fake_twscrape = MagicMock()
    fake_twscrape.API = MagicMock(return_value=fake_api)
    fake_twscrape.gather = AsyncMock(return_value=tweets)

    with (
        patch(
            "data_intelligence_hub.collectors.twscrape_collector._get_api",
            return_value=fake_api,
        ),
        patch(
            "data_intelligence_hub.collectors.twscrape_collector._ensure_accounts",
            new_callable=AsyncMock,
        ),
        patch.dict("sys.modules", {"twscrape": fake_twscrape}),
    ):
        result = await _user_tweets({"username": "alice", "limit": 5}).collect()

    assert len(result.raw_records) == 5
    assert all(r.record_type == "post" for r in result.raw_records)


# ---------------------------------------------------------------------------
# collect() — TwscrapeTrendsCollector
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trends_collect_returns_trend_record(monkeypatch):
    monkeypatch.setenv(
        "TWITTER_ACCOUNTS_JSON",
        json.dumps([{"username": "u1", "cookies": "auth_token=x"}]),
    )
    trends = [_fake_trend(name) for name in ["#AI", "#Python", "#OpenSource"]]

    fake_api = MagicMock()
    fake_api.pool = AsyncMock()
    fake_api.trends = MagicMock(return_value=iter([]))

    fake_twscrape = MagicMock()
    fake_twscrape.API = MagicMock(return_value=fake_api)
    fake_twscrape.gather = AsyncMock(return_value=trends)

    with (
        patch(
            "data_intelligence_hub.collectors.twscrape_collector._get_api",
            return_value=fake_api,
        ),
        patch(
            "data_intelligence_hub.collectors.twscrape_collector._ensure_accounts",
            new_callable=AsyncMock,
        ),
        patch.dict("sys.modules", {"twscrape": fake_twscrape}),
    ):
        result = await _trends({"category": "news"}).collect()

    assert len(result.raw_records) == 1
    rec = result.raw_records[0]
    assert rec.record_type == "trend"
    content = rec.content
    assert content["category"] == "news"
    assert content["total"] == 3
    names = [t["name"] for t in content["trends"]]
    assert "#AI" in names
    assert "#Python" in names
