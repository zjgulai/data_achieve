from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol, Self, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from data_intelligence_hub.schemas.workflow_execution import Sha256Digest
from data_intelligence_hub.schemas.youtube_read_adapter import YouTubeKeywordVideoQuery
from data_intelligence_hub.social_api.contracts import CredentialHandle

_YOUTUBE_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
_YOUTUBE_LANGUAGE_TAG = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")


class YouTubeFixtureContract(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class YouTubeOfficialRequestContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class YouTubeSearchListRequest(YouTubeOfficialRequestContract):
    method: Literal["search.list"] = "search.list"
    q: str = Field(min_length=1, max_length=200)
    max_results: int = Field(default=50, ge=1, le=50)
    published_after: datetime | None = None
    published_before: datetime | None = None
    region_code: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    relevance_language: str | None = Field(default=None, min_length=2, max_length=35)
    order: Literal["date", "relevance", "viewCount"] | None = None

    @classmethod
    def from_query(cls, query: YouTubeKeywordVideoQuery) -> Self:
        return cls(
            q=query.query,
            max_results=query.max_items,
            published_after=query.published_after,
            published_before=query.published_before,
            region_code=query.region_code,
            relevance_language=query.relevance_language,
            order=query.order,
        )

    @field_validator("q", mode="before")
    @classmethod
    def validate_query_text(cls, value: object) -> object:
        if isinstance(value, str) and (
            value != value.strip()
            or any(unicodedata.category(character) in {"Cc", "Cf"} for character in value)
        ):
            raise ValueError("youtube_official_query_invalid")
        return value

    @field_validator("published_after", "published_before")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.utcoffset() is None:
            raise ValueError("youtube_official_timestamp_timezone_required")
        return value.astimezone(UTC)

    @field_validator("relevance_language")
    @classmethod
    def validate_language_tag(cls, value: str | None) -> str | None:
        if value is not None and _YOUTUBE_LANGUAGE_TAG.fullmatch(value) is None:
            raise ValueError("youtube_official_relevance_language_invalid")
        return value

    @model_validator(mode="after")
    def validate_time_window(self) -> Self:
        if (
            self.published_after is not None
            and self.published_before is not None
            and self.published_after >= self.published_before
        ):
            raise ValueError("youtube_official_time_window_invalid")
        return self


class YouTubeVideosListRequest(YouTubeOfficialRequestContract):
    method: Literal["videos.list"] = "videos.list"
    video_ids: tuple[str, ...] = Field(min_length=1, max_length=50)

    @field_validator("video_ids")
    @classmethod
    def validate_video_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(_YOUTUBE_VIDEO_ID.fullmatch(video_id) is None for video_id in value):
            raise ValueError("youtube_official_video_id_invalid")
        if len(value) != len(set(value)):
            raise ValueError("youtube_official_video_id_duplicate")
        return value


YouTubeOfficialReadRequest = YouTubeSearchListRequest | YouTubeVideosListRequest


def _require_utc(value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise ValueError("youtube_fixture_timestamp_timezone_required")
    return value.astimezone(UTC)


class YouTubeFixtureManifestEntry(YouTubeFixtureContract):
    kind: Literal["quota", "search", "videos"]
    relative_path: str = Field(min_length=1, max_length=200)
    expected_sha256: Sha256Digest


class YouTubeReadFixtureManifest(YouTubeFixtureContract):
    schema_version: Literal["youtube_read_fixture_manifest.v1"]
    fixture_profile_id: Literal["youtube-read-a1-recorded-v1"]
    implementation_id: Literal["youtube.v3"]
    entries: list[YouTubeFixtureManifestEntry] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_entries(self) -> Self:
        kinds = [item.kind for item in self.entries]
        paths = [item.relative_path for item in self.entries]
        if set(kinds) != {"quota", "search", "videos"} or len(kinds) != len(set(kinds)):
            raise ValueError("youtube_fixture_manifest_kind_invalid")
        if len(paths) != len(set(paths)):
            raise ValueError("youtube_fixture_manifest_path_duplicate")
        return self


class YouTubeQuotaEvidenceEntry(YouTubeFixtureContract):
    method: Literal["search.list", "videos.list"]
    bucket: str = Field(min_length=1, max_length=100)
    units_per_request: int = Field(ge=1)
    evidence_ref: str = Field(min_length=1, max_length=500)
    source_url: str = Field(min_length=1, max_length=4000)


class YouTubeQuotaEvidence(YouTubeFixtureContract):
    schema_version: Literal["youtube_quota_evidence.v1"]
    observed_at: datetime
    entries: list[YouTubeQuotaEvidenceEntry] = Field(min_length=2, max_length=2)

    _normalize_observed_at = field_validator("observed_at")(_require_utc)

    @model_validator(mode="after")
    def validate_methods(self) -> Self:
        methods = [item.method for item in self.entries]
        if len(methods) != len(set(methods)):
            raise ValueError("youtube_quota_method_duplicate")
        expected = {
            "search.list": ("youtube_search_queries", 1),
            "videos.list": ("youtube_data_daily_units", 1),
        }
        actual = {item.method: (item.bucket, item.units_per_request) for item in self.entries}
        if actual != expected:
            raise ValueError("youtube_quota_fact_invalid")
        return self


class YouTubePageInfo(YouTubeFixtureContract):
    total_results: int = Field(alias="totalResults", ge=0)
    results_per_page: int = Field(alias="resultsPerPage", ge=0, le=50)


class YouTubePublicSnippet(YouTubeFixtureContract):
    published_at: datetime = Field(alias="publishedAt")
    channel_id: str = Field(alias="channelId", min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(max_length=5000)
    channel_title: str = Field(alias="channelTitle", min_length=1, max_length=500)

    _normalize_published_at = field_validator("published_at")(_require_utc)


class YouTubeSearchIdentity(YouTubeFixtureContract):
    kind: Literal["youtube#video"]
    video_id: str = Field(
        alias="videoId",
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


class YouTubeSearchItem(YouTubeFixtureContract):
    kind: Literal["youtube#searchResult"]
    etag: str = Field(min_length=1, max_length=500)
    id: YouTubeSearchIdentity
    snippet: YouTubePublicSnippet


class YouTubeSearchResponse(YouTubeFixtureContract):
    kind: Literal["youtube#searchListResponse"]
    etag: str = Field(min_length=1, max_length=500)
    region_code: str = Field(alias="regionCode", pattern=r"^[A-Z]{2}$")
    page_info: YouTubePageInfo = Field(alias="pageInfo")
    items: list[YouTubeSearchItem] = Field(min_length=1, max_length=50)


class YouTubeRecordedSearchSnapshot(YouTubeFixtureContract):
    schema_version: Literal["youtube_recorded_search_response.v1"]
    snapshot_id: Literal["youtube-search-list-public-v1"]
    method: Literal["search.list"]
    captured_at: datetime
    evidence_refs: list[str] = Field(min_length=1, max_length=4)
    response: YouTubeSearchResponse

    _normalize_captured_at = field_validator("captured_at")(_require_utc)


class YouTubeContentDetails(YouTubeFixtureContract):
    duration: str = Field(min_length=1, max_length=100)


class YouTubeStatistics(YouTubeFixtureContract):
    view_count: str | None = Field(
        default=None,
        alias="viewCount",
        max_length=20,
        pattern=r"^[0-9]+$",
    )
    like_count: str | None = Field(
        default=None,
        alias="likeCount",
        max_length=20,
        pattern=r"^[0-9]+$",
    )
    comment_count: str | None = Field(
        default=None,
        alias="commentCount",
        max_length=20,
        pattern=r"^[0-9]+$",
    )


class YouTubeVideoItem(YouTubeFixtureContract):
    kind: Literal["youtube#video"]
    etag: str = Field(min_length=1, max_length=500)
    id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    snippet: YouTubePublicSnippet
    content_details: YouTubeContentDetails = Field(alias="contentDetails")
    statistics: YouTubeStatistics = Field(default_factory=YouTubeStatistics)


class YouTubeVideosResponse(YouTubeFixtureContract):
    kind: Literal["youtube#videoListResponse"]
    etag: str = Field(min_length=1, max_length=500)
    page_info: YouTubePageInfo = Field(alias="pageInfo")
    items: list[YouTubeVideoItem] = Field(min_length=1, max_length=50)


class YouTubeRecordedVideosSnapshot(YouTubeFixtureContract):
    schema_version: Literal["youtube_recorded_videos_response.v1"]
    snapshot_id: Literal["youtube-videos-list-public-v1"]
    method: Literal["videos.list"]
    captured_at: datetime
    evidence_refs: list[str] = Field(min_length=1, max_length=4)
    response: YouTubeVideosResponse

    _normalize_captured_at = field_validator("captured_at")(_require_utc)


@dataclass(frozen=True, slots=True)
class LoadedYouTubeReadFixture:
    manifest: YouTubeReadFixtureManifest
    quota: YouTubeQuotaEvidence
    search: YouTubeRecordedSearchSnapshot
    videos: YouTubeRecordedVideosSnapshot
    snapshot_digest: Sha256Digest
    evidence_refs: tuple[str, ...]


class YouTubeReadTransport(Protocol):
    async def execute(
        self,
        request: YouTubeOfficialReadRequest,
        *,
        credential: CredentialHandle,
    ) -> object: ...


@runtime_checkable
class YouTubeTransportFactory(Protocol):
    async def create(
        self,
        *,
        credential: CredentialHandle,
    ) -> YouTubeReadTransport: ...


__all__ = [
    "LoadedYouTubeReadFixture",
    "YouTubeQuotaEvidence",
    "YouTubeQuotaEvidenceEntry",
    "YouTubeReadFixtureManifest",
    "YouTubeOfficialReadRequest",
    "YouTubeReadTransport",
    "YouTubeSearchListRequest",
    "YouTubeTransportFactory",
    "YouTubeRecordedSearchSnapshot",
    "YouTubeRecordedVideosSnapshot",
    "YouTubeVideosListRequest",
]
