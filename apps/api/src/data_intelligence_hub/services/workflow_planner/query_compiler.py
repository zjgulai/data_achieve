from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Protocol, cast

from pydantic import JsonValue

from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityOperation,
    PlatformId,
    ResourceType,
)
from data_intelligence_hub.schemas.workflow_planner import (
    CompiledPlatformQuery,
    DecisionTraceEntry,
    MonitoringScopeType,
    NormalizedMonitoringScope,
    NormalizedPlanningInput,
    QueryCompilerFailure,
    QueryTerm,
)
from data_intelligence_hub.services.workflow_planner.candidate_expansion import (
    CandidateExpansionAdapter,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import (
    canonical_json_bytes,
)
from data_intelligence_hub.services.workflow_planner.normalization import (
    NormalizationResult,
    normalize_text,
)

_PLATFORM_ORDER = {platform: index for index, platform in enumerate(PlatformId)}
_TERM_ORIGINS = ("canonical", "alias", "include")
type DeterministicOrigin = Literal[
    "canonical",
    "alias",
    "include",
    "official_account",
    "seed_url",
]


class PlatformQueryCompiler(Protocol):
    @property
    def platform(self) -> PlatformId: ...

    @property
    def query_version(self) -> str: ...

    def compile(
        self,
        normalized_input: NormalizedPlanningInput,
        query_terms: Sequence[QueryTerm],
    ) -> list[CompiledPlatformQuery]: ...


@dataclass(frozen=True)
class QueryCompilationResult:
    query_terms: tuple[QueryTerm, ...]
    compiled_queries: tuple[CompiledPlatformQuery, ...]
    compiler_failures: tuple[QueryCompilerFailure, ...]
    limitations: tuple[str, ...]
    semantic_entries: tuple[DecisionTraceEntry, ...]
    query_versions: Mapping[PlatformId, str]


def _query_term_sort_key(term: QueryTerm) -> tuple[str, str, str, str, str]:
    return (
        term.scope_key,
        term.normalized_term,
        term.origin,
        term.term,
        term.source,
    )


def _input_query_term(
    *,
    scope: NormalizedMonitoringScope,
    scope_ref: str,
    term: str,
    origin: DeterministicOrigin,
    reason: str,
) -> QueryTerm:
    normalized_term = term if origin == "seed_url" else normalize_text(term)
    excluded_terms = {normalize_text(value) for value in scope.exclude_terms}
    rejected = normalized_term in excluded_terms
    return QueryTerm(
        term=term,
        normalized_term=normalized_term,
        scope_ref=scope_ref,
        scope_key=scope.scope_key,
        origin=origin,
        status="rejected" if rejected else "active",
        reason="excluded_term_precedence" if rejected else reason,
        source="user_input",
        score=None,
        conflict_codes=["excluded_term_overlap"] if rejected else [],
    )


def _deterministic_terms(scope: NormalizedMonitoringScope) -> list[QueryTerm]:
    scope_ref = sorted(scope.source_scope_refs)[0]
    terms: list[QueryTerm] = []
    if scope.canonical_term is not None:
        terms.append(
            _input_query_term(
                scope=scope,
                scope_ref=scope_ref,
                term=scope.canonical_term,
                origin="canonical",
                reason="deterministic_input",
            )
        )
    for alias in scope.aliases:
        terms.append(
            _input_query_term(
                scope=scope,
                scope_ref=scope_ref,
                term=alias,
                origin="alias",
                reason="deterministic_input",
            )
        )
    for include_term in scope.include_terms:
        terms.append(
            _input_query_term(
                scope=scope,
                scope_ref=scope_ref,
                term=include_term,
                origin="include",
                reason=(
                    "brand_context_required"
                    if scope.scope_type is MonitoringScopeType.BRAND
                    else "deterministic_input"
                ),
            )
        )
    for account in scope.official_accounts:
        terms.append(
            _input_query_term(
                scope=scope,
                scope_ref=scope_ref,
                term=account,
                origin="official_account",
                reason="deterministic_input",
            )
        )
    for seed_url in scope.seed_urls:
        terms.append(
            _input_query_term(
                scope=scope,
                scope_ref=scope_ref,
                term=seed_url,
                origin="seed_url",
                reason="deterministic_url_input",
            )
        )
    if scope.scope_type is MonitoringScopeType.BRAND and not any(
        term.status == "active"
        and term.origin in {"canonical", "alias", "official_account"}
        for term in terms
    ):
        terms = [
            term.model_copy(
                update={
                    "status": "rejected",
                    "reason": "brand_anchor_required",
                    "conflict_codes": [
                        *term.conflict_codes,
                        "brand_anchor_required",
                    ],
                }
            )
            if term.status == "active" and term.origin == "include"
            else term
            for term in terms
        ]
    return terms


def build_query_terms(
    normalization: NormalizationResult,
    *,
    candidate_adapter: CandidateExpansionAdapter,
) -> list[QueryTerm]:
    terms: list[QueryTerm] = []
    for scope in sorted(
        normalization.normalized_input.scopes,
        key=lambda item: item.scope_key,
    ):
        terms.extend(_deterministic_terms(scope))
        terms.extend(
            candidate_adapter.expand(
                scope,
                flow_mode=normalization.normalized_input.flow_mode,
            )
        )
    return sorted(terms, key=_query_term_sort_key)


@dataclass(frozen=True)
class DeclarativePlatformQueryCompiler:
    platform: PlatformId
    query_version: str

    def compile(
        self,
        normalized_input: NormalizedPlanningInput,
        query_terms: Sequence[QueryTerm],
    ) -> list[CompiledPlatformQuery]:
        terms_by_scope: dict[str, list[QueryTerm]] = {}
        for term in query_terms:
            terms_by_scope.setdefault(term.scope_key, []).append(term)

        queries: list[CompiledPlatformQuery] = []
        for scope in sorted(normalized_input.scopes, key=lambda item: item.scope_key):
            if self.platform not in scope.effective_platforms:
                continue

            active_terms = [
                term
                for term in terms_by_scope.get(scope.scope_key, [])
                if term.status == "active"
            ]
            include_terms = sorted(
                {
                    term.normalized_term
                    for term in active_terms
                    if term.origin in _TERM_ORIGINS
                }
            )
            exclude_terms = sorted(
                {normalize_text(term) for term in scope.exclude_terms}
            )
            account_filters = sorted(
                {
                    term.normalized_term
                    for term in active_terms
                    if term.origin == "official_account"
                }
            )
            url_inputs = sorted(
                {
                    term.normalized_term
                    for term in active_terms
                    if term.origin == "seed_url"
                }
            )
            expression: dict[str, JsonValue] = {
                "accounts": cast(JsonValue, account_filters),
                "active_terms": cast(JsonValue, include_terms),
                "exclusions": cast(JsonValue, exclude_terms),
                "match_mode": scope.match_mode.value,
                "platform": self.platform.value,
                "url_inputs": cast(JsonValue, url_inputs),
            }
            queries.append(
                CompiledPlatformQuery(
                    platform=self.platform,
                    scope_keys=[scope.scope_key],
                    source_scope_refs=sorted(scope.source_scope_refs),
                    resource_type=ResourceType.CONTENT,
                    operation=CapabilityOperation.SEARCH_DISCOVER,
                    query_version=self.query_version,
                    normalized_expression=canonical_json_bytes(expression).decode("utf-8"),
                    include_terms=include_terms,
                    exclude_terms=exclude_terms,
                    account_filters=account_filters,
                    url_inputs=url_inputs,
                    limitations=["declarative_preview_only"],
                )
            )
        return queries


def default_platform_query_compilers() -> dict[PlatformId, PlatformQueryCompiler]:
    return {
        platform: DeclarativePlatformQueryCompiler(
            platform=platform,
            query_version=f"{platform.value}.declarative.v1",
        )
        for platform in PlatformId
    }


def _requested_scope_keys(
    normalized_input: NormalizedPlanningInput,
) -> dict[PlatformId, list[str]]:
    requested: dict[PlatformId, set[str]] = {}
    for scope in normalized_input.scopes:
        for platform in scope.effective_platforms:
            requested.setdefault(platform, set()).add(scope.scope_key)
    return {
        platform: sorted(scope_keys)
        for platform, scope_keys in requested.items()
    }


def _fixture_no_match_entries(
    normalized_input: NormalizedPlanningInput,
    query_terms: Sequence[QueryTerm],
) -> list[DecisionTraceEntry]:
    expanded_scope_keys = {
        term.scope_key
        for term in query_terms
        if term.origin == "fixture_candidate_expansion"
    }
    entries: list[DecisionTraceEntry] = []
    for scope in normalized_input.scopes:
        if scope.canonical_term is None or scope.scope_key in expanded_scope_keys:
            continue
        entries.append(
            DecisionTraceEntry(
                code="fixture_expansion_no_match",
                reason="Fixture candidate expansion has no canonical-term match",
                scope_keys=[scope.scope_key],
                requirement_ref=None,
                details={
                    "normalized_canonical_term": normalize_text(scope.canonical_term)
                },
            )
        )
    return entries


def _validate_compiler_queries(
    *,
    platform: PlatformId,
    compiler: PlatformQueryCompiler,
    normalized_input: NormalizedPlanningInput,
    requested_scope_keys: Sequence[str],
    queries: Sequence[CompiledPlatformQuery],
) -> None:
    requested_scope_key_set = set(requested_scope_keys)
    scopes_by_key = {
        scope.scope_key: scope
        for scope in normalized_input.scopes
        if platform in scope.effective_platforms
    }
    for query in queries:
        if query.platform is not platform:
            raise ValueError(f"query_compiler_output_platform_mismatch:{platform.value}")
        if query.query_version != compiler.query_version:
            raise ValueError(f"query_compiler_output_version_mismatch:{platform.value}")
        if not query.scope_keys:
            raise ValueError(f"query_compiler_output_scope_keys_empty:{platform.value}")
        if query.scope_keys != sorted(set(query.scope_keys)):
            raise ValueError(f"query_compiler_output_scope_keys_invalid:{platform.value}")
        if not set(query.scope_keys).issubset(requested_scope_key_set):
            raise ValueError(f"query_compiler_output_scope_keys_invalid:{platform.value}")
        expected_source_refs = sorted(
            {
                scope_ref
                for scope_key in query.scope_keys
                for scope_ref in scopes_by_key[scope_key].source_scope_refs
            }
        )
        if query.source_scope_refs != expected_source_refs:
            raise ValueError(f"query_compiler_output_source_refs_mismatch:{platform.value}")


def compile_platform_queries(
    normalization: NormalizationResult,
    query_terms: Sequence[QueryTerm],
    *,
    compilers: Mapping[PlatformId, PlatformQueryCompiler],
) -> QueryCompilationResult:
    requested_scope_keys = _requested_scope_keys(normalization.normalized_input)
    requested_platforms = sorted(
        requested_scope_keys,
        key=lambda platform: _PLATFORM_ORDER[platform],
    )
    compiled_queries: list[CompiledPlatformQuery] = []
    failures: list[QueryCompilerFailure] = []
    limitations: list[str] = []
    semantic_entries = _fixture_no_match_entries(
        normalization.normalized_input,
        query_terms,
    )
    query_versions: dict[PlatformId, str] = {}

    for platform in requested_platforms:
        compiler = compilers.get(platform)
        if compiler is None:
            reason = f"Query compiler missing for {platform.value}"
            failures.append(
                QueryCompilerFailure(
                    platform=platform,
                    scope_keys=requested_scope_keys[platform],
                    reason=reason,
                )
            )
            limitation = f"compiler_missing:{platform.value}"
            limitations.append(limitation)
            semantic_entries.append(
                DecisionTraceEntry(
                    code="compiler_missing",
                    reason=reason,
                    scope_keys=requested_scope_keys[platform],
                    requirement_ref=None,
                    details={"platform": platform.value},
                )
            )
            continue
        if compiler.platform is not platform:
            raise ValueError(
                f"query_compiler_platform_mismatch:{platform.value}:{compiler.platform.value}"
            )

        platform_scope_keys = set(requested_scope_keys[platform])
        active_query_terms = tuple(
            sorted(
                (
                    term
                    for term in query_terms
                    if term.status == "active"
                    and term.scope_key in platform_scope_keys
                ),
                key=_query_term_sort_key,
            )
        )
        queries = compiler.compile(
            normalization.normalized_input,
            active_query_terms,
        )
        _validate_compiler_queries(
            platform=platform,
            compiler=compiler,
            normalized_input=normalization.normalized_input,
            requested_scope_keys=requested_scope_keys[platform],
            queries=queries,
        )
        query_versions[platform] = compiler.query_version
        compiled_queries.extend(queries)

    compiled_queries.sort(
        key=lambda query: (
            _PLATFORM_ORDER[query.platform],
            query.scope_keys,
            query.resource_type.value,
            query.operation.value,
        )
    )
    failures.sort(key=lambda failure: _PLATFORM_ORDER[failure.platform])
    semantic_entries.sort(
        key=lambda entry: (
            entry.scope_keys,
            entry.code,
            entry.reason,
            json.dumps(entry.details, ensure_ascii=False, sort_keys=True),
        )
    )
    return QueryCompilationResult(
        query_terms=tuple(sorted(query_terms, key=_query_term_sort_key)),
        compiled_queries=tuple(compiled_queries),
        compiler_failures=tuple(failures),
        limitations=tuple(limitations),
        semantic_entries=tuple(semantic_entries),
        query_versions=MappingProxyType(dict(query_versions)),
    )
