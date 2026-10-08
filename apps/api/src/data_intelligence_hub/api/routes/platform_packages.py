from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict

from data_intelligence_hub.platform_packages.models import (
    PlatformPackage,
    PlatformPackageCatalog,
)
from data_intelligence_hub.platform_packages.service import (
    PlatformPackageNotFoundError,
    build_platform_skill_archive,
    get_platform_package,
    get_platform_package_catalog,
    get_platform_playbook,
)

router = APIRouter(tags=["platform-packages"])


class PlatformPlaybookResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    platform_id: str
    markdown: str


@router.get("", response_model=PlatformPackageCatalog)
async def list_platform_packages(
    query: str | None = Query(default=None, max_length=100),
    status: str | None = Query(default=None, pattern="^(verified|pending|disabled)$"),
) -> PlatformPackageCatalog:
    catalog = await get_platform_package_catalog()
    normalized = query.casefold().strip() if query else None
    packages = tuple(
        package
        for package in catalog.packages
        if _matches(package, normalized, status)
    )
    return catalog.model_copy(update={"packages": packages, "platform_count": len(packages)})


@router.get("/{platform_id}", response_model=PlatformPackage)
async def read_platform_package(platform_id: str) -> PlatformPackage:
    try:
        return await get_platform_package(platform_id)
    except PlatformPackageNotFoundError as exc:
        raise HTTPException(status_code=404, detail="platform_package_not_found") from exc


@router.get("/{platform_id}/playbook", response_model=PlatformPlaybookResponse)
async def read_platform_playbook(platform_id: str) -> PlatformPlaybookResponse:
    try:
        markdown = await get_platform_playbook(platform_id)
    except PlatformPackageNotFoundError as exc:
        raise HTTPException(status_code=404, detail="platform_package_not_found") from exc
    return PlatformPlaybookResponse(platform_id=platform_id, markdown=markdown)


@router.get("/{platform_id}/download")
async def download_platform_skill(platform_id: str) -> Response:
    try:
        content = await build_platform_skill_archive(platform_id)
    except PlatformPackageNotFoundError as exc:
        raise HTTPException(status_code=404, detail="platform_package_not_found") from exc
    return Response(
        content=content,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{platform_id}-collector-skill.zip"'
            )
        },
    )


def _matches(package: PlatformPackage, query: str | None, status: str | None) -> bool:
    if status and not any(endpoint.status == status for endpoint in package.endpoints):
        return False
    if query is None:
        return True
    values = [package.platform_id, package.display_name, package.description]
    values.extend(endpoint.label for endpoint in package.endpoints)
    values.extend(endpoint.endpoint_type for endpoint in package.endpoints)
    return query in " ".join(values).casefold()
