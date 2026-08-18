"""Firecrawl collector — large-scale structured web crawling and extraction.

Supports three modes:
  - crawl_site: crawl an entire website up to max_pages, returning Markdown
  - extract_structured: extract structured JSON from a URL using a schema
  - batch_scrape: scrape a list of URLs and return Markdown for each

Requires a Firecrawl API key (cloud) or a self-hosted Firecrawl instance.

Environment variables:
    FIRECRAWL_API_KEY    Required for Firecrawl Cloud; leave empty for self-host
    FIRECRAWL_BASE_URL   Base URL (default: https://api.firecrawl.dev)
    FIRECRAWL_TIMEOUT    Request timeout in seconds (default: 60)
    HTTP_PROXY           Forwarded to httpx
"""
from __future__ import annotations

import json
import os
import time
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

_DEFAULT_BASE_URL = "https://api.firecrawl.dev"
_DEFAULT_TIMEOUT = 60.0
_POLL_INTERVAL = 3.0
_MAX_POLL_SECONDS = 300.0


def _base_url() -> str:
    return os.environ.get("FIRECRAWL_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")


def _api_key() -> str:
    return os.environ.get("FIRECRAWL_API_KEY", "").strip()


def _timeout() -> float:
    try:
        return float(os.environ.get("FIRECRAWL_TIMEOUT", str(_DEFAULT_TIMEOUT)))
    except ValueError:
        return _DEFAULT_TIMEOUT


def _client() -> httpx.AsyncClient:
    proxy = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
    headers: dict[str, str] = {"Content-Type": "application/json"}
    key = _api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return httpx.AsyncClient(
        timeout=_timeout(),
        proxy=proxy or None,
        headers=headers,
    )


async def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{_base_url()}{path}"
    try:
        async with _client() as client:
            r = await client.post(url, content=json.dumps(payload))
            r.raise_for_status()
    except httpx.HTTPError as exc:
        raise CollectorError(collector_http_error_message(exc)) from exc
    return r.json()


async def _get(path: str) -> dict[str, Any]:
    url = f"{_base_url()}{path}"
    try:
        async with _client() as client:
            r = await client.get(url)
            r.raise_for_status()
    except httpx.HTTPError as exc:
        raise CollectorError(collector_http_error_message(exc)) from exc
    return r.json()


async def _poll_job(job_id: str) -> dict[str, Any]:
    """Poll a Firecrawl async job until it completes or times out."""
    deadline = time.monotonic() + _MAX_POLL_SECONDS
    while time.monotonic() < deadline:
        body = await _get(f"/v1/crawl/{job_id}")
        status = body.get("status", "")
        if status in {"completed", "failed", "cancelled"}:
            return body
        import asyncio
        await asyncio.sleep(_POLL_INTERVAL)
    raise CollectorError(
        f"Firecrawl job {job_id!r} did not complete within {_MAX_POLL_SECONDS:.0f}s"
    )


# ─────────────────────────────────────────────
#  FirecrawlCrawlCollector
# ─────────────────────────────────────────────

class FirecrawlCrawlCollector(BaseCollector):
    """Crawl an entire site and return each page as Markdown via Firecrawl."""

    collector_type = "firecrawl_crawl_site"

    def validate_config(self) -> dict[str, Any]:
        url = require_text(self.config, "url")
        max_pages = int(self.config.get("max_pages", 10))
        if max_pages < 1 or max_pages > 500:
            raise CollectorError("max_pages must be between 1 and 500")
        include_paths: list[str] = self.config.get("include_paths", [])
        exclude_paths: list[str] = self.config.get("exclude_paths", [])
        return {
            "url": url,
            "max_pages": max_pages,
            "include_paths": include_paths,
            "exclude_paths": exclude_paths,
        }

    async def test(self) -> CollectorTestResult:
        key = _api_key()
        if not key and _base_url() == _DEFAULT_BASE_URL:
            msg = "FIRECRAWL_API_KEY not set — required for Firecrawl Cloud"
            return CollectorTestResult(
                status="failed", message=msg,
                logs=[collector_log("firecrawl_test_failed", msg, level="error")],
            )
        try:
            self.validate_config()
        except CollectorError as exc:
            return CollectorTestResult(
                status="failed", message=str(exc),
                logs=[collector_log("firecrawl_test_failed", str(exc), level="error")],
            )
        return CollectorTestResult(
            status="ok",
            message=f"Firecrawl ready at {_base_url()}",
            logs=[collector_log("firecrawl_test_ok", _base_url())],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        payload: dict[str, Any] = {
            "url": config["url"],
            "limit": config["max_pages"],
            "scrapeOptions": {"formats": ["markdown"]},
        }
        if config["include_paths"]:
            payload["includePaths"] = config["include_paths"]
        if config["exclude_paths"]:
            payload["excludePaths"] = config["exclude_paths"]

        try:
            resp = await _post("/v1/crawl", payload)
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("firecrawl_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        if not resp.get("success"):
            msg = f"Firecrawl crawl rejected: {resp}"
            errors.append(msg)
            logs.append(collector_log("firecrawl_collect_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        job_id = resp.get("id", "")
        logs.append(collector_log("firecrawl_crawl_started", f"job_id={job_id!r}"))

        try:
            result = await _poll_job(job_id)
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("firecrawl_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        if result.get("status") != "completed":
            msg = f"Firecrawl job failed: status={result.get('status')}"
            errors.append(msg)
            logs.append(collector_log("firecrawl_collect_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        pages = result.get("data") or []
        records = [
            CollectorRawRecord(
                record_type="web_page_markdown",
                source_url=page.get("metadata", {}).get("sourceURL") or page.get("url"),
                content={
                    "url": page.get("metadata", {}).get("sourceURL") or page.get("url"),
                    "title": page.get("metadata", {}).get("title") or "",
                    "markdown": page.get("markdown") or "",
                    "markdown_chars": len(page.get("markdown") or ""),
                },
                collected_at=collected_at,
            )
            for page in pages
        ]
        logs.append(
            collector_log(
                "firecrawl_crawl_collected",
                f"url={config['url']!r} pages={len(records)}",
            )
        )
        return CollectionResult(raw_records=records, logs=logs, errors=errors)


# ─────────────────────────────────────────────
#  FirecrawlExtractCollector
# ─────────────────────────────────────────────

class FirecrawlExtractCollector(BaseCollector):
    """Extract structured JSON from a URL using a Firecrawl schema prompt."""

    collector_type = "firecrawl_extract_structured"

    def validate_config(self) -> dict[str, Any]:
        url = require_text(self.config, "url")
        schema = self.config.get("schema")
        prompt = self.config.get("prompt", "").strip()
        if not schema and not prompt:
            raise CollectorError(
                "At least one of 'schema' (dict) or 'prompt' (str) must be provided"
            )
        return {"url": url, "schema": schema, "prompt": prompt}

    async def test(self) -> CollectorTestResult:
        key = _api_key()
        if not key and _base_url() == _DEFAULT_BASE_URL:
            msg = "FIRECRAWL_API_KEY not set — required for Firecrawl Cloud"
            return CollectorTestResult(
                status="failed", message=msg,
                logs=[collector_log("firecrawl_test_failed", msg, level="error")],
            )
        return CollectorTestResult(
            status="ok",
            message=f"Firecrawl ready at {_base_url()}",
            logs=[collector_log("firecrawl_test_ok", _base_url())],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        extract_payload: dict[str, Any] = {}
        if config["schema"]:
            extract_payload["schema"] = config["schema"]
        if config["prompt"]:
            extract_payload["prompt"] = config["prompt"]

        payload: dict[str, Any] = {
            "urls": [config["url"]],
            "formats": ["extract"],
            "extract": extract_payload,
        }

        try:
            resp = await _post("/v1/scrape", payload)
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("firecrawl_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        if not resp.get("success"):
            msg = f"Firecrawl extract rejected: {resp}"
            errors.append(msg)
            logs.append(collector_log("firecrawl_collect_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        extracted = resp.get("data", {}).get("extract") or {}
        record = CollectorRawRecord(
            record_type="structured_data",
            source_url=config["url"],
            content={
                "url": config["url"],
                "extracted": extracted,
                "schema": config["schema"],
                "prompt": config["prompt"],
            },
            collected_at=collected_at,
        )
        logs.append(
            collector_log(
                "firecrawl_extract_collected",
                f"url={config['url']!r} "
                f"keys={list(extracted.keys()) if isinstance(extracted, dict) else 'n/a'}",
            )
        )
        return CollectionResult(raw_records=[record], logs=logs, errors=errors)


# ─────────────────────────────────────────────
#  FirecrawlBatchScrapeCollector
# ─────────────────────────────────────────────

class FirecrawlBatchScrapeCollector(BaseCollector):
    """Scrape a list of URLs in parallel via Firecrawl, returning Markdown."""

    collector_type = "firecrawl_batch_scrape"

    def validate_config(self) -> dict[str, Any]:
        urls = self.config.get("urls", [])
        if not isinstance(urls, list) or not urls:
            raise CollectorError("config.urls must be a non-empty list of URL strings")
        if len(urls) > 100:
            raise CollectorError("config.urls may not exceed 100 URLs per batch")
        for u in urls:
            if not isinstance(u, str) or not u.strip():
                raise CollectorError("Every element in config.urls must be a non-empty string")
        return {"urls": [u.strip() for u in urls]}

    async def test(self) -> CollectorTestResult:
        key = _api_key()
        if not key and _base_url() == _DEFAULT_BASE_URL:
            msg = "FIRECRAWL_API_KEY not set — required for Firecrawl Cloud"
            return CollectorTestResult(
                status="failed", message=msg,
                logs=[collector_log("firecrawl_test_failed", msg, level="error")],
            )
        return CollectorTestResult(
            status="ok",
            message=f"Firecrawl batch scrape ready at {_base_url()}",
            logs=[collector_log("firecrawl_test_ok", _base_url())],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        collected_at = datetime.now(UTC)

        payload: dict[str, Any] = {
            "urls": config["urls"],
            "formats": ["markdown"],
        }

        try:
            resp = await _post("/v1/batch/scrape", payload)
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("firecrawl_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        if not resp.get("success"):
            msg = f"Firecrawl batch scrape rejected: {resp}"
            errors.append(msg)
            logs.append(collector_log("firecrawl_collect_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        pages = resp.get("data") or []
        records = [
            CollectorRawRecord(
                record_type="web_page_markdown",
                source_url=page.get("metadata", {}).get("sourceURL") or page.get("url"),
                content={
                    "url": page.get("metadata", {}).get("sourceURL") or page.get("url"),
                    "title": page.get("metadata", {}).get("title") or "",
                    "markdown": page.get("markdown") or "",
                    "markdown_chars": len(page.get("markdown") or ""),
                },
                collected_at=collected_at,
            )
            for page in pages
        ]
        logs.append(
            collector_log(
                "firecrawl_batch_collected",
                f"requested={len(config['urls'])} received={len(records)}",
            )
        )
        return CollectionResult(raw_records=records, logs=logs, errors=errors)
