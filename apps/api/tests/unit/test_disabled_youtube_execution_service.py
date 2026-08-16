from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from inspect import getsource, signature

import pytest

from data_intelligence_hub.services import disabled_youtube_execution as service_module
from data_intelligence_hub.services.disabled_youtube_execution import (
    DisabledYouTubeExecutionDecision,
    prepare_disabled_youtube_execution,
)
from data_intelligence_hub.social_api.contracts import (
    CredentialHandle,
    CredentialReference,
)
from data_intelligence_hub.social_api.provider_preflight import (
    ProviderCallIntent,
    ProviderCallOperationIntent,
    ProviderCallPolicy,
    QuotaCeiling,
)
from data_intelligence_hub.social_api.youtube.contracts import YouTubeReadTransport
from data_intelligence_hub.social_api.youtube.foundation import (
    DisabledYouTubeTransportFactory,
)


def _policy() -> ProviderCallPolicy:
    return ProviderCallPolicy(
        max_requests=2,
        max_items=25,
        max_cost_usd=Decimal("0"),
        quota_ceilings=(QuotaCeiling(bucket="youtube_search_queries", max_units=2),),
        timeout_seconds=15,
        max_retry_attempts=1,
        retention_hours=24,
    )


def _intent(*, estimated_cost_usd: Decimal | None = Decimal("0")) -> ProviderCallIntent:
    return ProviderCallIntent(
        provider_id="youtube.v3",
        operations=(
            ProviderCallOperationIntent(
                operation_id="youtube.search.list",
                method="search.list",
                request_count=1,
                max_items=25,
                quota_bucket="youtube_search_queries",
                quota_units_per_request=1,
                estimated_cost_usd=estimated_cost_usd,
                operation_class="safe_read",
            ),
        ),
        credential_reference=CredentialReference.parse("env:YOUTUBE_API_KEY"),
    )


class _PoisonCredentialResolver:
    def __init__(self) -> None:
        self.touched = False

    async def resolve(
        self,
        *,
        provider_id: str,
        credential_reference: CredentialReference,
    ) -> CredentialHandle:
        _ = (provider_id, credential_reference)
        self.touched = True
        raise AssertionError("credential_resolver_touched")


class _PoisonDisabledYouTubeTransportFactory(DisabledYouTubeTransportFactory):
    def __init__(self) -> None:
        self.create_touched = False

    async def create(
        self,
        *,
        credential: CredentialHandle,
    ) -> YouTubeReadTransport:
        _ = credential
        self.create_touched = True
        raise AssertionError("transport_factory_create_touched")


def test_blocked_preflight_stops_before_resolver_and_factory() -> None:
    resolver = _PoisonCredentialResolver()
    factory = _PoisonDisabledYouTubeTransportFactory()

    decision = prepare_disabled_youtube_execution(
        _intent(estimated_cost_usd=None),
        _policy(),
        credential_resolver=resolver,
        transport_factory=factory,
        evaluated_at=datetime(2026, 7, 22, tzinfo=UTC),
    )

    assert decision.status == "blocked"
    assert decision.error_code == "cost_unknown"
    assert decision.preflight_decision.preflight.eligible_for_authorization is False
    assert decision.preflight_decision.audit_draft.blockers[0].code == "cost_unknown"
    assert decision.disabled_boundary_checked is False
    assert resolver.touched is False
    assert factory.create_touched is False
    assert decision.credential_resolution_attempted is False
    assert decision.credential_read_attempted is False
    assert decision.client_construction_attempted is False
    assert decision.transport_invocation_attempted is False
    assert decision.provider_call_allowed is False
    assert decision.execution_allowed is False


def test_eligible_preflight_hits_disabled_boundary_before_resolver_and_factory_create() -> None:
    resolver = _PoisonCredentialResolver()
    factory = _PoisonDisabledYouTubeTransportFactory()

    decision = prepare_disabled_youtube_execution(
        _intent(),
        _policy(),
        credential_resolver=resolver,
        transport_factory=factory,
        evaluated_at=datetime(2026, 7, 22, tzinfo=UTC),
    )

    assert decision.status == "live_execution_disabled"
    assert decision.error_code == "youtube_live_execution_disabled"
    assert decision.preflight_decision.preflight.eligible_for_authorization is True
    assert decision.preflight_decision.audit_draft.provider_call_attempted is False
    assert decision.disabled_boundary_checked is True
    assert resolver.touched is False
    assert factory.create_touched is False
    assert decision.credential_resolution_attempted is False
    assert decision.credential_read_attempted is False
    assert decision.client_construction_attempted is False
    assert decision.transport_invocation_attempted is False
    assert decision.provider_call_allowed is False
    assert decision.execution_allowed is False
    assert "YOUTUBE_API_KEY" not in repr(decision)

    with pytest.raises((AttributeError, TypeError)):
        decision.status = "blocked"  # type: ignore[misc]


def test_disabled_composition_has_no_credential_or_transport_side_effect_calls() -> None:
    source = getsource(service_module)
    forbidden_source_tokens = (
        "os.environ",
        "EnvironmentCredentialSource",
        ".resolve(",
        ".create(",
        "googleapiclient",
        "asyncpraw",
        "httpx",
        "sqlalchemy",
        "AsyncSession",
    )

    assert all(token not in source for token in forbidden_source_tokens)
    assert tuple(signature(prepare_disabled_youtube_execution).parameters) == (
        "intent",
        "policy",
        "credential_resolver",
        "transport_factory",
        "evaluated_at",
    )
    assert DisabledYouTubeExecutionDecision.__dataclass_params__.frozen is True
