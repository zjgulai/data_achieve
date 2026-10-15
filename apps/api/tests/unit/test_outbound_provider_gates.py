"""Direct instantiation of provider collectors must honor the outbound policy.

Gates live inside each collector's test()/collect() so a caller that skips
build_collector cannot escape the server-owned network mode. Every test in
this module runs with real egress blocked: httpx send on a non-mock
transport, DNS resolution, and subprocess spawning all pytest.fail.
"""

from __future__ import annotations

import asyncio
import socket
import subprocess
from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from data_intelligence_hub.collectors import exa_collector as exa_module
from data_intelligence_hub.collectors import hackernews_collector as hn_module
from data_intelligence_hub.collectors.anysearch_collector import AnySearchCollector
from data_intelligence_hub.collectors.apify_actor import ApifyActorCollector
from data_intelligence_hub.collectors.base import CollectorError
from data_intelligence_hub.collectors.exa_collector import (
    ExaAnswerCollector,
    ExaContentsCollector,
    ExaFindSimilarCollector,
    ExaSearchCollector,
)
from data_intelligence_hub.collectors.github_repo import GitHubRepoCollector
from data_intelligence_hub.collectors.github_topic import GitHubTopicCollector
from data_intelligence_hub.collectors.hackernews_collector import (
    HackerNewsFrontPageCollector,
    HackerNewsSearchCollector,
    HackerNewsUserCollector,
)
from data_intelligence_hub.collectors.outbound_policy import CollectionPolicyDenied
from data_intelligence_hub.collectors.package_registry_collector import (
    NpmPackageCollector,
    NpmSearchCollector,
    PyPIPackageCollector,
    PyPISearchCollector,
)
from data_intelligence_hub.collectors.pkg_community_collector import (
    CratesIoPackageCollector,
    CratesIoSearchCollector,
    GoPackageCollector,
    GoSearchCollector,
    RubyGemsPackageCollector,
    RubyGemsSearchCollector,
)
from data_intelligence_hub.collectors.pkg_registry2_collector import (
    NuGetPackageCollector,
    NuGetSearchCollector,
    PackagistPackageCollector,
    PackagistSearchCollector,
    PubDevPackageCollector,
    PubDevSearchCollector,
)
from data_intelligence_hub.collectors.tikhub_social import TikHubSocialCollector
from data_intelligence_hub.core.config import get_settings


@pytest.fixture(autouse=True)
def forbid_real_egress(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Block DNS, non-mock HTTP, and subprocess for the whole module."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("COLLECTION_NETWORK_MODE", raising=False)
    get_settings.cache_clear()

    def _fail_dns(host: object, *args: Any, **kwargs: Any) -> list[Any]:
        pytest.fail(f"real DNS lookup attempted: {host!r}")

    monkeypatch.setattr(socket, "getaddrinfo", _fail_dns)

    real_send = httpx.AsyncClient.send

    async def guarded_send(
        self: httpx.AsyncClient, request: httpx.Request, **kwargs: Any
    ) -> httpx.Response:
        if not isinstance(self._transport, httpx.MockTransport):
            pytest.fail(f"real outbound request attempted: {request.method} {request.url}")
        return await real_send(self, request, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "send", guarded_send)

    def guarded_spawn(*args: Any, **kwargs: Any) -> None:
        pytest.fail(f"subprocess spawn attempted: {args!r}")

    for name in ("Popen", "run", "call", "check_call", "check_output", "getoutput"):
        monkeypatch.setattr(subprocess, name, guarded_spawn, raising=False)

    async def _fail_exec(*args: Any, **kwargs: Any) -> None:
        pytest.fail(f"async subprocess spawn attempted: {args!r}")

    monkeypatch.setattr(asyncio, "create_subprocess_shell", _fail_exec, raising=False)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fail_exec, raising=False)

    yield
    get_settings.cache_clear()


OFFLINE_CASES: list[tuple[str, type, dict[str, Any]]] = [
    ("github_repo", GitHubRepoCollector, {"owner": "openai", "repo": "codex"}),
    ("github_topic", GitHubTopicCollector, {"topic": "ai"}),
    (
        "apify_actor",
        ApifyActorCollector,
        {"actor_id": "apify/instagram-scraper", "actor_input": {}},
    ),
    (
        "tikhub_social",
        TikHubSocialCollector,
        {"endpoint_type": "tikhub_tiktok_video_search", "keyword": "x"},
    ),
    ("anysearch", AnySearchCollector, {"query": "x"}),
    ("exa_search", ExaSearchCollector, {"query": "x"}),
    ("exa_find_similar", ExaFindSimilarCollector, {"url": "https://a.test/page"}),
    ("exa_contents", ExaContentsCollector, {"urls": ["https://a.test/page"]}),
    ("exa_answer", ExaAnswerCollector, {"query": "x"}),
    ("hackernews_front_page", HackerNewsFrontPageCollector, {}),
    ("hackernews_search", HackerNewsSearchCollector, {"query": "x"}),
    ("hackernews_user", HackerNewsUserCollector, {"username": "pg"}),
    ("npm_package", NpmPackageCollector, {"package": "react"}),
    ("npm_search", NpmSearchCollector, {"query": "x"}),
    ("pypi_package", PyPIPackageCollector, {"package": "requests"}),
    ("pypi_search", PyPISearchCollector, {"query": "x"}),
    ("crates_package", CratesIoPackageCollector, {"package": "serde"}),
    ("crates_search", CratesIoSearchCollector, {"query": "x"}),
    ("rubygems_package", RubyGemsPackageCollector, {"package": "rails"}),
    ("rubygems_search", RubyGemsSearchCollector, {"query": "x"}),
    ("go_package", GoPackageCollector, {"package": "fmt"}),
    ("go_search", GoSearchCollector, {"query": "x"}),
    ("packagist_package", PackagistPackageCollector, {"package": "laravel/framework"}),
    ("packagist_search", PackagistSearchCollector, {"query": "x"}),
    ("nuget_package", NuGetPackageCollector, {"package": "newtonsoft.json"}),
    ("nuget_search", NuGetSearchCollector, {"query": "x"}),
    ("pubdev_package", PubDevPackageCollector, {"package": "http"}),
    ("pubdev_search", PubDevSearchCollector, {"query": "x"}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["collector_type", "collector_class", "config"],
    [pytest.param(t, c, cfg, id=t) for t, c, cfg in OFFLINE_CASES],
)
async def test_offline_rejects_direct_collect(
    collector_type: str, collector_class: type, config: dict[str, Any]
) -> None:
    del collector_type
    collector = collector_class(dict(config))
    with pytest.raises(CollectionPolicyDenied, match="collection_policy_denied"):
        await collector.collect()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["collector_type", "collector_class", "config"],
    [pytest.param(t, c, cfg, id=t) for t, c, cfg in OFFLINE_CASES],
)
async def test_offline_rejects_direct_test(
    collector_type: str, collector_class: type, config: dict[str, Any]
) -> None:
    del collector_type
    collector = collector_class(dict(config))
    with pytest.raises(CollectionPolicyDenied, match="collection_policy_denied"):
        await collector.test()


@pytest.mark.asyncio
async def test_offline_reason_mentions_policy_code() -> None:
    collector = GitHubRepoCollector({"owner": "openai", "repo": "codex"})
    with pytest.raises(CollectionPolicyDenied) as excinfo:
        await collector.collect()
    assert "collection_policy_denied" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Apify actor_id narrow validation: full URL / traversal / fragment / query
# must be rejected; legit owner/name (converted to owner~name) stays valid.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_id",
    [
        pytest.param("https://api.apify.com/v2/owner/actor", id="full-url"),
        pytest.param("http://evil.test/owner/actor", id="foreign-host-url"),
        pytest.param("owner/../admin", id="path-traversal"),
        pytest.param("../owner/actor", id="leading-traversal"),
        pytest.param("owner/name?maxItems=9999", id="query-injection"),
        pytest.param("owner/name#fragment", id="fragment"),
        pytest.param("owner/na%2Fe", id="percent-encoding"),
        pytest.param("owner/na me", id="whitespace"),
        pytest.param("owner/na\tme", id="tab"),
        pytest.param(".hidden/actor", id="leading-dot-owner"),
        pytest.param("owner/", id="empty-name"),
        pytest.param("/actor", id="empty-owner"),
        pytest.param("owner/name/run", id="extra-segment"),
    ],
)
def test_apify_actor_id_url_shapes_rejected(bad_id: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLLECTION_NETWORK_MODE", "restricted")
    get_settings.cache_clear()
    collector = ApifyActorCollector({"actor_id": bad_id, "actor_input": {}})
    with pytest.raises(CollectorError, match="apify_actor_id_invalid"):
        collector.validate_config()


@pytest.mark.parametrize(
    "good_id",
    ["apify/instagram-scraper", "harshmaur/data_xplorer", "clockworks/tiktok-scraper"],
)
def test_apify_actor_id_legit_format_still_valid(
    good_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COLLECTION_NETWORK_MODE", "restricted")
    get_settings.cache_clear()
    collector = ApifyActorCollector({"actor_id": good_id, "actor_input": {}})
    assert collector.validate_config()["actor_id"] == good_id


# ---------------------------------------------------------------------------
# Restricted mode keeps mock-transport tests usable (no runtime test switch).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_restricted_mode_mock_client_still_collects_github_repo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COLLECTION_NETWORK_MODE", "restricted")
    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        assert "user-agent" in request.headers
        if request.url.path.endswith("/readme"):
            return httpx.Response(
                200,
                json={
                    "name": "README.md",
                    "path": "README.md",
                    "sha": "abc123",
                    "html_url": "https://github.com/openai/codex/blob/main/README.md",
                    "download_url": "https://raw.githubusercontent.com/openai/codex/main/README.md",
                    "size": 2048,
                    "encoding": "base64",
                },
            )
        if request.url.path.endswith("/releases/latest"):
            return httpx.Response(
                200,
                json={
                    "tag_name": "v1.0.0",
                    "name": "v1.0.0",
                    "html_url": "https://github.com/openai/codex/releases/tag/v1.0.0",
                    "published_at": "2026-06-12T00:00:00Z",
                    "created_at": "2026-06-12T00:00:00Z",
                    "prerelease": False,
                    "draft": False,
                },
            )
        return httpx.Response(
            200,
            json={
                "name": "codex",
                "full_name": "openai/codex",
                "html_url": "https://github.com/openai/codex",
                "description": "Agentic coding.",
                "stargazers_count": 1000,
                "forks_count": 50,
                "open_issues_count": 12,
                "watchers_count": 1000,
                "default_branch": "main",
                "language": "Python",
                "topics": ["agent"],
                "license": {"spdx_id": "Apache-2.0", "name": "Apache License 2.0"},
                "pushed_at": "2026-06-11T00:00:00Z",
                "updated_at": "2026-06-11T00:00:00Z",
                "owner": {"login": "openai"},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await GitHubRepoCollector({"owner": "openai", "repo": "codex"}, client).collect()

    assert result.errors == []
    content = result.raw_records[0].content
    assert isinstance(content, dict)
    assert content["full_name"] == "openai/codex"


@pytest.mark.asyncio
async def test_restricted_mode_mock_exa_search_still_collects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COLLECTION_NETWORK_MODE", "restricted")
    monkeypatch.setenv("EXA_API_KEY", "test-key")
    get_settings.cache_clear()

    def fake_client(api_key: str) -> httpx.AsyncClient:
        del api_key
        return httpx.AsyncClient(
            base_url=exa_module.EXA_BASE_URL,
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"results": []})
            ),
        )

    monkeypatch.setattr(exa_module, "_exa_client", fake_client)
    result = await ExaSearchCollector({"query": "x"}).collect()
    assert result.errors == []
    assert result.raw_records == []


@pytest.mark.asyncio
async def test_restricted_mode_mock_hackernews_still_collects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COLLECTION_NETWORK_MODE", "restricted")
    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/topstories.json"):
            return httpx.Response(200, json=[1])
        return httpx.Response(
            200, json={"id": 1, "type": "story", "title": "t", "url": "https://a.test/x"}
        )

    real = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    class _Ctx:
        async def __aenter__(self) -> httpx.AsyncClient:
            return await real.__aenter__()

        async def __aexit__(self, *args: Any) -> None:
            await real.__aexit__(*args)

    monkeypatch.setattr(hn_module.httpx, "AsyncClient", lambda **_kw: _Ctx())
    result = await HackerNewsFrontPageCollector({}).collect()
    assert result.errors == []
    assert result.raw_records[0].record_type == "post"


# ---------------------------------------------------------------------------
# The egress guards themselves must fire (self-test of the fixture).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_guard_blocks_default_transport_client() -> None:
    async with httpx.AsyncClient() as client:
        with pytest.raises(pytest.fail.Exception):
            await client.get("https://example.invalid/")


def test_dns_guard_blocks_resolution() -> None:
    with pytest.raises(pytest.fail.Exception):
        socket.getaddrinfo("example.invalid", 443)


def test_subprocess_guard_blocks_spawn() -> None:
    with pytest.raises(pytest.fail.Exception):
        subprocess.run(["true"], check=False)


# ---------------------------------------------------------------------------
# Injected clients with follow_redirects=True must not be able to bounce a
# fixed provider host to another domain (per-request override at the get site).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_injected_follow_redirects_client_cannot_bounce_github_repo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COLLECTION_NETWORK_MODE", "restricted")
    get_settings.cache_clear()
    visited: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        visited.append(request.url.host)
        if "evil.test" in request.url.host:
            return httpx.Response(200, json={})
        return httpx.Response(302, headers={"location": "https://evil.test/x"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=True
    ) as client:
        with pytest.raises(CollectorError, match="http_status_error"):
            await GitHubRepoCollector({"owner": "openai", "repo": "codex"}, client).collect()

    assert "evil.test" not in visited
    assert visited == ["api.github.com"]


@pytest.mark.asyncio
async def test_injected_follow_redirects_client_cannot_bounce_github_topic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COLLECTION_NETWORK_MODE", "restricted")
    get_settings.cache_clear()
    visited: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        visited.append(request.url.host)
        if "evil.test" in request.url.host:
            return httpx.Response(200, json={"items": [], "total_count": 0})
        return httpx.Response(302, headers={"location": "https://evil.test/y"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=True
    ) as client:
        with pytest.raises(CollectorError, match="http_status_error"):
            await GitHubTopicCollector({"topic": "ai"}, client).collect()

    assert "evil.test" not in visited
    assert visited == ["api.github.com"]


@pytest.mark.asyncio
async def test_apify_traversal_actor_id_never_builds_external_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COLLECTION_NETWORK_MODE", "restricted")
    get_settings.cache_clear()
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, json={})

    real = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    class _Ctx:
        async def __aenter__(self) -> httpx.AsyncClient:
            return await real.__aenter__()

        async def __aexit__(self, *args: Any) -> None:
            await real.__aexit__(*args)

    collector = ApifyActorCollector(
        {"actor_id": "owner/../evil.test", "actor_input": {}},
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(CollectorError, match="apify_actor_id_invalid"):
        await collector.collect()
    assert requested == []


@pytest.mark.asyncio
async def test_apify_injected_client_cannot_redirect_off_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COLLECTION_NETWORK_MODE", "restricted")
    monkeypatch.setenv("APIFY_API_TOKEN", "test-token")
    get_settings.cache_clear()
    visited: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        visited.append(request.url.host)
        if request.url.host == "api.apify.com":
            return httpx.Response(307, headers={"location": "https://unapproved.test/run"})
        return httpx.Response(400, json={"error": "unexpected destination"})

    from data_intelligence_hub.collectors.apify_actor import _apify_post

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond), follow_redirects=True
    ) as client:
        with pytest.raises(CollectorError):
            await _apify_post(client, "/acts/owner~actor/runs", {}, {}, "test-token")
    assert visited == ["api.apify.com"]
