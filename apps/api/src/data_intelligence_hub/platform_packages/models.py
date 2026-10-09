from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict


class CapabilityNote(BaseModel):
    """一条平台/端点级坑点（策展来源，见 platform_packages/notes/*.json）。"""

    model_config = ConfigDict(frozen=True)

    scope: Literal["platform", "endpoint"]
    target: str  # platform_id (platform scope) 或 endpoint_type (endpoint scope)
    symptom: str
    cause: str
    workaround: str
    failure_class: str | None = None
    severity: Literal["info", "warning", "blocker"] = "warning"
    verified_at: date | None = None
    source_ref: str | None = None
    tags: tuple[str, ...] = ()


class PackageEndpoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    capability_id: str
    canonical_capability_id: str
    is_alias_view: bool
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
    notes: tuple[CapabilityNote, ...] = ()


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
    platform_notes: tuple[CapabilityNote, ...] = ()


class PlatformPackageCatalog(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str
    catalog_digest: str
    source_entry_count: int
    unique_endpoint_count: int
    capability_count: int
    platform_count: int
    packages: tuple[PlatformPackage, ...]
