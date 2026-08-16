from __future__ import annotations

import asyncio
import importlib
import json
import unicodedata
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Protocol, cast

from data_intelligence_hub.social_api.contracts import CredentialHandle
from data_intelligence_hub.social_api.reddit.contracts import (
    RedditCommentsNewRequest,
    RedditListingRequest,
    RedditOAuthCredentialHandle,
    RedditOAuthCredentialValues,
    RedditOAuthReadPolicy,
    RedditOfficialReadRequest,
    RedditSearchRequest,
    RedditSubredditAboutRequest,
)

_MAX_RESPONSE_BYTES = 1_000_000


class RedditLiveExecutionDisabledError(PermissionError):
    def __init__(self) -> None:
        super().__init__("reddit_live_execution_disabled")


class RedditOfficialClientDependencyUnavailableError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("reddit_official_client_dependency_unavailable")


class RedditOfficialClientConstructionError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("reddit_official_client_construction_failed")


class RedditOfficialCredentialUnavailableError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("reddit_official_credential_unavailable")


class RedditOfficialCredentialMismatchError(PermissionError):
    def __init__(self) -> None:
        super().__init__("reddit_official_credential_mismatch")


class RedditOfficialClientCallError(RuntimeError):
    def __init__(self, code: str = "reddit_official_client_call_failed") -> None:
        super().__init__(code)


class RedditOfficialClientResponseInvalidError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("reddit_official_client_response_invalid")


class RedditOfficialClientCloseError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("reddit_official_client_close_failed")


class _AsyncPrawSubreddit(Protocol):
    display_name: object
    name: object
    title: object
    public_description: object
    subscribers: object
    over18: object

    def hot(self, **kwargs: object) -> AsyncIterator[object]: ...

    def new(self, **kwargs: object) -> AsyncIterator[object]: ...

    def search(self, query: str, **kwargs: object) -> AsyncIterator[object]: ...

    def comments(self, **kwargs: object) -> AsyncIterator[object]: ...


class AsyncPrawRedditClient(Protocol):
    async def subreddit(self, display_name: str) -> _AsyncPrawSubreddit: ...

    async def close(self) -> None: ...


AsyncPrawRedditClientBuilder = Callable[
    [RedditOAuthCredentialValues, str],
    AsyncPrawRedditClient,
]


def build_asyncpraw_reddit_client(
    values: RedditOAuthCredentialValues,
    user_agent: str,
) -> AsyncPrawRedditClient:
    module = importlib.import_module("asyncpraw")
    constructor = getattr(module, "Reddit", None)
    if not callable(constructor):
        raise ModuleNotFoundError("asyncpraw.Reddit")
    return cast(
        AsyncPrawRedditClient,
        constructor(
            client_id=values.client_id,
            client_secret=values.client_secret,
            refresh_token=values.refresh_token,
            user_agent=user_agent,
        ),
    )


def _required_string(item: object, attribute: str) -> str:
    value = getattr(item, attribute, None)
    if not isinstance(value, str) or value == "":
        raise RedditOfficialClientResponseInvalidError
    return value


def _optional_string(item: object, attribute: str) -> str | None:
    value = getattr(item, attribute, None)
    if value is None:
        return None
    if not isinstance(value, str):
        raise RedditOfficialClientResponseInvalidError
    return value


def _required_number(item: object, attribute: str) -> int | float:
    value = getattr(item, attribute, None)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RedditOfficialClientResponseInvalidError
    return value


def _submission_payload(item: object) -> dict[str, object]:
    subreddit = getattr(item, "subreddit", None)
    return {
        "id": _required_string(item, "id"),
        "name": _required_string(item, "name"),
        "title": _required_string(item, "title"),
        "permalink": _required_string(item, "permalink"),
        "created_utc": _required_number(item, "created_utc"),
        "score": _required_number(item, "score"),
        "num_comments": _required_number(item, "num_comments"),
        "subreddit": _required_string(subreddit, "display_name"),
    }


def _comment_payload(item: object) -> dict[str, object]:
    return {
        "id": _required_string(item, "id"),
        "name": _required_string(item, "name"),
        "link_id": _required_string(item, "link_id"),
        "parent_id": _required_string(item, "parent_id"),
        "body": _required_string(item, "body"),
        "permalink": _required_string(item, "permalink"),
        "created_utc": _required_number(item, "created_utc"),
        "score": _required_number(item, "score"),
    }


async def _collect(
    items: AsyncIterator[object],
    *,
    limit: int,
    comment_items: bool,
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    async for item in items:
        result.append(_comment_payload(item) if comment_items else _submission_payload(item))
        if len(result) >= limit:
            break
    return result


def _bounded_response(response: dict[str, object]) -> dict[str, object]:
    try:
        encoded = json.dumps(
            response,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise RedditOfficialClientResponseInvalidError from None
    if len(encoded) > _MAX_RESPONSE_BYTES:
        raise RedditOfficialClientResponseInvalidError
    return response


def _mapped_call_error(exc: Exception) -> RedditOfficialClientCallError:
    name = type(exc).__name__
    if name in {"OAuthException", "InvalidToken", "Unauthorized"}:
        return RedditOfficialClientCallError("reddit_official_oauth_failed")
    if name in {"Forbidden", "InsufficientScope"}:
        return RedditOfficialClientCallError("reddit_official_access_forbidden")
    if name in {"TooManyRequests", "RateLimitExceeded"}:
        return RedditOfficialClientCallError("reddit_official_rate_limited")
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return RedditOfficialClientCallError("reddit_official_request_timeout")
    return RedditOfficialClientCallError()


@dataclass(frozen=True, slots=True)
class AsyncPrawReadTransport:
    client: AsyncPrawRedditClient = field(repr=False)
    reference_fingerprint: str = field(repr=False)
    _execute_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    async def execute(
        self,
        request: RedditOfficialReadRequest,
        *,
        credential: CredentialHandle,
    ) -> dict[str, object]:
        if credential.reference_fingerprint != self.reference_fingerprint:
            raise RedditOfficialCredentialMismatchError
        try:
            async with self._execute_lock:
                subreddit_name = request.subreddit
                subreddit = await self.client.subreddit(subreddit_name)
                if isinstance(request, RedditListingRequest):
                    listing = subreddit.hot if request.method == "hot.list" else subreddit.new
                    items = await _collect(
                        listing(limit=request.limit),
                        limit=request.limit,
                        comment_items=False,
                    )
                    response: dict[str, object] = {
                        "method": request.method,
                        "subreddit": subreddit_name,
                        "items": items,
                    }
                elif isinstance(request, RedditSearchRequest):
                    items = await _collect(
                        subreddit.search(
                            request.query,
                            sort=request.sort,
                            time_filter=request.time_filter,
                            limit=request.limit,
                        ),
                        limit=request.limit,
                        comment_items=False,
                    )
                    response = {
                        "method": request.method,
                        "subreddit": subreddit_name,
                        "items": items,
                    }
                elif isinstance(request, RedditCommentsNewRequest):
                    items = await _collect(
                        subreddit.comments(limit=request.limit),
                        limit=request.limit,
                        comment_items=True,
                    )
                    response = {
                        "method": request.method,
                        "subreddit": subreddit_name,
                        "items": items,
                    }
                elif isinstance(request, RedditSubredditAboutRequest):
                    response = {
                        "method": request.method,
                        "subreddit": {
                            "display_name": _required_string(subreddit, "display_name"),
                            "name": _required_string(subreddit, "name"),
                            "title": _required_string(subreddit, "title"),
                            "public_description": _optional_string(
                                subreddit,
                                "public_description",
                            ),
                            "subscribers": _required_number(subreddit, "subscribers"),
                            "over18": getattr(subreddit, "over18", None),
                        },
                    }
                    if not isinstance(response["subreddit"]["over18"], bool):  # type: ignore[index]
                        raise RedditOfficialClientResponseInvalidError
                else:
                    raise RedditOfficialClientResponseInvalidError
                return _bounded_response(response)
        except RedditOfficialClientResponseInvalidError:
            raise
        except Exception as exc:
            raise _mapped_call_error(exc) from None

    async def close(self) -> None:
        try:
            async with self._execute_lock:
                await self.client.close()
        except Exception:
            raise RedditOfficialClientCloseError from None


@dataclass(frozen=True, slots=True)
class AsyncPrawTransportFactory:
    user_agent: str
    live_client_enabled: bool = False
    client_builder: AsyncPrawRedditClientBuilder = field(
        default=build_asyncpraw_reddit_client,
        repr=False,
    )

    def __post_init__(self) -> None:
        if (
            not 10 <= len(self.user_agent) <= 256
            or self.user_agent != self.user_agent.strip()
            or any(unicodedata.category(character) in {"Cc", "Cf"} for character in self.user_agent)
        ):
            raise ValueError("reddit_official_user_agent_invalid")

    async def create(
        self,
        *,
        credential: CredentialHandle,
        policy: RedditOAuthReadPolicy,
    ) -> AsyncPrawReadTransport:
        if not self.live_client_enabled:
            raise RedditLiveExecutionDisabledError
        if not isinstance(policy, RedditOAuthReadPolicy):
            raise TypeError("reddit_oauth_policy_invalid")
        if not isinstance(credential, RedditOAuthCredentialHandle):
            raise RedditOfficialCredentialUnavailableError
        reference_fingerprint = credential.reference_fingerprint
        values = credential.reveal_for_transport()
        if not isinstance(values, RedditOAuthCredentialValues):
            raise RedditOfficialCredentialUnavailableError
        try:
            client = self.client_builder(values, self.user_agent)
        except ModuleNotFoundError:
            raise RedditOfficialClientDependencyUnavailableError from None
        except Exception:
            raise RedditOfficialClientConstructionError from None
        return AsyncPrawReadTransport(
            client=client,
            reference_fingerprint=reference_fingerprint,
        )


__all__ = [
    "AsyncPrawReadTransport",
    "AsyncPrawRedditClient",
    "AsyncPrawRedditClientBuilder",
    "AsyncPrawTransportFactory",
    "RedditLiveExecutionDisabledError",
    "RedditOfficialClientCallError",
    "RedditOfficialClientCloseError",
    "RedditOfficialClientConstructionError",
    "RedditOfficialClientDependencyUnavailableError",
    "RedditOfficialClientResponseInvalidError",
    "RedditOfficialCredentialMismatchError",
    "RedditOfficialCredentialUnavailableError",
    "build_asyncpraw_reddit_client",
]
