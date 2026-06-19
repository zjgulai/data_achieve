from __future__ import annotations

import ipaddress

import httpx
import pytest

from data_intelligence_hub.collectors import generic_web as generic_web_module
from data_intelligence_hub.collectors.base import CollectorError
from data_intelligence_hub.schemas.toolkit import ToolkitPreflightRequest
from data_intelligence_hub.services.toolkit_preflight_service import run_toolkit_preflight

TestIpAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


async def resolve_as_public_host(hostname: str) -> list[TestIpAddress]:
    del hostname
    return [ipaddress.IPv4Address("93.184.216.34")]


@pytest.mark.asyncio
async def test_toolkit_preflight_builds_public_page_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(generic_web_module, "_resolve_host_ips", resolve_as_public_host)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/":
            return httpx.Response(
                200,
                headers={
                    "content-type": "text/html; charset=utf-8",
                    "content-security-policy": "default-src 'self'",
                    "server": "unit-test",
                },
                text=(
                    "<html><head><title>Demo Site</title>"
                    "<meta name='description' content='Training preflight target'>"
                    "<link rel='canonical' href='/canonical'>"
                    "<link rel='stylesheet' href='/style.css'>"
                    "</head><body><h1>Demo Heading</h1><a href='/docs'>Docs</a>"
                    "<a href='https://external.example/path'>External</a>"
                    "<script src='/app.js'></script><img src='/hero.png'>"
                    "<p>Visible public content for extraction.</p></body></html>"
                ),
            )
        if path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow:\nSitemap: https://example.com/sitemap.xml\n",
            )
        if path == "/sitemap.xml":
            return httpx.Response(200, text="<urlset></urlset>")
        if path == "/.well-known/security.txt":
            return httpx.Response(404, text="not found")
        raise AssertionError(f"unexpected path: {path}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        report = await run_toolkit_preflight(
            ToolkitPreflightRequest(url="https://example.com", authorized=True),
            http_client=client,
        )

    assert report.requested_url == "https://example.com"
    assert report.final_url == "https://example.com"
    assert report.authorization_gate.allowed_to_continue is True
    assert report.authorization_gate.risk_level == "medium"
    assert report.headers["content-security-policy"] == "default-src 'self'"
    assert report.robots.available is True
    assert report.sitemap.available is True
    assert report.security_txt.available is False
    assert report.dom.title == "Demo Site"
    assert report.dom.description == "Training preflight target"
    assert report.dom.canonical_url == "https://example.com/canonical"
    assert report.dom.headings == ["Demo Heading"]
    assert report.network.same_origin_links == 1
    assert report.network.external_links == 1
    assert report.network.script_count == 1
    assert report.collection_strategy.recommended_path == "generic_web"
    assert report.collection_strategy.fit == "high"
    assert report.collection_strategy.field_stability == "high"
    assert "DOM 字段契约" in " ".join(report.collection_strategy.next_steps)


@pytest.mark.asyncio
async def test_toolkit_preflight_requires_authorization() -> None:
    with pytest.raises(CollectorError, match="preflight_authorization_required"):
        await run_toolkit_preflight(
            ToolkitPreflightRequest(url="https://example.com", authorized=False)
        )


@pytest.mark.asyncio
async def test_toolkit_preflight_rejects_private_hosts() -> None:
    with pytest.raises(CollectorError, match="url_host_not_public"):
        await run_toolkit_preflight(
            ToolkitPreflightRequest(url="http://127.0.0.1/admin", authorized=True)
        )


@pytest.mark.asyncio
async def test_toolkit_preflight_blocks_global_robots_disallow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(generic_web_module, "_resolve_host_ips", resolve_as_public_host)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /\n")
        if request.url.path == "/sitemap.xml":
            return httpx.Response(404)
        if request.url.path == "/.well-known/security.txt":
            return httpx.Response(404)
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<html><head><title>Blocked</title></head><body><h1>Blocked</h1></body></html>",
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        report = await run_toolkit_preflight(
            ToolkitPreflightRequest(url="https://example.com", authorized=True),
            http_client=client,
        )

    assert report.authorization_gate.allowed_to_continue is False
    assert report.authorization_gate.risk_level == "high"
    assert report.authorization_gate.blocked_reasons == [
        "robots.txt 对全站采集给出禁止信号。"
    ]
    assert report.collection_strategy.recommended_path == "blocked_review"
    assert report.collection_strategy.fit == "blocked"


@pytest.mark.asyncio
async def test_toolkit_preflight_recommends_browser_for_script_heavy_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(generic_web_module, "_resolve_host_ips", resolve_as_public_host)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow:\n")
        if request.url.path == "/sitemap.xml":
            return httpx.Response(404)
        if request.url.path == "/.well-known/security.txt":
            return httpx.Response(404)
        scripts = "".join(f"<script src='/app-{index}.js'></script>" for index in range(12))
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text=f"<html><head><title>App Shell</title></head><body>{scripts}</body></html>",
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        report = await run_toolkit_preflight(
            ToolkitPreflightRequest(url="https://example.com", authorized=True),
            http_client=client,
        )

    assert report.authorization_gate.allowed_to_continue is True
    assert report.collection_strategy.recommended_path == "browser_automation"
    assert report.collection_strategy.field_stability == "low"
    assert "真实浏览器" in " ".join(report.collection_strategy.next_steps)
