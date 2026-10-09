from __future__ import annotations

import io
import json
import os
import re
import zipfile
from functools import lru_cache

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.api.routes.collectors import get_collector_catalog
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.platform_packages.builder import build_platform_package_catalog
from data_intelligence_hub.platform_packages.models import (
    PackageEndpoint,
    PlatformPackage,
    PlatformPackageCatalog,
)
from data_intelligence_hub.platform_packages.notes import notes_version
from data_intelligence_hub.platform_packages.renderers import (
    render_playbook,
    render_readme,
    render_skill,
    render_trigger_cases,
)
from data_intelligence_hub.platform_packages.status import (
    GROUP_REQUIREMENTS,
    EndpointEvidence,
    ProviderStatusResponse,
    build_provider_status,
)
from data_intelligence_hub.schemas.collector_catalog import CollectorCatalogResponse


class PlatformPackageNotFoundError(LookupError):
    pass


class CapabilityNotFoundError(LookupError):
    pass


@lru_cache(maxsize=1)
def _build_cached(cache_key: str) -> PlatformPackageCatalog:
    source_json, _, _notes_version = cache_key.partition("\x00")
    source = CollectorCatalogResponse.model_validate_json(source_json)
    return build_platform_package_catalog(source)


async def get_platform_package_catalog() -> PlatformPackageCatalog:
    source = await get_collector_catalog()
    # 缓存键包含策展坑点版本，只改 notes（不改 catalog）时也能失效重建。
    return _build_cached(f"{source.model_dump_json()}\x00{notes_version()}")


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
        files = (
            ("SKILL.md", render_skill(package)),
            ("README.md", render_readme(package)),
            ("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"),
            ("references/playbook.md", render_playbook(package)),
            ("evals/trigger_cases.json", render_trigger_cases(package)),
        )
        for filename, content in files:
            info = zipfile.ZipInfo(filename, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, content.encode())
    return buffer.getvalue()


async def get_provider_status(session: AsyncSession) -> ProviderStatusResponse:
    result = await session.execute(
        select(CollectionTask.name, TaskRun)
        .join(TaskRun, TaskRun.task_id == CollectionTask.id)
        .where(
            or_(
                CollectionTask.name.like("[quick] [test]%"),
                CollectionTask.name.like("[quick] [quick] [test]%"),
            )
        )
        .order_by(TaskRun.created_at.desc())
    )
    evidence: dict[str, EndpointEvidence] = {}
    pattern = re.compile(r"^\[quick\](?: \[quick\])? \[test\] (.+)$")
    for task_name, run in result.all():
        match = pattern.match(task_name)
        if match is None or match.group(1) in evidence:
            continue
        evidence[match.group(1)] = EndpointEvidence(
            status=run.status,
            finished_at=run.finished_at,
            records_count=run.records_count,
            error_message=run.error_message,
        )
    configured_names = {
        name for groups in GROUP_REQUIREMENTS.values() for group in groups for name in group
    }
    configured = {name: bool(os.environ.get(name, "").strip()) for name in configured_names}
    return build_provider_status(
        await get_platform_package_catalog(),
        configured=configured,
        evidence=evidence,
    )
