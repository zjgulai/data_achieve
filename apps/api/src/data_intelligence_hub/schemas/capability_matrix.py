from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from data_intelligence_hub.schemas.capability_catalog import (
    AccessChannel,
    CapabilityAssertion,
    CapabilityEvidence,
    CapabilityImplementation,
    CapabilityOperation,
    CapabilityStatus,
    ContractModel,
    PlatformId,
    ResourceType,
)


class CapabilityMatrixCell(ContractModel):
    platform: PlatformId
    access_channel: AccessChannel
    summary_status: CapabilityStatus
    status_counts: dict[CapabilityStatus, int]
    implementation_ids: list[str]
    assertion_ids: list[str]
    resource_types: list[ResourceType]
    operations: list[CapabilityOperation]
    constraint_codes: list[str]
    evidence_count: int = Field(ge=0)
    last_verified_at: datetime | None


class CapabilityMatrixSummary(ContractModel):
    cell_count: Literal[42]
    populated_cell_count: int = Field(ge=0, le=42)
    unknown_cell_count: int = Field(ge=0, le=42)
    implementation_count: int = Field(ge=0)
    assertion_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)


class CapabilityMatrixResponse(ContractModel):
    schema_version: Literal["capability_matrix.v1"]
    generated_at: datetime
    evidence_level: str
    provider_call: Literal[False] = False
    production_write_allowed: Literal[False] = False
    platforms: list[PlatformId]
    access_channels: list[AccessChannel]
    cells: list[CapabilityMatrixCell]
    summary: CapabilityMatrixSummary


class CapabilityImplementationDetail(ContractModel):
    schema_version: Literal["capability_implementation_detail.v1"]
    implementation: CapabilityImplementation
    assertions: list[CapabilityAssertion]
    evidence: list[CapabilityEvidence]
