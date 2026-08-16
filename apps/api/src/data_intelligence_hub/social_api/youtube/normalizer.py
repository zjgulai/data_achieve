from __future__ import annotations

from pydantic import JsonValue

from data_intelligence_hub.schemas.capability_catalog import (
    CapabilityOperation,
    PlatformId,
    ResourceType,
)
from data_intelligence_hub.schemas.workflow_lineage import (
    WorkflowProviderPayloadEnvelope,
    WorkflowProviderPayloadRecord,
    compute_workflow_provider_payload_digest,
)
from data_intelligence_hub.social_api.youtube.contracts import LoadedYouTubeReadFixture


class YouTubeNormalizedPayloadInvalidError(ValueError):
    """A recorded YouTube response could not produce a canonical payload."""


def _invalid(reason: str) -> YouTubeNormalizedPayloadInvalidError:
    return YouTubeNormalizedPayloadInvalidError(f"youtube_normalized_payload_invalid:{reason}")


def ordered_search_video_ids(loaded: LoadedYouTubeReadFixture) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item.id.video_id for item in loaded.search.response.items))


def _optional_count(value: str | None) -> int | None:
    return int(value) if value is not None else None


def normalize_youtube_read_fixture(
    loaded: LoadedYouTubeReadFixture,
) -> list[WorkflowProviderPayloadRecord]:
    ordered_ids = ordered_search_video_ids(loaded)
    detail_by_id = {item.id: item for item in loaded.videos.response.items}
    if len(detail_by_id) != len(loaded.videos.response.items):
        raise _invalid("detail_id_duplicate")
    if set(detail_by_id) != set(ordered_ids):
        raise _invalid("search_detail_identity_mismatch")

    records: list[WorkflowProviderPayloadRecord] = []
    for video_id in ordered_ids:
        detail = detail_by_id[video_id]
        content: dict[str, JsonValue] = {
            "video_id": video_id,
            "title": detail.snippet.title,
            "description": detail.snippet.description,
            "channel_id": detail.snippet.channel_id,
            "channel_title": detail.snippet.channel_title,
            "published_at": detail.snippet.published_at.isoformat().replace("+00:00", "Z"),
            "duration": detail.content_details.duration,
        }
        for name, value in (
            ("view_count", _optional_count(detail.statistics.view_count)),
            ("like_count", _optional_count(detail.statistics.like_count)),
            ("comment_count", _optional_count(detail.statistics.comment_count)),
        ):
            if value is not None:
                content[name] = value
        records.append(
            WorkflowProviderPayloadRecord(
                record_type="youtube_video",
                source_url=f"https://www.youtube.com/watch?v={video_id}",
                collected_at=loaded.videos.captured_at,
                content=content,
            )
        )
    return records


def build_youtube_read_fixture_envelope(
    loaded: LoadedYouTubeReadFixture,
) -> WorkflowProviderPayloadEnvelope:
    records = normalize_youtube_read_fixture(loaded)
    return WorkflowProviderPayloadEnvelope(
        contract_version="workflow_provider_payload.v1",
        fixture_profile_id=loaded.manifest.fixture_profile_id,
        fixture_case_id="youtube-keyword-video-read-a1-v1",
        implementation_id=loaded.manifest.implementation_id,
        platform=PlatformId.YOUTUBE,
        resource_type=ResourceType.CONTENT,
        operation=CapabilityOperation.SEARCH_DISCOVER,
        evidence_refs=list(loaded.evidence_refs),
        records_count=len(records),
        records=records,
        payload_digest=compute_workflow_provider_payload_digest(records),
    )


__all__ = [
    "YouTubeNormalizedPayloadInvalidError",
    "build_youtube_read_fixture_envelope",
    "normalize_youtube_read_fixture",
    "ordered_search_video_ids",
]
