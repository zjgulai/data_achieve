from __future__ import annotations

from datetime import UTC, datetime
from threading import get_ident
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from data_intelligence_hub.schemas.youtube_read_adapter import YouTubeKeywordVideoQuery
from data_intelligence_hub.social_api.environment_credentials import (
    EnvironmentCredentialHandle,
)
from data_intelligence_hub.social_api.youtube import official_transport
from data_intelligence_hub.social_api.youtube.contracts import (
    YouTubeSearchListRequest,
    YouTubeTransportFactory,
    YouTubeVideosListRequest,
)
from data_intelligence_hub.social_api.youtube.foundation import (
    YouTubeLiveExecutionDisabledError,
)
from data_intelligence_hub.social_api.youtube.official_transport import (
    GoogleYouTubeTransportFactory,
    YouTubeOfficialClientCallError,
    YouTubeOfficialClientDependencyUnavailableError,
    YouTubeOfficialCredentialMismatchError,
    build_google_youtube_service,
)


class _FakeExecutableRequest:
    def __init__(
        self,
        response: object,
        error: Exception | None = None,
        execution_thread_ids: list[int] | None = None,
    ) -> None:
        self._response = response
        self._error = error
        self._execution_thread_ids = execution_thread_ids

    def execute(self) -> object:
        if self._execution_thread_ids is not None:
            self._execution_thread_ids.append(get_ident())
        if self._error is not None:
            raise self._error
        return self._response


class _FakeResource:
    def __init__(
        self,
        response: object,
        error: Exception | None = None,
        execution_thread_ids: list[int] | None = None,
    ) -> None:
        self.calls: list[dict[str, object]] = []
        self._response = response
        self._error = error
        self._execution_thread_ids = execution_thread_ids

    def list(self, **kwargs: object) -> _FakeExecutableRequest:
        self.calls.append(kwargs)
        return _FakeExecutableRequest(
            self._response,
            self._error,
            self._execution_thread_ids,
        )


class _FakeYouTubeService:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.execution_thread_ids: list[int] = []
        self.search_resource = _FakeResource(
            {"kind": "youtube#searchListResponse"},
            error,
            self.execution_thread_ids,
        )
        self.videos_resource = _FakeResource(
            {"kind": "youtube#videoListResponse"},
            error,
            self.execution_thread_ids,
        )

    def search(self) -> _FakeResource:
        return self.search_resource

    def videos(self) -> _FakeResource:
        return self.videos_resource


class _PoisonCredentialHandle:
    @property
    def reference_fingerprint(self) -> str:
        raise AssertionError("credential_handle_touched")

    def reveal_for_transport(self) -> str:
        raise AssertionError("credential_secret_touched")


def _credential(*, fingerprint: str = "credential-fingerprint") -> EnvironmentCredentialHandle:
    return EnvironmentCredentialHandle(
        reference_fingerprint=fingerprint,
        _secret_value="fixture-youtube-api-key",
    )


def _query() -> YouTubeKeywordVideoQuery:
    return YouTubeKeywordVideoQuery(
        query="agentic workflows",
        published_after=datetime(2026, 7, 1, tzinfo=UTC),
        published_before=datetime(2026, 7, 17, tzinfo=UTC),
        region_code="US",
        relevance_language="en",
        order="relevance",
        max_items=25,
    )


def test_youtube_official_requests_are_frozen_strict_and_bounded() -> None:
    search = YouTubeSearchListRequest.from_query(_query())
    videos = YouTubeVideosListRequest(video_ids=("video-b", "video-a"))

    assert search.q == "agentic workflows"
    assert search.max_results == 25
    assert videos.video_ids == ("video-b", "video-a")

    with pytest.raises(ValidationError):
        YouTubeSearchListRequest.model_validate({"q": "valid", "unsafe": "value"})
    with pytest.raises(ValidationError):
        YouTubeSearchListRequest(q="\ninvalid")
    with pytest.raises(ValidationError):
        YouTubeVideosListRequest(video_ids=("video-a", "video-a"))
    with pytest.raises(ValidationError):
        YouTubeVideosListRequest(video_ids=("bad/value",))
    with pytest.raises(ValidationError):
        search.q = "mutated"  # type: ignore[misc]


def test_google_service_builder_uses_bundled_discovery_without_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _FakeYouTubeService()
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_build(*args: object, **kwargs: object) -> _FakeYouTubeService:
        calls.append((args, kwargs))
        return service

    monkeypatch.setattr(
        official_transport.importlib,
        "import_module",
        lambda name: SimpleNamespace(build=fake_build),
    )

    result = build_google_youtube_service("fixture-youtube-api-key")

    assert result is service
    assert calls == [
        (
            ("youtube", "v3"),
            {
                "developerKey": "fixture-youtube-api-key",
                "cache_discovery": False,
                "static_discovery": True,
            },
        )
    ]


async def test_youtube_official_factory_is_disabled_before_credential_or_builder_access() -> None:
    builder_touched = False

    def poison_builder(developer_key: str) -> _FakeYouTubeService:
        nonlocal builder_touched
        _ = developer_key
        builder_touched = True
        raise AssertionError("service_builder_touched")

    factory = GoogleYouTubeTransportFactory(service_builder=poison_builder)

    assert isinstance(factory, YouTubeTransportFactory)
    with pytest.raises(
        YouTubeLiveExecutionDisabledError,
        match="^youtube_live_execution_disabled$",
    ):
        await factory.create(credential=_PoisonCredentialHandle())

    assert builder_touched is False


async def test_youtube_official_transport_sends_only_allowlisted_search_parameters() -> None:
    service = _FakeYouTubeService()
    builder_calls: list[str] = []
    builder_thread_ids: list[int] = []

    def builder(developer_key: str) -> _FakeYouTubeService:
        builder_calls.append(developer_key)
        builder_thread_ids.append(get_ident())
        return service

    credential = _credential()
    factory = GoogleYouTubeTransportFactory(
        live_client_enabled=True,
        service_builder=builder,
    )
    transport = await factory.create(credential=credential)

    response = await transport.execute(
        YouTubeSearchListRequest.from_query(_query()),
        credential=credential,
    )

    assert response == {"kind": "youtube#searchListResponse"}
    assert builder_calls == ["fixture-youtube-api-key"]
    assert service.search_resource.calls == [
        {
            "q": "agentic workflows",
            "part": "snippet",
            "type": "video",
            "maxResults": 25,
            "publishedAfter": "2026-07-01T00:00:00Z",
            "publishedBefore": "2026-07-17T00:00:00Z",
            "regionCode": "US",
            "relevanceLanguage": "en",
            "order": "relevance",
        }
    ]
    assert "fixture-youtube-api-key" not in repr(factory)
    assert "fixture-youtube-api-key" not in repr(transport)
    assert builder_thread_ids == service.execution_thread_ids
    await transport.close()


async def test_youtube_official_transport_sends_ids_without_unsupported_max_results() -> None:
    service = _FakeYouTubeService()
    credential = _credential()
    factory = GoogleYouTubeTransportFactory(
        live_client_enabled=True,
        service_builder=lambda developer_key: service,
    )
    transport = await factory.create(credential=credential)

    response = await transport.execute(
        YouTubeVideosListRequest(video_ids=("video-b", "video-a")),
        credential=credential,
    )

    assert response == {"kind": "youtube#videoListResponse"}
    assert service.videos_resource.calls == [
        {
            "id": "video-b,video-a",
            "part": "snippet,statistics,contentDetails",
        }
    ]
    assert "maxResults" not in service.videos_resource.calls[0]
    await transport.close()


async def test_youtube_official_transport_rejects_credential_mismatch_before_request() -> None:
    service = _FakeYouTubeService()
    factory = GoogleYouTubeTransportFactory(
        live_client_enabled=True,
        service_builder=lambda developer_key: service,
    )
    transport = await factory.create(credential=_credential())

    with pytest.raises(
        YouTubeOfficialCredentialMismatchError,
        match="^youtube_official_credential_mismatch$",
    ):
        await transport.execute(
            YouTubeVideosListRequest(video_ids=("video-a",)),
            credential=_credential(fingerprint="other-fingerprint"),
        )

    assert service.videos_resource.calls == []
    await transport.close()


async def test_youtube_official_factory_maps_missing_optional_dependency() -> None:
    def missing_dependency(developer_key: str) -> _FakeYouTubeService:
        _ = developer_key
        raise ModuleNotFoundError("googleapiclient")

    factory = GoogleYouTubeTransportFactory(
        live_client_enabled=True,
        service_builder=missing_dependency,
    )

    with pytest.raises(
        YouTubeOfficialClientDependencyUnavailableError,
        match="^youtube_official_client_dependency_unavailable$",
    ):
        await factory.create(credential=_credential())


async def test_youtube_official_client_errors_are_sanitized() -> None:
    secret_bearing_error = RuntimeError(
        "request failed: key=fixture-youtube-api-key"
    )
    service = _FakeYouTubeService(error=secret_bearing_error)
    credential = _credential()
    factory = GoogleYouTubeTransportFactory(
        live_client_enabled=True,
        service_builder=lambda developer_key: service,
    )
    transport = await factory.create(credential=credential)

    with pytest.raises(
        YouTubeOfficialClientCallError,
        match="^youtube_official_client_call_failed$",
    ) as captured:
        await transport.execute(
            YouTubeSearchListRequest.from_query(_query()),
            credential=credential,
        )

    assert "fixture-youtube-api-key" not in repr(captured.value)
    assert captured.value.__cause__ is None
    await transport.close()
