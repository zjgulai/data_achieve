from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PackageEndpoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    capability_id: str
    endpoint_type: str
    label: str
    platform: str
    description: str
    status: str
    required_params: tuple[str, ...]
    optional_params: tuple[str, ...]
    cost_hint: str | None
    provider: str
    provider_group: str
    provider_label: str
    content_type: str
    method: str
    param_fields: dict[str, str]


class PlatformPackage(BaseModel):
    model_config = ConfigDict(frozen=True)

    platform_id: str
    display_name: str
    description: str
    endpoint_count: int
    verified_count: int
    disabled_count: int
    provider_groups: tuple[str, ...]
    methods: tuple[str, ...]
    content_types: tuple[str, ...]
    endpoints: tuple[PackageEndpoint, ...]
    skill_path: str
    playbook_path: str
    detail_path: str


class PlatformPackageCatalog(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str
    catalog_digest: str
    source_entry_count: int
    unique_endpoint_count: int
    capability_count: int
    platform_count: int
    packages: tuple[PlatformPackage, ...]
