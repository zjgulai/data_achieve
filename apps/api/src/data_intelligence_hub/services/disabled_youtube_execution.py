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
from data_intelligence_hub.social_api.youtube.foundation import (
    DisabledYouTubeTransportFactory,
    YouTubeLiveExecutionDisabledError,
    reject_youtube_live_execution,
)

DisabledYouTubeExecutionStatus = Literal["blocked", "live_execution_disabled"]


@dataclass(frozen=True, slots=True)
class DisabledYouTubeExecutionDecision:
    status: DisabledYouTubeExecutionStatus
    error_code: str
    preflight_decision: ProviderExecutionPreflightDecision
    disabled_boundary_checked: bool
    credential_resolution_attempted: Literal[False] = False
    credential_read_attempted: Literal[False] = False
    client_construction_attempted: Literal[False] = False
    transport_invocation_attempted: Literal[False] = False
    provider_call_allowed: Literal[False] = False
    execution_allowed: Literal[False] = False


def prepare_disabled_youtube_execution(
    intent: ProviderCallIntent,
    policy: ProviderCallPolicy,
    *,
    credential_resolver: CredentialResolver,
    transport_factory: DisabledYouTubeTransportFactory,
    evaluated_at: datetime,
) -> DisabledYouTubeExecutionDecision:
    preflight_decision = prepare_provider_execution_preflight(
        intent,
        policy,
        evaluated_at=evaluated_at,
    )
    if preflight_decision.status == "blocked":
        blocker = preflight_decision.preflight.blockers[0]
        return DisabledYouTubeExecutionDecision(
            status="blocked",
            error_code=blocker.code,
            preflight_decision=preflight_decision,
            disabled_boundary_checked=False,
        )

    try:
        reject_youtube_live_execution(
            credential_resolver=credential_resolver,
            transport=transport_factory,
        )
    except YouTubeLiveExecutionDisabledError as exc:
        error_code = str(exc)
        if error_code != "youtube_live_execution_disabled":
            raise
        return DisabledYouTubeExecutionDecision(
            status="live_execution_disabled",
            error_code=error_code,
            preflight_decision=preflight_decision,
            disabled_boundary_checked=True,
        )

    raise RuntimeError("youtube_disabled_boundary_failed_open")


__all__ = [
    "DisabledYouTubeExecutionDecision",
    "DisabledYouTubeExecutionStatus",
    "prepare_disabled_youtube_execution",
]
