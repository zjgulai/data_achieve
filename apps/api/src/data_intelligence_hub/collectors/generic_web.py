from __future__ import annotations

import asyncio
import ipaddress
import socket
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

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

HTTP_REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
MAX_REDIRECTS = 3
IpAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


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
    current_url = url
    for redirect_count in range(MAX_REDIRECTS + 1):
        await _assert_public_http_url(current_url)
        try:
            response = await collector_get_with_retry(client, current_url)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in HTTP_REDIRECT_STATUS_CODES:
                raise CollectorError(collector_http_error_message(exc)) from exc
            if redirect_count == MAX_REDIRECTS:
                raise CollectorError("http_redirect_limit_exceeded") from exc
            location = exc.response.headers.get("location")
            if location is None or location.strip() == "":
                raise CollectorError("http_redirect_invalid: missing location header") from exc
            current_url = urljoin(str(exc.request.url), location)
            continue
        except httpx.HTTPError as exc:
            raise CollectorError(collector_http_error_message(exc)) from exc
        return response.text
    raise CollectorError("http_redirect_limit_exceeded")


async def _assert_public_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        raise CollectorError("url must be an absolute HTTP or HTTPS URL")
    if parsed.username is not None or parsed.password is not None:
        raise CollectorError("url_userinfo_not_allowed: credentials are not allowed in URLs")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname in {"localhost", "localhost.localdomain"}:
        raise CollectorError("url_host_not_public: host must resolve only to public addresses")
    addresses = _parse_ip_literal(hostname)
    if addresses is None:
        addresses = await _resolve_host_ips(hostname)
    if any(not _is_public_address(address) for address in addresses):
        raise CollectorError("url_host_not_public: host must resolve only to public addresses")


def _parse_ip_literal(hostname: str) -> list[IpAddress] | None:
    try:
        return [ipaddress.ip_address(hostname)]
    except ValueError:
        return None


async def _resolve_host_ips(hostname: str) -> list[IpAddress]:
    loop = asyncio.get_running_loop()
    try:
        address_info = await loop.run_in_executor(
            None,
            socket.getaddrinfo,
            hostname,
            None,
            socket.AF_UNSPEC,
            socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise CollectorError("url_host_unresolvable: host could not be resolved") from exc
    addresses: list[IpAddress] = []
    for entry in address_info:
        sockaddr = entry[4]
        ip_text = str(sockaddr[0])
        try:
            addresses.append(ipaddress.ip_address(ip_text))
        except ValueError as exc:
            raise CollectorError("url_host_invalid: resolved address is invalid") from exc
    if not addresses:
        raise CollectorError("url_host_unresolvable: host could not be resolved")
    return addresses


def _is_public_address(address: IpAddress) -> bool:
    return (
        address.is_global
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_multicast
        and not address.is_private
        and not address.is_reserved
        and not address.is_unspecified
    )


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
