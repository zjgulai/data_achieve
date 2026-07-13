from __future__ import annotations

import json
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import JsonValue

from data_intelligence_hub.schemas.capability_catalog import PlatformId
from data_intelligence_hub.schemas.workflow_planner import (
    DecisionTraceEntry,
    DeliveryIntent,
    FlowMode,
    MatchMode,
    MonitoringScopeDraft,
    MonitoringScopeType,
    NormalizedMonitoringScope,
    NormalizedPlanningInput,
    PlanningInput,
    ScheduleIntent,
    ScopeRefMapping,
)
from data_intelligence_hub.services.exceptions import WorkflowPlannerInputError
from data_intelligence_hub.services.workflow_planner.fingerprint import sha256_id

PLATFORM_HOSTS = {
    "youtube": {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"},
    "reddit": {"reddit.com", "www.reddit.com", "old.reddit.com"},
    "x": {"x.com", "www.x.com", "twitter.com", "www.twitter.com"},
    "instagram": {"instagram.com", "www.instagram.com"},
    "threads": {"threads.net", "www.threads.net"},
    "tiktok": {"tiktok.com", "www.tiktok.com", "m.tiktok.com"},
    "linkedin": {"linkedin.com", "www.linkedin.com"},
}

_PLATFORM_ORDER = {platform: index for index, platform in enumerate(PlatformId)}
_MATCH_MODE_DEFAULTS = {
    MonitoringScopeType.BRAND: MatchMode.PHRASE,
    MonitoringScopeType.CATEGORY: MatchMode.HYBRID,
    MonitoringScopeType.COMPETITOR: MatchMode.PHRASE,
    MonitoringScopeType.TOPIC: MatchMode.PHRASE,
    MonitoringScopeType.CAMPAIGN: MatchMode.PHRASE,
}


@dataclass(frozen=True)
class NormalizationResult:
    normalized_input: NormalizedPlanningInput
    fingerprint_input: dict[str, JsonValue]
    scope_ref_map: tuple[ScopeRefMapping, ...]
    semantic_entries: tuple[DecisionTraceEntry, ...]
    input_diagnostics: tuple[DecisionTraceEntry, ...]


def _display_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip()


def normalize_text(value: str) -> str:
    return _display_text(value).casefold()


def _display_texts(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        display_value = _display_text(value)
        normalized_value = display_value.casefold()
        if not display_value or normalized_value in seen:
            continue
        seen.add(normalized_value)
        result.append(display_value)
    return result


def _semantic_texts(values: Sequence[str]) -> list[str]:
    return sorted({normalized for value in values if (normalized := normalize_text(value))})


def _display_platforms(values: Sequence[PlatformId]) -> list[PlatformId]:
    result: list[PlatformId] = []
    seen: set[PlatformId] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _semantic_platforms(values: Sequence[PlatformId]) -> list[str]:
    return [
        platform.value
        for platform in sorted(set(values), key=lambda item: _PLATFORM_ORDER[item])
    ]


def normalize_seed_url(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("seed_url_must_be_string")

    source = _display_text(value)
    try:
        parsed = urlsplit(source)
        scheme = parsed.scheme.casefold()
        hostname = parsed.hostname
        username = parsed.username
        password = parsed.password
        port = parsed.port
    except ValueError as exc:
        raise ValueError("seed_url_invalid") from exc

    if scheme not in {"http", "https"} or not hostname:
        raise ValueError("seed_url_invalid")
    if username is not None or password is not None:
        raise ValueError("seed_url_userinfo_forbidden")

    normalized_host = hostname.casefold()
    netloc_host = f"[{normalized_host}]" if ":" in normalized_host else normalized_host
    netloc = f"{netloc_host}:{port}" if port is not None else netloc_host
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)), doseq=True)
    return urlunsplit((scheme, netloc, parsed.path, query, ""))


def classify_seed_url(value: str) -> PlatformId | None:
    normalized_url = normalize_seed_url(value)
    hostname = urlsplit(normalized_url).hostname
    if hostname is None:
        return None
    for platform, hosts in PLATFORM_HOSTS.items():
        if hostname in hosts:
            return PlatformId(platform)
    return None


def build_scope_key(scope: Mapping[str, object]) -> str:
    return sha256_id(cast(JsonValue, dict(scope)))


def _normalize_seed_urls(
    values: Sequence[str],
    *,
    scope_index: int,
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    issues: list[dict[str, object]] = []
    for url_index, value in enumerate(values):
        try:
            normalized_url = normalize_seed_url(value)
        except (TypeError, ValueError) as exc:
            issues.append(
                {
                    "loc": ["body", "scopes", scope_index, "seed_urls", url_index],
                    "msg": str(exc),
                    "type": "value_error",
                }
            )
            continue
        if normalized_url in seen:
            continue
        seen.add(normalized_url)
        result.append(normalized_url)
    if issues:
        raise WorkflowPlannerInputError(issues)
    return result


def _scope_semantics(
    *,
    scope: MonitoringScopeDraft,
    canonical_term: str | None,
    aliases: Sequence[str],
    include_terms: Sequence[str],
    exclude_terms: Sequence[str],
    official_accounts: Sequence[str],
    seed_urls: Sequence[str],
    effective_languages: Sequence[str],
    effective_regions: Sequence[str],
    effective_platforms: Sequence[PlatformId],
    match_mode: MatchMode,
) -> dict[str, JsonValue]:
    return cast(
        dict[str, JsonValue],
        {
            "scope_type": scope.scope_type.value,
            "canonical_term": normalize_text(canonical_term) if canonical_term else None,
            "aliases": _semantic_texts(aliases),
            "include_terms": _semantic_texts(include_terms),
            "exclude_terms": _semantic_texts(exclude_terms),
            "official_accounts": _semantic_texts(official_accounts),
            "seed_urls": sorted(set(seed_urls)),
            "effective_languages": _semantic_texts(effective_languages),
            "effective_regions": _semantic_texts(effective_regions),
            "effective_platforms": _semantic_platforms(effective_platforms),
            "match_mode": match_mode.value,
        },
    )


def _semantic_conflicts(
    *,
    scope_key: str,
    canonical_term: str | None,
    aliases: Sequence[str],
    include_terms: Sequence[str],
    official_accounts: Sequence[str],
    exclude_terms: Sequence[str],
) -> list[DecisionTraceEntry]:
    active_origins: dict[str, set[str]] = {}
    if canonical_term:
        active_origins.setdefault(normalize_text(canonical_term), set()).add("canonical")
    for origin, values in (
        ("alias", aliases),
        ("include", include_terms),
        ("official_account", official_accounts),
    ):
        for value in values:
            active_origins.setdefault(normalize_text(value), set()).add(origin)

    conflicts: list[DecisionTraceEntry] = []
    for excluded in _semantic_texts(exclude_terms):
        origins = active_origins.get(excluded)
        if not origins:
            continue
        conflicts.append(
            DecisionTraceEntry(
                code="excluded_term_precedence",
                reason="Excluded term overrides deterministic input",
                scope_keys=[scope_key],
                requirement_ref=None,
                details={
                    "normalized_term": excluded,
                    "origins": sorted(origins),
                },
            )
        )
    return conflicts


def _input_diagnostics_for_scope(
    *,
    scope_ref: str,
    scope_key: str,
    seed_urls: Sequence[str],
    effective_platforms: Sequence[PlatformId],
    declared_platforms: bool,
) -> list[DecisionTraceEntry]:
    diagnostics: list[DecisionTraceEntry] = []
    selected_platforms = set(effective_platforms)
    for seed_url in seed_urls:
        platform = classify_seed_url(seed_url)
        if platform is None:
            diagnostics.append(
                DecisionTraceEntry(
                    code="seed_url_unclassified",
                    reason="Seed URL does not match a supported platform host",
                    scope_keys=[scope_key],
                    requirement_ref=None,
                    details={"scope_ref": scope_ref, "seed_url": seed_url},
                )
            )
        elif declared_platforms and platform not in selected_platforms:
            diagnostics.append(
                DecisionTraceEntry(
                    code="platform_not_selected",
                    reason="Seed URL platform is outside the selected platform scope",
                    scope_keys=[scope_key],
                    requirement_ref=None,
                    details={
                        "scope_ref": scope_ref,
                        "seed_url": seed_url,
                        "classified_platform": platform.value,
                        "effective_platforms": _semantic_platforms(effective_platforms),
                    },
                )
            )
    return diagnostics


def _json_dump(value: object) -> JsonValue:
    return cast(JsonValue, value)


def normalize_planning_input(payload: PlanningInput) -> NormalizationResult:
    default_languages = _display_texts(payload.default_languages)
    default_regions = _display_texts(payload.default_regions)
    default_platforms = _display_platforms(payload.default_platforms)

    normalized_scopes: list[NormalizedMonitoringScope] = []
    scope_index_by_key: dict[str, int] = {}
    semantic_scope_by_key: dict[str, dict[str, JsonValue]] = {}
    scope_ref_map: list[ScopeRefMapping] = []
    semantic_entries: list[DecisionTraceEntry] = []
    input_diagnostics: list[DecisionTraceEntry] = []
    platform_issues: list[dict[str, object]] = []

    for scope_index, scope in enumerate(payload.scopes):
        canonical_display = _display_text(scope.canonical_term) if scope.canonical_term else None
        canonical_term = canonical_display or None
        aliases = _display_texts(scope.aliases)
        include_terms = _display_texts(scope.include_terms)
        exclude_terms = _display_texts(scope.exclude_terms)
        official_accounts = _display_texts(scope.official_accounts)
        seed_urls = _normalize_seed_urls(scope.seed_urls, scope_index=scope_index)

        scope_languages = _display_texts(scope.languages)
        scope_regions = _display_texts(scope.regions)
        scope_platforms = _display_platforms(scope.platforms)
        effective_languages = scope_languages or list(default_languages)
        effective_regions = scope_regions or list(default_regions)
        declared_platforms = bool(scope_platforms or default_platforms)
        effective_platforms = scope_platforms or list(default_platforms)
        if not effective_platforms:
            derived_platforms = [
                platform
                for seed_url in seed_urls
                if (platform := classify_seed_url(seed_url)) is not None
            ]
            effective_platforms = _display_platforms(derived_platforms)

        if payload.flow_mode is FlowMode.PERIODIC_MONITORING and not effective_platforms:
            platform_issues.append(
                {
                    "loc": ["body", "scopes", scope_index, "platforms"],
                    "msg": "periodic_effective_platform_required",
                    "type": "value_error",
                }
            )

        match_mode = scope.match_mode or _MATCH_MODE_DEFAULTS[scope.scope_type]
        semantic_scope = _scope_semantics(
            scope=scope,
            canonical_term=canonical_term,
            aliases=aliases,
            include_terms=include_terms,
            exclude_terms=exclude_terms,
            official_accounts=official_accounts,
            seed_urls=seed_urls,
            effective_languages=effective_languages,
            effective_regions=effective_regions,
            effective_platforms=effective_platforms,
            match_mode=match_mode,
        )
        scope_key = build_scope_key(semantic_scope)
        scope_ref_map.append(ScopeRefMapping(scope_ref=scope.scope_ref, scope_key=scope_key))

        input_diagnostics.extend(
            _input_diagnostics_for_scope(
                scope_ref=scope.scope_ref,
                scope_key=scope_key,
                seed_urls=seed_urls,
                effective_platforms=effective_platforms,
                declared_platforms=declared_platforms,
            )
        )

        existing_index = scope_index_by_key.get(scope_key)
        if existing_index is not None:
            existing = normalized_scopes[existing_index]
            normalized_scopes[existing_index] = existing.model_copy(
                update={"source_scope_refs": [*existing.source_scope_refs, scope.scope_ref]}
            )
            input_diagnostics.append(
                DecisionTraceEntry(
                    code="duplicate_scope_collapsed",
                    reason="Semantically duplicate Scope collapsed",
                    scope_keys=[scope_key],
                    requirement_ref=None,
                    details={
                        "scope_ref": scope.scope_ref,
                        "retained_scope_ref": existing.source_scope_refs[0],
                    },
                )
            )
            continue

        scope_index_by_key[scope_key] = len(normalized_scopes)
        semantic_scope_by_key[scope_key] = semantic_scope
        normalized_scopes.append(
            NormalizedMonitoringScope(
                scope_key=scope_key,
                source_scope_refs=[scope.scope_ref],
                scope_type=scope.scope_type,
                canonical_term=canonical_term,
                aliases=aliases,
                include_terms=include_terms,
                exclude_terms=exclude_terms,
                official_accounts=official_accounts,
                seed_urls=seed_urls,
                effective_languages=effective_languages,
                effective_regions=effective_regions,
                effective_platforms=effective_platforms,
                match_mode=match_mode,
            )
        )
        semantic_entries.extend(
            _semantic_conflicts(
                scope_key=scope_key,
                canonical_term=canonical_term,
                aliases=aliases,
                include_terms=include_terms,
                official_accounts=official_accounts,
                exclude_terms=exclude_terms,
            )
        )

    if platform_issues:
        raise WorkflowPlannerInputError(platform_issues)

    schedule_intent = (
        ScheduleIntent(
            cadence=payload.schedule_intent.cadence,
            timezone=_display_text(payload.schedule_intent.timezone),
        )
        if payload.schedule_intent is not None
        else None
    )
    delivery_intent = (
        DeliveryIntent(outputs=list(dict.fromkeys(payload.delivery_intent.outputs)))
        if payload.delivery_intent is not None
        else None
    )
    required_fields = _display_texts(payload.required_fields)
    optional_fields = _display_texts(payload.optional_fields)
    normalized_input = NormalizedPlanningInput(
        flow_mode=payload.flow_mode,
        scopes=normalized_scopes,
        schedule_intent=schedule_intent,
        delivery_intent=delivery_intent,
        policy_profile=payload.policy_profile,
        purpose=payload.purpose,
        required_fields=required_fields,
        optional_fields=optional_fields,
        budget_ceiling=payload.budget_ceiling,
        rate_limit_intent=payload.rate_limit_intent,
        retention_intent=payload.retention_intent,
        allow_partial_degradation=payload.allow_partial_degradation,
    )

    semantic_scopes: list[dict[str, JsonValue]] = []
    for scope_key, semantic_scope_value in semantic_scope_by_key.items():
        semantic_scopes.append({"scope_key": scope_key, **semantic_scope_value})
    semantic_scopes.sort(key=lambda item: cast(str, item["scope_key"]))

    schedule_fingerprint: JsonValue = None
    if schedule_intent is not None:
        schedule_fingerprint = {
            "cadence": schedule_intent.cadence,
            "timezone": normalize_text(schedule_intent.timezone),
        }
    delivery_fingerprint: JsonValue = None
    if delivery_intent is not None:
        delivery_fingerprint = _json_dump(
            {"outputs": sorted(set(delivery_intent.outputs))}
        )

    fingerprint_input: dict[str, JsonValue] = {
        "flow_mode": payload.flow_mode.value,
        "scopes": _json_dump(semantic_scopes),
        "default_languages": _json_dump(_semantic_texts(default_languages)),
        "default_regions": _json_dump(_semantic_texts(default_regions)),
        "default_platforms": _json_dump(_semantic_platforms(default_platforms)),
        "schedule_intent": schedule_fingerprint,
        "delivery_intent": delivery_fingerprint,
        "policy_profile": payload.policy_profile.value,
        "purpose": payload.purpose,
        "required_fields": _json_dump(_semantic_texts(required_fields)),
        "optional_fields": _json_dump(_semantic_texts(optional_fields)),
        "budget_ceiling": _json_dump(
            payload.budget_ceiling.model_dump(mode="json")
            if payload.budget_ceiling is not None
            else None
        ),
        "rate_limit_intent": _json_dump(
            payload.rate_limit_intent.model_dump(mode="json")
            if payload.rate_limit_intent is not None
            else None
        ),
        "retention_intent": _json_dump(
            payload.retention_intent.model_dump(mode="json")
            if payload.retention_intent is not None
            else None
        ),
        "allow_partial_degradation": payload.allow_partial_degradation,
    }

    semantic_entries.sort(
        key=lambda entry: (
            entry.scope_keys,
            entry.code,
            json.dumps(entry.details, ensure_ascii=False, sort_keys=True),
        )
    )
    return NormalizationResult(
        normalized_input=normalized_input,
        fingerprint_input=fingerprint_input,
        scope_ref_map=tuple(scope_ref_map),
        semantic_entries=tuple(semantic_entries),
        input_diagnostics=tuple(input_diagnostics),
    )
