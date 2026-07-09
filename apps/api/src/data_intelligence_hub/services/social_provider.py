from __future__ import annotations

import importlib
import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from data_intelligence_hub.schemas.social_provider import (
    SocialDatasetPreviewRequest,
    SocialDatasetPreviewResponse,
    SocialDatasetPreviewRow,
    SocialNormalizationPreviewRequest,
    SocialNormalizationPreviewResponse,
    SocialNormalizedPreviewItem,
    SocialProviderAdapterPlanRequest,
    SocialProviderAdapterPlanResponse,
    SocialProviderCatalogItem,
    SocialProviderCatalogResponse,
    SocialProviderDependencyGateRequest,
    SocialProviderDependencyGateResponse,
    SocialProviderEndpointItem,
    SocialProviderGateRequest,
    SocialProviderGateResponse,
    SocialProviderLiveApprovalTemplateRequest,
    SocialProviderLiveApprovalTemplateResponse,
    SocialProviderPolicyContext,
    SocialProviderQuotaRequest,
    SocialProviderRateLimitProfile,
    SocialProviderReadinessRequest,
    SocialProviderReadinessResponse,
    SocialProviderSdkSelection,
    SocialProviderSourceTemplateRequest,
    SocialProviderSourceTemplateResponse,
    SocialRawPreviewRecord,
    SocialRawPreviewRequest,
    SocialRawPreviewResponse,
)
from data_intelligence_hub.services.exceptions import (
    SocialProviderCatalogLoadError,
    SocialProviderGateAuthorizationError,
    SocialProviderUnknownPlatformError,
)

CATALOG_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "social_provider_catalog_overseas.json"
)

OPTIONAL_DEPENDENCY_EXTRAS: dict[str, str] = {
    "youtube.v3": "social-youtube",
    "reddit.praw": "social-reddit",
}

FIXTURE_ADAPTER_MODULES: dict[str, str] = {
    "youtube.v3": "data_intelligence_hub.social_api.youtube.google_api_client",
    "reddit.praw": "data_intelligence_hub.social_api.reddit.asyncpraw",
}

LIVE_APPROVAL_REQUIRED_CONFIRMATIONS = [
    "authorized=true",
    "approval_id_present",
    "credential_reference_secret_manager_or_env",
    "scope_limited_endpoints",
    "max_requests_and_max_items_set",
    "max_cost_usd_set",
    "retention_hours_set",
    "delete_policy_set",
    "allow_ai_training=false",
]


@dataclass(frozen=True)
class _CatalogEnvelope:
    schema_version: str
    evidence_level: str
    provider_call: bool
    generated_at: str
    providers: tuple[SocialProviderCatalogItem, ...]


_CATALOG_CACHE: _CatalogEnvelope | None = None


def _normalize_platform(platform: str) -> str:
    return platform.strip().lower()


def _to_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        normalized_item = item.strip()
        if normalized_item:
            normalized.append(normalized_item)
    return normalized


def _coerce_bool_map(
    value: bool | dict[str, bool],
    required: list[str],
) -> dict[str, bool]:
    if isinstance(value, bool):
        return {credential: bool(value) for credential in required}
    if not isinstance(value, dict):
        return {credential: False for credential in required}

    normalized: dict[str, bool] = {}
    for credential in required:
        normalized[credential] = bool(value.get(credential, False))
    return normalized


def _coerce_non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0:
        return None
    return value


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        if value < 0:
            return None
        return float(value)
    return None


def _to_endpoint_items(endpoints: list[str]) -> list[SocialProviderEndpointItem]:
    return [SocialProviderEndpointItem(endpoint_id=endpoint) for endpoint in endpoints]


def _build_sdk_selection(raw: dict[str, Any]) -> SocialProviderSdkSelection | None:
    sdk_block = raw.get("sdk_selection")
    if not isinstance(sdk_block, dict):
        return None
    package = sdk_block.get("package")
    source_url = sdk_block.get("source_url")
    if not isinstance(package, str) or not isinstance(source_url, str):
        return None
    return SocialProviderSdkSelection(
        package=package,
        import_name=(
            sdk_block["import_name"] if isinstance(sdk_block.get("import_name"), str) else None
        ),
        source_url=source_url,
        status=(
            sdk_block["status"]
            if sdk_block.get("status") in {"selected", "candidate", "manual_review", "blocked"}
            else "manual_review"
        ),
        reason=str(sdk_block.get("reason", "")),
    )


def _build_catalog_item(raw: dict[str, Any]) -> SocialProviderCatalogItem:
    required_fields = {
        "provider_id",
        "platform",
        "quota_hint",
        "policy_flags",
        "blocked_actions",
        "stability",
        "self_host_priority",
        "api_version",
    }
    if not required_fields.issubset(raw):
        raise SocialProviderCatalogLoadError

    required_credentials = _to_text_list(raw.get("required_credentials"))
    supported_endpoints = _to_text_list(raw.get("supported_endpoints"))
    resource_groups = _to_text_list(raw.get("resource_groups"))
    if not resource_groups:
        resource_groups = _to_text_list(raw.get("data_domain"))

    return SocialProviderCatalogItem(
        provider_id=str(raw["provider_id"]),
        platform=_normalize_platform(str(raw["platform"])),
        data_domain=_to_text_list(raw.get("data_domain")),
        resource_groups=resource_groups,
        official_docs=_to_text_list(raw.get("official_docs")),
        sdk_selection=_build_sdk_selection(raw),
        live_adapter_strategy=str(raw.get("live_adapter_strategy", "manual_review")),
        auth_mode=str(raw.get("auth_mode", "")),
        quota_hint=dict(raw.get("quota_hint", {})),
        policy_flags=_to_text_list(raw.get("policy_flags")),
        blocked_actions=_to_text_list(raw.get("blocked_actions")),
        stability=str(raw["stability"]),
        self_host_priority=str(raw["self_host_priority"]),
        api_version=str(raw["api_version"]),
        required_credentials=required_credentials,
        supported_endpoints=supported_endpoints,
        endpoint_contracts=_to_endpoint_items(supported_endpoints),
    )


def _load_catalog() -> _CatalogEnvelope:
    global _CATALOG_CACHE
    if _CATALOG_CACHE is not None:
        return _CATALOG_CACHE

    try:
        raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        catalog = raw["catalog"]
        providers_block = catalog.get("providers")
        if not isinstance(providers_block, list):
            raise SocialProviderCatalogLoadError
        providers = tuple(
            _build_catalog_item(item) for item in providers_block if isinstance(item, dict)
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise SocialProviderCatalogLoadError from exc

    if not providers:
        raise SocialProviderCatalogLoadError

    _CATALOG_CACHE = _CatalogEnvelope(
        schema_version=str(raw.get("schema_version", "external_provider_catalog.v1")),
        evidence_level=str(raw.get("evidence_level", "L1-public-or-runtime")),
        provider_call=bool(raw.get("provider_call", False)),
        generated_at=str(raw.get("generated_at", "")),
        providers=providers,
    )
    return _CATALOG_CACHE


def get_social_provider_catalog(
    platform: str | None = None,
    data_domain: str | None = None,
    resource_group: str | None = None,
) -> SocialProviderCatalogResponse:
    catalog = _load_catalog()
    filtered = list(catalog.providers)

    if platform is not None:
        requested_platform = _normalize_platform(platform)
        filtered = [item for item in filtered if item.platform == requested_platform]
        if not filtered:
            raise SocialProviderUnknownPlatformError

    if data_domain is not None:
        requested_domain = data_domain.strip().lower()
        filtered = [
            item
            for item in filtered
            if requested_domain in {domain.lower() for domain in item.data_domain}
        ]
    if resource_group is not None:
        requested_resource_group = resource_group.strip().lower()
        filtered = [
            item
            for item in filtered
            if requested_resource_group in {group.lower() for group in item.resource_groups}
        ]

    return SocialProviderCatalogResponse(
        schema_version=catalog.schema_version,
        evidence_level=catalog.evidence_level,
        provider_call=catalog.provider_call,
        generated_at=catalog.generated_at,
        providers=filtered,
    )


def _find_provider(platform: str, provider_id: str | None = None) -> SocialProviderCatalogItem:
    catalog = get_social_provider_catalog(platform)
    if provider_id is None:
        if not catalog.providers:
            raise SocialProviderUnknownPlatformError
        return catalog.providers[0]

    for provider in catalog.providers:
        if provider.provider_id == provider_id:
            return provider
    raise SocialProviderUnknownPlatformError


def _missing_endpoints(item: SocialProviderCatalogItem, endpoints: list[str]) -> list[str]:
    known_endpoints = {endpoint for endpoint in item.supported_endpoints}
    return [endpoint for endpoint in endpoints if endpoint not in known_endpoints]


def _policy_blockers(
    item: SocialProviderCatalogItem,
    context: SocialProviderPolicyContext,
) -> list[str]:
    policy_flags = {flag.lower() for flag in item.policy_flags}
    blockers: list[str] = []

    if context.allow_ai_training and any("no_ai_training" in flag for flag in policy_flags):
        blockers.append("policy_disallow_ai_training_not_respected")
    if context.allow_private_profile_merge and any("no_private" in flag for flag in policy_flags):
        blockers.append("policy_private_profile_merge_not_respected")
    if context.allow_login_state_collection and any(
        "no_login_state" in flag for flag in policy_flags
    ):
        blockers.append("policy_login_state_collection_not_respected")

    return blockers


def _as_blocker_reasons(prefix: str, values: list[str]) -> list[str]:
    return [f"{prefix}_missing:{value}" for value in values]


def _derive_policy_context(payload: SocialProviderGateRequest) -> SocialProviderPolicyContext:
    if payload.policy_context is not None:
        return payload.policy_context
    return SocialProviderPolicyContext(
        allow_ai_training=payload.allow_ai_training,
        allow_private_profile_merge=False,
        allow_login_state_collection=False,
    )


def _read_requests_limit(catalog_hint: dict[str, Any], key: str) -> int | None:
    return _coerce_non_negative_int(catalog_hint.get(key))


def _budget_profile(
    provider_id: str,
    quotas: SocialProviderQuotaRequest | None,
    catalog_hint: dict[str, Any],
) -> tuple[SocialProviderRateLimitProfile, list[str]]:
    requested = quotas.merged_snapshot() if quotas is not None else {}
    blockers: list[str] = []
    effective_limits: dict[str, Any] = {}

    catalog_minute = _read_requests_limit(catalog_hint, "default_requests_per_minute")
    catalog_hour = _read_requests_limit(catalog_hint, "default_requests_per_hour")
    catalog_day = _read_requests_limit(catalog_hint, "default_daily_requests")

    requested_rpm = _coerce_non_negative_int(requested.get("requests_per_minute"))
    if requested_rpm is not None:
        if catalog_minute is not None:
            effective_limits["requests_per_minute"] = min(requested_rpm, catalog_minute)
            if requested_rpm > catalog_minute:
                blockers.append("requests_per_minute_exceeds_catalog_hint")
        else:
            effective_limits["requests_per_minute"] = requested_rpm

    requested_rph = _coerce_non_negative_int(requested.get("requests_per_hour"))
    if requested_rph is not None:
        if catalog_hour is not None:
            effective_limits["requests_per_hour"] = min(requested_rph, catalog_hour)
            if requested_rph > catalog_hour:
                blockers.append("requests_per_hour_exceeds_catalog_hint")
        else:
            effective_limits["requests_per_hour"] = requested_rph

    requested_rpd = _coerce_non_negative_int(requested.get("requests_per_day"))
    if requested_rpd is not None:
        if catalog_day is not None:
            effective_limits["requests_per_day"] = min(requested_rpd, catalog_day)
            if requested_rpd > catalog_day:
                blockers.append("requests_per_day_exceeds_catalog_hint")
        else:
            effective_limits["requests_per_day"] = requested_rpd

    if catalog_minute is not None and "requests_per_minute" not in effective_limits:
        effective_limits["requests_per_minute"] = catalog_minute
    if catalog_hour is not None and "requests_per_hour" not in effective_limits:
        effective_limits["requests_per_hour"] = catalog_hour
    if catalog_day is not None and "requests_per_day" not in effective_limits:
        effective_limits["requests_per_day"] = catalog_day

    unit_cost = _coerce_float(catalog_hint.get("per_1000_unit_cost"))
    requested_cost_hint = _coerce_float(requested.get("estimated_cost_usd"))
    estimated_cost_usd = requested_cost_hint

    if unit_cost is not None:
        estimate_requests = _coerce_non_negative_int(requested_rpd)
        if estimate_requests is None:
            estimate_requests = _coerce_non_negative_int(requested_rph)
            if estimate_requests is not None:
                estimate_requests = estimate_requests * 24
        if estimate_requests is None:
            estimate_requests = _coerce_non_negative_int(requested_rpm)
            if estimate_requests is not None:
                estimate_requests = estimate_requests * 1440

        if estimate_requests is not None:
            estimated_cost = (estimate_requests / 1000) * unit_cost
            estimated_cost_usd = (
                estimated_cost
                if estimated_cost_usd is None
                else max(estimated_cost_usd, estimated_cost)
            )

    return (
        SocialProviderRateLimitProfile(
            provider_id=provider_id,
            requested=requested,
            catalog_hint=catalog_hint,
            budget_status="blocked" if blockers else "ok",
            effective_limits=effective_limits,
            estimated_cost_usd=estimated_cost_usd,
        ),
        blockers,
    )


def _cost_exceeds_budget(
    max_requests: int,
    max_cost_usd: float | None,
    catalog_hint: dict[str, Any],
) -> bool:
    if max_cost_usd is None:
        return False
    unit_cost = _coerce_float(catalog_hint.get("per_1000_unit_cost"))
    if unit_cost is None:
        return False
    estimated = (max_requests / 1000) * unit_cost
    return estimated > max_cost_usd


def _gate_budget_enforcement(max_requests: int, max_items: int) -> dict[str, Any]:
    return {
        "max_requests": max_requests,
        "max_items": max_items,
        "run_mode": "fixture_only",
        "provider_call_enforced": False,
        "provider_call_allowed": False,
    }


def prepare_social_provider_readiness(
    payload: SocialProviderReadinessRequest,
) -> SocialProviderReadinessResponse:
    normalized_endpoints = [endpoint.strip() for endpoint in payload.endpoints if endpoint.strip()]
    provider = _find_provider(_normalize_platform(payload.platform))

    missing_scope = _missing_endpoints(provider, normalized_endpoints)
    credentials_snapshot = _coerce_bool_map(
        payload.credentials_ready, provider.required_credentials
    )
    missing_credentials = [name for name, ready in credentials_snapshot.items() if not ready]

    policy_context = payload.policy_context or SocialProviderPolicyContext()
    policy_blockers = _policy_blockers(provider, policy_context)
    rate_limit_profile, budget_blockers = _budget_profile(
        provider.provider_id,
        payload.quotas,
        provider.quota_hint,
    )

    blocked_reasons = _as_blocker_reasons("credential", missing_credentials)
    blocked_reasons.extend(_as_blocker_reasons("scope", missing_scope))
    blocked_reasons.extend(_as_blocker_reasons("policy", policy_blockers))
    blocked_reasons.extend(budget_blockers)

    readiness = len(blocked_reasons) == 0
    return SocialProviderReadinessResponse(
        platform=provider.platform,
        provider_id=provider.provider_id,
        readiness=readiness,
        missing_credentials=missing_credentials,
        missing_scope=missing_scope,
        blocked_reasons=blocked_reasons,
        policy_blockers=policy_blockers,
        forbidden_actions=provider.blocked_actions,
        rate_limit_profile=rate_limit_profile,
        provider_call_allowed=readiness,
        dry_run=payload.dry_run,
    )


def prepare_social_provider_gate(
    payload: SocialProviderGateRequest,
) -> SocialProviderGateResponse:
    if not payload.authorized:
        raise SocialProviderGateAuthorizationError

    readiness_payload = SocialProviderReadinessRequest(
        platform=payload.platform,
        endpoints=payload.endpoints,
        credentials_ready=payload.credentials_ready,
        quotas=payload.quotas,
        policy_context=_derive_policy_context(payload),
        dry_run=payload.dry_run,
    )
    readiness = prepare_social_provider_readiness(readiness_payload)

    blocked_reasons = list(readiness.blocked_reasons)
    if payload.max_items < 1:
        blocked_reasons.append("max_items_must_be_positive")
    if payload.max_cost_usd is not None and _cost_exceeds_budget(
        max_requests=payload.max_requests,
        max_cost_usd=payload.max_cost_usd,
        catalog_hint=readiness.rate_limit_profile.catalog_hint,
    ):
        blocked_reasons.append("max_cost_usd_below_estimated_cost")

    provider_call_allowed = readiness.provider_call_allowed and not blocked_reasons

    return SocialProviderGateResponse(
        platform=readiness.platform,
        provider_id=readiness.provider_id,
        provider_call_allowed=provider_call_allowed,
        provider_call_attempted=False,
        readiness=readiness.readiness,
        blocked_reasons=blocked_reasons,
        policy_blockers=readiness.policy_blockers,
        forbidden_actions=readiness.forbidden_actions,
        max_requests=payload.max_requests,
        max_items=payload.max_items,
        max_cost_usd=payload.max_cost_usd,
        retention_hours=payload.retention_hours,
        budget_enforcement=_gate_budget_enforcement(
            max_requests=payload.max_requests,
            max_items=payload.max_items,
        ),
        rate_limit_profile=readiness.rate_limit_profile,
        approval_id=payload.approval_id,
        next_required_authorization="L4_social_api_gate_required_after_fixture",
        dry_run=payload.dry_run,
    )


def _provider_extra_name(provider_id: str) -> str | None:
    return OPTIONAL_DEPENDENCY_EXTRAS.get(provider_id)


def _dependency_install_command(provider: SocialProviderCatalogItem) -> list[str]:
    extra_name = _provider_extra_name(provider.provider_id)
    if extra_name is None:
        return []
    return ["python", "-m", "pip", "install", f".[{extra_name}]"]


def prepare_social_provider_live_approval_template(
    payload: SocialProviderLiveApprovalTemplateRequest,
) -> SocialProviderLiveApprovalTemplateResponse:
    provider = _find_provider(_normalize_platform(payload.platform), payload.provider_id)
    normalized_endpoints = [endpoint.strip() for endpoint in payload.endpoints if endpoint.strip()]
    missing_scope = _missing_endpoints(provider, normalized_endpoints)

    blocked_reasons = _as_blocker_reasons("scope", missing_scope)
    if payload.allow_ai_training:
        blocked_reasons.append("allow_ai_training_must_be_false_for_phase2")
    if payload.credential_reference is None:
        blocked_reasons.append("credential_reference_required_before_live")
    if payload.max_cost_usd is None:
        blocked_reasons.append("max_cost_usd_required")

    approval_packet = {
        "schema_version": "social_provider_l4_approval_packet.v1",
        "authorized": False,
        "approval_id": None,
        "platform": provider.platform,
        "provider_id": provider.provider_id,
        "endpoints": normalized_endpoints,
        "intended_use": payload.intended_use.strip(),
        "credential_reference": payload.credential_reference,
        "max_requests": payload.max_requests,
        "max_items": payload.max_items,
        "max_cost_usd": payload.max_cost_usd,
        "retention_hours": payload.retention_hours,
        "allow_ai_training": payload.allow_ai_training,
        "delete_policy": payload.delete_policy,
        "blocked_actions": provider.blocked_actions,
        "sdk_package": provider.sdk_selection.package if provider.sdk_selection else None,
        "optional_dependency_extra": _provider_extra_name(provider.provider_id),
        "provider_call": False,
        "production_write": False,
    }

    return SocialProviderLiveApprovalTemplateResponse(
        platform=provider.platform,
        provider_id=provider.provider_id,
        sdk_selection=provider.sdk_selection,
        approval_packet=approval_packet,
        required_confirmations=LIVE_APPROVAL_REQUIRED_CONFIRMATIONS,
        blocked_reasons=blocked_reasons,
        next_required_authorization="L4_social_api_live_approval_required",
    )


def prepare_social_provider_dependency_gate(
    payload: SocialProviderDependencyGateRequest,
) -> SocialProviderDependencyGateResponse:
    provider = _find_provider(_normalize_platform(payload.platform), payload.provider_id)
    sdk_selection = provider.sdk_selection
    extra_name = _provider_extra_name(provider.provider_id)

    blocked_reasons: list[str] = []
    if not payload.authorized:
        blocked_reasons.append("authorization_required")
    if payload.approval_id is None or not payload.approval_id.strip():
        blocked_reasons.append("approval_id_required")
    if not payload.confirm_dependency_review:
        blocked_reasons.append("dependency_review_confirmation_required")
    if not payload.confirm_no_provider_call:
        blocked_reasons.append("confirm_no_provider_call_required")
    if not payload.confirm_no_credential_read:
        blocked_reasons.append("confirm_no_credential_read_required")
    if sdk_selection is None:
        blocked_reasons.append("sdk_selection_missing")
    elif sdk_selection.status not in {"selected", "candidate"}:
        blocked_reasons.append(f"sdk_status_not_installable:{sdk_selection.status}")
    if extra_name is None:
        blocked_reasons.append("optional_dependency_extra_missing")

    dependency_install_allowed = (
        payload.install_scope == "local_dev_optional_dependency" and not blocked_reasons
    )
    installation_plan = {
        "package": sdk_selection.package if sdk_selection else None,
        "import_name": sdk_selection.import_name if sdk_selection else None,
        "source_url": sdk_selection.source_url if sdk_selection else None,
        "pyproject_extra": extra_name,
        "install_command": _dependency_install_command(provider),
        "dry_run": payload.dry_run,
        "executes_install": False,
        "enables_live_adapter": False,
    }

    return SocialProviderDependencyGateResponse(
        platform=provider.platform,
        provider_id=provider.provider_id,
        sdk_selection=sdk_selection,
        dependency_install_allowed=dependency_install_allowed,
        install_scope=payload.install_scope,
        installation_plan=installation_plan,
        blocked_reasons=blocked_reasons,
        approval_id=payload.approval_id,
        next_required_authorization="L4_social_api_dependency_install_required",
    )


def _optional_dependency_present(import_name: str | None) -> bool:
    if import_name is None or not import_name.strip():
        return False
    return importlib.util.find_spec(import_name.strip()) is not None


def _load_fixture_adapter_module(module_path: str | None) -> Any | None:
    if module_path is None:
        return None
    try:
        return importlib.import_module(module_path)
    except ImportError:
        return None


def prepare_social_provider_adapter_plan(
    payload: SocialProviderAdapterPlanRequest,
) -> SocialProviderAdapterPlanResponse:
    provider = _find_provider(_normalize_platform(payload.platform), payload.provider_id)
    normalized_endpoints = [endpoint.strip() for endpoint in payload.endpoints if endpoint.strip()]
    missing_scope = _missing_endpoints(provider, normalized_endpoints)
    sdk_selection = provider.sdk_selection
    dependency_import_name = sdk_selection.import_name if sdk_selection else None
    dependency_present = _optional_dependency_present(dependency_import_name)
    adapter_module = FIXTURE_ADAPTER_MODULES.get(provider.provider_id)
    fixture_adapter = _load_fixture_adapter_module(adapter_module)

    blocked_reasons = _as_blocker_reasons("scope", missing_scope)
    if adapter_module is None:
        blocked_reasons.append("fixture_adapter_module_missing")
    elif fixture_adapter is None:
        blocked_reasons.append("fixture_adapter_module_import_failed")
    if sdk_selection is None:
        blocked_reasons.append("sdk_selection_missing")
    elif sdk_selection.status not in {"selected", "candidate"}:
        blocked_reasons.append(f"sdk_status_not_adapter_ready:{sdk_selection.status}")
    if not dependency_present:
        blocked_reasons.append(f"optional_dependency_missing:{dependency_import_name}")
    if payload.mode == "live_dry_run":
        blocked_reasons.append("live_adapter_requires_separate_l4_authorization")
    if payload.authorized:
        blocked_reasons.append("authorized_ignored_for_fixture_adapter_plan")
    if payload.approval_id is not None:
        blocked_reasons.append("approval_id_ignored_for_fixture_adapter_plan")
    if payload.credential_reference is not None:
        blocked_reasons.append("credential_reference_ignored_for_fixture_adapter_plan")

    planned_operations: list[dict[str, Any]] = []
    if not missing_scope and fixture_adapter is not None:
        plan_fixture_operations = getattr(fixture_adapter, "plan_fixture_operations", None)
        if callable(plan_fixture_operations):
            planned_operations = plan_fixture_operations(
                endpoints=normalized_endpoints,
                fixture_limit=payload.fixture_limit,
            )
        else:
            blocked_reasons.append("fixture_adapter_plan_function_missing")

    adapter_ready = fixture_adapter is not None and dependency_present and not blocked_reasons

    return SocialProviderAdapterPlanResponse(
        platform=provider.platform,
        provider_id=provider.provider_id,
        sdk_selection=sdk_selection,
        adapter_module=adapter_module,
        dependency_present=dependency_present,
        dependency_import_name=dependency_import_name,
        adapter_ready=adapter_ready,
        planned_operations=planned_operations,
        blocked_reasons=blocked_reasons,
        next_required_authorization="L4_social_api_live_adapter_gate_required",
    )


def _default_source_name(provider: SocialProviderCatalogItem, endpoints: list[str]) -> str:
    endpoint_label = ",".join(endpoints[:3])
    return f"{provider.platform} social fixture source: {endpoint_label}"


def _source_template_payload(
    provider: SocialProviderCatalogItem,
    endpoints: list[str],
    source_name: str,
    project_id: str | None,
    fixture_limit: int,
) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "name": source_name,
        "type": "manual_json",
        "url": None,
        "config": {
            "entity_type": "social_provider_fixture",
            "json_data": {
                "schema_version": "social_provider_source_template_payload.v1",
                "platform": provider.platform,
                "provider_id": provider.provider_id,
                "endpoints": endpoints,
                "fixture_limit": fixture_limit,
                "provider_call": False,
                "provider_call_attempted": False,
                "credential_read_attempted": False,
                "production_write_allowed": False,
                "author_policy": "hashed",
                "source_mode": "manual_json_authorized_import",
                "blocked_actions": provider.blocked_actions,
            },
        },
        "schedule_cron": None,
    }


def prepare_social_provider_source_template(
    payload: SocialProviderSourceTemplateRequest,
) -> SocialProviderSourceTemplateResponse:
    provider = _find_provider(_normalize_platform(payload.platform), payload.provider_id)
    normalized_endpoints = [endpoint.strip() for endpoint in payload.endpoints if endpoint.strip()]
    missing_scope = _missing_endpoints(provider, normalized_endpoints)

    blocked_reasons = _as_blocker_reasons("scope", missing_scope)
    if payload.authorized:
        blocked_reasons.append("authorized_ignored_for_source_template_preview")
    if payload.approval_id is not None:
        blocked_reasons.append("approval_id_ignored_for_source_template_preview")
    if payload.credential_reference is not None:
        blocked_reasons.append("credential_reference_ignored_for_source_template_preview")

    source_name = (
        payload.source_name.strip()
        if payload.source_name is not None and payload.source_name.strip()
        else _default_source_name(provider, normalized_endpoints)
    )
    source_create_payload = (
        _source_template_payload(
            provider=provider,
            endpoints=normalized_endpoints,
            source_name=source_name,
            project_id=payload.project_id,
            fixture_limit=payload.fixture_limit,
        )
        if not missing_scope
        else None
    )

    return SocialProviderSourceTemplateResponse(
        platform=provider.platform,
        provider_id=provider.provider_id,
        source_create_payload=source_create_payload,
        blocked_reasons=blocked_reasons,
        next_required_authorization="L4_social_api_source_create_gate_required",
    )


def _fixture_payload(
    provider: SocialProviderCatalogItem,
    endpoint: str,
    index: int,
) -> dict[str, Any]:
    base_payload: dict[str, Any] = {
        "platform": provider.platform,
        "provider_id": provider.provider_id,
        "endpoint": endpoint,
        "fixture_index": index,
        "provider_call": False,
    }
    if provider.platform == "youtube":
        return {
            **base_payload,
            "content_id": f"yt_fixture_video_{index}",
            "title": f"YouTube fixture video {index}",
            "channel_id": f"yt_fixture_channel_{index}",
            "comment_count": 12 + index,
        }
    if provider.platform == "reddit":
        return {
            **base_payload,
            "subreddit": "example_subreddit",
            "post_id": f"reddit_fixture_post_{index}",
            "title": f"Reddit fixture post {index}",
            "comment_count": 8 + index,
        }
    if provider.platform == "x":
        return {
            **base_payload,
            "post_id": f"x_fixture_post_{index}",
            "author_id_hash": f"x_author_hash_{index}",
            "public_metrics": {"reply_count": index, "like_count": index * 2},
        }
    if provider.platform in {"instagram", "threads"}:
        return {
            **base_payload,
            "media_id": f"{provider.platform}_fixture_media_{index}",
            "owner_scope": "authorized_business_asset",
            "comment_count": 5 + index,
        }
    if provider.platform == "tiktok":
        return {
            **base_payload,
            "video_id": f"tiktok_fixture_video_{index}",
            "research_stage": "test_only",
            "comment_count": 6 + index,
        }
    if provider.platform == "linkedin":
        return {
            **base_payload,
            "organization_urn": f"urn:li:organization:{1000 + index}",
            "post_urn": f"urn:li:share:{2000 + index}",
            "social_actions_count": 3 + index,
        }
    return base_payload


def prepare_social_raw_preview(payload: SocialRawPreviewRequest) -> SocialRawPreviewResponse:
    provider = _find_provider(_normalize_platform(payload.platform), payload.provider_id)
    endpoint = payload.endpoint.strip()
    missing_scope = _missing_endpoints(provider, [endpoint])

    blocked_reasons: list[str] = []
    blocked_reasons.extend(_as_blocker_reasons("scope", missing_scope))
    if payload.include_live_comparison or payload.authorized:
        blocked_reasons.append("live_comparison_requires_separate_l4_authorization")
    if payload.approval_id is not None:
        blocked_reasons.append("approval_id_ignored_for_fixture_preview")

    records: list[SocialRawPreviewRecord] = []
    if not missing_scope:
        for index in range(1, payload.fixture_limit + 1):
            raw_record_id = f"fixture:{provider.provider_id}:{endpoint}:{index}"
            evidence_ref = f"fixture://{provider.provider_id}/{endpoint}/{index}"
            records.append(
                SocialRawPreviewRecord(
                    raw_record_id=raw_record_id,
                    provider_id=provider.provider_id,
                    platform=provider.platform,
                    endpoint=endpoint,
                    source_ref=f"{provider.provider_id}:{endpoint}",
                    evidence_ref=evidence_ref,
                    payload=_fixture_payload(provider, endpoint, index),
                )
            )

    return SocialRawPreviewResponse(
        platform=provider.platform,
        provider_id=provider.provider_id,
        endpoint=endpoint,
        blocked_reasons=blocked_reasons,
        records=records,
        sdk_selection=provider.sdk_selection,
        next_required_authorization="L4_social_raw_live_preview_gate_required",
    )


def _payload_text(payload: dict[str, Any]) -> str | None:
    for key in ("title", "body", "text", "caption", "description"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _fixture_index(payload: dict[str, Any]) -> int:
    value = payload.get("fixture_index")
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return 1
    return value


def _external_post_id(record: SocialRawPreviewRecord) -> str:
    for key in ("content_id", "post_id", "media_id", "video_id", "post_urn"):
        value = record.payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return record.raw_record_id


def _social_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for key in ("comment_count", "social_actions_count"):
        value = payload.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            metrics[key] = value
    public_metrics = payload.get("public_metrics")
    if isinstance(public_metrics, dict):
        metrics["public_metrics"] = public_metrics
    return metrics


def _effective_author_policy(
    requested: str,
) -> tuple[str, list[str]]:
    if requested == "retained_with_approval":
        return "hashed", ["author_retention_requires_separate_l4_authorization"]
    if requested == "dropped":
        return "dropped", []
    return "hashed", []


def _is_comment_endpoint(endpoint: str) -> bool:
    return "comment" in endpoint.lower()


def _build_social_post_item(
    record: SocialRawPreviewRecord,
    author_policy: str,
) -> SocialNormalizedPreviewItem:
    external_post_id = _external_post_id(record)
    title = _payload_text(record.payload)
    return SocialNormalizedPreviewItem(
        schema_version="social_post.v1",
        item_id=f"social_post:{record.provider_id}:{external_post_id}",
        provider_id=record.provider_id,
        platform=record.platform,
        raw_record_id=record.raw_record_id,
        evidence_ref=record.evidence_ref,
        author_policy=author_policy,
        payload={
            "external_post_id": external_post_id,
            "title": title,
            "body": title,
            "source_ref": record.source_ref,
            "source_url": None,
            "metrics": _social_metrics(record.payload),
            "collected_from_endpoint": record.endpoint,
            "provider_call": False,
        },
    )


def _build_social_comment_item(
    record: SocialRawPreviewRecord,
    author_policy: str,
) -> SocialNormalizedPreviewItem:
    external_post_id = _external_post_id(record)
    fixture_index = _fixture_index(record.payload)
    body = _payload_text(record.payload) or f"{record.platform} fixture comment {fixture_index}"
    external_comment_id = f"{external_post_id}:comment:{fixture_index}"
    return SocialNormalizedPreviewItem(
        schema_version="social_comment.v1",
        item_id=f"social_comment:{record.provider_id}:{external_comment_id}",
        provider_id=record.provider_id,
        platform=record.platform,
        raw_record_id=record.raw_record_id,
        evidence_ref=record.evidence_ref,
        author_policy=author_policy,
        payload={
            "external_comment_id": external_comment_id,
            "external_post_id": external_post_id,
            "parent_comment_id": None,
            "body": body,
            "source_ref": record.source_ref,
            "metrics": _social_metrics(record.payload),
            "collected_from_endpoint": record.endpoint,
            "provider_call": False,
        },
    )


def _build_social_voc_item(
    source_item: SocialNormalizedPreviewItem,
    text: str,
    author_policy: str,
) -> SocialNormalizedPreviewItem:
    return SocialNormalizedPreviewItem(
        schema_version="social_voc_item.v1",
        item_id=f"social_voc:{source_item.item_id}",
        provider_id=source_item.provider_id,
        platform=source_item.platform,
        raw_record_id=source_item.raw_record_id,
        evidence_ref=source_item.evidence_ref,
        author_policy=author_policy,
        payload={
            "source_item_schema": source_item.schema_version,
            "source_item_id": source_item.item_id,
            "raw_record_id": source_item.raw_record_id,
            "evidence_ref": source_item.evidence_ref,
            "text_excerpt": text[:500],
            "labels": [],
            "sentiment": None,
            "confidence_source": "fixture_rule",
            "llm_provider": None,
            "llm_model": None,
            "llm_call_attempted": False,
            "provider_call": False,
        },
    )


def prepare_social_normalization_preview(
    payload: SocialNormalizationPreviewRequest,
) -> SocialNormalizationPreviewResponse:
    raw_preview = prepare_social_raw_preview(
        SocialRawPreviewRequest(
            platform=payload.platform,
            endpoint=payload.endpoint,
            provider_id=payload.provider_id,
            fixture_limit=payload.fixture_limit,
            include_live_comparison=False,
            authorized=False,
            approval_id=None,
        ),
    )
    author_policy, author_blockers = _effective_author_policy(payload.author_policy)

    blocked_reasons = list(raw_preview.blocked_reasons)
    blocked_reasons.extend(author_blockers)
    if payload.include_live_comparison:
        blocked_reasons.append("live_comparison_requires_separate_l4_authorization")
    if payload.authorized:
        blocked_reasons.append("authorized_ignored_for_normalization_preview")
    if payload.approval_id is not None:
        blocked_reasons.append("approval_id_ignored_for_normalization_preview")

    normalized_items: list[SocialNormalizedPreviewItem] = []
    for record in raw_preview.records:
        source_item = (
            _build_social_comment_item(record, author_policy)
            if _is_comment_endpoint(raw_preview.endpoint)
            else _build_social_post_item(record, author_policy)
        )
        normalized_items.append(source_item)

        text = _payload_text(source_item.payload)
        if payload.include_voc and text is not None:
            normalized_items.append(
                _build_social_voc_item(
                    source_item=source_item,
                    text=text,
                    author_policy=author_policy,
                )
            )

    return SocialNormalizationPreviewResponse(
        platform=raw_preview.platform,
        provider_id=raw_preview.provider_id,
        endpoint=raw_preview.endpoint,
        blocked_reasons=blocked_reasons,
        raw_records=raw_preview.records,
        normalized_items=normalized_items,
        sdk_selection=raw_preview.sdk_selection,
        next_required_authorization="L4_social_normalization_write_gate_required",
    )


def _default_dataset_name(platform: str, endpoint: str) -> str:
    return f"{platform} social VOC fixture dataset: {endpoint}"


def _build_social_dataset_row(
    source_item: SocialNormalizedPreviewItem,
    row_index: int,
) -> SocialDatasetPreviewRow:
    return SocialDatasetPreviewRow(
        row_id=f"social_dataset_row:{source_item.provider_id}:{row_index}",
        provider_id=source_item.provider_id,
        platform=source_item.platform,
        raw_record_id=source_item.raw_record_id,
        evidence_ref=source_item.evidence_ref,
        source_item_id=source_item.item_id,
        source_schema_version="social_voc_item.v1",
        author_policy=source_item.author_policy,
        payload={
            "platform": source_item.platform,
            "provider_id": source_item.provider_id,
            "raw_record_id": source_item.raw_record_id,
            "evidence_ref": source_item.evidence_ref,
            "source_item_id": source_item.item_id,
            "source_item_schema": source_item.schema_version,
            "source_normalized_item_id": source_item.payload.get("source_item_id"),
            "source_normalized_schema": source_item.payload.get("source_item_schema"),
            "text_excerpt": source_item.payload.get("text_excerpt"),
            "labels": source_item.payload.get("labels", []),
            "sentiment": source_item.payload.get("sentiment"),
            "author_policy": source_item.author_policy,
            "llm_provider": source_item.payload.get("llm_provider"),
            "llm_model": source_item.payload.get("llm_model"),
            "llm_call_attempted": False,
            "provider_call": False,
        },
    )


def prepare_social_dataset_preview(
    payload: SocialDatasetPreviewRequest,
) -> SocialDatasetPreviewResponse:
    normalization_preview = prepare_social_normalization_preview(
        SocialNormalizationPreviewRequest(
            platform=payload.platform,
            endpoint=payload.endpoint,
            provider_id=payload.provider_id,
            fixture_limit=payload.fixture_limit,
            include_voc=True,
            include_live_comparison=False,
            authorized=False,
            approval_id=None,
            author_policy=payload.author_policy,
        ),
    )

    blocked_reasons = list(normalization_preview.blocked_reasons)
    if payload.include_live_comparison:
        blocked_reasons.append("live_comparison_requires_separate_l4_authorization")
    if payload.authorized:
        blocked_reasons.append("authorized_ignored_for_dataset_preview")
    if payload.approval_id is not None:
        blocked_reasons.append("approval_id_ignored_for_dataset_preview")
    if payload.save_requested:
        blocked_reasons.append("dataset_save_requires_separate_l4_authorization")
    if payload.export_requested:
        blocked_reasons.append("dataset_export_requires_separate_l4_authorization")

    source_items = [
        item
        for item in normalization_preview.normalized_items
        if item.schema_version == "social_voc_item.v1"
    ]
    rows = [
        _build_social_dataset_row(source_item=source_item, row_index=index)
        for index, source_item in enumerate(source_items[: payload.max_rows], start=1)
    ]
    dataset_name = (
        payload.dataset_name.strip()
        if payload.dataset_name is not None and payload.dataset_name.strip()
        else _default_dataset_name(normalization_preview.platform, normalization_preview.endpoint)
    )

    return SocialDatasetPreviewResponse(
        platform=normalization_preview.platform,
        provider_id=normalization_preview.provider_id,
        endpoint=normalization_preview.endpoint,
        dataset_name=dataset_name,
        blocked_reasons=blocked_reasons,
        source_item_count=len(source_items),
        row_count=len(rows),
        max_rows=payload.max_rows,
        truncated=len(source_items) > len(rows),
        rows=rows,
        normalized_items=normalization_preview.normalized_items,
        sdk_selection=normalization_preview.sdk_selection,
        next_required_authorization="L4_social_dataset_save_gate_required",
    )
