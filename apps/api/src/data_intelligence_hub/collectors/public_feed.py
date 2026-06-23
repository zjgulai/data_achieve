from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree

import httpx

from data_intelligence_hub.collectors.base import (
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
from data_intelligence_hub.collectors.generic_web import _assert_public_http_url

MAX_FEED_ITEMS = 100


@dataclass(frozen=True)
class ParsedFeed:
    feed_type: str
    title: str | None
    site_url: str | None
    description: str | None
    entries: list[dict[str, Any]]


class PublicFeedCollector(BaseCollector):
    collector_type = "public_feed"

    def validate_config(self) -> dict[str, Any]:
        url = require_text(self.config, "url")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise CollectorError("url must be an absolute HTTP or HTTPS URL")
        feed_type = self.config.get("feed_type", "auto")
        if feed_type not in {"auto", "rss", "atom"}:
            raise CollectorError("feed_type must be auto, rss, or atom")
        max_items = self.config.get("max_items", 20)
        if not isinstance(max_items, int) or max_items < 1 or max_items > MAX_FEED_ITEMS:
            raise CollectorError(f"max_items must be an integer between 1 and {MAX_FEED_ITEMS}")
        return {"url": url, "feed_type": feed_type, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        config = self.validate_config()
        xml_text = await self._get_xml(config["url"])
        parsed = parse_public_feed(xml_text, config["feed_type"], config["max_items"])
        if not parsed.entries:
            raise CollectorError("public_feed_empty: feed contains no entries")
        return CollectorTestResult(
            status="ok",
            message=f"Public feed parsed with {len(parsed.entries)} entries.",
            logs=[collector_log("public_feed_tested", "Public feed responded and parsed.")],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        xml_text = await self._get_xml(config["url"])
        parsed = parse_public_feed(xml_text, config["feed_type"], config["max_items"])
        if not parsed.entries:
            raise CollectorError("public_feed_empty: feed contains no entries")
        content: dict[str, Any] = {
            "provider": "public_feed",
            "kind": "feed_snapshot",
            "schema_version": "public_feed.v1",
            "feed_url": config["url"],
            "feed_type": parsed.feed_type,
            "title": parsed.title,
            "site_url": parsed.site_url,
            "description": parsed.description,
            "item_count": len(parsed.entries),
            "max_items": config["max_items"],
            "entries": parsed.entries,
            "feed_content_hash": _hash_text(xml_text),
            "provenance": {
                "endpoint_origin": config["url"],
                "parser": "xml.etree.ElementTree",
                "public_url_checked": True,
            },
        }
        return CollectionResult(
            raw_records=[
                CollectorRawRecord(
                    record_type=self.collector_type,
                    source_url=config["url"],
                    content=content,
                )
            ],
            logs=[
                collector_log(
                    "public_feed_collected",
                    f"Collected {len(parsed.entries)} public feed entries from {config['url']}.",
                )
            ],
            errors=[],
        )

    async def _get_xml(self, url: str) -> str:
        await _assert_public_http_url(url)
        if self.http_client is not None:
            return await _fetch_xml(self.http_client, url)
        async with httpx.AsyncClient() as client:
            return await _fetch_xml(client, url)


async def _fetch_xml(client: httpx.AsyncClient, url: str) -> str:
    try:
        response = await collector_get_with_retry(client, url)
    except httpx.HTTPError as exc:
        raise CollectorError(collector_http_error_message(exc)) from exc
    return response.text


def parse_public_feed(
    xml_text: str,
    expected_feed_type: str = "auto",
    max_items: int = 20,
) -> ParsedFeed:
    try:
        root = ElementTree.fromstring(xml_text.strip())
    except ElementTree.ParseError as exc:
        raise CollectorError("public_feed_invalid_xml") from exc
    root_name = _local_name(root.tag)
    if root_name in {"rss", "rdf"}:
        if expected_feed_type not in {"auto", "rss"}:
            raise CollectorError("public_feed_type_mismatch")
        return _parse_rss_feed(root, max_items)
    if root_name == "feed":
        if expected_feed_type not in {"auto", "atom"}:
            raise CollectorError("public_feed_type_mismatch")
        return _parse_atom_feed(root, max_items)
    raise CollectorError("public_feed_unsupported_format")


def _parse_rss_feed(root: ElementTree.Element, max_items: int) -> ParsedFeed:
    channel_element = _first_child(root, "channel")
    channel = channel_element if channel_element is not None else root
    title = _child_text(channel, "title")
    site_url = _child_text(channel, "link")
    description = _child_text(channel, "description")
    entries: list[dict[str, Any]] = []
    for item in _children(channel, "item")[:max_items]:
        title_text = _child_text(item, "title")
        link = _child_text(item, "link") or _child_text(item, "guid")
        published_at = _child_text(item, "pubDate") or _child_text(item, "date")
        summary = _child_text(item, "description") or _child_text(item, "encoded")
        author = _child_text(item, "author") or _child_text(item, "creator")
        tags = [
            cleaned
            for child in _children(item, "category")
            if (cleaned := _clean_text(child.text)) is not None
        ]
        entries.append(
            _entry_payload(
                title=title_text,
                link=link,
                published_at=published_at,
                updated_at=None,
                author=author,
                tags=tags,
                summary=summary,
            )
        )
    return ParsedFeed("rss", title, site_url, description, entries)


def _parse_atom_feed(root: ElementTree.Element, max_items: int) -> ParsedFeed:
    title = _child_text(root, "title")
    site_url = _atom_link(root)
    description = _child_text(root, "subtitle")
    entries: list[dict[str, Any]] = []
    for entry in _children(root, "entry")[:max_items]:
        author = None
        author_element = _first_child(entry, "author")
        if author_element is not None:
            author = _child_text(author_element, "name")
        tags = [
            _clean_text(child.attrib.get("term"))
            for child in _children(entry, "category")
            if _clean_text(child.attrib.get("term"))
        ]
        entries.append(
            _entry_payload(
                title=_child_text(entry, "title"),
                link=_atom_link(entry) or _child_text(entry, "id"),
                published_at=_child_text(entry, "published"),
                updated_at=_child_text(entry, "updated"),
                author=author,
                tags=tags,
                summary=_child_text(entry, "summary") or _child_text(entry, "content"),
            )
        )
    return ParsedFeed("atom", title, site_url, description, entries)


def _entry_payload(
    *,
    title: str | None,
    link: str | None,
    published_at: str | None,
    updated_at: str | None,
    author: str | None,
    tags: list[str],
    summary: str | None,
) -> dict[str, Any]:
    payload = {
        "title": title,
        "link": link,
        "published_at": published_at,
        "updated_at": updated_at,
        "author": author,
        "tags": tags,
        "summary": summary,
    }
    payload["content_hash"] = _hash_text(
        "|".join(
            str(payload.get(key) or "")
            for key in ("title", "link", "published_at", "updated_at", "summary")
        )
    )
    return payload


def _atom_link(element: ElementTree.Element) -> str | None:
    fallback: str | None = None
    for child in _children(element, "link"):
        href = _clean_text(child.attrib.get("href"))
        if href is None:
            continue
        rel = _clean_text(child.attrib.get("rel")) or "alternate"
        if rel == "alternate":
            return href
        fallback = fallback or href
    return fallback


def _child_text(element: ElementTree.Element, name: str) -> str | None:
    child = _first_child(element, name)
    if child is None:
        return None
    return _clean_text("".join(child.itertext()))


def _first_child(element: ElementTree.Element, name: str) -> ElementTree.Element | None:
    for child in element:
        if _local_name(child.tag) == name:
            return child
    return None


def _children(element: ElementTree.Element, name: str) -> list[ElementTree.Element]:
    return [child for child in element if _local_name(child.tag) == name]


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split()).strip()
    return normalized or None


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
