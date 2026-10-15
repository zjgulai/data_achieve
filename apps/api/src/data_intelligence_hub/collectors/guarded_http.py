"""Request-before-send host checks and one shared budget per collection run."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from data_intelligence_hub.collectors.base import (
    HTTP_HEADERS,
    HTTP_RETRY_BACKOFF_SECONDS,
    HTTP_TIMEOUT_SECONDS,
    CollectorError,
    _is_retryable_http_error,
    collector_http_error_message,
)
from data_intelligence_hub.collectors.outbound_policy import (
    GUARDED_HTTP_COLLECTORS,
    CollectionPolicyDenied,
    HttpGrant,
    assert_collector_allowed,
    canonical_host,
    http_grant,
)

REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
MAX_REDIRECTS = 3


@dataclass
class RequestBudget:
    grant: HttpGrant
    deadline: float = field(init=False)
    requests_sent: int = 0
    closed: bool = False
    hosts_used: set[str] = field(default_factory=set)
    in_flight: set[asyncio.Task[Any]] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.deadline = time.monotonic() + self.grant.timeout_seconds

    def check(self, url: str) -> str:
        if datetime.now(UTC) >= self.grant.expires_at:
            raise CollectionPolicyDenied("服务端域名批准已过期")
        if (
            self.closed
            or time.monotonic() >= self.deadline
            or self.requests_sent >= self.grant.max_requests
        ):
            raise CollectionPolicyDenied(
                "本次采集的请求或时间预算已用尽", code="outbound_budget_exceeded"
            )
        try:
            parsed = urlparse(url)
            if (
                parsed.scheme not in {"https", "http"}
                or parsed.hostname is None
                or parsed.username is not None
                or parsed.password is not None
                or parsed.port not in (None, 443 if parsed.scheme == "https" else 80)
            ):
                raise ValueError
            host = canonical_host(parsed.hostname)
        except (ValueError, UnicodeError) as exc:
            raise CollectionPolicyDenied(
                "URL 不符合批准范围", code="outbound_domain_denied"
            ) from exc
        if host not in self.grant.hosts:
            raise CollectionPolicyDenied(f"目标主机未获批准：{host}", code="outbound_domain_denied")
        if len(self.hosts_used | {host}) > self.grant.max_domains:
            raise CollectionPolicyDenied(
                "本次采集的域名预算已用尽", code="outbound_budget_exceeded"
            )
        return host

    def reserve(self, url: str) -> float:
        # There is no await between checking and incrementing: concurrent asyncio
        # requests sharing this budget cannot reserve the same final slot.
        host = self.check(url)
        self.requests_sent += 1
        self.hosts_used.add(host)
        return max(0.001, self.deadline - time.monotonic())


_active_budget: ContextVar[RequestBudget | None] = ContextVar(
    "collection_http_budget", default=None
)


@contextmanager
def collection_scope(collector_type: str) -> Iterator[RequestBudget | None]:
    existing = _active_budget.get()
    if existing is not None and collector_type in GUARDED_HTTP_COLLECTORS:
        yield existing
        return
    assert_collector_allowed(collector_type)
    if collector_type not in GUARDED_HTTP_COLLECTORS:
        yield None
        return
    budget = RequestBudget(http_grant(collector_type))
    token = _active_budget.set(budget)
    try:
        yield budget
    finally:
        budget.closed = True
        for request_task in tuple(budget.in_flight):
            if request_task is not asyncio.current_task():
                request_task.cancel()
        _active_budget.reset(token)


async def guarded_get(client: httpx.AsyncClient, url: str) -> httpx.Response:
    from data_intelligence_hub.collectors.generic_web import _assert_public_http_url

    budget = _active_budget.get()
    if budget is None:
        raise CollectionPolicyDenied("请求缺少受控采集上下文")
    current_url = url
    for redirect_count in range(MAX_REDIRECTS + 1):
        for attempt in range(len(HTTP_RETRY_BACKOFF_SECONDS) + 1):
            host = budget.check(current_url)  # Reject before DNS, then use one canonical host.
            current_url = str(httpx.URL(current_url).copy_with(host=host))
            remaining = max(0.001, budget.deadline - time.monotonic())
            try:
                async with asyncio.timeout(remaining):
                    request_task = asyncio.current_task()
                    if request_task is not None:
                        budget.in_flight.add(request_task)
                    try:
                        await _assert_public_http_url(current_url)
                        remaining = budget.reserve(current_url)
                        response = await client.get(
                            current_url,
                            headers=HTTP_HEADERS,
                            follow_redirects=False,
                            timeout=min(HTTP_TIMEOUT_SECONDS, remaining),
                            auth=None,
                        )
                    finally:
                        if request_task is not None:
                            budget.in_flight.discard(request_task)
            except TimeoutError as exc:
                raise CollectionPolicyDenied(
                    "本次采集的时间预算已用尽",
                    code="outbound_budget_exceeded",
                ) from exc
            except httpx.HTTPError as exc:
                if attempt == len(HTTP_RETRY_BACKOFF_SECONDS) or not _is_retryable_http_error(exc):
                    raise CollectorError(collector_http_error_message(exc)) from exc
                await asyncio.sleep(min(HTTP_RETRY_BACKOFF_SECONDS[attempt], remaining))
                continue
            if response.status_code in REDIRECT_STATUS_CODES:
                if redirect_count == MAX_REDIRECTS:
                    raise CollectorError("http_redirect_limit_exceeded")
                location = response.headers.get("location", "").strip()
                if not location:
                    raise CollectorError("http_redirect_invalid: missing location header")
                current_url = urljoin(str(response.url), location)
                break
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if attempt == len(HTTP_RETRY_BACKOFF_SECONDS) or not _is_retryable_http_error(exc):
                    raise CollectorError(collector_http_error_message(exc)) from exc
                await asyncio.sleep(min(HTTP_RETRY_BACKOFF_SECONDS[attempt], remaining))
                continue
            return response
    raise CollectorError("http_redirect_limit_exceeded")
