from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from data_intelligence_hub.social_api.provider_preflight import (
    CallAuditDraft,
    ProviderCallIntent,
    ProviderCallPolicy,
    ProviderCallPreflight,
    compile_provider_call_preflight,
)

ProviderExecutionPreflightStatus = Literal["blocked", "eligible_for_authorization"]


@dataclass(frozen=True, slots=True)
class ProviderExecutionPreflightDecision:
    status: ProviderExecutionPreflightStatus
    preflight: ProviderCallPreflight
    audit_draft: CallAuditDraft
    provider_call_allowed: Literal[False] = False
    credential_read_attempted: Literal[False] = False
    client_construction_attempted: Literal[False] = False
    transport_invocation_attempted: Literal[False] = False
    execution_allowed: Literal[False] = False
    next_required_authorization: Literal["exact_live_provider_call_authorization"] = (
        "exact_live_provider_call_authorization"
    )


def prepare_provider_execution_preflight(
    intent: ProviderCallIntent,
    policy: ProviderCallPolicy,
    *,
    evaluated_at: datetime,
) -> ProviderExecutionPreflightDecision:
    preflight, audit_draft = compile_provider_call_preflight(
        intent,
        policy,
        evaluated_at=evaluated_at,
    )
    status: ProviderExecutionPreflightStatus = (
        "eligible_for_authorization" if preflight.eligible_for_authorization else "blocked"
    )
    return ProviderExecutionPreflightDecision(
        status=status,
        preflight=preflight,
        audit_draft=audit_draft,
    )
