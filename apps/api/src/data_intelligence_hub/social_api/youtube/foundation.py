from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from typing import cast

from pydantic import JsonValue

from data_intelligence_hub.schemas.social_provider import SocialProviderCatalogItem
from data_intelligence_hub.schemas.youtube_read_adapter import (
    YouTubeFixtureValidation,
    YouTubeReadAdapterFoundationResponse,
    YouTubeReadPlanRequest,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import sha256_id
from data_intelligence_hub.social_api.contracts import CredentialHandle
from data_intelligence_hub.social_api.youtube.compiler import (
    build_youtube_quota_plan,
    compile_youtube_keyword_video_query,
)
from data_intelligence_hub.social_api.youtube.contracts import YouTubeReadTransport
from data_intelligence_hub.social_api.youtube.fixtures import load_youtube_read_fixture
from data_intelligence_hub.social_api.youtube.normalizer import (
    build_youtube_read_fixture_envelope,
)


class YouTubeLiveExecutionDisabledError(RuntimeError):
    """Live YouTube execution is structurally disabled in this foundation."""


class DisabledYouTubeTransportFactory:
    async def create(
        self,
        *,
        credential: CredentialHandle,
    ) -> YouTubeReadTransport:
        _ = credential
        raise YouTubeLiveExecutionDisabledError("youtube_live_execution_disabled")


def prepare_youtube_read_adapter_foundation(
    payload: YouTubeReadPlanRequest,
    *,
    provider: SocialProviderCatalogItem,
    dependency_present: bool | None = None,
    now: datetime | None = None,
) -> YouTubeReadAdapterFoundationResponse:
    if provider.provider_id != "youtube.v3" or provider.platform != "youtube":
        raise ValueError("youtube_provider_unavailable")
    requested_now = now or datetime.now(UTC)
    if requested_now.utcoffset() is None:
        raise ValueError("youtube_foundation_now_timezone_required")
    checked_at = requested_now.astimezone(UTC)
    loaded = load_youtube_read_fixture()
    compiled = compile_youtube_keyword_video_query(payload.query, video_ids=None)
    quota_plan = build_youtube_quota_plan(
        loaded.quota,
        detail_required=True,
        now=checked_at,
    )
    envelope = build_youtube_read_fixture_envelope(loaded)

    blocked_reasons = list(quota_plan.blocked_reasons)
    for endpoint in ("search.list", "videos.list"):
        if endpoint not in provider.supported_endpoints:
            blocked_reasons.append(f"scope_missing:{endpoint}")
    foundation_ready = not blocked_reasons
    credential_reference = payload.credential_reference
    dependency = (
        importlib.util.find_spec("googleapiclient") is not None
        if dependency_present is None
        else dependency_present
    )
    credential_fingerprint = (
        sha256_id(cast(JsonValue, credential_reference))
        if credential_reference is not None
        else None
    )
    return YouTubeReadAdapterFoundationResponse(
        foundation_ready=foundation_ready,
        declared_readiness=foundation_ready and credential_reference is not None,
        live_dependency_present=dependency,
        credential_reference_present=credential_reference is not None,
        credential_reference_fingerprint=credential_fingerprint,
        query_fingerprint=compiled.query_fingerprint,
        operations=list(compiled.operations),
        quota_plan=quota_plan,
        fixture_validation=YouTubeFixtureValidation(
            fixture_snapshot_digest=loaded.snapshot_digest,
            normalized_payload_digest=envelope.payload_digest,
            evidence_refs=list(loaded.evidence_refs),
            record_count=envelope.records_count,
        ),
        blocked_reasons=blocked_reasons,
        checked_at=checked_at,
    )


def reject_youtube_live_execution(
    *,
    credential_resolver: object,
    transport: object,
) -> None:
    _ = (credential_resolver, transport)
    raise YouTubeLiveExecutionDisabledError("youtube_live_execution_disabled")


__all__ = [
    "DisabledYouTubeTransportFactory",
    "YouTubeLiveExecutionDisabledError",
    "prepare_youtube_read_adapter_foundation",
    "reject_youtube_live_execution",
]
