from __future__ import annotations

import asyncio
import importlib
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Protocol, cast, runtime_checkable

from data_intelligence_hub.social_api.contracts import CredentialHandle
from data_intelligence_hub.social_api.youtube.contracts import (
    YouTubeOfficialReadRequest,
    YouTubeSearchListRequest,
    YouTubeVideosListRequest,
)
from data_intelligence_hub.social_api.youtube.foundation import (
    YouTubeLiveExecutionDisabledError,
)


class YouTubeOfficialClientDependencyUnavailableError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("youtube_official_client_dependency_unavailable")


class YouTubeOfficialClientConstructionError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("youtube_official_client_construction_failed")


class YouTubeOfficialCredentialUnavailableError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("youtube_official_credential_unavailable")


class YouTubeOfficialCredentialMismatchError(PermissionError):
    def __init__(self) -> None:
        super().__init__("youtube_official_credential_mismatch")


class YouTubeOfficialClientCallError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("youtube_official_client_call_failed")


class YouTubeOfficialClientResponseInvalidError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("youtube_official_client_response_invalid")


class _GoogleExecutableRequest(Protocol):
    def execute(self) -> object: ...


class _GoogleListResource(Protocol):
    def list(self, **kwargs: object) -> _GoogleExecutableRequest: ...


class GoogleYouTubeService(Protocol):
    def search(self) -> _GoogleListResource: ...

    def videos(self) -> _GoogleListResource: ...


@runtime_checkable
class _RevealableCredentialHandle(CredentialHandle, Protocol):
    def reveal_for_transport(self) -> str: ...


GoogleYouTubeServiceBuilder = Callable[[str], GoogleYouTubeService]


def build_google_youtube_service(developer_key: str) -> GoogleYouTubeService:
    discovery = importlib.import_module("googleapiclient.discovery")
    build = getattr(discovery, "build", None)
    if not callable(build):
        raise ModuleNotFoundError("googleapiclient.discovery.build")
    return cast(
        GoogleYouTubeService,
        build(
            "youtube",
            "v3",
            developerKey=developer_key,
            cache_discovery=False,
            static_discovery=True,
        ),
    )


def _timestamp_parameter(value: object) -> str:
    if not hasattr(value, "isoformat"):
        raise YouTubeOfficialClientResponseInvalidError
    return cast(str, value.isoformat()).replace("+00:00", "Z")


def _search_parameters(request: YouTubeSearchListRequest) -> dict[str, object]:
    parameters: dict[str, object] = {
        "q": request.q,
        "part": "snippet",
        "type": "video",
        "maxResults": request.max_results,
    }
    if request.published_after is not None:
        parameters["publishedAfter"] = _timestamp_parameter(request.published_after)
    if request.published_before is not None:
        parameters["publishedBefore"] = _timestamp_parameter(request.published_before)
    if request.region_code is not None:
        parameters["regionCode"] = request.region_code
    if request.relevance_language is not None:
        parameters["relevanceLanguage"] = request.relevance_language
    if request.order is not None:
        parameters["order"] = request.order
    return parameters


def _execute_google_request(
    service: GoogleYouTubeService,
    request: YouTubeOfficialReadRequest,
) -> dict[str, object]:
    if isinstance(request, YouTubeSearchListRequest):
        executable = service.search().list(**_search_parameters(request))
    elif isinstance(request, YouTubeVideosListRequest):
        executable = service.videos().list(
            id=",".join(request.video_ids),
            part="snippet,statistics,contentDetails",
        )
    else:
        raise YouTubeOfficialClientResponseInvalidError
    response = executable.execute()
    if not isinstance(response, dict):
        raise YouTubeOfficialClientResponseInvalidError
    return cast(dict[str, object], response)


@dataclass(frozen=True, slots=True)
class GoogleYouTubeReadTransport:
    service: GoogleYouTubeService = field(repr=False)
    reference_fingerprint: str = field(repr=False)
    executor: ThreadPoolExecutor = field(repr=False)
    _execute_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    async def execute(
        self,
        request: YouTubeOfficialReadRequest,
        *,
        credential: CredentialHandle,
    ) -> dict[str, object]:
        if credential.reference_fingerprint != self.reference_fingerprint:
            raise YouTubeOfficialCredentialMismatchError
        try:
            async with self._execute_lock:
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(
                    self.executor,
                    _execute_google_request,
                    self.service,
                    request,
                )
        except YouTubeOfficialClientResponseInvalidError:
            raise
        except Exception:
            raise YouTubeOfficialClientCallError from None

    async def close(self) -> None:
        async with self._execute_lock:
            await asyncio.to_thread(
                self.executor.shutdown,
                wait=True,
                cancel_futures=True,
            )


@dataclass(frozen=True, slots=True)
class GoogleYouTubeTransportFactory:
    live_client_enabled: bool = False
    service_builder: GoogleYouTubeServiceBuilder = field(
        default=build_google_youtube_service,
        repr=False,
    )

    async def create(
        self,
        *,
        credential: CredentialHandle,
    ) -> GoogleYouTubeReadTransport:
        if not self.live_client_enabled:
            raise YouTubeLiveExecutionDisabledError("youtube_live_execution_disabled")
        if not isinstance(credential, _RevealableCredentialHandle):
            raise YouTubeOfficialCredentialUnavailableError
        developer_key = credential.reveal_for_transport()
        if developer_key == "":
            raise YouTubeOfficialCredentialUnavailableError
        executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="youtube-official-client",
        )
        try:
            loop = asyncio.get_running_loop()
            service = await loop.run_in_executor(
                executor,
                self.service_builder,
                developer_key,
            )
        except ModuleNotFoundError:
            executor.shutdown(wait=True, cancel_futures=True)
            raise YouTubeOfficialClientDependencyUnavailableError from None
        except Exception:
            executor.shutdown(wait=True, cancel_futures=True)
            raise YouTubeOfficialClientConstructionError from None
        return GoogleYouTubeReadTransport(
            service=service,
            reference_fingerprint=credential.reference_fingerprint,
            executor=executor,
        )


__all__ = [
    "GoogleYouTubeReadTransport",
    "GoogleYouTubeService",
    "GoogleYouTubeServiceBuilder",
    "GoogleYouTubeTransportFactory",
    "YouTubeOfficialClientCallError",
    "YouTubeOfficialClientConstructionError",
    "YouTubeOfficialClientDependencyUnavailableError",
    "YouTubeOfficialClientResponseInvalidError",
    "YouTubeOfficialCredentialMismatchError",
    "YouTubeOfficialCredentialUnavailableError",
    "build_google_youtube_service",
]
