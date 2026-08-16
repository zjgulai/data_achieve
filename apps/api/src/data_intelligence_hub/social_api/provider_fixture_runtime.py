from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from typing import Literal, Protocol

from data_intelligence_hub.services.provider_execution_preflight import (
    ProviderExecutionPreflightDecision,
)
from data_intelligence_hub.social_api.output_contracts import (
    PlatformAdapterFixtureRequest,
    PlatformAdapterFixtureResponse,
)
from data_intelligence_hub.social_api.provider_preflight import (
    ProviderCallOperationIntent,
    ProviderCallPolicy,
)

FixtureRuntimeStatus = Literal["succeeded", "cached", "blocked", "failed"]
FixtureAttemptStatus = Literal[
    "succeeded",
    "retryable_error",
    "timeout",
    "terminal_error",
]
RuntimeStopCode = Literal[
    "runtime_request_budget_exceeded",
    "runtime_quota_budget_exceeded",
    "runtime_cost_budget_exceeded",
    "runtime_rate_limit_exceeded",
]

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")
_RETRYABLE_ERROR_CODES = frozenset({"fixture_transport_temporarily_unavailable"})
_TERMINAL_ERROR_CODES = frozenset({"fixture_transport_request_rejected"})


class FixtureRuntimeContractError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class FixtureTransportRetryableError(RuntimeError):
    def __init__(self, code: str) -> None:
        if code not in _RETRYABLE_ERROR_CODES:
            raise FixtureRuntimeContractError("fixture_retryable_error_code_invalid")
        self.code = code
        super().__init__(code)


class FixtureTransportTerminalError(RuntimeError):
    def __init__(self, code: str) -> None:
        if code not in _TERMINAL_ERROR_CODES:
            raise FixtureRuntimeContractError("fixture_terminal_error_code_invalid")
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class FixtureRuntimeLimits:
    rate_limit_requests: int
    rate_window_seconds: int
    cache_ttl_seconds: int
    attempt_timeout_seconds: float

    def __post_init__(self) -> None:
        if (
            isinstance(self.rate_limit_requests, bool)
            or not isinstance(self.rate_limit_requests, int)
            or self.rate_limit_requests <= 0
        ):
            raise FixtureRuntimeContractError("fixture_rate_limit_invalid")
        if (
            isinstance(self.rate_window_seconds, bool)
            or not isinstance(self.rate_window_seconds, int)
            or not 1 <= self.rate_window_seconds <= 86_400
        ):
            raise FixtureRuntimeContractError("fixture_rate_window_invalid")
        if (
            isinstance(self.cache_ttl_seconds, bool)
            or not isinstance(self.cache_ttl_seconds, int)
            or not 0 <= self.cache_ttl_seconds <= 604_800
        ):
            raise FixtureRuntimeContractError("fixture_cache_ttl_invalid")
        if (
            isinstance(self.attempt_timeout_seconds, bool)
            or not isinstance(self.attempt_timeout_seconds, int | float)
            or not 0 < self.attempt_timeout_seconds <= 120
        ):
            raise FixtureRuntimeContractError("fixture_attempt_timeout_invalid")


@dataclass(frozen=True, slots=True)
class CallAttemptAudit:
    attempt_number: int
    status: FixtureAttemptStatus
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class CallAuditRecord:
    execution_id: str
    preflight_id: str
    provider_id: str
    operation_id: str
    status: FixtureRuntimeStatus
    started_at: datetime
    completed_at: datetime
    expires_at: datetime
    attempts: tuple[CallAttemptAudit, ...]
    request_count: int
    quota_bucket: str
    quota_units: int
    estimated_cost_usd: Decimal
    cache_key: str
    cache_hit: bool
    response_size_bytes: int | None
    response_record_count: int | None
    error_code: str | None
    fixture_transport_invoked: bool
    provider_call_attempted: Literal[False] = False
    credential_read_attempted: Literal[False] = False


@dataclass(frozen=True, slots=True)
class FixtureRuntimeResult:
    status: FixtureRuntimeStatus
    audit: CallAuditRecord
    response: PlatformAdapterFixtureResponse | None = None
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class FixtureRuntimeCleanupReport:
    evaluated_at: datetime
    cache_entries_removed: int
    audit_records_removed: int


@dataclass(frozen=True, slots=True)
class RuntimeReservation:
    allowed: bool
    blocker: RuntimeStopCode | None = None


class FixtureRuntimeTransport(Protocol):
    async def execute(
        self,
        request: PlatformAdapterFixtureRequest,
    ) -> PlatformAdapterFixtureResponse: ...


class FixtureRuntimeStore(Protocol):
    def get_cached(
        self,
        *,
        cache_key: str,
        now: datetime,
    ) -> PlatformAdapterFixtureResponse | None: ...

    def reserve_attempt(
        self,
        *,
        preflight_id: str,
        provider_id: str,
        operation: ProviderCallOperationIntent,
        policy: ProviderCallPolicy,
        limits: FixtureRuntimeLimits,
        now: datetime,
    ) -> RuntimeReservation:
        """Atomically validate and consume one attempt's runtime budget."""

    def cache_response(
        self,
        *,
        cache_key: str,
        response: PlatformAdapterFixtureResponse,
        expires_at: datetime,
    ) -> None: ...

    def purge_expired(self, *, now: datetime) -> int: ...


class CallAuditRepository(Protocol):
    async def persist(self, audit: CallAuditRecord) -> None: ...

    async def purge_expired(self, *, now: datetime) -> int: ...


@dataclass(slots=True)
class _Usage:
    request_count: int = 0
    quota_units: dict[str, int] = field(default_factory=dict)
    estimated_cost_usd: Decimal = Decimal("0")


@dataclass(frozen=True, slots=True)
class _CacheEntry:
    response: PlatformAdapterFixtureResponse
    expires_at: datetime


class InMemoryFixtureRuntimeStore:
    def __init__(self) -> None:
        self._cache: dict[str, _CacheEntry] = {}
        self._usage: dict[str, _Usage] = {}
        self._rate_events: dict[str, list[datetime]] = {}

    @property
    def cache_entry_count(self) -> int:
        return len(self._cache)

    def get_cached(
        self,
        *,
        cache_key: str,
        now: datetime,
    ) -> PlatformAdapterFixtureResponse | None:
        _require_utc(now, code="fixture_runtime_now_utc_required")
        entry = self._cache.get(cache_key)
        if entry is None:
            return None
        if entry.expires_at <= now:
            del self._cache[cache_key]
            return None
        return entry.response

    def reserve_attempt(
        self,
        *,
        preflight_id: str,
        provider_id: str,
        operation: ProviderCallOperationIntent,
        policy: ProviderCallPolicy,
        limits: FixtureRuntimeLimits,
        now: datetime,
    ) -> RuntimeReservation:
        _require_utc(now, code="fixture_runtime_now_utc_required")
        usage = self._usage.setdefault(preflight_id, _Usage())
        next_requests = usage.request_count + operation.request_count
        if next_requests > policy.max_requests:
            return RuntimeReservation(False, "runtime_request_budget_exceeded")

        quota_increment = operation.request_count * operation.quota_units_per_request
        next_quota = usage.quota_units.get(operation.quota_bucket, 0) + quota_increment
        quota_ceilings = {item.bucket: item.max_units for item in policy.quota_ceilings}
        if next_quota > quota_ceilings[operation.quota_bucket]:
            return RuntimeReservation(False, "runtime_quota_budget_exceeded")

        if operation.estimated_cost_usd is None:
            raise FixtureRuntimeContractError("fixture_runtime_cost_unknown")
        next_cost = usage.estimated_cost_usd + operation.estimated_cost_usd
        if next_cost > policy.max_cost_usd:
            return RuntimeReservation(False, "runtime_cost_budget_exceeded")

        cutoff = now - timedelta(seconds=limits.rate_window_seconds)
        active_events = [
            event for event in self._rate_events.get(provider_id, []) if event > cutoff
        ]
        if len(active_events) + operation.request_count > limits.rate_limit_requests:
            self._rate_events[provider_id] = active_events
            return RuntimeReservation(False, "runtime_rate_limit_exceeded")

        usage.request_count = next_requests
        usage.quota_units[operation.quota_bucket] = next_quota
        usage.estimated_cost_usd = next_cost
        active_events.extend([now] * operation.request_count)
        self._rate_events[provider_id] = active_events
        return RuntimeReservation(True)

    def cache_response(
        self,
        *,
        cache_key: str,
        response: PlatformAdapterFixtureResponse,
        expires_at: datetime,
    ) -> None:
        _require_utc(expires_at, code="fixture_cache_expiry_utc_required")
        self._cache[cache_key] = _CacheEntry(response=response, expires_at=expires_at)

    def purge_expired(self, *, now: datetime) -> int:
        _require_utc(now, code="fixture_runtime_now_utc_required")
        expired = [key for key, entry in self._cache.items() if entry.expires_at <= now]
        for key in expired:
            del self._cache[key]
        return len(expired)


class InMemoryCallAuditRepository:
    def __init__(self) -> None:
        self._records: list[CallAuditRecord] = []

    @property
    def records(self) -> tuple[CallAuditRecord, ...]:
        return tuple(self._records)

    async def persist(self, audit: CallAuditRecord) -> None:
        if any(record.execution_id == audit.execution_id for record in self._records):
            raise FixtureRuntimeContractError("fixture_call_audit_execution_duplicate")
        self._records.append(audit)

    async def purge_expired(self, *, now: datetime) -> int:
        _require_utc(now, code="fixture_runtime_now_utc_required")
        retained = [record for record in self._records if record.expires_at > now]
        removed = len(self._records) - len(retained)
        self._records = retained
        return removed


def _require_utc(value: datetime, *, code: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise FixtureRuntimeContractError(code)


def _cache_key(
    *,
    preflight_id: str,
    operation_id: str,
    request: PlatformAdapterFixtureRequest,
) -> str:
    payload = {
        "preflight_id": preflight_id,
        "operation_id": operation_id,
        "request": request.model_dump(mode="json"),
    }
    canonical = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{sha256(canonical).hexdigest()}"


def _validate_execution_contract(
    *,
    execution_id: str,
    decision: ProviderExecutionPreflightDecision,
    operation: ProviderCallOperationIntent,
    request: PlatformAdapterFixtureRequest,
    limits: FixtureRuntimeLimits,
) -> None:
    if _IDENTIFIER.fullmatch(execution_id) is None:
        raise FixtureRuntimeContractError("fixture_execution_id_invalid")
    if operation.operation_id not in decision.audit_draft.operation_ids:
        raise FixtureRuntimeContractError("fixture_operation_not_in_preflight")
    if request.operation_id != operation.operation_id:
        raise FixtureRuntimeContractError("fixture_request_operation_mismatch")
    if request.provider_id != decision.preflight.provider_id:
        raise FixtureRuntimeContractError("fixture_request_provider_mismatch")
    if limits.attempt_timeout_seconds > decision.preflight.timeout_seconds:
        raise FixtureRuntimeContractError("fixture_attempt_timeout_exceeds_preflight")


def _audit_record(
    *,
    execution_id: str,
    decision: ProviderExecutionPreflightDecision,
    operation: ProviderCallOperationIntent,
    status: FixtureRuntimeStatus,
    started_at: datetime,
    completed_at: datetime,
    attempts: tuple[CallAttemptAudit, ...],
    request_count: int,
    quota_units: int,
    estimated_cost_usd: Decimal,
    cache_key: str,
    cache_hit: bool,
    response: PlatformAdapterFixtureResponse | None,
    error_code: str | None,
) -> CallAuditRecord:
    return CallAuditRecord(
        execution_id=execution_id,
        preflight_id=decision.preflight.preflight_id,
        provider_id=decision.preflight.provider_id,
        operation_id=operation.operation_id,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        expires_at=completed_at + timedelta(hours=decision.audit_draft.policy.retention_hours),
        attempts=attempts,
        request_count=request_count,
        quota_bucket=operation.quota_bucket,
        quota_units=quota_units,
        estimated_cost_usd=estimated_cost_usd,
        cache_key=cache_key,
        cache_hit=cache_hit,
        response_size_bytes=None if response is None else response.response_size_bytes,
        response_record_count=None if response is None else len(response.records),
        error_code=error_code,
        fixture_transport_invoked=bool(attempts),
    )


async def _persist_result(
    *,
    audit_repository: CallAuditRepository,
    audit: CallAuditRecord,
    response: PlatformAdapterFixtureResponse | None = None,
) -> FixtureRuntimeResult:
    await audit_repository.persist(audit)
    return FixtureRuntimeResult(
        status=audit.status,
        audit=audit,
        response=response,
        error_code=audit.error_code,
    )


async def execute_fixture_runtime(
    *,
    execution_id: str,
    decision: ProviderExecutionPreflightDecision,
    operation: ProviderCallOperationIntent,
    request: PlatformAdapterFixtureRequest,
    transport: FixtureRuntimeTransport,
    store: FixtureRuntimeStore,
    audit_repository: CallAuditRepository,
    limits: FixtureRuntimeLimits,
    clock: Callable[[], datetime],
) -> FixtureRuntimeResult:
    _validate_execution_contract(
        execution_id=execution_id,
        decision=decision,
        operation=operation,
        request=request,
        limits=limits,
    )
    started_at = clock()
    _require_utc(started_at, code="fixture_runtime_now_utc_required")
    cache_key = _cache_key(
        preflight_id=decision.preflight.preflight_id,
        operation_id=operation.operation_id,
        request=request,
    )

    if decision.status == "blocked":
        preflight_error_code = decision.preflight.blockers[0].code
        audit = _audit_record(
            execution_id=execution_id,
            decision=decision,
            operation=operation,
            status="blocked",
            started_at=started_at,
            completed_at=started_at,
            attempts=(),
            request_count=0,
            quota_units=0,
            estimated_cost_usd=Decimal("0"),
            cache_key=cache_key,
            cache_hit=False,
            response=None,
            error_code=preflight_error_code,
        )
        return await _persist_result(audit_repository=audit_repository, audit=audit)

    cached = store.get_cached(cache_key=cache_key, now=started_at)
    if cached is not None:
        audit = _audit_record(
            execution_id=execution_id,
            decision=decision,
            operation=operation,
            status="cached",
            started_at=started_at,
            completed_at=started_at,
            attempts=(),
            request_count=0,
            quota_units=0,
            estimated_cost_usd=Decimal("0"),
            cache_key=cache_key,
            cache_hit=True,
            response=cached,
            error_code=None,
        )
        return await _persist_result(
            audit_repository=audit_repository,
            audit=audit,
            response=cached,
        )

    attempts: list[CallAttemptAudit] = []
    request_count = 0
    quota_units = 0
    estimated_cost_usd = Decimal("0")
    max_attempts = 1 + decision.preflight.max_retry_attempts

    for attempt_number in range(1, max_attempts + 1):
        attempt_started_at = clock()
        _require_utc(attempt_started_at, code="fixture_runtime_now_utc_required")
        reservation = store.reserve_attempt(
            preflight_id=decision.preflight.preflight_id,
            provider_id=decision.preflight.provider_id,
            operation=operation,
            policy=decision.audit_draft.policy,
            limits=limits,
            now=attempt_started_at,
        )
        if not reservation.allowed:
            completed_at = clock()
            _require_utc(completed_at, code="fixture_runtime_now_utc_required")
            audit = _audit_record(
                execution_id=execution_id,
                decision=decision,
                operation=operation,
                status="blocked",
                started_at=started_at,
                completed_at=completed_at,
                attempts=tuple(attempts),
                request_count=request_count,
                quota_units=quota_units,
                estimated_cost_usd=estimated_cost_usd,
                cache_key=cache_key,
                cache_hit=False,
                response=None,
                error_code=reservation.blocker,
            )
            return await _persist_result(audit_repository=audit_repository, audit=audit)

        request_count += operation.request_count
        quota_units += operation.request_count * operation.quota_units_per_request
        if operation.estimated_cost_usd is None:
            raise FixtureRuntimeContractError("fixture_runtime_cost_unknown")
        estimated_cost_usd += operation.estimated_cost_usd

        error_code: str
        try:
            response = await asyncio.wait_for(
                transport.execute(request),
                timeout=limits.attempt_timeout_seconds,
            )
            if response.provider_id != request.provider_id or response.request != request:
                raise FixtureTransportTerminalError("fixture_transport_request_rejected")
        except TimeoutError:
            attempts.append(
                CallAttemptAudit(attempt_number, "timeout", "fixture_transport_timeout")
            )
            if attempt_number < max_attempts:
                continue
            error_code = "fixture_transport_timeout"
        except FixtureTransportRetryableError as exc:
            attempts.append(CallAttemptAudit(attempt_number, "retryable_error", exc.code))
            if attempt_number < max_attempts:
                continue
            error_code = "fixture_retry_exhausted"
        except FixtureTransportTerminalError as exc:
            attempts.append(CallAttemptAudit(attempt_number, "terminal_error", exc.code))
            error_code = exc.code
        except Exception:
            attempts.append(
                CallAttemptAudit(
                    attempt_number,
                    "terminal_error",
                    "fixture_transport_unexpected_error",
                )
            )
            error_code = "fixture_transport_unexpected_error"
        else:
            attempts.append(CallAttemptAudit(attempt_number, "succeeded"))
            completed_at = clock()
            _require_utc(completed_at, code="fixture_runtime_now_utc_required")
            if limits.cache_ttl_seconds > 0:
                store.cache_response(
                    cache_key=cache_key,
                    response=response,
                    expires_at=completed_at + timedelta(seconds=limits.cache_ttl_seconds),
                )
            audit = _audit_record(
                execution_id=execution_id,
                decision=decision,
                operation=operation,
                status="succeeded",
                started_at=started_at,
                completed_at=completed_at,
                attempts=tuple(attempts),
                request_count=request_count,
                quota_units=quota_units,
                estimated_cost_usd=estimated_cost_usd,
                cache_key=cache_key,
                cache_hit=False,
                response=response,
                error_code=None,
            )
            return await _persist_result(
                audit_repository=audit_repository,
                audit=audit,
                response=response,
            )

        completed_at = clock()
        _require_utc(completed_at, code="fixture_runtime_now_utc_required")
        audit = _audit_record(
            execution_id=execution_id,
            decision=decision,
            operation=operation,
            status="failed",
            started_at=started_at,
            completed_at=completed_at,
            attempts=tuple(attempts),
            request_count=request_count,
            quota_units=quota_units,
            estimated_cost_usd=estimated_cost_usd,
            cache_key=cache_key,
            cache_hit=False,
            response=None,
            error_code=error_code,
        )
        return await _persist_result(audit_repository=audit_repository, audit=audit)

    raise RuntimeError("fixture_runtime_unreachable")


async def cleanup_fixture_runtime(
    *,
    store: FixtureRuntimeStore,
    audit_repository: CallAuditRepository,
    now: datetime,
) -> FixtureRuntimeCleanupReport:
    _require_utc(now, code="fixture_runtime_now_utc_required")
    cache_entries_removed = store.purge_expired(now=now)
    audit_records_removed = await audit_repository.purge_expired(now=now)
    return FixtureRuntimeCleanupReport(
        evaluated_at=now,
        cache_entries_removed=cache_entries_removed,
        audit_records_removed=audit_records_removed,
    )


__all__ = [
    "CallAttemptAudit",
    "CallAuditRecord",
    "CallAuditRepository",
    "FixtureRuntimeCleanupReport",
    "FixtureRuntimeContractError",
    "FixtureRuntimeLimits",
    "FixtureRuntimeResult",
    "FixtureRuntimeStore",
    "FixtureRuntimeTransport",
    "FixtureTransportRetryableError",
    "FixtureTransportTerminalError",
    "InMemoryCallAuditRepository",
    "InMemoryFixtureRuntimeStore",
    "RuntimeReservation",
    "cleanup_fixture_runtime",
    "execute_fixture_runtime",
]
