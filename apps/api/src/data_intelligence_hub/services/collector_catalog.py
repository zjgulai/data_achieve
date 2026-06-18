from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.collector import Collector
from data_intelligence_hub.repositories.collectors import get_collector_by_type, list_collectors


@dataclass(frozen=True)
class CollectorDefinition:
    type: str
    name: str
    description: str
    config_schema: dict[str, Any]


COLLECTOR_CATALOG: tuple[CollectorDefinition, ...] = (
    CollectorDefinition(
        type="github_repo",
        name="GitHub Repo",
        description="Monitor a public GitHub repository.",
        config_schema={
            "required": ["owner", "repo"],
            "properties": {"owner": "string", "repo": "string"},
        },
    ),
    CollectorDefinition(
        type="github_topic",
        name="GitHub Topic",
        description="Discover public repositories by GitHub topic.",
        config_schema={
            "required": ["topic"],
            "properties": {"topic": "string", "max_results": "integer"},
        },
    ),
    CollectorDefinition(
        type="generic_web",
        name="Generic Web Page",
        description="Monitor a single public web page.",
        config_schema={
            "required": ["url"],
            "properties": {"url": "string", "extract_mode": "string"},
        },
    ),
    CollectorDefinition(
        type="manual_json",
        name="Manual JSON",
        description="Import structured JSON payloads manually.",
        config_schema={
            "required": ["entity_type", "json_data"],
            "properties": {"entity_type": "string", "json_data": "object"},
        },
    ),
    CollectorDefinition(
        type="ecommerce_product_discovery",
        name="Ecommerce Product Discovery",
        description="Discover product URLs from a public independent-site listing or sitemap page.",
        config_schema={
            "required": ["url"],
            "properties": {
                "url": "string",
                "max_products": "integer",
                "platform_hint": "string",
            },
        },
    ),
    CollectorDefinition(
        type="ecommerce_product_page",
        name="Ecommerce Product Page",
        description="Parse a public independent-site product page into structured product fields.",
        config_schema={
            "required": ["url"],
            "properties": {
                "url": "string",
                "fields": "array",
                "platform_hint": "string",
            },
        },
    ),
)


async def ensure_collectors_seeded(session: AsyncSession) -> None:
    existing = {collector.type for collector in await list_collectors(session)}
    for definition in COLLECTOR_CATALOG:
        if definition.type not in existing:
            session.add(
                Collector(
                    type=definition.type,
                    name=definition.name,
                    description=definition.description,
                    config_schema=definition.config_schema,
                    enabled=True,
                )
            )
    await session.flush()


async def require_collector(session: AsyncSession, collector_type: str) -> Collector:
    await ensure_collectors_seeded(session)
    collector = await get_collector_by_type(session, collector_type)
    if collector is None or not collector.enabled:
        from data_intelligence_hub.services.exceptions import CollectorNotFoundError

        raise CollectorNotFoundError
    return collector


def validate_collector_config(collector_type: str, config: dict[str, Any]) -> dict[str, Any]:
    if collector_type == "github_repo":
        return _validate_github_repo_config(config)
    if collector_type == "github_topic":
        return _validate_github_topic_config(config)
    if collector_type == "generic_web":
        return _validate_generic_web_config(config)
    if collector_type == "manual_json":
        return _validate_manual_json_config(config)
    if collector_type == "ecommerce_product_page":
        return _validate_ecommerce_product_page_config(config)
    if collector_type == "ecommerce_product_discovery":
        return _validate_ecommerce_product_discovery_config(config)

    from data_intelligence_hub.services.exceptions import CollectorNotFoundError

    raise CollectorNotFoundError


def _require_text(config: dict[str, Any], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or value.strip() == "":
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    return value.strip()


def _validate_github_repo_config(config: dict[str, Any]) -> dict[str, Any]:
    return {"owner": _require_text(config, "owner"), "repo": _require_text(config, "repo")}


def _validate_github_topic_config(config: dict[str, Any]) -> dict[str, Any]:
    topic = _require_text(config, "topic")
    max_results = config.get("max_results", 30)
    if not isinstance(max_results, int) or max_results < 1 or max_results > 100:
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    return {"topic": topic, "max_results": max_results}


def _validate_generic_web_config(config: dict[str, Any]) -> dict[str, Any]:
    url = _require_text(config, "url")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    extract_mode = config.get("extract_mode", "main_content")
    if extract_mode not in {"full_html", "main_content"}:
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    return {"url": url, "extract_mode": extract_mode}


def _validate_manual_json_config(config: dict[str, Any]) -> dict[str, Any]:
    entity_type = _require_text(config, "entity_type")
    json_data = config.get("json_data")
    if not isinstance(json_data, dict | list):
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    return {"entity_type": entity_type, "json_data": json_data}


def _validate_ecommerce_product_page_config(config: dict[str, Any]) -> dict[str, Any]:
    url = _require_text(config, "url")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    fields = config.get(
        "fields",
        [
            "title",
            "price",
            "currency",
            "availability",
            "sku",
            "brand",
            "description",
            "image_url",
            "canonical_url",
        ],
    )
    allowed_fields = {
        "title",
        "price",
        "currency",
        "availability",
        "sku",
        "brand",
        "description",
        "image_url",
        "canonical_url",
    }
    if not isinstance(fields, list) or not fields:
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    normalized_fields: list[str] = []
    for field in fields:
        if not isinstance(field, str) or field not in allowed_fields:
            from data_intelligence_hub.services.exceptions import CollectorConfigError

            raise CollectorConfigError
        normalized_fields.append(field)
    platform_hint = config.get("platform_hint", "auto")
    if platform_hint not in {"auto", "shopify", "independent_ecommerce"}:
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    return {"url": url, "fields": normalized_fields, "platform_hint": platform_hint}


def _validate_ecommerce_product_discovery_config(config: dict[str, Any]) -> dict[str, Any]:
    url = _require_text(config, "url")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    max_products = config.get("max_products", 50)
    if not isinstance(max_products, int) or max_products < 1 or max_products > 200:
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    platform_hint = config.get("platform_hint", "auto")
    if platform_hint not in {"auto", "shopify", "independent_ecommerce"}:
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    return {"url": url, "max_products": max_products, "platform_hint": platform_hint}
