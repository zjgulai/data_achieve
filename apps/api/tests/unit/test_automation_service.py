from __future__ import annotations

import ipaddress

import httpx
import pytest

from data_intelligence_hub.collectors import generic_web as generic_web_module
from data_intelligence_hub.schemas.automation import (
    AutomationFanoutCandidateInput,
    AutomationProductDiscoveryRequest,
    AutomationProductFanoutPreviewRequest,
    AutomationSiteAnalysisRequest,
)
from data_intelligence_hub.services.automation_service import (
    analyze_site_for_collection,
    discover_products_for_collection,
    preview_product_fanout,
)

TestIpAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


async def resolve_as_public_host(hostname: str) -> list[TestIpAddress]:
    del hostname
    return [ipaddress.IPv4Address("93.184.216.34")]


@pytest.mark.asyncio
async def test_analyze_site_for_collection_returns_product_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(generic_web_module, "_resolve_host_ips", resolve_as_public_host)

    html = """
    <html>
      <head>
        <title>Demo Product</title>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Demo Product",
          "sku": "SKU-100",
          "offers": {
            "@type": "Offer",
            "price": "79.50",
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock"
          }
        }
        </script>
      </head>
      <body><h1>Demo Product</h1></body>
    </html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await analyze_site_for_collection(
            AutomationSiteAnalysisRequest(
                url="https://shop.example/products/demo-product",
                authorized=True,
            ),
            http_client=client,
        )

    assert response.authorization_confirmed is True
    assert response.platform_profile.platform_type == "independent_ecommerce"
    assert response.page_structure.page_type == "product_detail"
    fields = {field.key: field for field in response.field_candidates}
    assert fields["title"].value == "Demo Product"
    assert fields["price"].value == 79.5
    assert fields["currency"].value == "USD"
    assert fields["sku"].value == "SKU-100"
    assert response.tool_recommendations[0].collector_type == "ecommerce_product_page"
    assert response.source_draft.type == "ecommerce_product_page"
    assert response.source_draft.config["fields"]
    assert response.blocked_reasons == []


@pytest.mark.asyncio
async def test_discover_products_for_collection_returns_candidate_plan(
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
      </head>
      <body>
        <a href="/products/weekend-tote">Weekend Tote</a>
        <a href="/pages/about">About</a>
      </body>
    </html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await discover_products_for_collection(
            AutomationProductDiscoveryRequest(
                url="https://shop.example/collections/summer-bags",
                authorized=True,
                max_products=10,
            ),
            http_client=client,
        )

    assert response.authorization_confirmed is True
    assert response.platform_profile.platform_type == "independent_ecommerce"
    assert response.page_structure.page_type == "collection_listing"
    assert response.page_structure.product_link_count == 1
    assert {candidate.url for candidate in response.product_candidates} == {
        "https://shop.example/products/demo-bag",
        "https://shop.example/products/weekend-tote",
    }
    assert response.discovery_plan.next_collector_type == "ecommerce_product_page"
    assert response.discovery_plan.fan_out_requires_review is True
    assert response.tool_recommendations[0].collector_type == "browser_runtime_candidate"
    assert response.source_draft.type == "ecommerce_product_discovery"
    assert response.source_draft.config["max_products"] == 10
    assert response.blocked_reasons == []


@pytest.mark.asyncio
async def test_preview_product_fanout_returns_source_drafts_and_blocked_candidates() -> None:
    response = await preview_product_fanout(
        AutomationProductFanoutPreviewRequest(
            parent_url="https://shop.example/collections/summer-bags",
            authorized=True,
            max_sources=2,
            fields=["title", "price", "canonical_url"],
            candidates=[
                AutomationFanoutCandidateInput(
                    url="https://shop.example/products/demo-bag#reviews",
                    title="Demo Carry Bag",
                    source="json_ld",
                    confidence=0.9,
                ),
                AutomationFanoutCandidateInput(
                    url="https://shop.example/products/demo-bag",
                    title="Duplicate Demo Carry Bag",
                    source="anchor",
                    confidence=0.86,
                ),
                AutomationFanoutCandidateInput(
                    url="https://other.example/products/external",
                    title="External Product",
                    source="anchor",
                    confidence=0.86,
                ),
                AutomationFanoutCandidateInput(
                    url="/products/relative",
                    title="Relative Product",
                    source="anchor",
                    confidence=0.86,
                ),
                AutomationFanoutCandidateInput(
                    url="https://shop.example/products/weekend-tote",
                    title="Weekend Tote",
                    source="anchor",
                    confidence=0.86,
                ),
                AutomationFanoutCandidateInput(
                    url="https://shop.example/products/over-limit",
                    title="Over Limit",
                    source="anchor",
                    confidence=0.86,
                ),
            ],
        )
    )

    assert response.authorization_confirmed is True
    assert response.batch_plan.run_mode == "preview_only"
    assert response.batch_plan.next_collector_type == "ecommerce_product_page"
    assert response.batch_plan.ready_count == 2
    assert response.batch_plan.blocked_count == 4
    assert response.batch_plan.fields == ["title", "price", "canonical_url"]
    assert response.batch_plan.manual_review_required is True
    assert response.batch_plan.execution_boundary == "preview_only_no_database_write"
    assert [draft.type for draft in response.source_drafts] == [
        "ecommerce_product_page",
        "ecommerce_product_page",
    ]
    assert response.source_drafts[0].config["url"] == "https://shop.example/products/demo-bag"
    assert response.source_drafts[0].suggested_name == "商品页采集：Demo Carry Bag"
    assert {status.reason for status in response.candidate_statuses if status.reason} == {
        "candidate_url_cross_origin",
        "candidate_url_invalid",
        "candidate_exceeds_preview_limit",
        "duplicate_candidate_url",
    }
    assert "当前结果仅为预览" in response.blocked_reasons[-1]
