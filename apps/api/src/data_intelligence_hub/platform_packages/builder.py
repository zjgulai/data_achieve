from __future__ import annotations

import hashlib
import json
from collections import defaultdict

from data_intelligence_hub.platform_packages.models import (
    PackageEndpoint,
    PlatformPackage,
    PlatformPackageCatalog,
)
from data_intelligence_hub.schemas.collector_catalog import CollectorCatalogResponse


def _display_name(platform_id: str) -> str:
    aliases = {
        "x": "X (Twitter)",
        "xiaohongshu": "小红书",
        "douyin": "抖音",
        "bilibili": "B站",
        "weibo": "微博",
        "kuaishou": "快手",
        "wechat": "微信",
        "zhihu": "知乎",
        "web": "开放网络",
        "rss": "RSS",
        "regulatory": "监管公告",
    }
    return aliases.get(platform_id, platform_id.replace("_", " ").title())


def build_platform_package_catalog(
    source: CollectorCatalogResponse,
) -> PlatformPackageCatalog:
    unique_endpoint_types: set[str] = set()
    canonical_capabilities: dict[str, str] = {}
    by_platform: dict[str, list[PackageEndpoint]] = defaultdict(list)
    source_entry_count = 0
    for group in source.collectors:
        for index, endpoint in enumerate(group.endpoints):
            source_entry_count += 1
            unique_endpoint_types.add(endpoint.endpoint_type)
            capability_id = (
                f"{endpoint.platform}:{group.collector_type}:"
                f"{endpoint.endpoint_type}:{index}"
            )
            canonical_id = canonical_capabilities.setdefault(
                endpoint.endpoint_type,
                capability_id,
            )
            packaged = PackageEndpoint(
                capability_id=capability_id,
                canonical_capability_id=canonical_id,
                is_alias_view=canonical_id != capability_id,
                endpoint_type=endpoint.endpoint_type,
                label=endpoint.label,
                platform=endpoint.platform,
                description=endpoint.description,
                status=endpoint.status,
                required_params=tuple(endpoint.required_params),
                optional_params=tuple(endpoint.optional_params),
                cost_hint=endpoint.cost_hint,
                provider=endpoint.provider,
                provider_group=group.collector_type,
                provider_label=group.label,
                content_type=endpoint.content_type,
                method=endpoint.method,
                param_fields=dict(endpoint.param_fields),
            )
            by_platform[endpoint.platform].append(packaged)

    packages = tuple(
        _build_package(platform_id, endpoints)
        for platform_id, endpoints in sorted(by_platform.items())
    )
    digest_payload = [package.model_dump(mode="json") for package in packages]
    digest = hashlib.sha256(
        json.dumps(digest_payload, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    return PlatformPackageCatalog(
        schema_version="platform-packages.v1",
        catalog_digest=digest,
        source_entry_count=source_entry_count,
        unique_endpoint_count=len(unique_endpoint_types),
        capability_count=sum(len(package.endpoints) for package in packages),
        platform_count=len(packages),
        packages=packages,
    )


def _build_package(
    platform_id: str,
    endpoints: list[PackageEndpoint],
) -> PlatformPackage:
    ordered = tuple(sorted(endpoints, key=lambda item: item.endpoint_type))
    display_name = _display_name(platform_id)
    return PlatformPackage(
        platform_id=platform_id,
        display_name=display_name,
        description=f"{display_name} 数据采集能力包，统一提供 Skill、MCP 与 Playbook。",
        endpoint_count=len(ordered),
        verified_count=sum(item.status == "verified" for item in ordered),
        disabled_count=sum(item.status == "disabled" for item in ordered),
        provider_groups=tuple(sorted({item.provider_group for item in ordered})),
        methods=tuple(sorted({item.method for item in ordered})),
        content_types=tuple(sorted({item.content_type for item in ordered})),
        endpoints=ordered,
        skill_path=f"generated/platform-skills/{platform_id}",
        playbook_path=f"docs/playbooks/platforms/{platform_id}.md",
        detail_path=f"/skills/{platform_id}",
    )
