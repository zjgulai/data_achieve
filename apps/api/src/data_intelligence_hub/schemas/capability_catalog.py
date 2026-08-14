from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlatformId(StrEnum):
    YOUTUBE = "youtube"
    REDDIT = "reddit"
    X = "x"
    INSTAGRAM = "instagram"
    THREADS = "threads"
    TIKTOK = "tiktok"
    LINKEDIN = "linkedin"


class AccessChannel(StrEnum):
    OFFICIAL_AUTHORIZED_API = "official_authorized_api"
    LICENSED_PARTNER_DATA_SERVICE = "licensed_partner_data_service"
    PUBLIC_WEB_FEED = "public_web_feed"
    AUTHORIZED_BROWSER = "authorized_browser"
    MANAGED_OPAQUE_COLLECTOR = "managed_opaque_collector"
    AUTHORIZED_EXPORT_IMPORT = "authorized_export_import"


class ResourceType(StrEnum):
    CONTENT = "content"
    CONVERSATION = "conversation"
    CREATOR = "creator"
    TOPIC = "topic"
    METRICS = "metrics"
    MEDIA_LIVE = "media_live"
    COMMERCE_ADS = "commerce_ads"
    RELATIONSHIP_GRAPH = "relationship_graph"


class CapabilityOperation(StrEnum):
    RESOLVE_DETAIL = "resolve_detail"
    SEARCH_DISCOVER = "search_discover"
    LIST_ENUMERATE = "list_enumerate"
    MONITOR_INCREMENTAL = "monitor_incremental"
    BACKFILL_HISTORY = "backfill_history"
    BATCH_PARSE = "batch_parse"
    EXPORT_DOWNLOAD = "export_download"


class CapabilityStatus(StrEnum):
    UNKNOWN = "unknown"
    CANDIDATE = "candidate"
    VERIFIED = "verified"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    UNSUPPORTED = "unsupported"
    DEPRECATED = "deprecated"


class DeliveryForm(StrEnum):
    ENDPOINT = "endpoint"
    SDK = "sdk"
    ACTOR = "actor"
    COLLECTOR = "collector"
    PARSER = "parser"
    WORKFLOW = "workflow"
    SKILL = "skill"
    MCP = "mcp"
    AGENT = "agent"


class DeploymentMode(StrEnum):
    OFFICIAL_CLOUD = "official_cloud"
    MANAGED_SAAS = "managed_saas"
    BYOK = "byok"
    SELF_HOSTED = "self_hosted"
    BROWSER_RUNTIME = "browser_runtime"
    MANUAL_IMPORT = "manual_import"


class EvidenceType(StrEnum):
    OFFICIAL_DOC = "official_doc"
    PUBLIC_MARKET = "public_market"
    REPOSITORY = "repository"
    FIXTURE = "fixture"
    AUTHORIZED_RUNTIME = "authorized_runtime"


class ConstraintSeverity(StrEnum):
    BLOCKING = "blocking"
    MAJOR = "major"
    MINOR = "minor"


class CapabilitySdkSelection(ContractModel):
    package: str
    import_name: str | None = None
    source_url: str
    status: Literal["selected", "candidate", "manual_review", "blocked"]
    reason: str


class CapabilityScoreProfile(ContractModel):
    coverage: int = Field(ge=1, le=5)
    freshness: int = Field(ge=1, le=5)
    history: int = Field(ge=1, le=5)
    reliability: int = Field(ge=1, le=5)
    schema_stability: int = Field(ge=1, le=5)
    cost_efficiency: int = Field(ge=1, le=5)
    maintainability: int = Field(ge=1, le=5)
    evidence_confidence: int = Field(ge=1, le=5)


class CapabilityConstraint(ContractModel):
    constraint_type: Literal["policy", "blocked_action", "quota", "purpose", "region"]
    severity: ConstraintSeverity
    code: str
    details: dict[str, Any] = Field(default_factory=dict)


class CapabilityEvidence(ContractModel):
    schema_version: Literal["capability_evidence.v1"]
    evidence_id: str
    evidence_type: EvidenceType
    source_url: str
    source_version: str
    observed_at: datetime
    content_hash: str = Field(min_length=64, max_length=64)
    hash_scope: Literal["source_reference_only", "retrieved_content"]
    evidence_grade: str
    provider_call_attempted: bool = False
    credential_read_attempted: bool = False
    live_client_created: bool = False
    production_write_attempted: bool = False


class CapabilityImplementation(ContractModel):
    schema_version: Literal["capability_implementation.v1"]
    implementation_id: str
    provider_id: str
    platform: PlatformId
    access_channel: AccessChannel
    delivery_form: DeliveryForm
    deployment_mode: DeploymentMode
    data_domains: list[str]
    resource_groups: list[str]
    official_docs: list[str]
    sdk_selection: CapabilitySdkSelection | None = None
    live_adapter_strategy: str
    auth_mode: str
    quota_hint: dict[str, Any]
    cost_hint: dict[str, Any]
    policy_flags: list[str]
    blocked_actions: list[str]
    stability: Literal["high", "medium", "low"]
    self_host_priority: str
    api_version: str
    required_credentials: list[str]
    supported_endpoints: list[str]
    lifecycle_status: Literal["active", "limited", "deprecated"]


class CapabilityAssertion(ContractModel):
    schema_version: Literal["capability_assertion.v1"]
    assertion_id: str
    implementation_id: str
    resource_type: ResourceType
    operation: CapabilityOperation
    support_status: CapabilityStatus
    source_resource_group: str
    region_scope: list[str]
    purpose_scope: list[str]
    auth_scope: list[str]
    field_contract: dict[str, Any]
    constraints: list[CapabilityConstraint]
    score_profile: CapabilityScoreProfile
    evidence_refs: list[str] = Field(min_length=1)
    last_verified_at: datetime


class CapabilityCatalog(ContractModel):
    schema_version: Literal["capability_catalog.v1"]
    evidence_level: str
    provider_call: Literal[False] = False
    production_write_allowed: Literal[False] = False
    generated_at: datetime
    implementations: list[CapabilityImplementation]
    assertions: list[CapabilityAssertion]
    evidence: list[CapabilityEvidence]

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        implementation_ids = [item.implementation_id for item in self.implementations]
        assertion_ids = [item.assertion_id for item in self.assertions]
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(implementation_ids) != len(set(implementation_ids)):
            raise ValueError("duplicate implementation_id")
        if len(assertion_ids) != len(set(assertion_ids)):
            raise ValueError("duplicate assertion_id")
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("duplicate evidence_id")

        implementation_set = set(implementation_ids)
        evidence_set = set(evidence_ids)
        for assertion in self.assertions:
            if assertion.implementation_id not in implementation_set:
                raise ValueError(
                    f"unknown implementation_id: {assertion.implementation_id}"
                )
            for evidence_ref in assertion.evidence_refs:
                if evidence_ref not in evidence_set:
                    raise ValueError(f"unknown evidence_ref: {evidence_ref}")
        return self
