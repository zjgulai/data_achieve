"""SERP collectors for Baidu, Bing, and DuckDuckGo via AnyCrawl.

AnyCrawl is an open-source Node.js crawler that extracts structured
search-engine results. It can be self-hosted as a sidecar service.

Deployment:
  Add an `anycrawl` container to docker-compose.yml:
    image: any4ai/anycrawl:latest
    ports: ["3001:3001"]
    environment:
      PORT: 3001

Environment variables (API-side):
    ANYCRAWL_BASE_URL    Base URL of the AnyCrawl service
                         (default: http://localhost:3001)
    ANYCRAWL_API_KEY     Optional API key if AnyCrawl is secured
    ANYCRAWL_TIMEOUT     Request timeout in seconds (default: 30)

Fallback: when ANYCRAWL_BASE_URL is not set or the service is
unreachable, falls back to lightweight httpx scraping using
DuckDuckGo HTML endpoint (no JS required).
"""
from __future__ import annotations

import os
import re
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

_DEFAULT_BASE_URL = "http://localhost:3001"
_DEFAULT_TIMEOUT = 30.0
_VALID_ENGINES = {"baidu", "bing", "duckduckgo", "google"}


def _base_url() -> str:
    return os.environ.get("ANYCRAWL_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")


def _api_key() -> str:
    return os.environ.get("ANYCRAWL_API_KEY", "")


def _timeout() -> float:
    try:
        return float(os.environ.get("ANYCRAWL_TIMEOUT", str(_DEFAULT_TIMEOUT)))
    except ValueError:
        return _DEFAULT_TIMEOUT


def _client(proxy: bool = True) -> httpx.AsyncClient:
    proxy_url = None
    if proxy:
        proxy_url = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
    headers: dict[str, str] = {}
    key = _api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return httpx.AsyncClient(
        timeout=_timeout(),
        proxy=proxy_url or None,
        headers=headers,
        follow_redirects=True,
    )


async def _anycrawl_serp(
    engine: str, keyword: str, max_items: int
) -> list[dict[str, Any]]:
    """Query AnyCrawl /search endpoint and return result items."""
    url = f"{_base_url()}/search"
    params: dict[str, Any] = {
        "engine": engine,
        "q": keyword,
        "num": max_items,
    }
    try:
        async with _client() as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
    except httpx.HTTPError as exc:
        raise CollectorError(collector_http_error_message(exc)) from exc

    body = r.json()
    # AnyCrawl responds with {"results": [...], ...} or just a list
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        results = body.get("results") or body.get("organic_results") or body.get("data") or []
        return results if isinstance(results, list) else []
    return []


def _normalize_result(item: dict[str, Any], rank: int, engine: str) -> dict[str, Any]:
    """Normalize an AnyCrawl result to a consistent schema."""
    return {
        "rank": rank,
        "engine": engine,
        "title": item.get("title") or item.get("name") or "",
        "url": item.get("url") or item.get("link") or item.get("href") or "",
        "snippet": item.get("snippet") or item.get("description") or item.get("body") or "",
        "domain": item.get("domain") or "",
        "is_ad": bool(item.get("is_ad") or item.get("sponsored")),
        "raw": item,
    }


# ─────────────────────────────────────────────
#  DuckDuckGo HTML fallback (no AnyCrawl needed)
# ─────────────────────────────────────────────

_DDG_RESULT_RE = re.compile(
    r'<a class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
    r'<a class="result__snippet"[^>]*>(.*?)</a>',
    re.DOTALL,
)


async def _ddg_html_fallback(keyword: str, max_items: int) -> list[dict[str, Any]]:
    """Minimal DuckDuckGo HTML scrape as a fallback when AnyCrawl is down."""
    url = "https://html.duckduckgo.com/html/"
    params = {"q": keyword, "kl": "us-en"}
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        async with httpx.AsyncClient(timeout=_timeout(), follow_redirects=True) as client:
            r = await client.post(url, data=params, headers=headers)
            r.raise_for_status()
    except httpx.HTTPError as exc:
        raise CollectorError(collector_http_error_message(exc)) from exc

    html = r.text
    items: list[dict[str, Any]] = []
    for rank, m in enumerate(_DDG_RESULT_RE.finditer(html), start=1):
        link, title_html, snippet_html = m.group(1), m.group(2), m.group(3)
        title = re.sub(r"<[^>]+>", "", title_html).strip()
        snippet = re.sub(r"<[^>]+>", "", snippet_html).strip()
        items.append({
            "rank": rank,
            "engine": "duckduckgo",
            "title": title,
            "url": link,
            "snippet": snippet,
            "domain": "",
            "is_ad": False,
            "raw": {},
        })
        if rank >= max_items:
            break
    return items


# ─────────────────────────────────────────────
#  Base SERP collector
# ─────────────────────────────────────────────

class _SerpCollector(BaseCollector):
    """Shared logic for SERP collectors."""

    engine: str = ""

    def validate_config(self) -> dict[str, Any]:
        keyword = require_text(self.config, "keyword")
        max_items = int(self.config.get("max_items", 10))
        if max_items < 1 or max_items > 100:
            raise CollectorError("max_items must be between 1 and 100")
        return {"keyword": keyword, "max_items": max_items}

    async def test(self) -> CollectorTestResult:
        base = _base_url()
        if base == _DEFAULT_BASE_URL:
            msg = (
                f"{self.engine.title()} SERP collector ready. "
                "AnyCrawl not configured — will use HTML fallback for DuckDuckGo "
                "or fail gracefully for Baidu/Bing."
            )
        else:
            msg = f"{self.engine.title()} SERP via AnyCrawl at {base}"
        return CollectorTestResult(
            status="ok",
            message=msg,
            logs=[collector_log(f"{self.engine}_test_ok", msg)],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)
        engine = self.engine
        keyword: str = config["keyword"]
        max_items: int = config["max_items"]

        # Try AnyCrawl first, then fallback for DDG
        anycrawl_url = _base_url()
        items: list[dict[str, Any]] = []
        used_fallback = False

        if anycrawl_url != _DEFAULT_BASE_URL:
            try:
                raw_items = await _anycrawl_serp(engine, keyword, max_items)
                items = [
                    _normalize_result(it, i + 1, engine)
                    for i, it in enumerate(raw_items[:max_items])
                ]
            except CollectorError as exc:
                # AnyCrawl unreachable — fall back for DuckDuckGo only
                if engine == "duckduckgo":
                    logs.append(
                        collector_log(
                            "anycrawl_fallback",
                            f"AnyCrawl failed ({exc}), using HTML fallback",
                        )
                    )
                else:
                    errors.append(str(exc))
                    logs.append(
                        collector_log(f"{engine}_collect_error", str(exc), level="error")
                    )
                    return CollectionResult(raw_records=[], logs=logs, errors=errors)
        else:
            if engine == "duckduckgo":
                used_fallback = True
            else:
                msg = (
                    f"ANYCRAWL_BASE_URL is not configured — "
                    f"{engine.title()} SERP requires AnyCrawl. "
                    "Set ANYCRAWL_BASE_URL to your AnyCrawl service URL."
                )
                errors.append(msg)
                logs.append(collector_log(f"{engine}_collect_error", msg, level="error"))
                return CollectionResult(raw_records=[], logs=logs, errors=errors)

        if used_fallback or (engine == "duckduckgo" and not items):
            try:
                items = await _ddg_html_fallback(keyword, max_items)
                used_fallback = True
            except CollectorError as exc:
                errors.append(str(exc))
                logs.append(collector_log("ddg_fallback_error", str(exc), level="error"))
                return CollectionResult(raw_records=[], logs=logs, errors=errors)

        records = [
            CollectorRawRecord(
                record_type="serp_result",
                source_url=it.get("url"),
                content=it,
                collected_at=collected_at,
            )
            for it in items
        ]

        source_note = "DDG-HTML-fallback" if used_fallback else "AnyCrawl"
        logs.append(
            collector_log(
                f"{engine}_serp_collected",
                f"keyword={keyword!r} count={len(records)} via={source_note}",
            )
        )
        return CollectionResult(raw_records=records, logs=logs, errors=errors)


# ─────────────────────────────────────────────
#  Concrete SERP collectors
# ─────────────────────────────────────────────

class BaiduSearchCollector(_SerpCollector):
    """Collect Baidu organic search results for a keyword."""
    collector_type = "baidu_search"
    engine = "baidu"


class BingSearchCollector(_SerpCollector):
    """Collect Bing organic search results for a keyword."""
    collector_type = "bing_search"
    engine = "bing"


class DuckDuckGoSearchCollector(_SerpCollector):
    """Collect DuckDuckGo organic search results (AnyCrawl or HTML fallback)."""
    collector_type = "duckduckgo_search"
    engine = "duckduckgo"
