"""真实策略配合内存 HTTP transport；任何外部 DNS/网络均禁止。"""

from __future__ import annotations

import json
from collections.abc import Iterator

import httpx
import pytest

from data_intelligence_hub.collectors.base import CollectorError
from data_intelligence_hub.collectors.generic_web import GenericWebCollector
from data_intelligence_hub.core.config import get_settings


@pytest.fixture(autouse=True)
def restricted_http(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("COLLECTION_NETWORK_MODE", "restricted")
    monkeypatch.setenv(
        "COLLECTION_HTTP_GRANTS",
        json.dumps(
            [
                {
                    "collector_type": "generic_web",
                    "hosts": ["example.com"],
                    "expires_at": "2099-01-01T00:00:00Z",
                    "max_requests": 2,
                }
            ]
        ),
    )
    get_settings.cache_clear()
    import ipaddress

    from data_intelligence_hub.collectors import generic_web

    async def public_dns(host: str):
        if host != "example.com":
            pytest.fail(f"unapproved DNS lookup: {host}")
        return [ipaddress.ip_address("93.184.216.34")]

    monkeypatch.setattr(generic_web, "_resolve_host_ips", public_dns)
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_injected_client_cannot_follow_redirect_to_unapproved_host() -> None:
    sent: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        sent.append(request.url.host)
        return httpx.Response(302, headers={"location": "https://unapproved.test/"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond), follow_redirects=True
    ) as c:
        with pytest.raises(CollectorError, match="outbound_domain_denied"):
            await GenericWebCollector({"url": "https://example.com"}, c).collect()
    assert sent == ["example.com"]


@pytest.mark.asyncio
async def test_unapproved_host_is_rejected_before_dns() -> None:
    def unexpected_request(request: httpx.Request) -> httpx.Response:
        pytest.fail(f"unapproved request: {request.url.host}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(unexpected_request)) as c:
        with pytest.raises(CollectorError, match="outbound_domain_denied"):
            await GenericWebCollector({"url": "https://other.test"}, c).collect()


@pytest.mark.asyncio
async def test_request_budget_counts_retries_before_sending() -> None:
    sent: list[str] = []

    def fail(request: httpx.Request) -> httpx.Response:
        sent.append(request.url.host)
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as c:
        with pytest.raises(CollectorError, match="outbound_budget_exceeded"):
            await GenericWebCollector(
                {"url": "https://example.com", "max_requests": 1000}, c
            ).collect()
    assert sent == ["example.com", "example.com"]


@pytest.mark.asyncio
async def test_approved_page_keeps_extracted_output() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, text="<html><title>Approved</title><p>Content</p></html>")
        )
    ) as c:
        result = await GenericWebCollector({"url": "https://example.com"}, c).collect()
    assert result.raw_records[0].content["title"] == "Approved"


@pytest.mark.asyncio
async def test_expired_grant_rejected_without_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "COLLECTION_HTTP_GRANTS",
        json.dumps(
            [
                {
                    "collector_type": "generic_web",
                    "hosts": ["example.com"],
                    "expires_at": "2020-01-01T00:00:00Z",
                }
            ]
        ),
    )
    get_settings.cache_clear()

    def no_network(request: httpx.Request) -> httpx.Response:
        pytest.fail("expired approval caused network activity")

    async with httpx.AsyncClient(transport=httpx.MockTransport(no_network)) as c:
        with pytest.raises(CollectorError, match="collection_policy_denied"):
            await GenericWebCollector({"url": "https://example.com"}, c).collect()


@pytest.mark.asyncio
async def test_rss_cannot_fetch_without_a_server_grant() -> None:
    from data_intelligence_hub.collectors.public_feed import PublicFeedCollector

    def no_network(request: httpx.Request) -> httpx.Response:
        pytest.fail("RSS bypassed the server approval")

    async with httpx.AsyncClient(transport=httpx.MockTransport(no_network)) as c:
        with pytest.raises(CollectorError, match="collection_policy_denied"):
            await PublicFeedCollector({"url": "https://example.com/rss"}, c).test()


@pytest.mark.asyncio
async def test_concurrent_requests_cannot_take_the_same_budget_slot() -> None:
    import asyncio

    from data_intelligence_hub.collectors.guarded_http import collection_scope

    sent: list[str] = []

    async def respond(request: httpx.Request) -> httpx.Response:
        sent.append(request.url.path)
        await asyncio.sleep(0)
        return httpx.Response(200, text="<p>ok</p>")

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with collection_scope("generic_web"):
            results = await asyncio.gather(
                *(
                    GenericWebCollector({"url": f"https://example.com/{i}"}, client).collect()
                    for i in range(8)
                ),
                return_exceptions=True,
            )
    assert len(sent) == 2
    assert sum(isinstance(r, CollectorError) for r in results) == 6


@pytest.mark.parametrize(
    "url",
    [
        "https://sub.example.com",
        "https://example.com:444",
        "https://user@example.com",
        "http://127.0.0.1",
        "https://example.com.evil.test",
        "file:///etc/passwd",
    ],
)
@pytest.mark.asyncio
async def test_unapproved_url_variants_never_send(url: str) -> None:
    def no_network(request: httpx.Request) -> httpx.Response:
        pytest.fail("unapproved URL reached HTTP transport")

    async with httpx.AsyncClient(transport=httpx.MockTransport(no_network)) as client:
        with pytest.raises(CollectorError):
            await GenericWebCollector({"url": url}, client).collect()


@pytest.mark.asyncio
async def test_scope_expiry_stops_the_next_request(monkeypatch: pytest.MonkeyPatch) -> None:
    from data_intelligence_hub.collectors import guarded_http
    from data_intelligence_hub.collectors.guarded_http import collection_scope

    sent: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        sent.append(request.url.path)
        return httpx.Response(200, text="<p>ok</p>")

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with collection_scope("generic_web") as budget:
            await GenericWebCollector({"url": "https://example.com/first"}, client).collect()
            monkeypatch.setattr(guarded_http.time, "monotonic", lambda: budget.deadline + 1)
            with pytest.raises(CollectorError, match="outbound_budget_exceeded"):
                await GenericWebCollector({"url": "https://example.com/second"}, client).collect()
    assert sent == ["/first"]


@pytest.mark.asyncio
async def test_approved_hostname_and_transport_use_identical_idna(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import AsyncMock

    from data_intelligence_hub.collectors import generic_web

    monkeypatch.setenv(
        "COLLECTION_HTTP_GRANTS",
        json.dumps(
            [
                {
                    "collector_type": "generic_web",
                    "hosts": ["strasse.example"],
                    "expires_at": "2099-01-01T00:00:00Z",
                    "max_requests": 2,
                }
            ]
        ),
    )
    get_settings.cache_clear()
    dns = AsyncMock()
    monkeypatch.setattr(generic_web, "_assert_public_http_url", dns)
    sent: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        sent.append(request.url.host)
        return httpx.Response(200, text="<p>wrong host</p>")

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(CollectorError, match="outbound_domain_denied"):
            await GenericWebCollector({"url": "https://straße.example/"}, client).collect()
    assert sent == []
    assert dns.await_count == 0


@pytest.mark.asyncio
async def test_inherited_scope_cannot_send_after_parent_finishes() -> None:
    import asyncio

    from data_intelligence_hub.collectors.guarded_http import collection_scope

    release = asyncio.Event()
    sent: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        sent.append(request.url.host)
        return httpx.Response(200, text="<p>not allowed after scope exit</p>")

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:

        async def delayed_request():
            await release.wait()
            return await GenericWebCollector({"url": "https://example.com"}, client).collect()

        with collection_scope("generic_web"):
            task = asyncio.create_task(delayed_request())
        release.set()
        with pytest.raises(CollectorError, match="outbound_budget_exceeded"):
            await task
    assert sent == []


@pytest.mark.asyncio
async def test_unicode_host_uses_approved_ascii_host_for_dns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import AsyncMock

    from data_intelligence_hub.collectors import generic_web

    monkeypatch.setenv(
        "COLLECTION_HTTP_GRANTS",
        json.dumps(
            [
                {
                    "collector_type": "generic_web",
                    "hosts": ["xn--strae-oqa.example"],
                    "expires_at": "2099-01-01T00:00:00Z",
                }
            ]
        ),
    )
    get_settings.cache_clear()
    dns = AsyncMock()
    monkeypatch.setattr(generic_web, "_assert_public_http_url", dns)
    visited: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        visited.append(request.url.raw_host.decode("ascii"))
        return httpx.Response(200, text="<p>approved</p>")

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        await GenericWebCollector({"url": "https://straße.example/"}, client).collect()
    assert dns.call_args.args[0] == "https://xn--strae-oqa.example/"
    assert visited == ["xn--strae-oqa.example"]


@pytest.mark.asyncio
async def test_finishing_parent_cancels_an_in_flight_child_request() -> None:
    import asyncio

    from data_intelligence_hub.collectors.guarded_http import collection_scope

    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def respond(request: httpx.Request) -> httpx.Response:
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise
        raise AssertionError("unreachable")

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with collection_scope("generic_web"):
            child = asyncio.create_task(
                GenericWebCollector({"url": "https://example.com"}, client).collect()
            )
            await started.wait()
        await asyncio.sleep(0)
        was_cancelled = cancelled.is_set()
        child.cancel()
        await asyncio.gather(child, return_exceptions=True)
    assert was_cancelled
