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
    require_text,
)

JINA_BASE_URL = "https://r.jina.ai/"
JINA_TIMEOUT = 30.0
_VALID_FORMATS = {"markdown", "text", "html"}


def _get_api_key() -> str:
    key = os.environ.get("JINA_API_KEY", "")
    if not key:
        raise CollectorError("JINA_API_KEY not set — add to .env.production")
    return key


def _jina_client() -> httpx.AsyncClient:
    proxy = (os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY") or "").strip() or None
    return httpx.AsyncClient(timeout=JINA_TIMEOUT, proxy=proxy)


class JinaReaderCollector(BaseCollector):
    collector_type = "jina_reader"

    def validate_config(self) -> dict[str, Any]:
        url = require_text(self.config, "url")
        return_format = self.config.get("return_format", "markdown")
        if return_format not in _VALID_FORMATS:
            raise CollectorError(f"return_format must be one of {_VALID_FORMATS}")
        return {"url": url, "return_format": return_format}

    async def test(self) -> CollectorTestResult:
        config = self.validate_config()
        try:
            api_key = _get_api_key()
        except CollectorError as exc:
            return CollectorTestResult(
                status="failed",
                message=str(exc),
                logs=[collector_log("jina_test_failed", str(exc), level="error")],
            )
        try:
            async with _jina_client() as client:
                r = await client.get(
                    f"{JINA_BASE_URL}{config['url']}",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Accept": "text/plain",
                        "X-Return-Format": config["return_format"],
                    },
                    follow_redirects=True,
                )
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            return CollectorTestResult(
                status="failed",
                message=msg,
                logs=[collector_log("jina_test_failed", msg, level="error")],
            )
        if r.status_code not in {200, 422}:
            return CollectorTestResult(
                status="failed",
                message=f"Jina Reader returned HTTP {r.status_code}",
                logs=[collector_log("jina_test_failed", r.text[:200])],
            )
        return CollectorTestResult(
            status="ok",
            message=f"Jina Reader reachable, url={config['url']!r}",
            logs=[collector_log("jina_test_ok", f"size={len(r.text)}")],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        logs: list[dict[str, Any]] = []
        errors: list[str] = []
        try:
            api_key = _get_api_key()
        except CollectorError as exc:
            errors.append(str(exc))
            logs.append(collector_log("jina_collect_error", str(exc), level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        collected_at = datetime.now(UTC)
        try:
            async with _jina_client() as client:
                r = await client.get(
                    f"{JINA_BASE_URL}{config['url']}",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Accept": "text/plain",
                        "X-Return-Format": config["return_format"],
                    },
                    follow_redirects=True,
                )
        except httpx.HTTPError as exc:
            msg = collector_http_error_message(exc)
            errors.append(msg)
            logs.append(collector_log("jina_collect_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        if r.status_code not in {200, 422}:
            msg = f"Jina Reader HTTP {r.status_code}: {r.text[:200]}"
            errors.append(msg)
            logs.append(collector_log("jina_collect_error", msg, level="error"))
            return CollectionResult(raw_records=[], logs=logs, errors=errors)

        record = CollectorRawRecord(
            record_type="web_page_markdown",
            source_url=config["url"],
            content={
                "url": config["url"],
                "return_format": config["return_format"],
                "http_status": r.status_code,
                "content": r.text,
            },
            collected_at=collected_at,
        )
        logs.append(collector_log("jina_collected", f"url={config['url']!r} size={len(r.text)}"))
        return CollectionResult(raw_records=[record], logs=logs, errors=errors)
