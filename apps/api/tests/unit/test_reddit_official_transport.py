from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from data_intelligence_hub.social_api.reddit import official_transport
from data_intelligence_hub.social_api.reddit.contracts import (
    RedditCommentsNewRequest,
    RedditListingRequest,
    RedditOAuthCredentialValues,
    RedditOAuthReadPolicy,
    RedditSearchRequest,
    RedditSubredditAboutRequest,
    RedditTransportFactory,
)
from data_intelligence_hub.social_api.reddit.official_transport import (
    AsyncPrawTransportFactory,
    RedditLiveExecutionDisabledError,
    RedditOfficialClientCallError,
    RedditOfficialClientResponseInvalidError,
    RedditOfficialCredentialMismatchError,
    build_asyncpraw_reddit_client,
)


class _AsyncItems:
    def __init__(self, items: list[object]) -> None:
        self._items = iter(items)

    def __aiter__(self) -> _AsyncItems:
        return self

    async def __anext__(self) -> object:
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration from None


class _FakeSubreddit:
    display_name = "Python"
    name = "t5_fixture"
    title = "Python"
    public_description = "Python discussion"
    subscribers = 123
    over18 = False

    def __init__(self, *, error: Exception | None = None) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self._error = error

    def _items(self, method: str, parameters: dict[str, object]) -> _AsyncItems:
        self.calls.append((method, parameters))
        if self._error is not None:
            raise self._error
        return _AsyncItems(
            [
                SimpleNamespace(
                    id="item-1",
                    name="t3_item-1",
                    title="Fixture post",
                    permalink="/r/Python/comments/item-1",
                    created_utc=1_700_000_000.0,
                    score=8,
                    num_comments=3,
                    subreddit=SimpleNamespace(display_name="Python"),
                    link_id="t3_parent",
                    parent_id="t3_parent",
                    body="Fixture comment",
                )
            ]
        )

    def hot(self, **kwargs: object) -> _AsyncItems:
        return self._items("hot", kwargs)

    def new(self, **kwargs: object) -> _AsyncItems:
        return self._items("new", kwargs)

    def search(self, query: str, **kwargs: object) -> _AsyncItems:
        return self._items("search", {"query": query, **kwargs})

    def comments(self, **kwargs: object) -> _AsyncItems:
        return self._items("comments", kwargs)


class _FakeReddit:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.subreddit_names: list[str] = []
        self.subreddit_instance = _FakeSubreddit(error=error)
        self.closed = False

    async def subreddit(self, display_name: str) -> _FakeSubreddit:
        self.subreddit_names.append(display_name)
        return self.subreddit_instance

    async def close(self) -> None:
        self.closed = True


@dataclass(frozen=True)
class _Credential:
    reference_fingerprint: str = "reddit-credential-fingerprint"

    def reveal_for_transport(self) -> RedditOAuthCredentialValues:
        return RedditOAuthCredentialValues(
            client_id="fixture-client-id",
            client_secret="fixture-client-secret",
            refresh_token="fixture-refresh-token",
        )


class _PoisonCredential:
    @property
    def reference_fingerprint(self) -> str:
        raise AssertionError("credential_handle_touched")

    def reveal_for_transport(self) -> RedditOAuthCredentialValues:
        raise AssertionError("credential_secret_touched")


def _policy() -> RedditOAuthReadPolicy:
    return RedditOAuthReadPolicy(
        purpose="market_research",
        retention_hours=24,
    )


def test_reddit_contracts_are_frozen_strict_minimum_scope_and_bounded() -> None:
    policy = _policy()
    request = RedditSearchRequest(query="agentic workflows", subreddit="Python")

    assert policy.oauth_scopes == ("read",)
    assert policy.cleanup_mode == "delete_on_expiry"
    assert policy.ai_training_allowed is False
    assert policy.user_profile_allowed is False
    assert policy.separate_live_authorization_required is True
    assert request.limit == 25

    with pytest.raises(ValidationError):
        RedditOAuthReadPolicy(
            purpose="market_research",
            retention_hours=24,
            oauth_scopes=("read", "identity"),
        )
    with pytest.raises(ValidationError):
        RedditOAuthReadPolicy(purpose="market_research", retention_hours=169)
    with pytest.raises(ValidationError):
        RedditListingRequest(method="hot.list", subreddit="bad/name")
    with pytest.raises(ValidationError):
        RedditSearchRequest(query="\ninvalid")
    with pytest.raises(ValidationError):
        RedditSubredditAboutRequest.model_validate({"subreddit": "Python", "unsafe": True})
    with pytest.raises(ValidationError):
        request.query = "mutated"  # type: ignore[misc]


def test_asyncpraw_builder_uses_only_explicit_oauth_values_and_user_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reddit = _FakeReddit()
    calls: list[dict[str, object]] = []

    def constructor(**kwargs: object) -> _FakeReddit:
        calls.append(kwargs)
        return reddit

    monkeypatch.setattr(
        official_transport.importlib,
        "import_module",
        lambda name: SimpleNamespace(Reddit=constructor),
    )

    result = build_asyncpraw_reddit_client(
        RedditOAuthCredentialValues(
            client_id="fixture-client-id",
            client_secret="fixture-client-secret",
            refresh_token="fixture-refresh-token",
        ),
        user_agent="data-achieve:reddit-read-adapter:v1 (owner: local-test)",
    )

    assert result is reddit
    assert calls == [
        {
            "client_id": "fixture-client-id",
            "client_secret": "fixture-client-secret",
            "refresh_token": "fixture-refresh-token",
            "user_agent": "data-achieve:reddit-read-adapter:v1 (owner: local-test)",
        }
    ]


def test_reddit_response_boundary_rejects_non_finite_numbers() -> None:
    with pytest.raises(
        RedditOfficialClientResponseInvalidError,
        match="^reddit_official_client_response_invalid$",
    ):
        official_transport._bounded_response({"score": float("nan")})


async def test_reddit_factory_is_disabled_before_credential_or_builder_access() -> None:
    builder_touched = False

    def poison_builder(
        values: RedditOAuthCredentialValues,
        user_agent: str,
    ) -> _FakeReddit:
        nonlocal builder_touched
        _ = (values, user_agent)
        builder_touched = True
        raise AssertionError("reddit_builder_touched")

    factory = AsyncPrawTransportFactory(
        user_agent="data-achieve:reddit-read-adapter:v1 (owner: local-test)",
        client_builder=poison_builder,
    )

    assert isinstance(factory, RedditTransportFactory)
    with pytest.raises(
        RedditLiveExecutionDisabledError,
        match="^reddit_live_execution_disabled$",
    ):
        await factory.create(credential=_PoisonCredential(), policy=_policy())

    assert builder_touched is False


async def test_reddit_transport_executes_only_allowlisted_public_reads_and_closes() -> None:
    reddit = _FakeReddit()
    credential = _Credential()
    factory = AsyncPrawTransportFactory(
        live_client_enabled=True,
        user_agent="data-achieve:reddit-read-adapter:v1 (owner: local-test)",
        client_builder=lambda values, user_agent: reddit,
    )
    transport = await factory.create(credential=credential, policy=_policy())

    listing = await transport.execute(
        RedditListingRequest(method="hot.list", subreddit="Python", limit=10),
        credential=credential,
    )
    search = await transport.execute(
        RedditSearchRequest(query="agents", subreddit="Python", limit=5),
        credential=credential,
    )
    comments = await transport.execute(
        RedditCommentsNewRequest(subreddit="Python", limit=3),
        credential=credential,
    )
    about = await transport.execute(
        RedditSubredditAboutRequest(subreddit="Python"),
        credential=credential,
    )

    assert listing["items"][0]["title"] == "Fixture post"
    assert "author" not in listing["items"][0]
    assert search["items"][0]["id"] == "item-1"
    assert comments["items"][0]["body"] == "Fixture comment"
    assert about["subreddit"]["display_name"] == "Python"
    assert reddit.subreddit_instance.calls == [
        ("hot", {"limit": 10}),
        ("search", {"query": "agents", "sort": "relevance", "time_filter": "all", "limit": 5}),
        ("comments", {"limit": 3}),
    ]
    assert "fixture-client-secret" not in repr(factory)
    assert "fixture-client-secret" not in repr(transport)

    await transport.close()
    assert reddit.closed is True


async def test_reddit_transport_rejects_credential_mismatch_before_request() -> None:
    reddit = _FakeReddit()
    factory = AsyncPrawTransportFactory(
        live_client_enabled=True,
        user_agent="data-achieve:reddit-read-adapter:v1 (owner: local-test)",
        client_builder=lambda values, user_agent: reddit,
    )
    transport = await factory.create(credential=_Credential(), policy=_policy())

    with pytest.raises(
        RedditOfficialCredentialMismatchError,
        match="^reddit_official_credential_mismatch$",
    ):
        await transport.execute(
            RedditListingRequest(method="new.list", subreddit="Python"),
            credential=_Credential(reference_fingerprint="other-fingerprint"),
        )

    assert reddit.subreddit_names == []
    await transport.close()


async def test_reddit_oauth_and_provider_errors_are_sanitized() -> None:
    secret_error = type("OAuthException", (RuntimeError,), {})(
        "invalid refresh token fixture-refresh-token"
    )
    reddit = _FakeReddit(error=secret_error)
    credential = _Credential()
    factory = AsyncPrawTransportFactory(
        live_client_enabled=True,
        user_agent="data-achieve:reddit-read-adapter:v1 (owner: local-test)",
        client_builder=lambda values, user_agent: reddit,
    )
    transport = await factory.create(credential=credential, policy=_policy())

    with pytest.raises(
        RedditOfficialClientCallError,
        match="^reddit_official_oauth_failed$",
    ) as captured:
        await transport.execute(
            RedditListingRequest(method="hot.list", subreddit="Python"),
            credential=credential,
        )

    assert "fixture-refresh-token" not in repr(captured.value)
    await transport.close()
