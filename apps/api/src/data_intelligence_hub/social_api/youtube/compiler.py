from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast

from pydantic import JsonValue

from data_intelligence_hub.schemas.workflow_execution import Sha256Digest
from data_intelligence_hub.schemas.youtube_read_adapter import (
    YouTubeKeywordVideoQuery,
    YouTubeQuotaEntry,
    YouTubeQuotaPlan,
    YouTubeReadOperation,
)
from data_intelligence_hub.services.workflow_planner.fingerprint import sha256_id
from data_intelligence_hub.social_api.youtube.contracts import YouTubeQuotaEvidence

QUOTA_MAX_AGE = timedelta(days=30)
_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{1,100}$")


@dataclass(frozen=True, slots=True)
class CompiledYouTubeReadPlan:
    query_fingerprint: Sha256Digest
    operations: tuple[YouTubeReadOperation, ...]
    video_ids: tuple[str, ...]


def _ordered_video_ids(video_ids: list[str], *, limit: int) -> tuple[str, ...]:
    normalized: list[str] = []
    for video_id in video_ids:
        if _VIDEO_ID.fullmatch(video_id) is None:
            raise ValueError("youtube_video_id_invalid")
        if video_id not in normalized:
            normalized.append(video_id)
        if len(normalized) == limit:
            break
    return tuple(normalized)


def compile_youtube_keyword_video_query(
    query: YouTubeKeywordVideoQuery,
    *,
    video_ids: list[str] | None,
) -> CompiledYouTubeReadPlan:
    parameter_names = ["q", "part", "type", "maxResults"]
    if query.published_after is not None:
        parameter_names.append("publishedAfter")
    if query.published_before is not None:
        parameter_names.append("publishedBefore")
    if query.region_code is not None:
        parameter_names.append("regionCode")
    if query.relevance_language is not None:
        parameter_names.append("relevanceLanguage")
    if query.order is not None:
        parameter_names.append("order")

    normalized_ids = (
        _ordered_video_ids(video_ids, limit=query.max_items)
        if video_ids is not None
        else ()
    )
    operations = [
        YouTubeReadOperation(
            method="search.list",
            part=("snippet",),
            required=True,
            conditional=False,
            max_items=query.max_items,
            item_count=query.max_items,
            parameter_names=tuple(parameter_names),
        )
    ]
    if video_ids is None or normalized_ids:
        operations.append(
            YouTubeReadOperation(
                method="videos.list",
                part=("snippet", "statistics", "contentDetails"),
                required=False,
                conditional=True,
                max_items=50,
                item_count=len(normalized_ids),
                parameter_names=("id", "part"),
            )
        )
    query_payload = cast(JsonValue, query.model_dump(mode="json"))
    return CompiledYouTubeReadPlan(
        query_fingerprint=sha256_id(query_payload),
        operations=tuple(operations),
        video_ids=normalized_ids,
    )


def build_youtube_quota_plan(
    evidence: YouTubeQuotaEvidence,
    *,
    detail_required: bool,
    now: datetime,
) -> YouTubeQuotaPlan:
    if now.utcoffset() is None:
        raise ValueError("youtube_quota_now_timezone_required")
    checked_at = now.astimezone(UTC)
    age = checked_at - evidence.observed_at
    blocked_reasons: list[str] = []
    if age < timedelta(0):
        blocked_reasons.append("youtube_quota_evidence_from_future")
    elif age > QUOTA_MAX_AGE:
        blocked_reasons.append("youtube_quota_evidence_stale")

    evidence_by_method = {item.method: item for item in evidence.entries}
    entries: list[YouTubeQuotaEntry] = []
    for method in ("search.list", "videos.list"):
        source = evidence_by_method.get(method)
        if source is None:
            blocked_reasons.append(f"youtube_quota_evidence_missing:{method}")
            continue
        is_search = method == "search.list"
        max_requests = 1 if is_search or detail_required else 0
        min_requests = 1 if is_search else 0
        entries.append(
            YouTubeQuotaEntry(
                method=method,
                bucket=source.bucket,
                required=is_search,
                conditional=not is_search,
                min_requests=min_requests,
                max_requests=max_requests,
                units_per_request=source.units_per_request,
                min_units=min_requests * source.units_per_request,
                max_units=max_requests * source.units_per_request,
                evidence_ref=source.evidence_ref,
                source_url=source.source_url,
                observed_at=evidence.observed_at,
            )
        )

    min_requests = sum(item.min_requests for item in entries)
    max_requests = sum(item.max_requests for item in entries)
    digest_payload = cast(
        JsonValue,
        {
            "entries": [item.model_dump(mode="json") for item in entries],
            "min_requests": min_requests,
            "max_requests": max_requests,
            "blocked_reasons": blocked_reasons,
        },
    )
    return YouTubeQuotaPlan(
        entries=entries,
        min_requests=min_requests,
        max_requests=max_requests,
        fresh=not blocked_reasons,
        blocked_reasons=blocked_reasons,
        digest=sha256_id(digest_payload),
    )


__all__ = [
    "CompiledYouTubeReadPlan",
    "build_youtube_quota_plan",
    "compile_youtube_keyword_video_query",
]
