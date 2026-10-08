from __future__ import annotations

import io
import json
import zipfile
from functools import lru_cache

from data_intelligence_hub.api.routes.collectors import get_collector_catalog
from data_intelligence_hub.platform_packages.builder import build_platform_package_catalog
from data_intelligence_hub.platform_packages.models import (
    PackageEndpoint,
    PlatformPackage,
    PlatformPackageCatalog,
)
from data_intelligence_hub.platform_packages.renderers import (
    render_playbook,
    render_readme,
    render_skill,
    render_trigger_cases,
)
from data_intelligence_hub.schemas.collector_catalog import CollectorCatalogResponse


class PlatformPackageNotFoundError(LookupError):
    pass


class CapabilityNotFoundError(LookupError):
    pass


@lru_cache(maxsize=1)
def _build_cached(source_json: str) -> PlatformPackageCatalog:
    source = CollectorCatalogResponse.model_validate_json(source_json)
    return build_platform_package_catalog(source)


async def get_platform_package_catalog() -> PlatformPackageCatalog:
    source = await get_collector_catalog()
    return _build_cached(source.model_dump_json())


async def get_platform_package(platform_id: str) -> PlatformPackage:
    catalog = await get_platform_package_catalog()
    for package in catalog.packages:
        if package.platform_id == platform_id:
            return package
    raise PlatformPackageNotFoundError(platform_id)


async def get_capability(endpoint_type: str) -> PackageEndpoint:
    catalog = await get_platform_package_catalog()
    for package in catalog.packages:
        for endpoint in package.endpoints:
            if endpoint.endpoint_type == endpoint_type:
                return endpoint
    raise CapabilityNotFoundError(endpoint_type)


async def get_platform_playbook(platform_id: str) -> str:
    return render_playbook(await get_platform_package(platform_id))


async def build_platform_skill_archive(platform_id: str) -> bytes:
    package = await get_platform_package(platform_id)
    catalog = await get_platform_package_catalog()
    manifest = {
        "schema_version": catalog.schema_version,
        "catalog_digest": catalog.catalog_digest,
        **package.model_dump(mode="json"),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("SKILL.md", render_skill(package))
        archive.writestr("README.md", render_readme(package))
        archive.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )
        archive.writestr("references/playbook.md", render_playbook(package))
        archive.writestr("evals/trigger_cases.json", render_trigger_cases(package))
    return buffer.getvalue()
