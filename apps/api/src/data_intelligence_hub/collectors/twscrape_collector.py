"""X/Twitter collector backed by twscrape (multi-account, rate-limit aware).

Requires accounts to be provisioned via the TWITTER_ACCOUNTS_JSON env var:
    [{"username": "...", "cookies": "auth_token=xxx; ct0=yyy"}, ...]

or via TWITTER_ACCOUNTS_FILE pointing to a JSON file with the same schema.

Environment variables:
    TWITTER_ACCOUNTS_JSON   JSON string of account list (priority)
    TWITTER_ACCOUNTS_FILE   Path to JSON file of account list
    TWITTER_DB_PATH         SQLite path for twscrape session store
                            (default: /tmp/twscrape.db)
    HTTP_PROXY              Optional proxy forwarded to twscrape
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

from data_intelligence_hub.collectors.base import (
    BaseCollector,
    CollectionResult,
    CollectorError,
    CollectorRawRecord,
    CollectorTestResult,
    collector_log,
    require_text,
)

_DB_PATH = os.environ.get("TWITTER_DB_PATH", "/tmp/twscrape.db")
_VALID_PRODUCTS = {"Latest", "Top", "Media"}
_VALID_TREND_CATS = {"news", "sport", "entertainment", "trending"}


def _load_accounts() -> list[dict[str, str]]:
    raw = os.environ.get("TWITTER_ACCOUNTS_JSON", "").strip()
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError as exc:
            raise CollectorError(
                f"TWITTER_ACCOUNTS_JSON is not valid JSON: {exc}"
            ) from exc

    fpath = os.environ.get("TWITTER_ACCOUNTS_FILE", "").strip()
    if fpath and os.path.exists(fpath):
        with open(fpath, encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, list):
                return data

    return []


def _get_api() -> Any:
    """Lazily import twscrape and return a configured API instance."""
    try:
        from twscrape import API  # type: ignore[import-untyped]
    except ImportError as exc:
        raise CollectorError(
            "twscrape not installed — add it to pyproject.toml dependencies"
        ) from exc

    proxy = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
    api = API(pool=_DB_PATH, proxy=proxy or None)
    return api


async def _ensure_accounts(api: Any) -> None:
    accounts = _load_accounts()
    if not accounts:
        raise CollectorError(
            "No Twitter accounts configured — set TWITTER_ACCOUNTS_JSON or "
            "TWITTER_ACCOUNTS_FILE with at least one {username, cookies} entry"
        )
    for acc in accounts:
        username = acc.get("username", "")
        cookies = acc.get("cookies", "")
        if username and cookies:
            await api.pool.add_account_cookies(username, cookies)


def _tweet_to_dict(tweet: Any) -> dict[str, Any]:
    return {
        "id": str(tweet.id),
        "url": tweet.url if hasattr(tweet, "url") else None,
        "content": tweet.rawContent if hasattr(tweet, "rawContent") else "",
        "author": tweet.user.username if hasattr(tweet, "user") and tweet.user else None,
        "author_id": str(tweet.user.id) if hasattr(tweet, "user") and tweet.user else None,
        "reply_count": tweet.replyCount if hasattr(tweet, "replyCount") else 0,
        "retweet_count": tweet.retweetCount if hasattr(tweet, "retweetCount") else 0,
        "like_count": tweet.likeCount if hasattr(tweet, "likeCount") else 0,
        "view_count": tweet.viewCount if hasattr(tweet, "viewCount") else None,
        "created_at": tweet.date.isoformat() if hasattr(tweet, "date") and tweet.date else None,
        "lang": tweet.lang if hasattr(tweet, "lang") else None,
        "is_retweet": tweet.retweetedTweet is not None
        if hasattr(tweet, "retweetedTweet")
        else False,
    }


def _user_to_dict(user: Any) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "username": user.username if hasattr(user, "username") else "",
        "display_name": user.displayname if hasattr(user, "displayname") else "",
        "followers": user.followersCount if hasattr(user, "followersCount") else 0,
        "following": user.followingCount if hasattr(user, "followingCount") else 0,
        "tweets": user.statusesCount if hasattr(user, "statusesCount") else 0,
        "verified": user.verified if hasattr(user, "verified") else False,
        "bio": user.rawDescription if hasattr(user, "rawDescription") else "",
        "url": f"https://x.com/{user.username}" if hasattr(user, "username") else None,
        "created_at": user.created.isoformat()
        if hasattr(user, "created") and user.created
        else None,
    }


# ─────────────────────────────────────────────
#  TwscrapeSearchCollector
# ─────────────────────────────────────────────

class TwscrapeSearchCollector(BaseCollector):
    """Search X/Twitter for tweets matching a query."""

    collector_type = "twscrape_search"

    def validate_config(self) -> dict[str, Any]:
        query = require_text(self.config, "query")
        limit = int(self.config.get("limit", 20))
        product = self.config.get("product", "Latest")
        if product not in _VALID_PRODUCTS:
            raise CollectorError(f"product must be one of {sorted(_VALID_PRODUCTS)}")
        if limit < 1 or limit > 1000:
            raise CollectorError("limit must be between 1 and 1000")
        return {"query": query, "limit": limit, "product": product}

    async def test(self) -> CollectorTestResult:
        try:
            _get_api()
        except CollectorError as exc:
            return CollectorTestResult(
                status="failed",
                message=str(exc),
                logs=[collector_log("twscrape_test_failed", str(exc), level="error")],
            )
        accounts = _load_accounts()
        if not accounts:
            msg = "No Twitter accounts configured"
            return CollectorTestResult(
                status="failed",
                message=msg,
                logs=[collector_log("twscrape_test_failed", msg, level="error")],
            )
        return CollectorTestResult(
            status="ok",
            message=f"twscrape ready, {len(accounts)} account(s) configured",
            logs=[collector_log("twscrape_test_ok", f"accounts={len(accounts)}")],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []

        try:
            from twscrape import gather  # type: ignore[import-untyped]
            api = _get_api()
            await _ensure_accounts(api)
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("twscrape_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        collected_at = datetime.now(UTC)
        try:
            tweets = await gather(
                api.search(
                    config["query"],
                    limit=config["limit"],
                    kv={"product": config["product"]},
                )
            )
        except Exception as exc:  # noqa: BLE001
            msg = f"twscrape search failed: {exc}"
            errors.append(msg)
            logs.append(collector_log("twscrape_collect_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        records = [
            CollectorRawRecord(
                record_type="post",
                source_url=t.url if hasattr(t, "url") else None,
                content=_tweet_to_dict(t),
                collected_at=collected_at,
            )
            for t in tweets
        ]
        logs.append(
            collector_log(
                "twscrape_search_collected",
                f"query={config['query']!r} count={len(records)}",
            )
        )
        return CollectionResult(raw_records=records, logs=logs, errors=errors)


# ─────────────────────────────────────────────
#  TwscrapeUserTweetsCollector
# ─────────────────────────────────────────────

class TwscrapeUserTweetsCollector(BaseCollector):
    """Fetch the public timeline of an X/Twitter user."""

    collector_type = "twscrape_user_tweets"

    def validate_config(self) -> dict[str, Any]:
        username = require_text(self.config, "username")
        limit = int(self.config.get("limit", 50))
        if limit < 1 or limit > 3200:
            raise CollectorError("limit must be between 1 and 3200")
        return {"username": username, "limit": limit}

    async def test(self) -> CollectorTestResult:
        try:
            _get_api()
        except CollectorError as exc:
            return CollectorTestResult(
                status="failed",
                message=str(exc),
                logs=[collector_log("twscrape_test_failed", str(exc), level="error")],
            )
        accounts = _load_accounts()
        if not accounts:
            msg = "No Twitter accounts configured"
            return CollectorTestResult(
                status="failed",
                message=msg,
                logs=[collector_log("twscrape_test_failed", msg, level="error")],
            )
        return CollectorTestResult(
            status="ok",
            message=f"twscrape ready, {len(accounts)} account(s) configured",
            logs=[collector_log("twscrape_test_ok", f"accounts={len(accounts)}")],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []

        try:
            from twscrape import gather  # type: ignore[import-untyped]
            api = _get_api()
            await _ensure_accounts(api)
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("twscrape_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        collected_at = datetime.now(UTC)
        username = config["username"]

        try:
            user = await api.user_by_login(username)
            if user is None:
                raise CollectorError(f"User not found: {username!r}")
            tweets = await gather(api.user_tweets(user.id, limit=config["limit"]))
        except CollectorError:
            raise
        except Exception as exc:  # noqa: BLE001
            msg = f"twscrape user_tweets failed: {exc}"
            errors.append(msg)
            logs.append(collector_log("twscrape_collect_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        records = [
            CollectorRawRecord(
                record_type="post",
                source_url=t.url if hasattr(t, "url") else None,
                content=_tweet_to_dict(t),
                collected_at=collected_at,
            )
            for t in tweets
        ]
        logs.append(
            collector_log(
                "twscrape_user_tweets_collected",
                f"username={username!r} count={len(records)}",
            )
        )
        return CollectionResult(raw_records=records, logs=logs, errors=errors)


# ─────────────────────────────────────────────
#  TwscrapeTrendsCollector
# ─────────────────────────────────────────────

class TwscrapeTrendsCollector(BaseCollector):
    """Fetch X/Twitter trending topics for a given category."""

    collector_type = "twscrape_trends"

    def validate_config(self) -> dict[str, Any]:
        category = self.config.get("category", "news")
        if category not in _VALID_TREND_CATS:
            raise CollectorError(
                f"category must be one of {sorted(_VALID_TREND_CATS)}"
            )
        return {"category": category}

    async def test(self) -> CollectorTestResult:
        try:
            _get_api()
        except CollectorError as exc:
            return CollectorTestResult(
                status="failed",
                message=str(exc),
                logs=[collector_log("twscrape_test_failed", str(exc), level="error")],
            )
        return CollectorTestResult(
            status="ok",
            message="twscrape trends endpoint ready",
            logs=[collector_log("twscrape_test_ok", "ok")],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []

        try:
            from twscrape import gather  # type: ignore[import-untyped]
            api = _get_api()
            await _ensure_accounts(api)
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("twscrape_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        collected_at = datetime.now(UTC)
        category = config["category"]

        try:
            trends = await gather(api.trends(category))
        except Exception as exc:  # noqa: BLE001
            msg = f"twscrape trends failed: {exc}"
            errors.append(msg)
            logs.append(collector_log("twscrape_collect_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        trend_list = [
            {
                "name": t.name if hasattr(t, "name") else str(t),
                "tweet_count": t.tweetCount if hasattr(t, "tweetCount") else None,
                "url": t.url if hasattr(t, "url") else None,
            }
            for t in trends
        ]

        record = CollectorRawRecord(
            record_type="trend",
            source_url=f"https://x.com/explore/tabs/{category}",
            content={
                "category": category,
                "trends": trend_list,
                "total": len(trend_list),
            },
            collected_at=collected_at,
        )
        logs.append(
            collector_log(
                "twscrape_trends_collected",
                f"category={category!r} count={len(trend_list)}",
            )
        )
        return CollectionResult(raw_records=[record], logs=logs, errors=errors)
