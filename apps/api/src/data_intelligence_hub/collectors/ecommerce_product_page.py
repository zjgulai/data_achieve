from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

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
from data_intelligence_hub.collectors.generic_web import GenericWebCollector

ECOMMERCE_PRODUCT_FIELDS = (
    "title",
    "price",
    "currency",
    "availability",
    "sku",
    "brand",
    "description",
    "image_url",
    "canonical_url",
)


class EcommerceProductPageCollector(BaseCollector):
    collector_type = "ecommerce_product_page"

    def validate_config(self) -> dict[str, Any]:
        url = require_text(self.config, "url")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise CollectorError("url must be an absolute HTTP or HTTPS URL")
        fields = self.config.get("fields", list(ECOMMERCE_PRODUCT_FIELDS))
        if not isinstance(fields, list) or not fields:
            raise CollectorError("fields must be a non-empty list")
        normalized_fields: list[str] = []
        for field in fields:
            if field not in ECOMMERCE_PRODUCT_FIELDS:
                raise CollectorError(f"unsupported ecommerce field: {field}")
            normalized_fields.append(str(field))
        platform_hint = self.config.get("platform_hint", "auto")
        if platform_hint not in {"auto", "shopify", "independent_ecommerce"}:
            raise CollectorError("platform_hint must be auto, shopify, or independent_ecommerce")
        return {
            "url": url,
            "fields": normalized_fields,
            "platform_hint": platform_hint,
        }

    async def test(self) -> CollectorTestResult:
        config = self.validate_config()
        html = await _fetch_html(config["url"], self.http_client)
        analysis = analyze_ecommerce_product_page(config["url"], html, config["fields"])
        if not analysis.field_candidates:
            raise CollectorError("ecommerce_product_fields_not_detected")
        return CollectorTestResult(
            status="ok",
            message="Product page fields were detected.",
            logs=[
                collector_log(
                    "ecommerce_product_page_tested",
                    f"Detected {len(analysis.field_candidates)} candidate fields.",
                )
            ],
        )

    async def collect(self) -> CollectionResult:
        config = self.validate_config()
        html = await _fetch_html(config["url"], self.http_client)
        analysis = analyze_ecommerce_product_page(config["url"], html, config["fields"])
        content = analysis.to_raw_content()
        return CollectionResult(
            raw_records=[
                CollectorRawRecord(
                    record_type=self.collector_type,
                    source_url=config["url"],
                    content=content,
                    collected_at=datetime.now(UTC),
                )
            ],
            logs=[
                collector_log(
                    "ecommerce_product_page_collected",
                    f"Collected product page with {len(analysis.field_candidates)} fields.",
                )
            ],
            errors=[],
        )


@dataclass(frozen=True)
class FieldCandidate:
    key: str
    label: str
    value: str | int | float | bool | None
    data_type: str
    source: str
    confidence: float
    selected: bool
    cleaning_rule: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "value": self.value,
            "data_type": self.data_type,
            "source": self.source,
            "confidence": self.confidence,
            "selected": self.selected,
            "cleaning_rule": self.cleaning_rule,
        }


@dataclass(frozen=True)
class PlatformProfile:
    platform_type: str
    confidence: float
    indicators: list[str]
    risk_level: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform_type": self.platform_type,
            "confidence": self.confidence,
            "indicators": self.indicators,
            "risk_level": self.risk_level,
        }


@dataclass(frozen=True)
class PageStructure:
    page_type: str
    title: str | None
    canonical_url: str | None
    script_count: int
    form_count: int
    image_count: int
    product_schema_count: int
    same_origin_link_count: int
    text_sample: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_type": self.page_type,
            "title": self.title,
            "canonical_url": self.canonical_url,
            "script_count": self.script_count,
            "form_count": self.form_count,
            "image_count": self.image_count,
            "product_schema_count": self.product_schema_count,
            "same_origin_link_count": self.same_origin_link_count,
            "text_sample": self.text_sample,
        }


@dataclass(frozen=True)
class EcommerceProductAnalysis:
    url: str
    platform_profile: PlatformProfile
    page_structure: PageStructure
    field_candidates: list[FieldCandidate]
    tool_recommendations: list[dict[str, Any]]
    cleaning_plan: list[dict[str, str]]
    selected_fields: list[str]

    def extracted_fields(self) -> dict[str, Any]:
        return {
            candidate.key: candidate.value
            for candidate in self.field_candidates
            if candidate.selected and candidate.value is not None
        }

    def to_raw_content(self) -> dict[str, Any]:
        return {
            "provider": "ecommerce",
            "kind": "product_page",
            "url": self.url,
            "platform_profile": self.platform_profile.to_dict(),
            "page_structure": self.page_structure.to_dict(),
            "field_schema": [candidate.to_dict() for candidate in self.field_candidates],
            "selected_fields": self.selected_fields,
            "extracted_fields": self.extracted_fields(),
            "tool_recommendations": self.tool_recommendations,
            "cleaning_plan": self.cleaning_plan,
        }


async def _fetch_html(url: str, http_client: httpx.AsyncClient | None) -> str:
    collector = GenericWebCollector(
        {"url": url, "extract_mode": "full_html"},
        http_client=http_client,
    )
    result = await collector.collect()
    if not result.raw_records:
        raise CollectorError("ecommerce_product_page_empty_response")
    content = result.raw_records[0].content
    html_content = content.get("html_content") if isinstance(content, dict) else None
    if not isinstance(html_content, str):
        raise CollectorError("ecommerce_product_page_missing_html")
    return html_content


def analyze_ecommerce_product_page(
    url: str,
    html: str,
    selected_fields: list[str] | None = None,
) -> EcommerceProductAnalysis:
    requested_fields = selected_fields or list(ECOMMERCE_PRODUCT_FIELDS)
    inspector = _EcommerceHtmlInspector(url)
    inspector.feed(html)
    products = list(_iter_jsonld_products(inspector.jsonld_documents))
    product = products[0] if products else {}
    extracted = _extract_product_fields(product, inspector, url)
    field_candidates = _field_candidates(extracted, requested_fields)
    platform = _platform_profile(url, html, inspector, products)
    structure = PageStructure(
        page_type="product_detail" if products or extracted.get("price") else "ecommerce_page",
        title=_text(extracted.get("title")) or inspector.title,
        canonical_url=_text(extracted.get("canonical_url")) or inspector.canonical_url,
        script_count=inspector.script_count,
        form_count=inspector.form_count,
        image_count=inspector.image_count,
        product_schema_count=len(products),
        same_origin_link_count=inspector.same_origin_link_count,
        text_sample=" ".join(inspector.text_parts).strip()[:360],
    )
    return EcommerceProductAnalysis(
        url=url,
        platform_profile=platform,
        page_structure=structure,
        field_candidates=field_candidates,
        tool_recommendations=_tool_recommendations(platform, structure, field_candidates),
        cleaning_plan=_cleaning_plan(field_candidates),
        selected_fields=requested_fields,
    )


class _EcommerceHtmlInspector(HTMLParser):
    def __init__(self, final_url: str) -> None:
        super().__init__()
        self.final_url = final_url
        self.title_parts: list[str] = []
        self.title: str | None = None
        self.canonical_url: str | None = None
        self.meta: dict[str, str] = {}
        self.jsonld_documents: list[Any] = []
        self.script_count = 0
        self.form_count = 0
        self.image_count = 0
        self.same_origin_link_count = 0
        self.text_parts: list[str] = []
        self._in_title = False
        self._in_jsonld = False
        self._jsonld_parts: list[str] = []
        self._ignore_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = tag.lower()
        attrs_by_name = {name.lower(): value or "" for name, value in attrs}
        if tag_name == "title":
            self._in_title = True
        if tag_name == "script":
            self.script_count += 1
            script_type = attrs_by_name.get("type", "").lower()
            self._in_jsonld = script_type == "application/ld+json"
            self._jsonld_parts = []
            self._ignore_depth += 1
        if tag_name in {"style", "noscript"}:
            self._ignore_depth += 1
        if tag_name == "form":
            self.form_count += 1
        if tag_name == "img":
            self.image_count += 1
        if tag_name == "meta":
            key = attrs_by_name.get("property") or attrs_by_name.get("name")
            content = attrs_by_name.get("content", "").strip()
            if key and content:
                self.meta[key.lower()] = content
        if tag_name == "link":
            rel = attrs_by_name.get("rel", "").lower()
            href = attrs_by_name.get("href", "").strip()
            if "canonical" in rel and href:
                self.canonical_url = urljoin(self.final_url, href)
        if tag_name == "a":
            href = attrs_by_name.get("href", "").strip()
            if href and _origin(urljoin(self.final_url, href)) == _origin(self.final_url):
                self.same_origin_link_count += 1

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

    def handle_data(self, data: str) -> None:
        normalized = " ".join(data.split())
        if self._in_title and normalized:
            self.title_parts.append(normalized)
        if self._in_jsonld:
            self._jsonld_parts.append(data)
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


def _iter_jsonld_products(documents: list[Any]) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    for document in documents:
        products.extend(_find_products(document))
    return products


def _find_products(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        products: list[dict[str, Any]] = []
        for item in value:
            products.extend(_find_products(item))
        return products
    if not isinstance(value, dict):
        return []
    found: list[dict[str, Any]] = []
    if _jsonld_type_matches(value.get("@type"), "Product"):
        found.append(value)
    graph = value.get("@graph")
    if isinstance(graph, list):
        for item in graph:
            found.extend(_find_products(item))
    return found


def _jsonld_type_matches(value: Any, expected: str) -> bool:
    if isinstance(value, str):
        return value.lower() == expected.lower()
    if isinstance(value, list):
        return any(_jsonld_type_matches(item, expected) for item in value)
    return False


def _extract_product_fields(
    product: dict[str, Any],
    inspector: _EcommerceHtmlInspector,
    url: str,
) -> dict[str, Any]:
    offer = _first_dict(product.get("offers"))
    brand = product.get("brand")
    if isinstance(brand, dict):
        brand_value: Any = brand.get("name")
    else:
        brand_value = brand
    image = product.get("image") or inspector.meta.get("og:image")
    if isinstance(image, list):
        image = next((item for item in image if isinstance(item, str)), None)
    price = _number(offer.get("price") if offer else None)
    if price is None:
        price = _number(inspector.meta.get("product:price:amount"))
    return {
        "title": _text(product.get("name"))
        or inspector.meta.get("og:title")
        or inspector.title,
        "price": price,
        "currency": _text(offer.get("priceCurrency") if offer else None)
        or inspector.meta.get("product:price:currency"),
        "availability": _availability(_text(offer.get("availability") if offer else None)),
        "sku": _text(product.get("sku")) or _text(product.get("mpn")),
        "brand": _text(brand_value),
        "description": _text(product.get("description")) or inspector.meta.get("og:description"),
        "image_url": urljoin(url, image) if isinstance(image, str) else None,
        "canonical_url": inspector.canonical_url or _text(product.get("url")) or url,
    }


def _first_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return next((item for item in value if isinstance(item, dict)), None)
    return None


def _field_candidates(
    extracted: dict[str, Any],
    selected_fields: list[str],
) -> list[FieldCandidate]:
    labels = {
        "title": "商品标题",
        "price": "价格",
        "currency": "货币",
        "availability": "库存状态",
        "sku": "SKU",
        "brand": "品牌",
        "description": "描述",
        "image_url": "主图",
        "canonical_url": "规范 URL",
    }
    candidates: list[FieldCandidate] = []
    for key in ECOMMERCE_PRODUCT_FIELDS:
        value = extracted.get(key)
        candidates.append(
            FieldCandidate(
                key=key,
                label=labels[key],
                value=value,
                data_type=_data_type(value, key),
                source="json_ld_or_meta" if value is not None else "missing",
                confidence=_field_confidence(value, key),
                selected=key in selected_fields and value is not None,
                cleaning_rule=_cleaning_rule(key),
            )
        )
    return candidates


def _platform_profile(
    url: str,
    html: str,
    inspector: _EcommerceHtmlInspector,
    products: list[dict[str, Any]],
) -> PlatformProfile:
    lowered = html.lower()
    indicators: list[str] = []
    host = urlparse(url).hostname or ""
    if "myshopify.com" in host or "cdn.shopify.com" in lowered:
        indicators.append("Shopify asset or host marker")
    if "shopify-section" in lowered or "/cart.js" in lowered or "shopify.theme" in lowered:
        indicators.append("Shopify theme runtime marker")
    if products:
        indicators.append("schema.org Product JSON-LD")
    if inspector.meta.get("product:price:amount"):
        indicators.append("product price meta")
    platform_type = (
        "shopify"
        if any("Shopify" in item for item in indicators)
        else "independent_ecommerce"
    )
    confidence = min(0.95, 0.35 + len(indicators) * 0.18)
    risk_level = "medium" if inspector.form_count > 0 or inspector.script_count > 12 else "low"
    return PlatformProfile(
        platform_type=platform_type,
        confidence=round(confidence, 2),
        indicators=indicators or ["generic ecommerce page markers"],
        risk_level=risk_level,
    )


def _tool_recommendations(
    platform: PlatformProfile,
    structure: PageStructure,
    fields: list[FieldCandidate],
) -> list[dict[str, Any]]:
    detected_fields = [field for field in fields if field.value is not None]
    recommendations = [
        {
            "tool": "ecommerce_product_page",
            "collector_type": "ecommerce_product_page",
            "fit": "primary",
            "risk_level": platform.risk_level,
            "reason": "商品结构字段已从 JSON-LD 或 meta 中识别，可直接进入结构化采集。",
        }
    ]
    if structure.script_count > 12 or len(detected_fields) < 3:
        recommendations.insert(
            0,
            {
                "tool": "Playwright browser snapshot",
                "collector_type": "browser_runtime_candidate",
                "fit": "fallback",
                "risk_level": "medium",
                "reason": "页面脚本较多或字段不足，后续应使用浏览器运行时复核动态渲染字段。",
            },
        )
    recommendations.append(
        {
            "tool": "Generic Web",
            "collector_type": "generic_web",
            "fit": "evidence",
            "risk_level": "low",
            "reason": "保留原始页面快照用于证据追溯和字段漂移对比。",
        }
    )
    return recommendations


def _cleaning_plan(fields: list[FieldCandidate]) -> list[dict[str, str]]:
    return [
        {
            "field": field.key,
            "operation": field.cleaning_rule,
            "description": _cleaning_description(field.key),
        }
        for field in fields
        if field.selected
    ]


def _cleaning_rule(key: str) -> str:
    if key == "price":
        return "parse_decimal"
    if key in {"image_url", "canonical_url"}:
        return "normalize_url"
    if key == "availability":
        return "normalize_enum"
    return "strip_text"


def _cleaning_description(key: str) -> str:
    descriptions = {
        "price": "去除货币符号和千分位，保存为 decimal number。",
        "image_url": "转为绝对 URL，去除空白和无效协议。",
        "canonical_url": "转为绝对 URL，用于去重和回溯。",
        "availability": "归一化为 in_stock、out_of_stock 或 unknown。",
    }
    return descriptions.get(key, "去除首尾空白，保留原始语义。")


def _origin(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        return ""
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{parsed.hostname}{port}"


def _availability(value: str | None) -> str | None:
    if value is None:
        return None
    lowered = value.lower()
    if "instock" in lowered or "in_stock" in lowered:
        return "in_stock"
    if "outofstock" in lowered or "out_of_stock" in lowered or "soldout" in lowered:
        return "out_of_stock"
    return value.rsplit("/", maxsplit=1)[-1].strip() or value


def _data_type(value: Any, key: str) -> str:
    if key == "price":
        return "number"
    if key in {"image_url", "canonical_url"}:
        return "url"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int | float):
        return "number"
    return "string"


def _field_confidence(value: Any, key: str) -> float:
    if value is None:
        return 0.0
    if key in {"title", "price", "canonical_url"}:
        return 0.92
    return 0.78


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = " ".join(value.split())
    return stripped or None


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if not isinstance(value, str):
        return None
    match = re.search(r"-?\d+(?:[,.]\d+)*(?:\.\d+)?", value)
    if match is None:
        return None
    normalized = match.group(0).replace(",", "")
    try:
        return float(normalized)
    except ValueError:
        return None
