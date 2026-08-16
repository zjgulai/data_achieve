from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from data_intelligence_hub.schemas.workflow_execution import Sha256Digest
from data_intelligence_hub.social_api.contracts import (
    CredentialReference as ParsedCredentialReference,
)
from data_intelligence_hub.social_api.contracts import CredentialReferenceInvalidError

QueryText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
CredentialReference = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=5, max_length=135),
]

_LANGUAGE_TAG = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")


class YouTubeReadContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class YouTubeKeywordVideoQuery(YouTubeReadContract):
    schema_version: Literal["youtube_keyword_video_query.v1"] = "youtube_keyword_video_query.v1"
    query: QueryText
    published_after: datetime | None = None
    published_before: datetime | None = None
    region_code: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    relevance_language: str | None = Field(default=None, min_length=2, max_length=35)
    order: Literal["date", "relevance", "viewCount"] | None = None
    max_items: int = Field(default=50, ge=1, le=50)

    @field_validator("query", mode="before")
    @classmethod
    def reject_query_control_characters(cls, value: object) -> object:
        if isinstance(value, str) and any(
            unicodedata.category(character) in {"Cc", "Cf"} for character in value
        ):
            raise ValueError("youtube_query_control_character_invalid")
        return value

    @field_validator("published_after", "published_before")
    @classmethod
    def normalize_query_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.utcoffset() is None:
            raise ValueError("youtube_query_timestamp_timezone_required")
        return value.astimezone(UTC)

    @field_validator("relevance_language")
    @classmethod
    def validate_language_tag(cls, value: str | None) -> str | None:
        if value is not None and _LANGUAGE_TAG.fullmatch(value) is None:
            raise ValueError("youtube_relevance_language_invalid")
        return value

    @model_validator(mode="after")
    def validate_time_window(self) -> Self:
        if (
            self.published_after is not None
            and self.published_before is not None
            and self.published_after >= self.published_before
        ):
            raise ValueError("youtube_query_time_window_invalid")
        return self


class YouTubeReadPlanRequest(YouTubeReadContract):
    schema_version: Literal["youtube_read_plan_request.v1"] = "youtube_read_plan_request.v1"
    query: YouTubeKeywordVideoQuery
    credential_reference: CredentialReference | None = None

    @field_validator("credential_reference", mode="before")
    @classmethod
    def validate_credential_reference(cls, value: object) -> object:
        if isinstance(value, str) and value != value.strip():
            raise ValueError("youtube_credential_reference_invalid")
        if isinstance(value, str):
            try:
                ParsedCredentialReference.parse(value)
            except CredentialReferenceInvalidError as exc:
                raise ValueError("youtube_credential_reference_invalid") from exc
        return value


class YouTubeReadOperation(YouTubeReadContract):
    method: Literal["search.list", "videos.list"]
    part: tuple[str, ...]
    required: bool
    conditional: bool
    max_items: int = Field(ge=1, le=50)
    item_count: int = Field(ge=0, le=50)
    parameter_names: tuple[str, ...]


class YouTubeQuotaEntry(YouTubeReadContract):
    method: Literal["search.list", "videos.list"]
    bucket: str = Field(min_length=1, max_length=100)
    required: bool
    conditional: bool
    min_requests: int = Field(ge=0, le=1)
    max_requests: int = Field(ge=0, le=1)
    units_per_request: int = Field(ge=1)
    min_units: int = Field(ge=0)
    max_units: int = Field(ge=0)
    evidence_ref: str = Field(min_length=1, max_length=500)
    source_url: str = Field(min_length=1, max_length=4000)
    observed_at: datetime


class YouTubeQuotaPlan(YouTubeReadContract):
    schema_version: Literal["youtube_quota_plan.v1"] = "youtube_quota_plan.v1"
    entries: list[YouTubeQuotaEntry] = Field(default_factory=list, max_length=2)
    min_requests: int = Field(ge=0, le=2)
    max_requests: int = Field(ge=0, le=2)
    fresh: bool
    blocked_reasons: list[str] = Field(default_factory=list, max_length=8)
    digest: Sha256Digest


class YouTubeFixtureValidation(YouTubeReadContract):
    schema_version: Literal["youtube_fixture_validation.v1"] = "youtube_fixture_validation.v1"
    fixture_snapshot_digest: Sha256Digest
    normalized_payload_digest: Sha256Digest
    evidence_refs: list[str] = Field(min_length=1, max_length=10)
    record_count: int = Field(ge=1, le=50)


class YouTubeReadAdapterFoundationResponse(YouTubeReadContract):
    schema_version: Literal["youtube_read_adapter_foundation.v1"] = (
        "youtube_read_adapter_foundation.v1"
    )
    provider_id: Literal["youtube.v3"] = "youtube.v3"
    platform: Literal["youtube"] = "youtube"
    foundation_ready: bool
    declared_readiness: bool
    readiness_basis: Literal["caller_declared"] = "caller_declared"
    execution_enabled: Literal[False] = False
    live_dependency_present: bool
    credential_reference_present: bool
    credential_reference_fingerprint: Sha256Digest | None = None
    credential_reference: None = None
    query_fingerprint: Sha256Digest
    query: None = None
    operations: list[YouTubeReadOperation] = Field(min_length=1, max_length=2)
    quota_plan: YouTubeQuotaPlan
    fixture_validation: YouTubeFixtureValidation
    blocked_reasons: list[str] = Field(default_factory=list, max_length=16)
    provider_call_allowed: Literal[False] = False
    provider_call_attempted: Literal[False] = False
    credential_read_attempted: Literal[False] = False
    live_client_created: Literal[False] = False
    database_write: Literal[False] = False
    workflow_run_created: Literal[False] = False
    raw_record_write: Literal[False] = False
    dataset_write: Literal[False] = False
    production_write_allowed: Literal[False] = False
    next_required_authorization: Literal["L4_youtube_read_live_gate_required"] = (
        "L4_youtube_read_live_gate_required"
    )
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


__all__ = [
    "YouTubeFixtureValidation",
    "YouTubeKeywordVideoQuery",
    "YouTubeQuotaEntry",
    "YouTubeQuotaPlan",
    "YouTubeReadAdapterFoundationResponse",
    "YouTubeReadOperation",
    "YouTubeReadPlanRequest",
]
