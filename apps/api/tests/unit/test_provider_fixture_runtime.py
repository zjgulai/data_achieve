from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from inspect import getsource

import pytest

from data_intelligence_hub.services.provider_execution_preflight import (
    prepare_provider_execution_preflight,
)
from data_intelligence_hub.social_api.contracts import CredentialReference
from data_intelligence_hub.social_api.output_contracts import (
    PlatformAdapterFixtureRequest,
    PlatformAdapterFixtureResponse,
    PlatformAdapterNormalizedRecord,
)
from data_intelligence_hub.social_api.provider_fixture_runtime import (
    CallAuditRecord,
    FixtureRuntimeLimits,
    FixtureTransportRetryableError,
    InMemoryCallAuditRepository,
    InMemoryFixtureRuntimeStore,
    cleanup_fixture_runtime,
    execute_fixture_runtime,
)
from data_intelligence_hub.social_api.provider_preflight import (
    ProviderCallIntent,
    ProviderCallOperationIntent,
    ProviderCallPolicy,
    QuotaCeiling,
)


def _operation(
    *,
    estimated_cost_usd: Decimal = Decimal("1"),
) -> ProviderCallOperationIntent:
    return ProviderCallOperationIntent(
        operation_id="fixture:youtube.v3:search.list",
        method="search.list",
        request_count=1,
        max_items=1,
        quota_bucket="youtube_search_queries",
        quota_units_per_request=1,
        estimated_cost_usd=estimated_cost_usd,
        operation_class="safe_read",
    )


def _decision(
    *,
    operation: ProviderCallOperationIntent | None = None,
    max_requests: int = 4,
    max_quota_units: int = 4,
    max_cost_usd: Decimal = Decimal("4"),
    max_retry_attempts: int = 0,
    evaluated_at: datetime | None = None,
):
    selected_operation = operation or _operation()
    intent = ProviderCallIntent(
        provider_id="youtube.v3",
        operations=(selected_operation,),
        credential_reference=CredentialReference.parse("env:YOUTUBE_API_KEY"),
    )
    policy = ProviderCallPolicy(
        max_requests=max_requests,
        max_items=1,
        max_cost_usd=max_cost_usd,
        quota_ceilings=(
            QuotaCeiling(
                bucket="youtube_search_queries",
                max_units=max_quota_units,
            ),
        ),
        timeout_seconds=1,
        max_retry_attempts=max_retry_attempts,
        retention_hours=1,
    )
    return prepare_provider_execution_preflight(
        intent,
        policy,
        evaluated_at=evaluated_at or datetime(2026, 7, 22, tzinfo=UTC),
    )


def _request() -> PlatformAdapterFixtureRequest:
    return PlatformAdapterFixtureRequest(
        provider_id="youtube.v3",
        operation_id="fixture:youtube.v3:search.list",
        endpoint="search.list",
        fixture_limit=1,
        max_response_bytes=10_000,
    )


def _response(request: PlatformAdapterFixtureRequest) -> PlatformAdapterFixtureResponse:
    evidence_ref = "fixture://youtube.v3/search.list/1"
    return PlatformAdapterFixtureResponse(
        request=request,
        provider_id="youtube.v3",
        platform="youtube",
        response_size_bytes=128,
        evidence_refs=(evidence_ref,),
        records=(
            PlatformAdapterNormalizedRecord(
                raw_record_id="youtube:video:fixture-video-1",
                provider_id="youtube.v3",
                platform="youtube",
                endpoint="search.list",
                source_ref="https://www.youtube.com/watch?v=fixture-video-1",
                evidence_ref=evidence_ref,
                record_type="post",
                external_post_id="fixture-video-1",
                text="Fixture video",
                metrics={"views": 10},
                payload_digest="sha256:" + "1" * 64,
            ),
        ),
    )


class _SequenceTransport:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.call_count = 0

    async def execute(
        self,
        request: PlatformAdapterFixtureRequest,
    ) -> PlatformAdapterFixtureResponse:
        outcome = self.outcomes[self.call_count]
        self.call_count += 1
        if isinstance(outcome, Exception):
            raise outcome
        if outcome == "hang":
            await asyncio.Event().wait()
        assert outcome == "success"
        return _response(request)


class _Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


@pytest.mark.asyncio
async def test_fixture_runtime_retries_within_bound_and_records_actual_usage() -> None:
    operation = _operation()
    decision = _decision(operation=operation, max_retry_attempts=2)
    transport = _SequenceTransport(
        [
            FixtureTransportRetryableError("fixture_transport_temporarily_unavailable"),
            FixtureTransportRetryableError("fixture_transport_temporarily_unavailable"),
            "success",
        ]
    )
    store = InMemoryFixtureRuntimeStore()
    audits = InMemoryCallAuditRepository()

    result = await execute_fixture_runtime(
        execution_id="fixture-run-retry-success",
        decision=decision,
        operation=operation,
        request=_request(),
        transport=transport,
        store=store,
        audit_repository=audits,
        limits=FixtureRuntimeLimits(
            rate_limit_requests=3,
            rate_window_seconds=60,
            cache_ttl_seconds=0,
            attempt_timeout_seconds=1,
        ),
        clock=_Clock(datetime(2026, 7, 22, 1, tzinfo=UTC)),
    )

    assert result.status == "succeeded"
    assert result.response is not None
    assert transport.call_count == 3
    assert tuple(attempt.status for attempt in result.audit.attempts) == (
        "retryable_error",
        "retryable_error",
        "succeeded",
    )
    assert result.audit.request_count == 3
    assert result.audit.quota_units == 3
    assert result.audit.estimated_cost_usd == Decimal("3")
    assert result.audit.provider_call_attempted is False
    assert result.audit.credential_read_attempted is False
    assert audits.records == (result.audit,)


@pytest.mark.asyncio
async def test_fixture_runtime_timeout_is_bounded_and_sanitized() -> None:
    operation = _operation()
    decision = _decision(operation=operation)
    transport = _SequenceTransport(["hang"])
    audits = InMemoryCallAuditRepository()

    result = await execute_fixture_runtime(
        execution_id="fixture-run-timeout",
        decision=decision,
        operation=operation,
        request=_request(),
        transport=transport,
        store=InMemoryFixtureRuntimeStore(),
        audit_repository=audits,
        limits=FixtureRuntimeLimits(
            rate_limit_requests=1,
            rate_window_seconds=60,
            cache_ttl_seconds=0,
            attempt_timeout_seconds=0.01,
        ),
        clock=_Clock(datetime(2026, 7, 22, 1, tzinfo=UTC)),
    )

    assert result.status == "failed"
    assert result.error_code == "fixture_transport_timeout"
    assert transport.call_count == 1
    assert result.audit.attempts[0].status == "timeout"
    assert "hang" not in repr(result.audit)


@pytest.mark.asyncio
async def test_fixture_runtime_stops_retry_at_rate_limit_before_transport() -> None:
    operation = _operation()
    decision = _decision(operation=operation, max_retry_attempts=1)
    transport = _SequenceTransport(
        [FixtureTransportRetryableError("fixture_transport_temporarily_unavailable")]
    )

    result = await execute_fixture_runtime(
        execution_id="fixture-run-rate-stop",
        decision=decision,
        operation=operation,
        request=_request(),
        transport=transport,
        store=InMemoryFixtureRuntimeStore(),
        audit_repository=InMemoryCallAuditRepository(),
        limits=FixtureRuntimeLimits(
            rate_limit_requests=1,
            rate_window_seconds=60,
            cache_ttl_seconds=0,
            attempt_timeout_seconds=1,
        ),
        clock=_Clock(datetime(2026, 7, 22, 1, tzinfo=UTC)),
    )

    assert result.status == "blocked"
    assert result.error_code == "runtime_rate_limit_exceeded"
    assert transport.call_count == 1
    assert result.audit.request_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("limit_name", "expected_code"),
    [
        ("request", "runtime_request_budget_exceeded"),
        ("quota", "runtime_quota_budget_exceeded"),
        ("cost", "runtime_cost_budget_exceeded"),
    ],
)
async def test_fixture_runtime_cumulative_budget_stops_before_second_transport(
    limit_name: str,
    expected_code: str,
) -> None:
    operation = _operation()
    decision = _decision(
        operation=operation,
        max_requests=1 if limit_name == "request" else 2,
        max_quota_units=1 if limit_name == "quota" else 2,
        max_cost_usd=Decimal("1") if limit_name == "cost" else Decimal("2"),
    )
    transport = _SequenceTransport(["success"])
    store = InMemoryFixtureRuntimeStore()
    audits = InMemoryCallAuditRepository()
    limits = FixtureRuntimeLimits(
        rate_limit_requests=2,
        rate_window_seconds=60,
        cache_ttl_seconds=0,
        attempt_timeout_seconds=1,
    )
    clock = _Clock(datetime(2026, 7, 22, 1, tzinfo=UTC))

    first = await execute_fixture_runtime(
        execution_id=f"fixture-run-{limit_name}-first",
        decision=decision,
        operation=operation,
        request=_request(),
        transport=transport,
        store=store,
        audit_repository=audits,
        limits=limits,
        clock=clock,
    )
    second = await execute_fixture_runtime(
        execution_id=f"fixture-run-{limit_name}-second",
        decision=decision,
        operation=operation,
        request=_request(),
        transport=transport,
        store=store,
        audit_repository=audits,
        limits=limits,
        clock=clock,
    )

    assert first.status == "succeeded"
    assert second.status == "blocked"
    assert second.error_code == expected_code
    assert transport.call_count == 1
    assert len(audits.records) == 2


@pytest.mark.asyncio
async def test_fixture_runtime_cache_hit_is_zero_budget_and_cleanup_is_explicit() -> None:
    operation = _operation()
    decision = _decision(operation=operation, max_requests=1, max_quota_units=1)
    transport = _SequenceTransport(["success"])
    store = InMemoryFixtureRuntimeStore()
    audits = InMemoryCallAuditRepository()
    clock = _Clock(datetime(2026, 7, 22, 1, tzinfo=UTC))
    limits = FixtureRuntimeLimits(
        rate_limit_requests=1,
        rate_window_seconds=60,
        cache_ttl_seconds=30,
        attempt_timeout_seconds=1,
    )

    first = await execute_fixture_runtime(
        execution_id="fixture-run-cache-first",
        decision=decision,
        operation=operation,
        request=_request(),
        transport=transport,
        store=store,
        audit_repository=audits,
        limits=limits,
        clock=clock,
    )
    second = await execute_fixture_runtime(
        execution_id="fixture-run-cache-second",
        decision=decision,
        operation=operation,
        request=_request(),
        transport=transport,
        store=store,
        audit_repository=audits,
        limits=limits,
        clock=clock,
    )

    assert first.status == "succeeded"
    assert second.status == "cached"
    assert second.response == first.response
    assert second.audit.request_count == 0
    assert second.audit.quota_units == 0
    assert second.audit.estimated_cost_usd == Decimal("0")
    assert transport.call_count == 1

    clock.now += timedelta(hours=2)
    report = await cleanup_fixture_runtime(
        store=store,
        audit_repository=audits,
        now=clock(),
    )

    assert report.cache_entries_removed == 1
    assert report.audit_records_removed == 2
    assert store.cache_entry_count == 0
    assert audits.records == ()


@pytest.mark.asyncio
async def test_blocked_preflight_persists_audit_without_touching_transport() -> None:
    operation = _operation(estimated_cost_usd=Decimal("2"))
    decision = _decision(
        operation=operation,
        max_cost_usd=Decimal("1"),
    )
    transport = _SequenceTransport([])
    audits = InMemoryCallAuditRepository()

    result = await execute_fixture_runtime(
        execution_id="fixture-run-preflight-blocked",
        decision=decision,
        operation=operation,
        request=_request(),
        transport=transport,
        store=InMemoryFixtureRuntimeStore(),
        audit_repository=audits,
        limits=FixtureRuntimeLimits(
            rate_limit_requests=1,
            rate_window_seconds=60,
            cache_ttl_seconds=0,
            attempt_timeout_seconds=1,
        ),
        clock=_Clock(datetime(2026, 7, 22, 1, tzinfo=UTC)),
    )

    assert result.status == "blocked"
    assert result.error_code == "cost_budget_exceeded"
    assert transport.call_count == 0
    assert result.audit.fixture_transport_invoked is False
    assert audits.records == (result.audit,)


def test_runtime_contract_is_immutable_and_has_no_live_side_effect_dependencies() -> None:
    from data_intelligence_hub.social_api import provider_fixture_runtime as runtime_module

    source = getsource(runtime_module)
    forbidden_tokens = (
        "os.environ",
        "EnvironmentCredentialSource",
        "googleapiclient",
        "asyncpraw",
        "httpx",
        "sqlalchemy",
        "AsyncSession",
    )

    assert all(token not in source for token in forbidden_tokens)
    assert CallAuditRecord.__dataclass_params__.frozen is True
    with pytest.raises((AttributeError, TypeError)):
        FixtureRuntimeLimits(
            rate_limit_requests=1,
            rate_window_seconds=60,
            cache_ttl_seconds=0,
            attempt_timeout_seconds=1,
        ).cache_ttl_seconds = 1  # type: ignore[misc]
