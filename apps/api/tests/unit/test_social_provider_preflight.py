from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from inspect import Parameter, getsource, signature

import pytest

from data_intelligence_hub.social_api import provider_preflight as preflight_module
from data_intelligence_hub.social_api.contracts import CredentialReference
from data_intelligence_hub.social_api.provider_preflight import (
    ProviderCallIntent,
    ProviderCallOperationIntent,
    ProviderCallPolicy,
    ProviderCallPreflightContractError,
    ProviderOperationClass,
    QuotaCeiling,
)


def _operation(
    *,
    operation_id: str = "youtube.search.list",
    request_count: int = 1,
    max_items: int = 25,
    quota_bucket: str = "youtube_search_queries",
    quota_units_per_request: int = 1,
    estimated_cost_usd: Decimal | None = Decimal("0"),
    operation_class: ProviderOperationClass = "safe_read",
) -> ProviderCallOperationIntent:
    return ProviderCallOperationIntent(
        operation_id=operation_id,
        method="search.list",
        request_count=request_count,
        max_items=max_items,
        quota_bucket=quota_bucket,
        quota_units_per_request=quota_units_per_request,
        estimated_cost_usd=estimated_cost_usd,
        operation_class=operation_class,
    )


def _policy(
    *,
    max_requests: int = 2,
    max_items: int = 25,
    max_cost_usd: Decimal = Decimal("0"),
    quota_units: int = 2,
    max_retry_attempts: int = 1,
) -> ProviderCallPolicy:
    return ProviderCallPolicy(
        max_requests=max_requests,
        max_items=max_items,
        max_cost_usd=max_cost_usd,
        quota_ceilings=(
            QuotaCeiling(
                bucket="youtube_search_queries",
                max_units=quota_units,
            ),
        ),
        timeout_seconds=15,
        max_retry_attempts=max_retry_attempts,
        retention_hours=24,
    )


def test_preflight_contracts_are_immutable_and_hide_the_raw_reference() -> None:
    reference = CredentialReference.parse("env:YOUTUBE_API_KEY")
    intent = ProviderCallIntent(
        provider_id="youtube.v3",
        operations=(_operation(),),
        credential_reference=reference,
    )
    policy = _policy()

    assert "YOUTUBE_API_KEY" not in repr(intent)
    assert intent.operations[0].operation_class == "safe_read"
    assert policy.max_retry_attempts == 1

    with pytest.raises((AttributeError, TypeError)):
        intent.provider_id = "reddit.asyncpraw"  # type: ignore[misc]


def test_preflight_contract_rejects_duplicate_operations() -> None:
    operation = _operation()
    with pytest.raises(
        ProviderCallPreflightContractError,
        match="^provider_preflight_operation_duplicate$",
    ):
        ProviderCallIntent(
            provider_id="youtube.v3",
            operations=(operation, operation),
            credential_reference=CredentialReference.parse("env:YOUTUBE_API_KEY"),
        )


def test_compile_preflight_emits_stable_non_authorizing_audit() -> None:
    intent = ProviderCallIntent(
        provider_id="youtube.v3",
        operations=(_operation(),),
        credential_reference=CredentialReference.parse("env:YOUTUBE_API_KEY"),
    )

    first_preflight, first_audit = preflight_module.compile_provider_call_preflight(
        intent,
        _policy(),
        evaluated_at=datetime(2026, 7, 20, 0, 0, tzinfo=UTC),
    )
    second_preflight, second_audit = preflight_module.compile_provider_call_preflight(
        intent,
        _policy(),
        evaluated_at=datetime(2026, 7, 20, 1, 0, tzinfo=UTC),
    )

    assert first_preflight.eligible_for_authorization is True
    assert first_preflight.provider_call_allowed is False
    assert first_preflight.preflight_id == second_preflight.preflight_id
    assert first_preflight.totals.worst_case_requests == 2
    assert first_audit.provider_call_attempted is False
    assert first_audit.evaluated_at != second_audit.evaluated_at
    assert first_audit.reference_fingerprint == second_audit.reference_fingerprint
    serialized = repr((asdict(first_preflight), asdict(first_audit)))
    assert "env:YOUTUBE_API_KEY" not in serialized
    assert "YOUTUBE_API_KEY" not in serialized


def test_compile_preflight_requires_explicit_utc_evaluation_time() -> None:
    intent = ProviderCallIntent(
        provider_id="youtube.v3",
        operations=(_operation(),),
        credential_reference=CredentialReference.parse("env:YOUTUBE_API_KEY"),
    )

    with pytest.raises(
        ProviderCallPreflightContractError,
        match="^provider_preflight_evaluated_at_utc_required$",
    ):
        preflight_module.compile_provider_call_preflight(
            intent,
            _policy(),
            evaluated_at=datetime(2026, 7, 20),
        )


@pytest.mark.parametrize(
    ("operation", "policy", "expected_codes"),
    [
        pytest.param(_operation(), _policy(), (), id="requests-at-limit"),
        pytest.param(
            _operation(),
            _policy(max_requests=1),
            ("request_budget_exceeded", "retry_amplification_exceeded"),
            id="requests-over-limit",
        ),
        pytest.param(_operation(), _policy(max_items=25), (), id="items-at-limit"),
        pytest.param(
            _operation(max_items=26),
            _policy(max_items=25),
            ("item_budget_exceeded",),
            id="items-over-limit",
        ),
        pytest.param(_operation(), _policy(quota_units=2), (), id="quota-at-limit"),
        pytest.param(
            _operation(),
            _policy(quota_units=1),
            ("quota_budget_exceeded", "retry_amplification_exceeded"),
            id="quota-over-limit",
        ),
        pytest.param(
            _operation(quota_bucket="youtube_unregistered_bucket"),
            _policy(),
            ("quota_ceiling_missing",),
            id="quota-ceiling-absent",
        ),
        pytest.param(
            _operation(estimated_cost_usd=None),
            _policy(),
            ("cost_unknown",),
            id="cost-unknown",
        ),
        pytest.param(
            _operation(estimated_cost_usd=Decimal("0.01")),
            _policy(max_cost_usd=Decimal("0.02")),
            (),
            id="cost-at-limit",
        ),
        pytest.param(
            _operation(estimated_cost_usd=Decimal("0.01")),
            _policy(max_cost_usd=Decimal("0.01")),
            ("cost_budget_exceeded", "retry_amplification_exceeded"),
            id="cost-over-limit",
        ),
        pytest.param(
            _operation(operation_class="unsafe_write"),
            _policy(),
            ("operation_not_safe_read",),
            id="unsafe-operation",
        ),
    ],
)
def test_preflight_policy_matrix_fails_closed(
    operation: ProviderCallOperationIntent,
    policy: ProviderCallPolicy,
    expected_codes: tuple[str, ...],
) -> None:
    preflight, audit = preflight_module.compile_provider_call_preflight(
        ProviderCallIntent(
            provider_id="youtube.v3",
            operations=(operation,),
            credential_reference=CredentialReference.parse("env:YOUTUBE_API_KEY"),
        ),
        policy,
        evaluated_at=datetime(2026, 7, 20, tzinfo=UTC),
    )

    assert tuple(blocker.code for blocker in preflight.blockers) == expected_codes
    assert preflight.eligible_for_authorization is (not expected_codes)
    assert preflight.provider_call_allowed is False
    assert audit.provider_call_attempted is False


def test_preflight_retry_amplifies_request_quota_and_known_cost_totals() -> None:
    preflight, _ = preflight_module.compile_provider_call_preflight(
        ProviderCallIntent(
            provider_id="youtube.v3",
            operations=(
                _operation(
                    request_count=2,
                    quota_units_per_request=3,
                    estimated_cost_usd=Decimal("0.25"),
                ),
            ),
            credential_reference=CredentialReference.parse("env:YOUTUBE_API_KEY"),
        ),
        ProviderCallPolicy(
            max_requests=6,
            max_items=25,
            max_cost_usd=Decimal("0.75"),
            quota_ceilings=(QuotaCeiling(bucket="youtube_search_queries", max_units=18),),
            timeout_seconds=15,
            max_retry_attempts=2,
            retention_hours=24,
        ),
        evaluated_at=datetime(2026, 7, 20, tzinfo=UTC),
    )

    assert preflight.totals.base_requests == 2
    assert preflight.totals.worst_case_requests == 6
    assert preflight.totals.quota_usage[0].base_units == 6
    assert preflight.totals.quota_usage[0].worst_case_units == 18
    assert preflight.totals.base_cost_usd == Decimal("0.25")
    assert preflight.totals.worst_case_cost_usd == Decimal("0.75")


def test_preflight_canonical_payload_excludes_raw_credential_reference() -> None:
    payload = preflight_module._canonical_preflight_payload(
        ProviderCallIntent(
            provider_id="youtube.v3",
            operations=(_operation(),),
            credential_reference=CredentialReference.parse("env:YOUTUBE_API_KEY"),
        ),
        _policy(),
    )

    serialized = json.dumps(payload, sort_keys=True)
    assert "env:YOUTUBE_API_KEY" not in serialized
    assert "YOUTUBE_API_KEY" not in serialized


def test_preflight_contract_errors_are_fixed_and_sanitized() -> None:
    reference = CredentialReference.parse("env:YOUTUBE_API_KEY")
    operation = _operation()
    invalid_contracts: tuple[tuple[str, Callable[[], object]], ...] = (
        (
            "provider_preflight_provider_id_invalid",
            lambda: ProviderCallIntent(
                provider_id="youtube provider",
                operations=(operation,),
                credential_reference=reference,
            ),
        ),
        (
            "provider_preflight_operations_empty",
            lambda: ProviderCallIntent(
                provider_id="youtube.v3",
                operations=(),
                credential_reference=reference,
            ),
        ),
        (
            "provider_preflight_operation_duplicate",
            lambda: ProviderCallIntent(
                provider_id="youtube.v3",
                operations=(operation, operation),
                credential_reference=reference,
            ),
        ),
        (
            "provider_preflight_request_count_invalid",
            lambda: _operation(request_count=0),
        ),
        (
            "provider_preflight_max_items_invalid",
            lambda: _operation(max_items=0),
        ),
        (
            "provider_preflight_quota_units_invalid",
            lambda: _operation(quota_units_per_request=0),
        ),
        (
            "provider_preflight_estimated_cost_invalid",
            lambda: _operation(estimated_cost_usd=Decimal("-0.01")),
        ),
        (
            "provider_preflight_estimated_cost_invalid",
            lambda: _operation(estimated_cost_usd=Decimal("NaN")),
        ),
        (
            "provider_preflight_quota_ceiling_duplicate",
            lambda: ProviderCallPolicy(
                max_requests=2,
                max_items=25,
                max_cost_usd=Decimal("0"),
                quota_ceilings=(
                    QuotaCeiling(bucket="youtube_search_queries", max_units=2),
                    QuotaCeiling(bucket="youtube_search_queries", max_units=3),
                ),
                timeout_seconds=15,
                max_retry_attempts=1,
                retention_hours=24,
            ),
        ),
        (
            "provider_preflight_timeout_invalid",
            lambda: ProviderCallPolicy(
                max_requests=2,
                max_items=25,
                max_cost_usd=Decimal("0"),
                quota_ceilings=(QuotaCeiling(bucket="youtube_search_queries", max_units=2),),
                timeout_seconds=0,
                max_retry_attempts=1,
                retention_hours=24,
            ),
        ),
        (
            "provider_preflight_retry_invalid",
            lambda: ProviderCallPolicy(
                max_requests=2,
                max_items=25,
                max_cost_usd=Decimal("0"),
                quota_ceilings=(QuotaCeiling(bucket="youtube_search_queries", max_units=2),),
                timeout_seconds=15,
                max_retry_attempts=4,
                retention_hours=24,
            ),
        ),
        (
            "provider_preflight_retention_invalid",
            lambda: ProviderCallPolicy(
                max_requests=2,
                max_items=25,
                max_cost_usd=Decimal("0"),
                quota_ceilings=(QuotaCeiling(bucket="youtube_search_queries", max_units=2),),
                timeout_seconds=15,
                max_retry_attempts=1,
                retention_hours=0,
            ),
        ),
        (
            "provider_preflight_evaluated_at_utc_required",
            lambda: preflight_module.compile_provider_call_preflight(
                ProviderCallIntent(
                    provider_id="youtube.v3",
                    operations=(operation,),
                    credential_reference=reference,
                ),
                _policy(),
                evaluated_at=datetime(2026, 7, 20),
            ),
        ),
    )

    for expected_code, build_invalid_contract in invalid_contracts:
        with pytest.raises(ProviderCallPreflightContractError) as exc_info:
            build_invalid_contract()
        assert str(exc_info.value) == expected_code
        assert "YOUTUBE_API_KEY" not in str(exc_info.value)


def test_preflight_source_and_signature_exclude_side_effect_dependencies() -> None:
    source = getsource(preflight_module)
    forbidden_source_tokens = (
        "os.environ",
        "EnvironmentCredentialSource",
        "CredentialHandle",
        "googleapiclient",
        "asyncpraw",
        "httpx",
        "sqlalchemy",
    )

    assert all(token not in source for token in forbidden_source_tokens)
    parameters = signature(preflight_module.compile_provider_call_preflight).parameters
    assert tuple(parameters) == ("intent", "policy", "evaluated_at")
    assert parameters["evaluated_at"].kind is Parameter.KEYWORD_ONLY
