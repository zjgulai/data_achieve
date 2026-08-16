from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from inspect import getsource, signature

from data_intelligence_hub.services import disabled_reddit_execution as service_module
from data_intelligence_hub.services.disabled_reddit_execution import (
    DisabledRedditExecutionDecision,
    prepare_disabled_reddit_execution,
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
from data_intelligence_hub.social_api.reddit.contracts import (
    RedditOAuthReadPolicy,
    RedditReadTransport,
)


def _provider_policy(*, retention_hours: int = 24) -> ProviderCallPolicy:
    return ProviderCallPolicy(
        max_requests=2,
        max_items=25,
        max_cost_usd=Decimal("0"),
        quota_ceilings=(QuotaCeiling(bucket="reddit_data_api_requests", max_units=2),),
        timeout_seconds=15,
        max_retry_attempts=1,
        retention_hours=retention_hours,
    )


def _oauth_policy() -> RedditOAuthReadPolicy:
    return RedditOAuthReadPolicy(
        purpose="market_research",
        retention_hours=24,
    )


def _intent(
    *,
    method: str = "search",
    estimated_cost_usd: Decimal | None = Decimal("0"),
) -> ProviderCallIntent:
    return ProviderCallIntent(
        provider_id="reddit.praw",
        operations=(
            ProviderCallOperationIntent(
                operation_id="reddit.search",
                method=method,
                request_count=1,
                max_items=25,
                quota_bucket="reddit_data_api_requests",
                quota_units_per_request=1,
                estimated_cost_usd=estimated_cost_usd,
                operation_class="safe_read",
            ),
        ),
        credential_reference=CredentialReference.parse("secret:reddit-oauth"),
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


class _PoisonRedditTransportFactory:
    def __init__(self) -> None:
        self.create_touched = False

    async def create(
        self,
        *,
        credential: CredentialHandle,
        policy: RedditOAuthReadPolicy,
    ) -> RedditReadTransport:
        _ = (credential, policy)
        self.create_touched = True
        raise AssertionError("transport_factory_create_touched")


def test_blocked_preflight_stops_before_reddit_oauth_and_runtime_boundaries() -> None:
    resolver = _PoisonCredentialResolver()
    factory = _PoisonRedditTransportFactory()

    decision = prepare_disabled_reddit_execution(
        _intent(estimated_cost_usd=None),
        _provider_policy(),
        _oauth_policy(),
        credential_resolver=resolver,
        transport_factory=factory,
        evaluated_at=datetime(2026, 7, 22, tzinfo=UTC),
    )

    assert decision.status == "blocked"
    assert decision.error_code == "cost_unknown"
    assert decision.oauth_policy_checked is False
    assert decision.disabled_boundary_checked is False
    assert resolver.touched is False
    assert factory.create_touched is False
    assert decision.provider_call_allowed is False
    assert decision.execution_allowed is False


def test_reddit_oauth_boundary_blocks_retention_mismatch_and_user_profile() -> None:
    resolver = _PoisonCredentialResolver()
    factory = _PoisonRedditTransportFactory()

    retention = prepare_disabled_reddit_execution(
        _intent(),
        _provider_policy(retention_hours=48),
        _oauth_policy(),
        credential_resolver=resolver,
        transport_factory=factory,
        evaluated_at=datetime(2026, 7, 22, tzinfo=UTC),
    )
    profile = prepare_disabled_reddit_execution(
        _intent(method="user.profile"),
        _provider_policy(),
        _oauth_policy(),
        credential_resolver=resolver,
        transport_factory=factory,
        evaluated_at=datetime(2026, 7, 22, tzinfo=UTC),
    )

    assert retention.status == "blocked"
    assert retention.error_code == "reddit_retention_policy_mismatch"
    assert profile.status == "blocked"
    assert profile.error_code == "reddit_operation_not_allowlisted"
    assert retention.oauth_policy_checked is True
    assert profile.oauth_policy_checked is True
    assert resolver.touched is False
    assert factory.create_touched is False


def test_eligible_reddit_preflight_hits_separate_disabled_boundary() -> None:
    resolver = _PoisonCredentialResolver()
    factory = _PoisonRedditTransportFactory()

    decision = prepare_disabled_reddit_execution(
        _intent(),
        _provider_policy(),
        _oauth_policy(),
        credential_resolver=resolver,
        transport_factory=factory,
        evaluated_at=datetime(2026, 7, 22, tzinfo=UTC),
    )

    assert decision.status == "live_execution_disabled"
    assert decision.error_code == "reddit_live_execution_disabled"
    assert decision.oauth_policy_checked is True
    assert decision.disabled_boundary_checked is True
    assert decision.purpose == "market_research"
    assert decision.oauth_scopes == ("read",)
    assert decision.retention_hours == 24
    assert decision.cleanup_mode == "delete_on_expiry"
    assert decision.next_required_authorization == "exact_reddit_live_provider_call_authorization"
    assert resolver.touched is False
    assert factory.create_touched is False
    assert decision.credential_resolution_attempted is False
    assert decision.credential_read_attempted is False
    assert decision.client_construction_attempted is False
    assert decision.transport_invocation_attempted is False
    assert decision.provider_call_allowed is False
    assert decision.execution_allowed is False


def test_disabled_reddit_composition_has_no_runtime_side_effect_calls() -> None:
    source = getsource(service_module)
    forbidden_source_tokens = (
        "os.environ",
        ".resolve(",
        ".create(",
        "asyncpraw",
        "httpx",
        "sqlalchemy",
        "AsyncSession",
    )

    assert all(token not in source for token in forbidden_source_tokens)
    assert tuple(signature(prepare_disabled_reddit_execution).parameters) == (
        "intent",
        "provider_policy",
        "oauth_policy",
        "credential_resolver",
        "transport_factory",
        "evaluated_at",
    )
    assert DisabledRedditExecutionDecision.__dataclass_params__.frozen is True
