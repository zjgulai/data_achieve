from __future__ import annotations

from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

import httpx

from data_intelligence_hub.collectors.base import (
    HTTP_HEADERS,
    HTTP_TIMEOUT_SECONDS,
    BaseCollector,
    CollectionResult,
    CollectorError,
    CollectorRawRecord,
    CollectorTestResult,
    collector_log,
    require_text,
)


class GenericWebCollector(BaseCollector):
    collector_type = "generic_web"

    def validate_config(self) -> dict[str, Any]:
        url = require_text(self.config, "url")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise CollectorError("url must be an absolute HTTP or HTTPS URL")
        extract_mode = self.config.get("extract_mode", "main_content")
        if extract_mode not in {"main_content", "full_html"}:
            raise CollectorError("extract_mode must be main_content or full_html")
        return {"url": url, "extract_mode": extract_mode}

    async def test(self) -> CollectorTestResult:
        config = self.validate_config()
        await self._get_html(config["url"])
        return CollectorTestResult(
            status="ok",
            message="Web page is reachable.",
            logs=[collector_log("collector_tested", "Web page responded.")],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        html = await self._get_html(config["url"])
        extracted = _extract_text(html)
        content: dict[str, Any] = {
            "provider": "generic_web",
            "kind": "html_snapshot",
            "url": config["url"],
            "title": extracted.title,
            "text_content": extracted.text,
            "extract_mode": config["extract_mode"],
            "html_content": html,
        }
        return CollectionResult(
            raw_records=[
                CollectorRawRecord(
                    record_type="generic_web",
                    source_url=config["url"],
                    content=content,
                )
            ],
            logs=[
                collector_log(
                    "generic_web_collected",
                    f"Collected HTML snapshot for {config['url']}.",
                )
            ],
            errors=[],
        )

    async def _get_html(self, url: str) -> str:
        if self.http_client is not None:
            return await _fetch_html(self.http_client, url)
        async with httpx.AsyncClient() as client:
            return await _fetch_html(client, url)


async def _fetch_html(client: httpx.AsyncClient, url: str) -> str:
    response = await client.get(url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text


class ExtractedHtml:
    def __init__(self, title: str | None, text: str) -> None:
        self.title = title
        self.text = text


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self._in_title = False
        self._ignore_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        tag_name = tag.lower()
        if tag_name in {"script", "style", "noscript"}:
            self._ignore_depth += 1
        if tag_name == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        tag_name = tag.lower()
        if tag_name in {"script", "style", "noscript"} and self._ignore_depth > 0:
            self._ignore_depth -= 1
        if tag_name == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        normalized = " ".join(data.split())
        if normalized == "" or self._ignore_depth > 0:
            return
        if self._in_title:
            self.title_parts.append(normalized)
        self.text_parts.append(normalized)


def _extract_text(html: str) -> ExtractedHtml:
    parser = _TextExtractor()
    parser.feed(html)
    title = " ".join(parser.title_parts).strip() or None
    text = " ".join(parser.text_parts).strip()
    return ExtractedHtml(title=title, text=text)
