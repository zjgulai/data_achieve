from __future__ import annotations

import ipaddress

import httpx
import pytest

from data_intelligence_hub.collectors import generic_web as generic_web_module
from data_intelligence_hub.collectors.base import (
    HTTP_TIMEOUT_SECONDS,
    HTTP_USER_AGENT,
    CollectorError,
)
from data_intelligence_hub.collectors.ecommerce_product_discovery import (
    EcommerceProductDiscoveryCollector,
)
from data_intelligence_hub.collectors.ecommerce_product_page import EcommerceProductPageCollector
from data_intelligence_hub.collectors.generic_web import GenericWebCollector
from data_intelligence_hub.collectors.github_repo import GitHubRepoCollector
from data_intelligence_hub.collectors.github_topic import GitHubTopicCollector
from data_intelligence_hub.collectors.manual_json import ManualJsonCollector

TestIpAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


def assert_request_policy(request: httpx.Request) -> None:
    assert request.headers["user-agent"] == HTTP_USER_AGENT
    timeout = request.extensions.get("timeout")
    assert isinstance(timeout, dict)
    assert timeout["connect"] == HTTP_TIMEOUT_SECONDS


async def resolve_as_public_host(hostname: str) -> list[TestIpAddress]:
    del hostname
    return [ipaddress.IPv4Address("93.184.216.34")]


@pytest.mark.asyncio
async def test_manual_json_collector_validates_tests_collects_and_normalizes() -> None:
    collector = ManualJsonCollector(
        {"entity_type": "product", "json_data": {"name": "Demo", "price": 99}}
    )

    assert collector.validate_config()["entity_type"] == "product"
    test_result = await collector.test()
    collect_result = await collector.collect()

    assert test_result.status == "ok"
    assert collect_result.errors == []
    assert collect_result.raw_records[0].record_type == "manual_json"
    content = collect_result.raw_records[0].content
    assert isinstance(content, dict)
    assert content["entity_type"] == "product"
    assert collector.normalize(collect_result.raw_records[0]) == []


@pytest.mark.asyncio
async def test_github_repo_collector_uses_http_policy_and_collects_repo_snapshot() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert_request_policy(request)
        if request.url.path.endswith("/releases/latest"):
            return httpx.Response(
                200,
                json={
                    "tag_name": "v1.0.0",
                    "name": "v1.0.0",
                    "html_url": "https://github.com/openai/codex/releases/tag/v1.0.0",
                    "published_at": "2026-06-12T00:00:00Z",
                    "created_at": "2026-06-12T00:00:00Z",
                    "prerelease": False,
                    "draft": False,
                },
            )
        return httpx.Response(
            200,
            json={
                "name": "codex",
                "full_name": "openai/codex",
                "html_url": "https://github.com/openai/codex",
                "description": "Agentic coding.",
                "stargazers_count": 1000,
                "forks_count": 50,
                "open_issues_count": 12,
                "watchers_count": 1000,
                "default_branch": "main",
                "language": "Python",
                "topics": ["agent"],
                "license": {"spdx_id": "Apache-2.0", "name": "Apache License 2.0"},
                "pushed_at": "2026-06-11T00:00:00Z",
                "updated_at": "2026-06-11T00:00:00Z",
                "owner": {"login": "openai"},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        collector = GitHubRepoCollector({"owner": "openai", "repo": "codex"}, client)
        test_result = await collector.test()
        collect_result = await collector.collect()

    assert test_result.status == "ok"
    raw_record = collect_result.raw_records[0]
    content = raw_record.content
    assert isinstance(content, dict)
    assert raw_record.source_url == "https://github.com/openai/codex"
    assert content["full_name"] == "openai/codex"
    assert content["license_spdx_id"] == "Apache-2.0"
    assert content["latest_release_tag"] == "v1.0.0"
    assert content["latest_release_published_at"] == "2026-06-12T00:00:00Z"
    assert content["provenance"]["latest_release_found"] is True
    assert collector.normalize(raw_record) == []


@pytest.mark.asyncio
async def test_github_repo_collector_retries_transient_upstream_failure() -> None:
    repo_request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal repo_request_count
        assert_request_policy(request)
        if request.url.path.endswith("/releases/latest"):
            return httpx.Response(404, json={"message": "Not Found"})
        repo_request_count += 1
        if repo_request_count == 1:
            return httpx.Response(502, json={"message": "bad gateway"})
        return httpx.Response(
            200,
            json={
                "name": "codex",
                "full_name": "openai/codex",
                "html_url": "https://github.com/openai/codex",
                "owner": {"login": "openai"},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        collector = GitHubRepoCollector({"owner": "openai", "repo": "codex"}, client)
        collect_result = await collector.collect()

    assert repo_request_count == 2
    content = collect_result.raw_records[0].content
    assert isinstance(content, dict)
    assert content["full_name"] == "openai/codex"
    assert content["latest_release"] is None
    assert content["provenance"]["latest_release_found"] is False


@pytest.mark.asyncio
async def test_github_repo_collector_uses_github_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-token"
        assert request.headers["x-github-api-version"] == "2022-11-28"
        if request.url.path.endswith("/releases/latest"):
            return httpx.Response(404, json={"message": "Not Found"})
        return httpx.Response(
            200,
            json={
                "name": "codex",
                "full_name": "openai/codex",
                "html_url": "https://github.com/openai/codex",
                "owner": {"login": "openai"},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        collector = GitHubRepoCollector({"owner": "openai", "repo": "codex"}, client)
        collect_result = await collector.collect()

    assert collect_result.raw_records[0].source_url == "https://github.com/openai/codex"


@pytest.mark.asyncio
async def test_github_topic_collector_collects_repository_search_snapshot() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert_request_policy(request)
        assert request.url.params["q"] == "topic:web-scraping"
        return httpx.Response(
            200,
            json={
                "total_count": 1,
                "items": [
                    {
                        "owner": {"login": "example", "type": "Organization"},
                        "full_name": "example/scraper",
                        "html_url": "https://github.com/example/scraper",
                        "description": "Scraper",
                        "stargazers_count": 42,
                        "forks_count": 3,
                        "open_issues_count": 1,
                        "watchers_count": 42,
                        "language": "Python",
                        "topics": ["crawler"],
                        "license": {"spdx_id": "MIT", "name": "MIT License"},
                        "default_branch": "main",
                        "archived": False,
                        "fork": False,
                        "created_at": "2026-06-01T00:00:00Z",
                        "pushed_at": "2026-06-10T00:00:00Z",
                        "updated_at": "2026-06-11T00:00:00Z",
                    }
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        collector = GitHubTopicCollector({"topic": "web-scraping", "max_results": 10}, client)
        test_result = await collector.test()
        collect_result = await collector.collect()

    assert test_result.status == "ok"
    raw_record = collect_result.raw_records[0]
    content = raw_record.content
    assert isinstance(content, dict)
    assert raw_record.record_type == "github_topic"
    assert content["repositories"][0]["full_name"] == "example/scraper"
    assert content["repositories"][0]["license_spdx_id"] == "MIT"
    assert content["repositories"][0]["default_branch"] == "main"
    assert content["repositories"][0]["owner_login"] == "example"
    assert content["schema_version"] == "github_topic.v2"
    assert content["provenance"]["source"] == "github_search_api"
    assert collector.normalize(raw_record) == []


@pytest.mark.asyncio
async def test_generic_web_collector_collects_html_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(generic_web_module, "_resolve_host_ips", resolve_as_public_host)

    def handler(request: httpx.Request) -> httpx.Response:
        assert_request_policy(request)
        return httpx.Response(
            200,
            text="<html><head><title>Demo</title></head><body><h1>Hello</h1></body></html>",
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        collector = GenericWebCollector({"url": "https://example.com"}, client)
        test_result = await collector.test()
        collect_result = await collector.collect()

    assert test_result.status == "ok"
    raw_record = collect_result.raw_records[0]
    content = raw_record.content
    assert isinstance(content, dict)
    assert raw_record.record_type == "generic_web"
    assert content["title"] == "Demo"
    assert "Hello" in content["text_content"]
    assert collector.normalize(raw_record) == []


@pytest.mark.asyncio
async def test_ecommerce_product_page_collector_extracts_product_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(generic_web_module, "_resolve_host_ips", resolve_as_public_host)

    html = """
    <html>
      <head>
        <title>Demo Shopify Product</title>
        <link rel="canonical" href="/products/demo-bag">
        <meta property="og:image" content="/cdn/demo.jpg">
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Demo Carry Bag",
          "sku": "BAG-001",
          "brand": {"@type": "Brand", "name": "Demo Brand"},
          "description": "A compact product fixture.",
          "image": ["/cdn/demo.jpg"],
          "offers": {
            "@type": "Offer",
            "price": "129.90",
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock"
          }
        }
        </script>
        <script src="https://cdn.shopify.com/theme.js"></script>
      </head>
      <body><h1>Demo Carry Bag</h1><form></form></body>
    </html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        assert_request_policy(request)
        return httpx.Response(200, text=html)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        collector = EcommerceProductPageCollector(
            {"url": "https://shop.example/products/demo-bag"},
            client,
        )
        test_result = await collector.test()
        collect_result = await collector.collect()

    assert test_result.status == "ok"
    raw_record = collect_result.raw_records[0]
    assert raw_record.record_type == "ecommerce_product_page"
    content = raw_record.content
    assert isinstance(content, dict)
    assert content["platform_profile"]["platform_type"] == "shopify"
    assert content["extracted_fields"]["title"] == "Demo Carry Bag"
    assert content["extracted_fields"]["price"] == 129.9
    assert content["extracted_fields"]["currency"] == "USD"
    assert content["extracted_fields"]["sku"] == "BAG-001"
    assert content["extracted_fields"]["availability"] == "in_stock"
    assert content["extracted_fields"]["canonical_url"] == (
        "https://shop.example/products/demo-bag"
    )
    assert content["tool_recommendations"][0]["collector_type"] == "ecommerce_product_page"


@pytest.mark.asyncio
async def test_ecommerce_product_page_collector_uses_demo_fixture_without_http_client() -> None:
    collector = EcommerceProductPageCollector(
        {"url": "https://shop.example/products/demo-bag"},
    )

    test_result = await collector.test()
    collect_result = await collector.collect()

    assert test_result.status == "ok"
    content = collect_result.raw_records[0].content
    assert isinstance(content, dict)
    assert content["extracted_fields"]["title"] == "Demo Carry Bag"
    assert content["extracted_fields"]["price"] == 129.9
    assert content["page_structure"]["product_schema_count"] == 1


@pytest.mark.asyncio
async def test_ecommerce_product_discovery_collector_detects_product_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(generic_web_module, "_resolve_host_ips", resolve_as_public_host)

    html = """
    <html>
      <head>
        <title>Summer Bags</title>
        <link rel="canonical" href="/collections/summer-bags">
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "ItemList",
          "itemListElement": [
            {
              "@type": "ListItem",
              "item": {
                "@type": "Product",
                "name": "Demo Carry Bag",
                "url": "/products/demo-bag"
              }
            }
          ]
        }
        </script>
        <script src="https://cdn.shopify.com/theme.js"></script>
      </head>
      <body>
        <a href="/collections/summer-bags/products/demo-bag">Demo Carry Bag</a>
        <a href="/products/weekend-tote">Weekend Tote</a>
        <a href="/pages/about">About</a>
      </body>
    </html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        assert_request_policy(request)
        return httpx.Response(200, text=html)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        collector = EcommerceProductDiscoveryCollector(
            {"url": "https://shop.example/collections/summer-bags", "max_products": 10},
            client,
        )
        test_result = await collector.test()
        collect_result = await collector.collect()

    assert test_result.status == "ok"
    raw_record = collect_result.raw_records[0]
    assert raw_record.record_type == "ecommerce_product_discovery"
    content = raw_record.content
    assert isinstance(content, dict)
    candidates = content["product_candidates"]
    assert isinstance(candidates, list)
    candidate_urls = {candidate["url"] for candidate in candidates}
    assert candidate_urls == {
        "https://shop.example/products/demo-bag",
        "https://shop.example/collections/summer-bags/products/demo-bag",
        "https://shop.example/products/weekend-tote",
    }
    assert content["page_structure"]["page_type"] == "collection_listing"
    assert content["page_structure"]["product_link_count"] == 2
    assert content["discovery_plan"]["next_collector_type"] == "ecommerce_product_page"
    assert content["tool_recommendations"][0]["collector_type"] == (
        "ecommerce_product_discovery"
    )


@pytest.mark.asyncio
async def test_ecommerce_product_discovery_collector_uses_demo_fixture_without_http_client(
) -> None:
    collector = EcommerceProductDiscoveryCollector(
        {"url": "https://shop.example/collections/summer-bags", "max_products": 10},
    )

    test_result = await collector.test()
    collect_result = await collector.collect()

    assert test_result.status == "ok"
    content = collect_result.raw_records[0].content
    assert isinstance(content, dict)
    candidates = content["product_candidates"]
    assert [candidate["url"] for candidate in candidates] == [
        "https://shop.example/products/demo-bag",
        "https://shop.example/products/weekend-tote",
    ]
    assert content["page_structure"]["page_type"] == "collection_listing"


@pytest.mark.asyncio
async def test_generic_web_collector_rejects_private_network_hosts() -> None:
    for unsafe_url in [
        "http://127.0.0.1/admin",
        "http://10.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/admin",
        "http://localhost/admin",
    ]:
        collector = GenericWebCollector({"url": unsafe_url})
        with pytest.raises(CollectorError, match="url_host_not_public"):
            await collector.test()


@pytest.mark.asyncio
async def test_generic_web_collector_revalidates_redirect_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(generic_web_module, "_resolve_host_ips", resolve_as_public_host)
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        assert_request_policy(request)
        return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        collector = GenericWebCollector({"url": "https://example.com"}, client)
        with pytest.raises(CollectorError, match="url_host_not_public"):
            await collector.collect()

    assert requested_urls == ["https://example.com"]


@pytest.mark.asyncio
async def test_github_topic_collector_classifies_rate_limit_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert_request_policy(request)
        return httpx.Response(429, headers={"retry-after": "60"}, json={"message": "rate limit"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        collector = GitHubTopicCollector({"topic": "web-scraping", "max_results": 10}, client)
        with pytest.raises(CollectorError, match="http_rate_limited"):
            await collector.collect()


@pytest.mark.asyncio
async def test_generic_web_collector_classifies_connection_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(generic_web_module, "_resolve_host_ips", resolve_as_public_host)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        collector = GenericWebCollector({"url": "https://example.com"}, client)
        with pytest.raises(CollectorError, match="http_connection_failed"):
            await collector.collect()
