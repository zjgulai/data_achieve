from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from data_intelligence_hub.social_api.contracts import CredentialHandle

_SUBREDDIT_NAME = re.compile(r"^[A-Za-z0-9_]{2,21}$")


class RedditOfficialContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class RedditOAuthReadPolicy(RedditOfficialContract):
    purpose: Literal["brand_monitoring", "market_research", "customer_feedback"]
    oauth_scopes: tuple[Literal["read"], ...] = Field(
        default=("read",),
        min_length=1,
        max_length=1,
    )
    retention_hours: int = Field(ge=1, le=168)
    cleanup_mode: Literal["delete_on_expiry"] = "delete_on_expiry"
    ai_training_allowed: Literal[False] = False
    private_message_allowed: Literal[False] = False
    user_profile_allowed: Literal[False] = False
    account_data_aggregation_allowed: Literal[False] = False
    separate_live_authorization_required: Literal[True] = True


class RedditListingRequest(RedditOfficialContract):
    method: Literal["hot.list", "new.list"]
    subreddit: str = Field(min_length=2, max_length=21)
    limit: int = Field(default=25, ge=1, le=100)

    @field_validator("subreddit")
    @classmethod
    def validate_subreddit(cls, value: str) -> str:
        if _SUBREDDIT_NAME.fullmatch(value) is None:
            raise ValueError("reddit_official_subreddit_invalid")
        return value


class RedditSearchRequest(RedditOfficialContract):
    method: Literal["search"] = "search"
    query: str = Field(min_length=1, max_length=512)
    subreddit: str = Field(default="all", min_length=2, max_length=21)
    sort: Literal["relevance", "hot", "top", "new", "comments"] = "relevance"
    time_filter: Literal["all", "hour", "day", "week", "month", "year"] = "all"
    limit: int = Field(default=25, ge=1, le=100)

    @field_validator("query", mode="before")
    @classmethod
    def validate_query(cls, value: object) -> object:
        if isinstance(value, str) and (
            value != value.strip()
            or any(unicodedata.category(character) in {"Cc", "Cf"} for character in value)
        ):
            raise ValueError("reddit_official_query_invalid")
        return value

    @field_validator("subreddit")
    @classmethod
    def validate_subreddit(cls, value: str) -> str:
        if value != "all" and _SUBREDDIT_NAME.fullmatch(value) is None:
            raise ValueError("reddit_official_subreddit_invalid")
        return value


class RedditCommentsNewRequest(RedditOfficialContract):
    method: Literal["comments.new"] = "comments.new"
    subreddit: str = Field(min_length=2, max_length=21)
    limit: int = Field(default=25, ge=1, le=100)

    @field_validator("subreddit")
    @classmethod
    def validate_subreddit(cls, value: str) -> str:
        if _SUBREDDIT_NAME.fullmatch(value) is None:
            raise ValueError("reddit_official_subreddit_invalid")
        return value


class RedditSubredditAboutRequest(RedditOfficialContract):
    method: Literal["r/{subreddit}/about"] = "r/{subreddit}/about"
    subreddit: str = Field(min_length=2, max_length=21)

    @field_validator("subreddit")
    @classmethod
    def validate_subreddit(cls, value: str) -> str:
        if _SUBREDDIT_NAME.fullmatch(value) is None:
            raise ValueError("reddit_official_subreddit_invalid")
        return value


RedditOfficialReadRequest = (
    RedditListingRequest
    | RedditSearchRequest
    | RedditCommentsNewRequest
    | RedditSubredditAboutRequest
)


@dataclass(frozen=True, slots=True)
class RedditOAuthCredentialValues:
    client_id: str = field(repr=False)
    client_secret: str = field(repr=False)
    refresh_token: str = field(repr=False)

    def __post_init__(self) -> None:
        values = (self.client_id, self.client_secret, self.refresh_token)
        if any(not isinstance(value, str) or value == "" for value in values):
            raise ValueError("reddit_oauth_credential_value_invalid")


@runtime_checkable
class RedditOAuthCredentialHandle(CredentialHandle, Protocol):
    def reveal_for_transport(self) -> RedditOAuthCredentialValues: ...


class RedditReadTransport(Protocol):
    async def execute(
        self,
        request: RedditOfficialReadRequest,
        *,
        credential: CredentialHandle,
    ) -> dict[str, object]: ...

    async def close(self) -> None: ...


@runtime_checkable
class RedditTransportFactory(Protocol):
    async def create(
        self,
        *,
        credential: CredentialHandle,
        policy: RedditOAuthReadPolicy,
    ) -> RedditReadTransport: ...


__all__ = [
    "RedditCommentsNewRequest",
    "RedditListingRequest",
    "RedditOAuthCredentialHandle",
    "RedditOAuthCredentialValues",
    "RedditOAuthReadPolicy",
    "RedditOfficialReadRequest",
    "RedditReadTransport",
    "RedditSearchRequest",
    "RedditSubredditAboutRequest",
    "RedditTransportFactory",
]
