from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from data_intelligence_hub.services.provider_execution_preflight import (
    ProviderExecutionPreflightDecision,
    prepare_provider_execution_preflight,
)
from data_intelligence_hub.social_api.contracts import CredentialResolver
from data_intelligence_hub.social_api.provider_preflight import (
    ProviderCallIntent,
    ProviderCallPolicy,
)
from data_intelligence_hub.social_api.reddit.contracts import (
    RedditOAuthReadPolicy,
    RedditTransportFactory,
)
from data_intelligence_hub.social_api.reddit.official_transport import (
    RedditLiveExecutionDisabledError,
)

DisabledRedditExecutionStatus = Literal["blocked", "live_execution_disabled"]
RedditPurpose = Literal["brand_monitoring", "market_research", "customer_feedback"]

_ALLOWED_METHODS = frozenset(
    {
        "hot.list",
        "new.list",
        "search",
        "comments.new",
        "r/{subreddit}/about",
    }
)


@dataclass(frozen=True, slots=True)
class DisabledRedditExecutionDecision:
    status: DisabledRedditExecutionStatus
    error_code: str
    preflight_decision: ProviderExecutionPreflightDecision
    purpose: RedditPurpose
    oauth_scopes: tuple[Literal["read"], ...]
    retention_hours: int
    cleanup_mode: Literal["delete_on_expiry"]
    oauth_policy_checked: bool
    disabled_boundary_checked: bool
    credential_resolution_attempted: Literal[False] = False
    credential_read_attempted: Literal[False] = False
    client_construction_attempted: Literal[False] = False
    transport_invocation_attempted: Literal[False] = False
    provider_call_allowed: Literal[False] = False
    execution_allowed: Literal[False] = False
    next_required_authorization: str = "exact_reddit_live_provider_call_authorization"


def _oauth_policy_blocker(
    intent: ProviderCallIntent,
    provider_policy: ProviderCallPolicy,
    oauth_policy: RedditOAuthReadPolicy,
) -> str | None:
    if intent.provider_id != "reddit.praw":
        return "reddit_provider_id_invalid"
    if any(operation.method not in _ALLOWED_METHODS for operation in intent.operations):
        return "reddit_operation_not_allowlisted"
    if provider_policy.retention_hours != oauth_policy.retention_hours:
        return "reddit_retention_policy_mismatch"
    return None


def _decision(
    *,
    status: DisabledRedditExecutionStatus,
    error_code: str,
    preflight_decision: ProviderExecutionPreflightDecision,
    oauth_policy: RedditOAuthReadPolicy,
    oauth_policy_checked: bool,
    disabled_boundary_checked: bool,
) -> DisabledRedditExecutionDecision:
    return DisabledRedditExecutionDecision(
        status=status,
        error_code=error_code,
        preflight_decision=preflight_decision,
        purpose=oauth_policy.purpose,
        oauth_scopes=oauth_policy.oauth_scopes,
        retention_hours=oauth_policy.retention_hours,
        cleanup_mode=oauth_policy.cleanup_mode,
        oauth_policy_checked=oauth_policy_checked,
        disabled_boundary_checked=disabled_boundary_checked,
    )


def _reject_reddit_live_execution(
    *,
    credential_resolver: CredentialResolver,
    transport_factory: RedditTransportFactory,
) -> None:
    _ = (credential_resolver, transport_factory)
    raise RedditLiveExecutionDisabledError


def prepare_disabled_reddit_execution(
    intent: ProviderCallIntent,
    provider_policy: ProviderCallPolicy,
    oauth_policy: RedditOAuthReadPolicy,
    *,
    credential_resolver: CredentialResolver,
    transport_factory: RedditTransportFactory,
    evaluated_at: datetime,
) -> DisabledRedditExecutionDecision:
    preflight_decision = prepare_provider_execution_preflight(
        intent,
        provider_policy,
        evaluated_at=evaluated_at,
    )
    if preflight_decision.status == "blocked":
        blocker = preflight_decision.preflight.blockers[0]
        return _decision(
            status="blocked",
            error_code=blocker.code,
            preflight_decision=preflight_decision,
            oauth_policy=oauth_policy,
            oauth_policy_checked=False,
            disabled_boundary_checked=False,
        )

    oauth_blocker = _oauth_policy_blocker(intent, provider_policy, oauth_policy)
    if oauth_blocker is not None:
        return _decision(
            status="blocked",
            error_code=oauth_blocker,
            preflight_decision=preflight_decision,
            oauth_policy=oauth_policy,
            oauth_policy_checked=True,
            disabled_boundary_checked=False,
        )

    try:
        _reject_reddit_live_execution(
            credential_resolver=credential_resolver,
            transport_factory=transport_factory,
        )
    except RedditLiveExecutionDisabledError as exc:
        error_code = str(exc)
        if error_code != "reddit_live_execution_disabled":
            raise
        return _decision(
            status="live_execution_disabled",
            error_code=error_code,
            preflight_decision=preflight_decision,
            oauth_policy=oauth_policy,
            oauth_policy_checked=True,
            disabled_boundary_checked=True,
        )

    raise RuntimeError("reddit_disabled_boundary_failed_open")


__all__ = [
    "DisabledRedditExecutionDecision",
    "DisabledRedditExecutionStatus",
    "prepare_disabled_reddit_execution",
]
