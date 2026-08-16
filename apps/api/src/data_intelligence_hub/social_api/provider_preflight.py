from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from typing import Literal

from data_intelligence_hub.social_api.contracts import CredentialReference

ProviderOperationClass = Literal["safe_read", "unsafe_write"]
PreflightBlockerCode = Literal[
    "request_budget_exceeded",
    "item_budget_exceeded",
    "quota_ceiling_missing",
    "quota_budget_exceeded",
    "cost_unknown",
    "cost_budget_exceeded",
    "retry_amplification_exceeded",
    "operation_not_safe_read",
]

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_BLOCKER_PRIORITY: tuple[PreflightBlockerCode, ...] = (
    "request_budget_exceeded",
    "item_budget_exceeded",
    "quota_ceiling_missing",
    "quota_budget_exceeded",
    "cost_unknown",
    "cost_budget_exceeded",
    "retry_amplification_exceeded",
    "operation_not_safe_read",
)


class ProviderCallPreflightContractError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require_identifier(value: object, *, code: str) -> None:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ProviderCallPreflightContractError(code)


def _require_positive_int(value: object, *, code: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ProviderCallPreflightContractError(code)


def _require_bounded_int(value: object, *, minimum: int, maximum: int, code: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ProviderCallPreflightContractError(code)


def _require_non_negative_decimal(value: object, *, code: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ProviderCallPreflightContractError(code)


@dataclass(frozen=True, slots=True)
class QuotaCeiling:
    bucket: str
    max_units: int

    def __post_init__(self) -> None:
        _require_identifier(
            self.bucket,
            code="provider_preflight_quota_bucket_invalid",
        )
        _require_positive_int(
            self.max_units,
            code="provider_preflight_quota_ceiling_invalid",
        )


@dataclass(frozen=True, slots=True)
class ProviderCallOperationIntent:
    operation_id: str
    method: str
    request_count: int
    max_items: int
    quota_bucket: str
    quota_units_per_request: int
    estimated_cost_usd: Decimal | None
    operation_class: ProviderOperationClass

    def __post_init__(self) -> None:
        _require_identifier(
            self.operation_id,
            code="provider_preflight_operation_id_invalid",
        )
        _require_identifier(
            self.method,
            code="provider_preflight_method_invalid",
        )
        _require_positive_int(
            self.request_count,
            code="provider_preflight_request_count_invalid",
        )
        _require_positive_int(
            self.max_items,
            code="provider_preflight_max_items_invalid",
        )
        _require_identifier(
            self.quota_bucket,
            code="provider_preflight_quota_bucket_invalid",
        )
        _require_positive_int(
            self.quota_units_per_request,
            code="provider_preflight_quota_units_invalid",
        )
        if self.estimated_cost_usd is not None:
            _require_non_negative_decimal(
                self.estimated_cost_usd,
                code="provider_preflight_estimated_cost_invalid",
            )
        if self.operation_class not in ("safe_read", "unsafe_write"):
            raise ProviderCallPreflightContractError("provider_preflight_operation_class_invalid")


@dataclass(frozen=True, slots=True)
class ProviderCallIntent:
    provider_id: str
    operations: tuple[ProviderCallOperationIntent, ...]
    credential_reference: CredentialReference = field(repr=False)

    def __post_init__(self) -> None:
        _require_identifier(
            self.provider_id,
            code="provider_preflight_provider_id_invalid",
        )
        if not isinstance(self.operations, tuple) or not self.operations:
            raise ProviderCallPreflightContractError("provider_preflight_operations_empty")
        if not all(isinstance(item, ProviderCallOperationIntent) for item in self.operations):
            raise ProviderCallPreflightContractError("provider_preflight_operation_invalid")
        operation_ids = [item.operation_id for item in self.operations]
        if len(operation_ids) != len(set(operation_ids)):
            raise ProviderCallPreflightContractError("provider_preflight_operation_duplicate")
        if not isinstance(self.credential_reference, CredentialReference):
            raise ProviderCallPreflightContractError(
                "provider_preflight_credential_reference_invalid"
            )


@dataclass(frozen=True, slots=True)
class ProviderCallPolicy:
    max_requests: int
    max_items: int
    max_cost_usd: Decimal
    quota_ceilings: tuple[QuotaCeiling, ...]
    timeout_seconds: int
    max_retry_attempts: int
    retention_hours: int

    def __post_init__(self) -> None:
        _require_positive_int(
            self.max_requests,
            code="provider_preflight_max_requests_invalid",
        )
        _require_positive_int(
            self.max_items,
            code="provider_preflight_max_items_invalid",
        )
        _require_non_negative_decimal(
            self.max_cost_usd,
            code="provider_preflight_max_cost_invalid",
        )
        if not isinstance(self.quota_ceilings, tuple) or not self.quota_ceilings:
            raise ProviderCallPreflightContractError("provider_preflight_quota_ceilings_empty")
        if not all(isinstance(item, QuotaCeiling) for item in self.quota_ceilings):
            raise ProviderCallPreflightContractError("provider_preflight_quota_ceiling_invalid")
        buckets = [item.bucket for item in self.quota_ceilings]
        if len(buckets) != len(set(buckets)):
            raise ProviderCallPreflightContractError("provider_preflight_quota_ceiling_duplicate")
        _require_bounded_int(
            self.timeout_seconds,
            minimum=1,
            maximum=120,
            code="provider_preflight_timeout_invalid",
        )
        _require_bounded_int(
            self.max_retry_attempts,
            minimum=0,
            maximum=3,
            code="provider_preflight_retry_invalid",
        )
        _require_bounded_int(
            self.retention_hours,
            minimum=1,
            maximum=8760,
            code="provider_preflight_retention_invalid",
        )


@dataclass(frozen=True, slots=True)
class PreflightBlocker:
    code: PreflightBlockerCode
    subject: str | None = None


@dataclass(frozen=True, slots=True)
class QuotaUsage:
    bucket: str
    base_units: int
    worst_case_units: int


@dataclass(frozen=True, slots=True)
class ProviderCallTotals:
    base_requests: int
    worst_case_requests: int
    max_items: int
    quota_usage: tuple[QuotaUsage, ...]
    base_cost_usd: Decimal | None
    worst_case_cost_usd: Decimal | None


@dataclass(frozen=True, slots=True)
class ProviderCallPreflight:
    preflight_id: str
    provider_id: str
    eligible_for_authorization: bool
    blockers: tuple[PreflightBlocker, ...]
    totals: ProviderCallTotals
    timeout_seconds: int
    max_retry_attempts: int
    provider_call_allowed: Literal[False] = False
    next_required_authorization: str = "exact_live_provider_call_authorization"


@dataclass(frozen=True, slots=True)
class CallAuditDraft:
    preflight_id: str
    evaluated_at: datetime
    provider_id: str
    operation_ids: tuple[str, ...]
    reference_fingerprint: str
    policy: ProviderCallPolicy
    totals: ProviderCallTotals
    blockers: tuple[PreflightBlocker, ...]
    provider_call_attempted: Literal[False] = False


def _reference_fingerprint(intent: ProviderCallIntent) -> str:
    reference = intent.credential_reference
    return sha256(
        bytes(
            f"{intent.provider_id}:{reference.scheme}:{reference.name}",
            encoding="utf-8",
        )
    ).hexdigest()


def _canonical_preflight_payload(
    intent: ProviderCallIntent,
    policy: ProviderCallPolicy,
) -> dict[str, object]:
    return {
        "provider_id": intent.provider_id,
        "operations": [
            {
                "operation_id": operation.operation_id,
                "method": operation.method,
                "request_count": operation.request_count,
                "max_items": operation.max_items,
                "quota_bucket": operation.quota_bucket,
                "quota_units_per_request": operation.quota_units_per_request,
                "estimated_cost_usd": (
                    None
                    if operation.estimated_cost_usd is None
                    else str(operation.estimated_cost_usd)
                ),
                "operation_class": operation.operation_class,
            }
            for operation in intent.operations
        ],
        "reference_fingerprint": _reference_fingerprint(intent),
        "policy": {
            "max_requests": policy.max_requests,
            "max_items": policy.max_items,
            "max_cost_usd": str(policy.max_cost_usd),
            "quota_ceilings": [
                {"bucket": ceiling.bucket, "max_units": ceiling.max_units}
                for ceiling in sorted(policy.quota_ceilings, key=lambda item: item.bucket)
            ],
            "timeout_seconds": policy.timeout_seconds,
            "max_retry_attempts": policy.max_retry_attempts,
            "retention_hours": policy.retention_hours,
        },
    }


def _preflight_id(intent: ProviderCallIntent, policy: ProviderCallPolicy) -> str:
    payload = _canonical_preflight_payload(intent, policy)
    canonical = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{sha256(canonical).hexdigest()}"


def _compile_totals(
    intent: ProviderCallIntent,
    policy: ProviderCallPolicy,
) -> ProviderCallTotals:
    multiplier = 1 + policy.max_retry_attempts
    quota_totals: defaultdict[str, int] = defaultdict(int)
    for operation in intent.operations:
        quota_totals[operation.quota_bucket] += (
            operation.request_count * operation.quota_units_per_request
        )

    known_costs = [
        operation.estimated_cost_usd
        for operation in intent.operations
        if operation.estimated_cost_usd is not None
    ]
    all_costs_known = len(known_costs) == len(intent.operations)
    base_cost = sum(known_costs, start=Decimal("0")) if all_costs_known else None

    return ProviderCallTotals(
        base_requests=sum(operation.request_count for operation in intent.operations),
        worst_case_requests=sum(operation.request_count for operation in intent.operations)
        * multiplier,
        max_items=sum(operation.max_items for operation in intent.operations),
        quota_usage=tuple(
            QuotaUsage(
                bucket=bucket,
                base_units=units,
                worst_case_units=units * multiplier,
            )
            for bucket, units in sorted(quota_totals.items())
        ),
        base_cost_usd=base_cost,
        worst_case_cost_usd=None if base_cost is None else base_cost * multiplier,
    )


def _policy_blockers(
    intent: ProviderCallIntent,
    policy: ProviderCallPolicy,
    totals: ProviderCallTotals,
) -> tuple[PreflightBlocker, ...]:
    blockers: list[PreflightBlocker] = []
    retry_amplification_exceeded = False

    if totals.worst_case_requests > policy.max_requests:
        blockers.append(PreflightBlocker(code="request_budget_exceeded"))
        retry_amplification_exceeded = totals.base_requests <= policy.max_requests

    if totals.max_items > policy.max_items:
        blockers.append(PreflightBlocker(code="item_budget_exceeded"))

    quota_ceilings = {ceiling.bucket: ceiling.max_units for ceiling in policy.quota_ceilings}
    for usage in totals.quota_usage:
        ceiling = quota_ceilings.get(usage.bucket)
        if ceiling is None:
            blockers.append(
                PreflightBlocker(
                    code="quota_ceiling_missing",
                    subject=usage.bucket,
                )
            )
        elif usage.worst_case_units > ceiling:
            blockers.append(
                PreflightBlocker(
                    code="quota_budget_exceeded",
                    subject=usage.bucket,
                )
            )
            retry_amplification_exceeded = (
                retry_amplification_exceeded or usage.base_units <= ceiling
            )

    if totals.worst_case_cost_usd is None:
        blockers.append(PreflightBlocker(code="cost_unknown"))
    elif totals.worst_case_cost_usd > policy.max_cost_usd:
        blockers.append(PreflightBlocker(code="cost_budget_exceeded"))
        retry_amplification_exceeded = (
            retry_amplification_exceeded
            or totals.base_cost_usd is not None
            and totals.base_cost_usd <= policy.max_cost_usd
        )

    if retry_amplification_exceeded:
        blockers.append(PreflightBlocker(code="retry_amplification_exceeded"))

    blockers.extend(
        PreflightBlocker(
            code="operation_not_safe_read",
            subject=operation.operation_id,
        )
        for operation in intent.operations
        if operation.operation_class != "safe_read"
    )
    return tuple(blockers)


def compile_provider_call_preflight(
    intent: ProviderCallIntent,
    policy: ProviderCallPolicy,
    *,
    evaluated_at: datetime,
) -> tuple[ProviderCallPreflight, CallAuditDraft]:
    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() != timedelta(0):
        raise ProviderCallPreflightContractError("provider_preflight_evaluated_at_utc_required")

    totals = _compile_totals(intent, policy)
    blockers = tuple(
        sorted(
            _policy_blockers(intent, policy, totals),
            key=lambda blocker: (
                _BLOCKER_PRIORITY.index(blocker.code),
                blocker.subject or "",
            ),
        )
    )
    preflight_id = _preflight_id(intent, policy)
    preflight = ProviderCallPreflight(
        preflight_id=preflight_id,
        provider_id=intent.provider_id,
        eligible_for_authorization=not blockers,
        blockers=blockers,
        totals=totals,
        timeout_seconds=policy.timeout_seconds,
        max_retry_attempts=policy.max_retry_attempts,
    )
    audit = CallAuditDraft(
        preflight_id=preflight_id,
        evaluated_at=evaluated_at,
        provider_id=intent.provider_id,
        operation_ids=tuple(operation.operation_id for operation in intent.operations),
        reference_fingerprint=_reference_fingerprint(intent),
        policy=policy,
        totals=totals,
        blockers=blockers,
    )
    return preflight, audit
