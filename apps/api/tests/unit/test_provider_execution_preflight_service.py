from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from inspect import Parameter, getsource, signature

import pytest

from data_intelligence_hub.services import provider_execution_preflight as service_module
from data_intelligence_hub.services.provider_execution_preflight import (
    ProviderExecutionPreflightDecision,
    prepare_provider_execution_preflight,
)
from data_intelligence_hub.social_api.contracts import CredentialReference
from data_intelligence_hub.social_api.provider_preflight import (
    ProviderCallIntent,
    ProviderCallOperationIntent,
    ProviderCallPolicy,
    QuotaCeiling,
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


def test_prepare_provider_execution_preflight_returns_only_authorization_eligibility() -> None:
    policy = _policy()
    decision = prepare_provider_execution_preflight(
        _intent(),
        policy,
        evaluated_at=datetime(2026, 7, 22, tzinfo=UTC),
    )

    assert decision.status == "eligible_for_authorization"
    assert decision.preflight.eligible_for_authorization is True
    assert decision.preflight.provider_call_allowed is False
    assert decision.audit_draft.operation_ids == ("youtube.search.list",)
    assert decision.audit_draft.policy == policy
    assert decision.provider_call_allowed is False
    assert decision.credential_read_attempted is False
    assert decision.client_construction_attempted is False
    assert decision.transport_invocation_attempted is False
    assert decision.execution_allowed is False
    assert decision.next_required_authorization == "exact_live_provider_call_authorization"
    assert "YOUTUBE_API_KEY" not in repr(decision)

    with pytest.raises((AttributeError, TypeError)):
        decision.status = "blocked"  # type: ignore[misc]


def test_prepare_provider_execution_preflight_retains_fail_closed_blockers() -> None:
    decision = prepare_provider_execution_preflight(
        _intent(estimated_cost_usd=None),
        _policy(),
        evaluated_at=datetime(2026, 7, 22, tzinfo=UTC),
    )

    assert decision.status == "blocked"
    assert tuple(blocker.code for blocker in decision.preflight.blockers) == ("cost_unknown",)
    assert decision.preflight.eligible_for_authorization is False
    assert decision.provider_call_allowed is False
    assert decision.execution_allowed is False
    assert decision.audit_draft.provider_call_attempted is False


def test_provider_execution_preflight_service_has_no_side_effect_dependencies() -> None:
    source = getsource(service_module)
    forbidden_source_tokens = (
        "os.environ",
        "EnvironmentCredentialSource",
        "CredentialHandle",
        "DisabledYouTubeTransportFactory",
        "googleapiclient",
        "asyncpraw",
        "httpx",
        "sqlalchemy",
        "AsyncSession",
    )

    assert all(token not in source for token in forbidden_source_tokens)
    parameters = signature(prepare_provider_execution_preflight).parameters
    assert tuple(parameters) == ("intent", "policy", "evaluated_at")
    assert parameters["evaluated_at"].kind is Parameter.KEYWORD_ONLY
    assert ProviderExecutionPreflightDecision.__dataclass_params__.frozen is True
