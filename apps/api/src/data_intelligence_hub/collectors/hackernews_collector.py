"""Hacker News API collectors - completely free, no API key required.

API docs: https://github.com/HackerNews/API
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from .base import (
    BaseCollector,
    CollectionResult,
    CollectorError,
    CollectorRawRecord,
    CollectorTestResult,
    collector_get_with_retry,
    collector_http_error_message,
    collector_log,
    require_text,
)

HN_API_BASE = "https://hacker-news.firebaseio.com/v0"


class HackerNewsFrontPageCollector(BaseCollector):
    """Collect top stories from Hacker News front page."""

    collector_type = "hackernews_front_page"

    def validate_config(self) -> dict[str, Any]:
        max_items = self.config.get("max_items", 30)
        if not isinstance(max_items, int) or max_items < 1 or max_items > 500:
            raise CollectorError("max_items must be between 1 and 500")
        return {"max_items": max_items}

    async def test(self) -> CollectorTestResult:
        logs = []
        try:
            async with httpx.AsyncClient() as client:
                response = await collector_get_with_retry(client, f"{HN_API_BASE}/topstories.json")
                story_ids = response.json()[:5]
                logs.append(collector_log("test", f"fetched {len(story_ids)} story IDs"))
                return CollectorTestResult(
                    status="ok",
                    message=f"Hacker News API reachable, {len(story_ids)} stories available",
                    logs=logs,
                )
        except httpx.HTTPError as exc:
            logs.append(collector_log("test_failed", collector_http_error_message(exc), "error"))
            return CollectorTestResult(status="failed", message=str(exc), logs=logs)

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        max_items = config["max_items"]
        logs = []
        errors = []
        raw_records = []

        try:
            async with httpx.AsyncClient() as client:
                response = await collector_get_with_retry(client, f"{HN_API_BASE}/topstories.json")
                story_ids = response.json()[:max_items]
                logs.append(collector_log("fetch_ids", f"fetched {len(story_ids)} story IDs"))

                # Fetch stories in parallel batches of 20
                for i in range(0, len(story_ids), 20):
                    batch = story_ids[i : i + 20]
                    tasks = [self._fetch_story(client, story_id) for story_id in batch]
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    for story_id, result in zip(batch, results):
                        if isinstance(result, Exception):
                            errors.append(f"story {story_id}: {result}")
                        elif result:
                            raw_records.append(result)

                logs.append(collector_log("collect_done", f"collected {len(raw_records)} stories"))
        except httpx.HTTPError as exc:
            error_msg = collector_http_error_message(exc)
            errors.append(error_msg)
            logs.append(collector_log("collect_failed", error_msg, "error"))

        return CollectionResult(raw_records=raw_records, logs=logs, errors=errors)

    async def _fetch_story(self, client: httpx.AsyncClient, story_id: int) -> CollectorRawRecord | None:
        try:
            response = await collector_get_with_retry(client, f"{HN_API_BASE}/item/{story_id}.json")
            data = response.json()
            if not data or data.get("type") not in ["story", "job", "poll"]:
                return None
            url = data.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
            return CollectorRawRecord(
                record_type="post",
                source_url=url,
                content=data,
            )
        except httpx.HTTPError:
            return None


class HackerNewsSearchCollector(BaseCollector):
    """Search Hacker News stories."""

    collector_type = "hackernews_search"

    def validate_config(self) -> dict[str, Any]:
        query = require_text(self.config, "query")
        max_items = self.config.get("max_items", 30)
        if not isinstance(max_items, int) or max_items < 1 or max_items > 500:
            raise CollectorError("max_items must be between 1 and 500")
        return {"query": query, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        logs = []
        try:
            async with httpx.AsyncClient() as client:
                url = "https://hn.algolia.com/api/v1/search"
                response = await collector_get_with_retry(client, url, params={"query": "openai", "hitsPerPage": "3"})
                data = response.json()
                hits = data.get("hits", [])
                logs.append(collector_log("test", f"search returned {len(hits)} results"))
                return CollectorTestResult(
                    status="ok",
                    message=f"Hacker News search API reachable, {len(hits)} results",
                    logs=logs,
                )
        except httpx.HTTPError as exc:
            logs.append(collector_log("test_failed", collector_http_error_message(exc), "error"))
            return CollectorTestResult(status="failed", message=str(exc), logs=logs)

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        query = config["query"]
        max_items = config["max_items"]
        logs = []
        errors = []
        raw_records = []

        try:
            async with httpx.AsyncClient() as client:
                url = "https://hn.algolia.com/api/v1/search"
                response = await collector_get_with_retry(
                    client, url, params={"query": query, "hitsPerPage": str(max_items)}
                )
                data = response.json()
                hits = data.get("hits", [])
                logs.append(collector_log("search", f"found {len(hits)} results"))

                for hit in hits:
                    object_id = hit.get("objectID")
                    url = hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}"
                    raw_records.append(
                        CollectorRawRecord(
                            record_type="post",
                            source_url=url,
                            content=hit,
                        )
                    )

                logs.append(collector_log("collect_done", f"collected {len(raw_records)} stories"))
        except httpx.HTTPError as exc:
            error_msg = collector_http_error_message(exc)
            errors.append(error_msg)
            logs.append(collector_log("collect_failed", error_msg, "error"))

        return CollectionResult(raw_records=raw_records, logs=logs, errors=errors)


class HackerNewsUserCollector(BaseCollector):
    """Collect a Hacker News user's submissions."""

    collector_type = "hackernews_user"

    def validate_config(self) -> dict[str, Any]:
        username = require_text(self.config, "username")
        max_items = self.config.get("max_items", 30)
        if not isinstance(max_items, int) or max_items < 1 or max_items > 500:
            raise CollectorError("max_items must be between 1 and 500")
        return {"username": username, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        logs = []
        try:
            async with httpx.AsyncClient() as client:
                response = await collector_get_with_retry(client, f"{HN_API_BASE}/user/pg.json")
                data = response.json()
                logs.append(collector_log("test", f"user has {len(data.get('submitted', []))} submissions"))
                return CollectorTestResult(status="ok", message="Hacker News API reachable", logs=logs)
        except httpx.HTTPError as exc:
            logs.append(collector_log("test_failed", collector_http_error_message(exc), "error"))
            return CollectorTestResult(status="failed", message=str(exc), logs=logs)

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        username = config["username"]
        max_items = config["max_items"]
        logs = []
        errors = []
        raw_records = []

        try:
            async with httpx.AsyncClient() as client:
                response = await collector_get_with_retry(client, f"{HN_API_BASE}/user/{username}.json")
                user_data = response.json()
                submitted = user_data.get("submitted", [])[:max_items]
                logs.append(collector_log("fetch_user", f"user has {len(submitted)} submissions"))

                # Fetch items in parallel batches
                for i in range(0, len(submitted), 20):
                    batch = submitted[i : i + 20]
                    tasks = [self._fetch_item(client, item_id) for item_id in batch]
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    for item_id, result in zip(batch, results):
                        if isinstance(result, Exception):
                            errors.append(f"item {item_id}: {result}")
                        elif result:
                            raw_records.append(result)

                logs.append(collector_log("collect_done", f"collected {len(raw_records)} items"))
        except httpx.HTTPError as exc:
            error_msg = collector_http_error_message(exc)
            errors.append(error_msg)
            logs.append(collector_log("collect_failed", error_msg, "error"))

        return CollectionResult(raw_records=raw_records, logs=logs, errors=errors)

    async def _fetch_item(self, client: httpx.AsyncClient, item_id: int) -> CollectorRawRecord | None:
        try:
            response = await collector_get_with_retry(client, f"{HN_API_BASE}/item/{item_id}.json")
            data = response.json()
            if not data:
                return None
            url = data.get("url") or f"https://news.ycombinator.com/item?id={item_id}"
            return CollectorRawRecord(
                record_type="post",
                source_url=url,
                content=data,
            )
        except httpx.HTTPError:
            return None
