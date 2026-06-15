from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import urlparse

import httpx

HTTP_TIMEOUT_SECONDS = 10.0
HTTP_USER_AGENT = "DataIntelligenceHub/0.1 (+https://localhost)"
HTTP_HEADERS = {"User-Agent": HTTP_USER_AGENT, "Accept": "application/json, text/html"}
HTTP_RETRY_BACKOFF_SECONDS = (0.25, 1.0)

JsonContent = dict[str, Any] | list[Any]


class CollectorError(Exception):
    pass


@dataclass(frozen=True)
class CollectorRawRecord:
    record_type: str
    source_url: str | None
    content: JsonContent
    screenshot_url: str | None = None
    collected_at: datetime | None = None


@dataclass(frozen=True)
class CollectorTestResult:
    status: Literal["ok", "failed"]
    message: str
    logs: list[dict[str, Any]]


@dataclass(frozen=True)
class CollectionResult:
    raw_records: list[CollectorRawRecord]
    logs: list[dict[str, Any]]
    errors: list[str]


class BaseCollector(ABC):
    collector_type: str

    def __init__(
        self,
        config: dict[str, Any],
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self.http_client = http_client

    @abstractmethod
    def validate_config(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def test(self) -> CollectorTestResult:
        raise NotImplementedError

    @abstractmethod
    async def collect(self) -> CollectionResult:
        raise NotImplementedError

    def normalize(self, raw_record: CollectorRawRecord) -> list[dict[str, Any]]:
        return []


def collector_log(step: str, message: str, level: str = "info") -> dict[str, Any]:
    return {
        "step": step,
        "message": message,
        "level": level,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def require_text(config: dict[str, Any], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or value.strip() == "":
        raise CollectorError(f"Collector config field is required: {key}")
    return value.strip()


def collector_http_error_message(exc: httpx.HTTPError) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return f"http_timeout: upstream did not respond within {HTTP_TIMEOUT_SECONDS:g}s"
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        retry_after = exc.response.headers.get("retry-after")
        retry_hint = f"; retry_after={retry_after}" if retry_after else ""
        if status_code == 429:
            return f"http_rate_limited: upstream returned 429{retry_hint}"
        if status_code == 404:
            return "http_not_found: upstream returned 404"
        if status_code == 403:
            return "http_forbidden: upstream returned 403"
        if status_code >= 500:
            return f"http_upstream_error: upstream returned {status_code}"
        return f"http_status_error: upstream returned {status_code}"
    if isinstance(exc, httpx.ConnectError):
        return "http_connection_failed: upstream connection failed"
    if isinstance(exc, httpx.NetworkError):
        return "http_network_error: upstream network failed"
    return f"http_request_failed: {exc.__class__.__name__}"


async def collector_get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, str] | None = None,
) -> httpx.Response:
    attempts = len(HTTP_RETRY_BACKOFF_SECONDS) + 1
    for attempt_index in range(attempts):
        try:
            response = await client.get(
                url,
                params=params,
                headers=_headers_for_url(url),
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            if attempt_index == attempts - 1 or not _is_retryable_http_error(exc):
                raise
            await asyncio.sleep(HTTP_RETRY_BACKOFF_SECONDS[attempt_index])
    raise CollectorError("http_request_failed: retry attempts exhausted")


def _is_retryable_http_error(exc: httpx.HTTPError) -> bool:
    if isinstance(exc, httpx.TimeoutException | httpx.NetworkError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        return status_code == 429 or status_code >= 500
    return False


def _headers_for_url(url: str) -> dict[str, str]:
    headers = dict(HTTP_HEADERS)
    if urlparse(url).hostname == "api.github.com":
        token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
            headers["X-GitHub-Api-Version"] = "2022-11-28"
    return headers
