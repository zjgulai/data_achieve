from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

import httpx

from data_intelligence_hub.collectors.base import (
    BaseCollector,
    CollectionResult,
    CollectorError,
    CollectorRawRecord,
    CollectorTestResult,
    collector_log,
    require_text,
)
from data_intelligence_hub.collectors.ecommerce_demo_fixture import demo_ecommerce_html
from data_intelligence_hub.collectors.ecommerce_product_page import PlatformProfile
from data_intelligence_hub.collectors.generic_web import GenericWebCollector


class EcommerceProductDiscoveryCollector(BaseCollector):
    collector_type = "ecommerce_product_discovery"

    def validate_config(self) -> dict[str, Any]:
        url = require_text(self.config, "url")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise CollectorError("url must be an absolute HTTP or HTTPS URL")
        max_products = self.config.get("max_products", 50)
        if not isinstance(max_products, int) or max_products < 1 or max_products > 200:
            raise CollectorError("max_products must be an integer between 1 and 200")
        platform_hint = self.config.get("platform_hint", "auto")
        if platform_hint not in {"auto", "shopify", "independent_ecommerce"}:
            raise CollectorError("platform_hint must be auto, shopify, or independent_ecommerce")
        return {
            "url": url,
            "max_products": max_products,
            "platform_hint": platform_hint,
        }

    async def test(self) -> CollectorTestResult:
        config = self.validate_config()
        html = await _fetch_html(config["url"], self.http_client)
        analysis = analyze_ecommerce_product_discovery(
            config["url"],
            html,
            config["max_products"],
        )
        if not analysis.product_candidates:
            raise CollectorError("ecommerce_product_urls_not_detected")
        return CollectorTestResult(
            status="ok",
            message="Product URLs were detected.",
            logs=[
                collector_log(
                    "ecommerce_product_discovery_tested",
                    f"Detected {len(analysis.product_candidates)} product URL candidates.",
                )
            ],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        html = await _fetch_html(config["url"], self.http_client)
        analysis = analyze_ecommerce_product_discovery(
            config["url"],
            html,
            config["max_products"],
        )
        return CollectionResult(
            raw_records=[
                CollectorRawRecord(
                    record_type=self.collector_type,
                    source_url=config["url"],
                    content=analysis.to_raw_content(),
                    collected_at=datetime.now(UTC),
                )
            ],
            logs=[
                collector_log(
                    "ecommerce_product_discovery_collected",
                    f"Collected discovery page with {len(analysis.product_candidates)} candidates.",
                )
            ],
            errors=[],
        )


@dataclass(frozen=True)
class ProductUrlCandidate:
    url: str
    title: str | None
    source: str
    confidence: float
    canonical_url: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "source": self.source,
            "confidence": self.confidence,
            "canonical_url": self.canonical_url,
        }


@dataclass(frozen=True)
class DiscoveryPageStructure:
    page_type: str
    title: str | None
    canonical_url: str | None
    link_count: int
    product_link_count: int
    jsonld_url_count: int
    sitemap_url_count: int
    pagination_url_count: int
    duplicate_url_count: int
    skipped_url_count: int
    script_count: int
    text_sample: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_type": self.page_type,
            "title": self.title,
            "canonical_url": self.canonical_url,
            "link_count": self.link_count,
            "product_link_count": self.product_link_count,
            "jsonld_url_count": self.jsonld_url_count,
            "sitemap_url_count": self.sitemap_url_count,
            "pagination_url_count": self.pagination_url_count,
            "duplicate_url_count": self.duplicate_url_count,
            "skipped_url_count": self.skipped_url_count,
            "script_count": self.script_count,
            "text_sample": self.text_sample,
        }


@dataclass(frozen=True)
class EcommerceProductDiscoveryAnalysis:
    url: str
    platform_profile: PlatformProfile
    page_structure: DiscoveryPageStructure
    product_candidates: list[ProductUrlCandidate]
    tool_recommendations: list[dict[str, Any]]
    discovery_plan: dict[str, Any]

    def to_raw_content(self) -> dict[str, Any]:
        return {
            "provider": "ecommerce",
            "kind": "product_discovery",
            "url": self.url,
            "platform_profile": self.platform_profile.to_dict(),
            "page_structure": self.page_structure.to_dict(),
            "product_candidates": [candidate.to_dict() for candidate in self.product_candidates],
            "tool_recommendations": self.tool_recommendations,
            "discovery_plan": self.discovery_plan,
        }


async def _fetch_html(url: str, http_client: httpx.AsyncClient | None) -> str:
    if http_client is None:
        fixture_html = demo_ecommerce_html(url)
        if fixture_html is not None:
            return fixture_html

    collector = GenericWebCollector(
        {"url": url, "extract_mode": "full_html"},
        http_client=http_client,
    )
    result = await collector.collect()
    if not result.raw_records:
        raise CollectorError("ecommerce_product_discovery_empty_response")
    content = result.raw_records[0].content
    html_content = content.get("html_content") if isinstance(content, dict) else None
    if not isinstance(html_content, str):
        raise CollectorError("ecommerce_product_discovery_missing_html")
    return html_content


def analyze_ecommerce_product_discovery(
    url: str,
    html: str,
    max_products: int = 50,
) -> EcommerceProductDiscoveryAnalysis:
    inspector = _ProductDiscoveryHtmlInspector(url)
    inspector.feed(html)
    jsonld_candidates = _jsonld_product_url_candidates(inspector.jsonld_documents, url)
    sitemap_candidates = _sitemap_product_url_candidates(html, url)
    link_candidates, skip_counts = _link_product_url_candidates(inspector.links, url)
    all_candidates = [*jsonld_candidates, *sitemap_candidates, *link_candidates]
    candidates, duplicate_url_count = _dedupe_candidates(
        all_candidates,
        max_products,
    )
    if duplicate_url_count:
        skip_counts["duplicate_canonical_url"] = duplicate_url_count
    skipped_url_count = sum(skip_counts.values())
    structure = DiscoveryPageStructure(
        page_type=_page_type(url, inspector, sitemap_candidates, candidates),
        title=inspector.title,
        canonical_url=inspector.canonical_url,
        link_count=len(inspector.links),
        product_link_count=len([candidate for candidate in link_candidates if candidate.url]),
        jsonld_url_count=len(jsonld_candidates),
        sitemap_url_count=len(sitemap_candidates),
        pagination_url_count=len(inspector.pagination_urls),
        duplicate_url_count=duplicate_url_count,
        skipped_url_count=skipped_url_count,
        script_count=inspector.script_count,
        text_sample=" ".join(inspector.text_parts).strip()[:360],
    )
    platform = _platform_profile(url, html, inspector, candidates)
    return EcommerceProductDiscoveryAnalysis(
        url=url,
        platform_profile=platform,
        page_structure=structure,
        product_candidates=candidates,
        tool_recommendations=_tool_recommendations(platform, structure, candidates),
        discovery_plan={
            "next_collector_type": "ecommerce_product_page",
            "candidate_count": len(candidates),
            "max_products": max_products,
            "fan_out_requires_review": True,
            "pagination_urls": sorted(inspector.pagination_urls),
            "dedupe_summary": {
                "input_url_count": len(all_candidates),
                "canonical_candidate_count": len(candidates),
                "duplicate_url_count": duplicate_url_count,
                "skipped_url_count": skipped_url_count,
                "skipped_reasons": _skip_reasons(skip_counts),
            },
        },
    )


class _ProductDiscoveryHtmlInspector(HTMLParser):
    def __init__(self, final_url: str) -> None:
        super().__init__()
        self.final_url = final_url
        self.title_parts: list[str] = []
        self.title: str | None = None
        self.canonical_url: str | None = None
        self.links: list[tuple[str, str | None]] = []
        self.pagination_urls: set[str] = set()
        self.jsonld_documents: list[Any] = []
        self.script_count = 0
        self.text_parts: list[str] = []
        self._in_title = False
        self._in_jsonld = False
        self._jsonld_parts: list[str] = []
        self._ignore_depth = 0
        self._anchor_href: str | None = None
        self._anchor_rel: str = ""
        self._anchor_text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = tag.lower()
        attrs_by_name = {name.lower(): value or "" for name, value in attrs}
        if tag_name == "title":
            self._in_title = True
        if tag_name == "script":
            self.script_count += 1
            self._in_jsonld = attrs_by_name.get("type", "").lower() == "application/ld+json"
            self._jsonld_parts = []
            self._ignore_depth += 1
        if tag_name in {"style", "noscript"}:
            self._ignore_depth += 1
        if tag_name == "link":
            rel = attrs_by_name.get("rel", "").lower()
            href = attrs_by_name.get("href", "").strip()
            if "canonical" in rel and href:
                self.canonical_url = _clean_url(urljoin(self.final_url, href))
            if href and _looks_like_pagination_link(href, None, rel):
                self.pagination_urls.add(_clean_url(urljoin(self.final_url, href)))
        if tag_name == "a":
            self._anchor_href = attrs_by_name.get("href", "").strip() or None
            self._anchor_rel = attrs_by_name.get("rel", "").lower()
            self._anchor_text_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag_name = tag.lower()
        if tag_name == "title":
            self._in_title = False
            self.title = " ".join(self.title_parts).strip()[:180] or None
        if tag_name == "script":
            if self._in_jsonld:
                self._capture_jsonld("".join(self._jsonld_parts))
            self._in_jsonld = False
            self._jsonld_parts = []
            if self._ignore_depth > 0:
                self._ignore_depth -= 1
        if tag_name in {"style", "noscript"} and self._ignore_depth > 0:
            self._ignore_depth -= 1
        if tag_name == "a" and self._anchor_href:
            title = " ".join(self._anchor_text_parts).strip() or None
            absolute_url = urljoin(self.final_url, self._anchor_href)
            self.links.append((absolute_url, title))
            if _looks_like_pagination_link(absolute_url, title, self._anchor_rel):
                self.pagination_urls.add(_clean_url(absolute_url))
            self._anchor_href = None
            self._anchor_rel = ""
            self._anchor_text_parts = []

    def handle_data(self, data: str) -> None:
        normalized = " ".join(data.split())
        if self._in_title and normalized:
            self.title_parts.append(normalized)
        if self._in_jsonld:
            self._jsonld_parts.append(data)
        if self._anchor_href and normalized:
            self._anchor_text_parts.append(normalized)
        if self._ignore_depth == 0 and normalized:
            self.text_parts.append(normalized)

    def _capture_jsonld(self, text: str) -> None:
        stripped = text.strip()
        if not stripped:
            return
        try:
            self.jsonld_documents.append(json.loads(stripped))
        except ValueError:
            return


def _jsonld_product_url_candidates(
    documents: list[Any],
    base_url: str,
) -> list[ProductUrlCandidate]:
    candidates: list[ProductUrlCandidate] = []
    for document in documents:
        for item in _walk_jsonld(document):
            url = _jsonld_url(item)
            if url is None:
                continue
            title = _text(item.get("name"))
            candidates.append(
                ProductUrlCandidate(
                    url=_canonical_product_url(urljoin(base_url, url)),
                    title=title,
                    source="json_ld",
                    confidence=0.9,
                    canonical_url=_canonical_product_url(urljoin(base_url, url)),
                )
            )
    return candidates


def _walk_jsonld(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        list_results: list[dict[str, Any]] = []
        for item in value:
            list_results.extend(_walk_jsonld(item))
        return list_results
    if not isinstance(value, dict):
        return []
    results: list[dict[str, Any]] = []
    if _jsonld_type_matches(value.get("@type"), "Product"):
        results.append(value)
    if _jsonld_type_matches(value.get("@type"), "ListItem"):
        item = value.get("item")
        if isinstance(item, dict):
            results.extend(_walk_jsonld(item))
        elif isinstance(item, str):
            results.append({"url": item})
    graph = value.get("@graph")
    if isinstance(graph, list):
        for item in graph:
            results.extend(_walk_jsonld(item))
    elements = value.get("itemListElement")
    if isinstance(elements, list):
        for item in elements:
            results.extend(_walk_jsonld(item))
    return results


def _jsonld_type_matches(value: Any, expected: str) -> bool:
    if isinstance(value, str):
        return value.lower() == expected.lower()
    if isinstance(value, list):
        return any(_jsonld_type_matches(item, expected) for item in value)
    return False


def _jsonld_url(item: dict[str, Any]) -> str | None:
    value = item.get("url") or item.get("@id")
    if isinstance(value, str):
        return value
    offers = item.get("offers")
    offer_url = offers.get("url") if isinstance(offers, dict) else None
    if isinstance(offer_url, str):
        return offer_url
    return None


def _sitemap_product_url_candidates(html: str, base_url: str) -> list[ProductUrlCandidate]:
    candidates: list[ProductUrlCandidate] = []
    for match in re.finditer(r"<loc>\s*([^<]+?)\s*</loc>", html, flags=re.IGNORECASE):
        candidate_url = _canonical_product_url(urljoin(base_url, match.group(1).strip()))
        if _looks_like_product_url(candidate_url):
            candidates.append(
                ProductUrlCandidate(
                    url=candidate_url,
                    title=None,
                    source="sitemap",
                    confidence=0.88,
                    canonical_url=candidate_url,
                )
            )
    return candidates


def _link_product_url_candidates(
    links: list[tuple[str, str | None]],
    base_url: str,
) -> tuple[list[ProductUrlCandidate], dict[str, int]]:
    candidates: list[ProductUrlCandidate] = []
    skip_counts: dict[str, int] = {}
    base_origin = _origin(base_url)
    for link_url, title in links:
        candidate_url = _clean_url(link_url)
        if not candidate_url:
            _count_skip(skip_counts, "empty_url")
            continue
        if _origin(candidate_url) != base_origin:
            _count_skip(skip_counts, "cross_origin_url")
            continue
        if not _looks_like_product_url(candidate_url):
            _count_skip(skip_counts, "non_product_url_pattern")
            continue
        canonical_url = _canonical_product_url(candidate_url)
        confidence = 0.86
        if "/collections/" in urlparse(candidate_url).path and "/products/" in urlparse(
            candidate_url
        ).path:
            confidence = 0.9
        candidates.append(
            ProductUrlCandidate(
                url=canonical_url,
                title=title,
                source="anchor",
                confidence=confidence,
                canonical_url=canonical_url,
            )
        )
    return candidates, skip_counts


def _dedupe_candidates(
    candidates: list[ProductUrlCandidate],
    max_products: int,
) -> tuple[list[ProductUrlCandidate], int]:
    best_by_url: dict[str, ProductUrlCandidate] = {}
    duplicate_count = 0
    for candidate in candidates:
        existing = best_by_url.get(candidate.canonical_url)
        if existing is not None:
            duplicate_count += 1
        if existing is None or candidate.confidence > existing.confidence:
            best_by_url[candidate.canonical_url] = candidate
        elif existing.title is None and candidate.title:
            best_by_url[candidate.canonical_url] = ProductUrlCandidate(
                url=existing.canonical_url,
                title=candidate.title,
                source=existing.source,
                confidence=existing.confidence,
                canonical_url=existing.canonical_url,
            )
    deduped = sorted(
        best_by_url.values(),
        key=lambda item: (-item.confidence, item.url),
    )[:max_products]
    return deduped, duplicate_count


def _platform_profile(
    url: str,
    html: str,
    inspector: _ProductDiscoveryHtmlInspector,
    candidates: list[ProductUrlCandidate],
) -> PlatformProfile:
    lowered = html.lower()
    indicators: list[str] = []
    host = urlparse(url).hostname or ""
    if "myshopify.com" in host or "cdn.shopify.com" in lowered:
        indicators.append("Shopify asset or host marker")
    if "shopify-section" in lowered or "/cart.js" in lowered or "shopify.theme" in lowered:
        indicators.append("Shopify theme runtime marker")
    if candidates:
        indicators.append("product URL pattern")
    if inspector.jsonld_documents:
        indicators.append("JSON-LD catalog data")
    platform_type = (
        "shopify"
        if any("Shopify" in item for item in indicators)
        else "independent_ecommerce"
    )
    confidence = min(0.95, 0.35 + len(indicators) * 0.18)
    risk_level = "medium" if inspector.script_count > 14 and len(candidates) < 3 else "low"
    return PlatformProfile(
        platform_type=platform_type,
        confidence=round(confidence, 2),
        indicators=indicators or ["generic listing page markers"],
        risk_level=risk_level,
    )


def _tool_recommendations(
    platform: PlatformProfile,
    structure: DiscoveryPageStructure,
    candidates: list[ProductUrlCandidate],
) -> list[dict[str, Any]]:
    recommendations = [
        {
            "tool": "ecommerce_product_discovery",
            "collector_type": "ecommerce_product_discovery",
            "fit": "primary",
            "risk_level": platform.risk_level,
            "reason": "页面内已发现商品 URL，可作为后续商品页字段采集的候选入口。",
        }
    ]
    if structure.script_count > 14 or len(candidates) < 3:
        recommendations.insert(
            0,
            {
                "tool": "Playwright browser snapshot",
                "collector_type": "browser_runtime_candidate",
                "fit": "fallback",
                "risk_level": "medium",
                "reason": "页面脚本较多或商品链接较少，后续应使用浏览器运行时复核动态渲染列表。",
            },
        )
    recommendations.append(
        {
            "tool": "ecommerce_product_page",
            "collector_type": "ecommerce_product_page",
            "fit": "next_step",
            "risk_level": "low",
            "reason": "候选商品 URL 经过人工确认后，可转入商品详情页字段解析。",
        }
    )
    return recommendations


def _page_type(
    url: str,
    inspector: _ProductDiscoveryHtmlInspector,
    sitemap_candidates: list[ProductUrlCandidate],
    candidates: list[ProductUrlCandidate],
) -> str:
    path = urlparse(url).path.lower()
    if sitemap_candidates or path.endswith(".xml") or "sitemap" in path:
        return "sitemap"
    if "/collections/" in path or "/category/" in path or "/collections" in path:
        return "collection_listing"
    if candidates and len(candidates) >= 3:
        return "product_listing"
    if inspector.links:
        return "link_index"
    return "unknown_listing"


def _looks_like_product_url(value: str) -> bool:
    path = urlparse(value).path.lower()
    product_markers = ("/products/", "/product/", "/p/")
    if any(marker in path for marker in product_markers):
        return True
    return bool(re.search(r"/products?[-_/][a-z0-9][a-z0-9-]{2,}", path))


def _looks_like_pagination_link(
    value: str,
    title: str | None,
    rel: str,
) -> bool:
    parsed = urlparse(value)
    path_and_query = f"{parsed.path}?{parsed.query}".lower()
    title_text = (title or "").strip().lower()
    if any(token in rel for token in ("next", "prev", "pagination")):
        return True
    if re.search(r"(?:[?&]page=\d+|/page/\d+|/collections/[^?]+/page/\d+)", path_and_query):
        return True
    return title_text in {"next", "previous", "prev", "older", "newer", "下一页", "上一页"}


def _clean_url(value: str) -> str:
    cleaned, _fragment = urldefrag(value.strip())
    return cleaned


def _canonical_product_url(value: str) -> str:
    cleaned = _clean_url(value)
    parsed = urlparse(cleaned)
    match = re.search(r"/products/([^/?#]+)", parsed.path, flags=re.IGNORECASE)
    if match:
        return urlunparse((parsed.scheme, parsed.netloc, f"/products/{match.group(1)}", "", "", ""))
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def _origin(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        return ""
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{parsed.hostname}{port}"


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = " ".join(value.split())
    return stripped or None


def _count_skip(skip_counts: dict[str, int], reason: str) -> None:
    skip_counts[reason] = skip_counts.get(reason, 0) + 1


def _skip_reasons(skip_counts: dict[str, int]) -> list[str]:
    return [f"{reason}:{count}" for reason, count in sorted(skip_counts.items())]
