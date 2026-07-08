from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SocialProviderEndpointItem(BaseModel):
    endpoint_id: str
    auth_scope: str | None = None
    methods: list[str] = Field(default_factory=list)
    data_domain: list[str] = Field(default_factory=list)


class SocialProviderSdkSelection(BaseModel):
    package: str
    import_name: str | None = None
    source_url: str
    status: Literal["selected", "candidate", "manual_review", "blocked"]
    reason: str


class SocialProviderCatalogItem(BaseModel):
    provider_id: str
    platform: str
    data_domain: list[str]
    resource_groups: list[str]
    official_docs: list[str] = Field(default_factory=list)
    sdk_selection: SocialProviderSdkSelection | None = None
    live_adapter_strategy: str = "manual_review"
    auth_mode: str
    quota_hint: dict[str, Any]
    policy_flags: list[str]
    blocked_actions: list[str]
    stability: str
    self_host_priority: str
    api_version: str
    required_credentials: list[str]
    supported_endpoints: list[str]
    endpoint_contracts: list[SocialProviderEndpointItem] = Field(default_factory=list)


class SocialProviderCatalogResponse(BaseModel):
    schema_version: str
    evidence_level: str
    provider_call: bool
    generated_at: str
    providers: list[SocialProviderCatalogItem]


class SocialProviderQuotaRequest(BaseModel):
    requests_per_minute: int | None = Field(default=None, ge=0)
    requests_per_day: int | None = Field(default=None, ge=0)
    requests_per_hour: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)

    def merged_snapshot(self) -> dict[str, Any]:
        return {
            "requests_per_minute": self.requests_per_minute,
            "requests_per_hour": self.requests_per_hour,
            "requests_per_day": self.requests_per_day,
            "estimated_cost_usd": self.estimated_cost_usd,
        }


class SocialProviderPolicyContext(BaseModel):
    allow_ai_training: bool = False
    allow_private_profile_merge: bool = False
    allow_login_state_collection: bool = False
    max_retention_hours: int | None = Field(default=None, ge=1, le=8760)


class SocialProviderReadinessRequest(BaseModel):
    platform: str
    endpoints: list[str] = Field(min_length=1, max_length=40)
    credentials_ready: bool | dict[str, bool] = False
    quotas: SocialProviderQuotaRequest | None = None
    policy_context: SocialProviderPolicyContext | None = None
    dry_run: bool = True


class SocialProviderRateLimitProfile(BaseModel):
    provider_id: str
    requested: dict[str, Any]
    catalog_hint: dict[str, Any]
    budget_status: str
    effective_limits: dict[str, Any]
    estimated_cost_usd: float | None = None


class SocialProviderReadinessResponse(BaseModel):
    schema_version: str = "social_provider_readiness.v1"
    platform: str
    provider_id: str
    readiness: bool
    missing_credentials: list[str]
    missing_scope: list[str]
    blocked_reasons: list[str]
    policy_blockers: list[str]
    forbidden_actions: list[str]
    rate_limit_profile: SocialProviderRateLimitProfile
    provider_call_allowed: bool
    provider_call_attempted: bool = False
    dry_run: bool
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SocialProviderGateRequest(BaseModel):
    authorized: bool
    platform: str
    provider_id: str | None = None
    credentials_ready: bool | dict[str, bool] = False
    endpoints: list[str] = Field(min_length=1, max_length=40)
    max_requests: int = Field(default=200, ge=1, le=10000)
    max_items: int = Field(default=100, ge=1, le=5000)
    max_cost_usd: float | None = Field(default=None, ge=0)
    retention_hours: int = Field(default=24, ge=1, le=8760)
    approval_id: str = Field(min_length=1, max_length=120)
    allow_ai_training: bool = False
    dry_run: bool = True
    quotas: SocialProviderQuotaRequest | None = None
    policy_context: SocialProviderPolicyContext | None = None


class SocialProviderGateResponse(BaseModel):
    schema_version: str = "social_provider_gate.v1"
    platform: str
    provider_id: str
    provider_call_allowed: bool
    provider_call_attempted: bool
    readiness: bool
    blocked_reasons: list[str]
    policy_blockers: list[str]
    forbidden_actions: list[str]
    max_requests: int
    max_items: int
    max_cost_usd: float | None
    retention_hours: int
    budget_enforcement: dict[str, Any]
    rate_limit_profile: SocialProviderRateLimitProfile
    approval_id: str
    next_required_authorization: str
    run_scope: Literal["fixture_readiness", "fixture_gate_only", "live"] = "fixture_gate_only"
    production_write_allowed: bool = False
    dry_run: bool = True
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SocialProviderLiveApprovalTemplateRequest(BaseModel):
    platform: str
    endpoints: list[str] = Field(min_length=1, max_length=20)
    provider_id: str | None = None
    intended_use: str = Field(min_length=3, max_length=300)
    max_requests: int = Field(default=10, ge=1, le=1000)
    max_items: int = Field(default=50, ge=1, le=1000)
    max_cost_usd: float | None = Field(default=0, ge=0)
    retention_hours: int = Field(default=24, ge=1, le=8760)
    allow_ai_training: bool = False
    credential_reference: str | None = Field(default=None, max_length=200)
    delete_policy: str = Field(default="delete_or_retain_by_policy_gate", max_length=200)


class SocialProviderLiveApprovalTemplateResponse(BaseModel):
    schema_version: str = "social_provider_live_approval_template.v1"
    platform: str
    provider_id: str
    sdk_selection: SocialProviderSdkSelection | None = None
    approval_packet: dict[str, Any]
    required_confirmations: list[str]
    blocked_reasons: list[str]
    provider_call_allowed: bool = False
    provider_call_attempted: bool = False
    dependency_install_allowed: bool = False
    production_write_allowed: bool = False
    next_required_authorization: str
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SocialProviderDependencyGateRequest(BaseModel):
    platform: str
    provider_id: str | None = None
    authorized: bool = False
    approval_id: str | None = Field(default=None, max_length=120)
    confirm_dependency_review: bool = False
    confirm_no_provider_call: bool = True
    confirm_no_credential_read: bool = True
    install_scope: Literal["metadata_only", "local_dev_optional_dependency"] = "metadata_only"
    dry_run: bool = True


class SocialProviderDependencyGateResponse(BaseModel):
    schema_version: str = "social_provider_dependency_gate.v1"
    platform: str
    provider_id: str
    sdk_selection: SocialProviderSdkSelection | None = None
    dependency_install_allowed: bool
    dependency_install_executed: bool = False
    live_adapter_enabled: bool = False
    credential_read_attempted: bool = False
    provider_call_attempted: bool = False
    production_write_allowed: bool = False
    install_scope: Literal["metadata_only", "local_dev_optional_dependency"]
    installation_plan: dict[str, Any]
    blocked_reasons: list[str]
    approval_id: str | None
    next_required_authorization: str
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SocialProviderAdapterPlanRequest(BaseModel):
    platform: str
    provider_id: str | None = None
    endpoints: list[str] = Field(min_length=1, max_length=40)
    mode: Literal["fixture_replay", "live_dry_run"] = "fixture_replay"
    authorized: bool = False
    approval_id: str | None = Field(default=None, max_length=120)
    credential_reference: str | None = Field(default=None, max_length=200)
    max_requests: int = Field(default=10, ge=1, le=1000)
    fixture_limit: int = Field(default=3, ge=1, le=10)


class SocialProviderAdapterPlanResponse(BaseModel):
    schema_version: str = "social_provider_adapter_plan.v1"
    platform: str
    provider_id: str
    sdk_selection: SocialProviderSdkSelection | None = None
    adapter_module: str | None
    dependency_present: bool
    dependency_import_name: str | None
    adapter_ready: bool
    provider_call_allowed: bool = False
    provider_call_attempted: bool = False
    credential_read_attempted: bool = False
    live_client_created: bool = False
    production_write_allowed: bool = False
    fixture_replay_supported: bool = True
    planned_operations: list[dict[str, Any]]
    blocked_reasons: list[str]
    next_required_authorization: str
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SocialProviderSourceTemplateRequest(BaseModel):
    platform: str
    endpoints: list[str] = Field(min_length=1, max_length=40)
    provider_id: str | None = None
    source_name: str | None = Field(default=None, min_length=1, max_length=200)
    project_id: str | None = Field(default=None, max_length=120)
    authorized: bool = False
    approval_id: str | None = Field(default=None, max_length=120)
    credential_reference: str | None = Field(default=None, max_length=200)
    fixture_limit: int = Field(default=3, ge=1, le=10)


class SocialProviderSourceTemplateResponse(BaseModel):
    schema_version: str = "social_provider_source_template.v1"
    platform: str
    provider_id: str
    source_type: Literal["manual_json"] = "manual_json"
    template_strategy: Literal["manual_json_authorized_import"] = "manual_json_authorized_import"
    fixture_only: bool = True
    source_create_allowed: bool = False
    source_created: bool = False
    task_created: bool = False
    provider_call_attempted: bool = False
    credential_read_attempted: bool = False
    production_write_allowed: bool = False
    source_create_payload: dict[str, Any] | None
    blocked_reasons: list[str]
    next_required_authorization: str
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SocialRawPreviewRequest(BaseModel):
    platform: str
    endpoint: str = Field(min_length=1, max_length=120)
    provider_id: str | None = None
    fixture_limit: int = Field(default=3, ge=1, le=10)
    include_live_comparison: bool = False
    authorized: bool = False
    approval_id: str | None = Field(default=None, max_length=120)


class SocialRawPreviewRecord(BaseModel):
    schema_version: str = "social_raw.v1"
    raw_record_id: str
    provider_id: str
    platform: str
    endpoint: str
    source_ref: str
    evidence_ref: str
    author_policy: Literal["hashed", "dropped", "retained_with_approval"] = "hashed"
    payload: dict[str, Any]


class SocialRawPreviewResponse(BaseModel):
    schema_version: str = "social_raw_preview.v1"
    platform: str
    provider_id: str
    endpoint: str
    fixture_only: bool = True
    provider_call_allowed: bool = False
    provider_call_attempted: bool = False
    production_write_allowed: bool = False
    live_comparison_available: bool = False
    blocked_reasons: list[str]
    records: list[SocialRawPreviewRecord]
    sdk_selection: SocialProviderSdkSelection | None = None
    next_required_authorization: str
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
