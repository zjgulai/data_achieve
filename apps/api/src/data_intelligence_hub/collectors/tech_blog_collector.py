"""Tech blog collectors: Dev.to, 掘金 (Juejin), and Substack.

All use public APIs or RSS feeds — no new Python dependencies required.
Everything runs on the existing httpx client already in the container.

Environment variables:
    HTTP_PROXY   Forwarded to httpx (optional)
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
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
    require_text,
)

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)
_TIMEOUT = 30.0


def _get_proxy() -> str | None:
    import os
    return os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY") or None


def _client(accept: str = "application/json") -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=_TIMEOUT,
        proxy=_get_proxy(),
        headers={"User-Agent": _UA, "Accept": accept},
        follow_redirects=True,
    )


def _text(el: ET.Element | None, tag: str) -> str:
    if el is None:
        return ""
    child = el.find(tag)
    return (child.text or "").strip() if child is not None and child.text else ""


class DevToArticlesCollector(BaseCollector):
    """Search published articles on Dev.to using the public REST API."""

    collector_type = "devto_articles"

    def validate_config(self) -> dict[str, Any]:
        tag = self.config.get("tag", "").strip()
        username = self.config.get("username", "").strip()
        keyword = self.config.get("keyword", "").strip()
        if not any([tag, username, keyword]):
            raise CollectorError(
                "Provide at least one of: tag, username, or keyword"
            )
        max_items = int(self.config.get("max_items", 20))
        if max_items < 1 or max_items > 100:
            raise CollectorError("max_items must be between 1 and 100")
        return {
            "tag": tag, "username": username,
            "keyword": keyword, "max_items": max_items,
        }

    async def test(self) -> CollectorTestResult:
        try:
            async with _client() as c:
                r = await c.get("https://dev.to/api/articles?per_page=1")
            if r.status_code != 200:
                msg = f"Dev.to API returned HTTP {r.status_code}"
                return CollectorTestResult(
                    status="failed", message=msg,
                    logs=[collector_log("devto_test_failed", msg, level="error")],
                )
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            return CollectorTestResult(
                status="failed", message=msg,
                logs=[collector_log("devto_test_failed", msg, level="error")],
            )
        return CollectorTestResult(
            status="ok", message="Dev.to API reachable",
            logs=[collector_log("devto_test_ok", "api reachable")],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        params: dict[str, Any] = {"per_page": config["max_items"]}
        if config["tag"]:
            params["tag"] = config["tag"]
        if config["username"]:
            params["username"] = config["username"]
        if config["keyword"]:
            params["search"] = config["keyword"]

        try:
            async with _client() as c:
                r = await c.get("https://dev.to/api/articles", params=params)
                r.raise_for_status()
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("devto_collect_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        articles: list[dict[str, Any]] = r.json() if isinstance(r.json(), list) else []
        records = [
            CollectorRawRecord(
                record_type="news",
                source_url=a.get("url") or a.get("canonical_url"),
                content={
                    "id": a.get("id"),
                    "title": a.get("title", ""),
                    "url": a.get("url") or a.get("canonical_url"),
                    "description": a.get("description", ""),
                    "tags": a.get("tag_list", []),
                    "author": a.get("user", {}).get("username", ""),
                    "published_at": a.get("published_at", ""),
                    "reactions_count": a.get("positive_reactions_count", 0),
                    "comments_count": a.get("comments_count", 0),
                    "reading_time_minutes": a.get("reading_time_minutes", 0),
                },
                collected_at=collected_at,
            )
            for a in articles[: config["max_items"]]
        ]
        logs.append(
            collector_log("devto_collected", f"count={len(records)}")
        )
        return CollectionResult(raw_records=records, logs=logs, errors=errors)


class JuejinArticlesCollector(BaseCollector):
    """Search articles on 掘金 (Juejin) using the public API."""

    collector_type = "juejin_articles"

    _CATE_MAP = {
        "frontend": "6809637767543259144",
        "backend": "6809637769959178254",
        "android": "6809635626879549454",
        "ios": "6809635629687816200",
        "ai": "6809637773935640594",
        "devops": "6809637774304781320",
        "": "",
    }

    def validate_config(self) -> dict[str, Any]:
        keyword = require_text(self.config, "keyword")
        max_items = int(self.config.get("max_items", 20))
        if max_items < 1 or max_items > 100:
            raise CollectorError("max_items must be between 1 and 100")
        category = self.config.get("category", "").strip().lower()
        return {"keyword": keyword, "max_items": max_items, "category": category}

    async def test(self) -> CollectorTestResult:
        return CollectorTestResult(
            status="ok", message="Juejin collector ready (httpx only)",
            logs=[collector_log("juejin_test_ok", "ready")],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        payload: dict[str, Any] = {
            "key_word": config["keyword"],
            "search_type": 0,
        }

        try:
            async with _client("application/json") as c:
                r = await c.post(
                    "https://api.juejin.cn/search_api/v1/search",
                    json=payload,
                    headers={
                        "User-Agent": _UA,
                        "Content-Type": "application/json",
                        "Referer": "https://juejin.cn/",
                    },
                )
                r.raise_for_status()
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("juejin_collect_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        body = r.json()
        raw_list: list[dict[str, Any]] = []
        if isinstance(body, dict):
            data = body.get("data") or []
            raw_list = data if isinstance(data, list) else []

        records = []
        for item in raw_list[: config["max_items"]]:
            info = item.get("result_model") or item
            article_info = info.get("article_info") or info
            author_info = info.get("author_user_info") or {}
            record = CollectorRawRecord(
                record_type="news",
                source_url=(
                    f"https://juejin.cn/post/{article_info.get('article_id', '')}"
                    if article_info.get("article_id")
                    else None
                ),
                content={
                    "article_id": article_info.get("article_id", ""),
                    "title": article_info.get("title", ""),
                    "brief_content": article_info.get("brief_content", ""),
                    "url": (
                        f"https://juejin.cn/post/{article_info.get('article_id', '')}"
                    ),
                    "tags": info.get("tags", []),
                    "author": author_info.get("user_name", ""),
                    "view_count": article_info.get("view_count", 0),
                    "collect_count": article_info.get("collect_count", 0),
                    "comment_count": article_info.get("comment_count", 0),
                    "digg_count": article_info.get("digg_count", 0),
                    "publish_time": article_info.get("rtime", 0),
                },
                collected_at=collected_at,
            )
            records.append(record)

        logs.append(
            collector_log(
                "juejin_collected",
                f"keyword={config['keyword']!r} count={len(records)}",
            )
        )
        return CollectionResult(raw_records=records, logs=logs, errors=errors)


class SubstackPostsCollector(BaseCollector):
    """Collect recent posts from a Substack publication via its public RSS feed."""

    collector_type = "substack_posts"

    def validate_config(self) -> dict[str, Any]:
        publication = require_text(self.config, "publication")
        publication = (
            publication.strip().lower()
            .replace("https://", "").replace("/", "").replace(".substack.com", "")
        )
        max_items = int(self.config.get("max_items", 20))
        if max_items < 1 or max_items > 100:
            raise CollectorError("max_items must be between 1 and 100")
        return {"publication": publication, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        return CollectorTestResult(
            status="ok", message="Substack RSS collector ready",
            logs=[collector_log("substack_test_ok", "ready")],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        feed_url = f"https://{config['publication']}.substack.com/feed"

        try:
            async with _client("application/rss+xml, application/xml, text/xml") as c:
                r = await c.get(feed_url)
                r.raise_for_status()
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("substack_collect_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        try:
            root = ET.fromstring(r.text)
        except ET.ParseError as exc:
            msg = f"substack_rss_parse_error: {exc}"
            errors.append(msg)
            logs.append(collector_log("substack_collect_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        channel = root.find("channel")
        if channel is None:
            errors.append("substack_rss_no_channel")
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        items = channel.findall("item")[: config["max_items"]]
        records = []
        for item in items:
            link = _text(item, "link")
            records.append(
                CollectorRawRecord(
                    record_type="news",
                    source_url=link or None,
                    content={
                        "title": _text(item, "title"),
                        "url": link,
                        "description": _text(item, "description"),
                        "author": _text(item, "author") or _text(item, "{http://purl.org/dc/elements/1.1/}creator"),
                        "pub_date": _text(item, "pubDate"),
                        "guid": _text(item, "guid"),
                        "publication": config["publication"],
                    },
                    collected_at=collected_at,
                )
            )

        logs.append(
            collector_log(
                "substack_collected",
                f"publication={config['publication']!r} count={len(records)}",
            )
        )
        return CollectionResult(raw_records=records, logs=logs, errors=errors)
