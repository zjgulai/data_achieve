"""BestBlogs content collector — LLM-scored tech article discovery.

BestBlogs.dev aggregates programming, AI, and product articles from
400+ RSS sources and applies LLM-based 6-dimensional quality scoring.

Endpoint used: GET https://api.bestblogs.dev/openapi/v2/discover/feeds
Authentication: X-API-KEY header (required — set BESTBLOGS_API_KEY)

Environment variables:
    BESTBLOGS_API_KEY   API key from bestblogs.dev/settings
    HTTP_PROXY          Optional proxy forwarded to httpx
"""
from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import httpx

from data_intelligence_hub.collectors.base import (
    BaseCollector,
    CollectionResult,
    CollectorError,
    CollectorRawRecord,
    CollectorTestResult,
    collector_http_error_message,
    collector_log,
)

_BASE = "https://api.bestblogs.dev/openapi/v2"
_VALID_CATEGORIES = {"programming", "ai", "product", "devops", "design", "security"}
_VALID_LANGS = {"zh", "en", "all"}


def _api_key() -> str:
    key = os.environ.get("BESTBLOGS_API_KEY", "").strip()
    if not key:
        raise CollectorError("BESTBLOGS_API_KEY is not set — get one at bestblogs.dev/settings")
    return key


def _client() -> httpx.AsyncClient:
    proxy = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
    key = _api_key()
    return httpx.AsyncClient(
        timeout=30.0,
        proxy=proxy or None,
        headers={"X-API-KEY": key, "Accept": "application/json"},
        follow_redirects=True,
    )


class BestBlogsArticlesCollector(BaseCollector):
    collector_type = "bestblogs_articles"

    def validate_config(self) -> dict[str, Any]:
        category = self.config.get("category", "").strip().lower()
        if category and category not in _VALID_CATEGORIES:
            raise CollectorError(
                f"category must be one of {sorted(_VALID_CATEGORIES)} or empty"
            )
        lang = self.config.get("lang", "all").strip().lower()
        if lang not in _VALID_LANGS:
            raise CollectorError(f"lang must be one of {sorted(_VALID_LANGS)}")
        min_score = int(self.config.get("min_score", 70))
        if not (0 <= min_score <= 100):
            raise CollectorError("min_score must be between 0 and 100")
        limit = int(self.config.get("limit", 20))
        if not (1 <= limit <= 100):
            raise CollectorError("limit must be between 1 and 100")
        return {
            "category": category,
            "lang": lang,
            "min_score": min_score,
            "limit": limit,
        }

    async def test(self) -> CollectorTestResult:
        try:
            _api_key()
        except CollectorError as exc:
            return CollectorTestResult(
                status="failed", message=str(exc),
                logs=[collector_log("bestblogs_test_failed", str(exc), level="error")],
            )
        try:
            async with _client() as c:
                r = await c.get(f"{_BASE}/discover/feeds", params={"limit": 1})
            if r.status_code not in {200, 204}:
                msg = f"BestBlogs API returned HTTP {r.status_code}"
                return CollectorTestResult(
                    status="failed", message=msg,
                    logs=[collector_log("bestblogs_test_failed", msg, level="error")],
                )
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            return CollectorTestResult(
                status="failed", message=msg,
                logs=[collector_log("bestblogs_test_failed", msg, level="error")],
            )
        return CollectorTestResult(
            status="ok", message="BestBlogs API reachable",
            logs=[collector_log("bestblogs_test_ok", "api reachable")],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        params: dict[str, Any] = {"limit": config["limit"]}
        if config["category"]:
            params["category"] = config["category"]
        if config["lang"] != "all":
            params["lang"] = config["lang"]
        if config["min_score"] > 0:
            params["minScore"] = config["min_score"]

        try:
            async with _client() as c:
                r = await c.get(f"{_BASE}/discover/feeds", params=params)
                r.raise_for_status()
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("bestblogs_collect_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        body = r.json()
        items: list[dict[str, Any]] = []
        if isinstance(body, list):
            items = body
        elif isinstance(body, dict):
            items = body.get("data") or body.get("items") or body.get("articles") or []

        records = [
            CollectorRawRecord(
                record_type="news",
                source_url=a.get("url") or a.get("link"),
                content={
                    "title": a.get("title", ""),
                    "url": a.get("url") or a.get("link", ""),
                    "summary": a.get("summary") or a.get("description", ""),
                    "score": a.get("score"),
                    "scores": a.get("scores"),
                    "category": a.get("category", ""),
                    "lang": a.get("lang", ""),
                    "author": a.get("author", ""),
                    "published_at": a.get("publishedAt") or a.get("published_at", ""),
                    "source": a.get("source") or a.get("feed", ""),
                    "tags": a.get("tags", []),
                    "key_points": a.get("keyPoints") or a.get("key_points", []),
                },
                collected_at=collected_at,
            )
            for a in items
        ]
        logs.append(
            collector_log(
                "bestblogs_collected",
                f"category={config['category'] or 'all'} count={len(records)}",
            )
        )
        return CollectionResult(raw_records=records, logs=logs, errors=errors)
