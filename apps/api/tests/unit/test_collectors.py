from __future__ import annotations

import httpx
import pytest

from data_intelligence_hub.collectors.base import (
    HTTP_TIMEOUT_SECONDS,
    HTTP_USER_AGENT,
    CollectorError,
)
from data_intelligence_hub.collectors.generic_web import GenericWebCollector
from data_intelligence_hub.collectors.github_repo import GitHubRepoCollector
from data_intelligence_hub.collectors.github_topic import GitHubTopicCollector
from data_intelligence_hub.collectors.manual_json import ManualJsonCollector


def assert_request_policy(request: httpx.Request) -> None:
    assert request.headers["user-agent"] == HTTP_USER_AGENT
    timeout = request.extensions.get("timeout")
    assert isinstance(timeout, dict)
    assert timeout["connect"] == HTTP_TIMEOUT_SECONDS


@pytest.mark.asyncio
async def test_manual_json_collector_validates_tests_collects_and_normalizes() -> None:
    collector = ManualJsonCollector(
        {"entity_type": "product", "json_data": {"name": "Demo", "price": 99}}
    )

    assert collector.validate_config()["entity_type"] == "product"
    test_result = await collector.test()
    collect_result = await collector.collect()

    assert test_result.status == "ok"
    assert collect_result.errors == []
    assert collect_result.raw_records[0].record_type == "manual_json"
    content = collect_result.raw_records[0].content
    assert isinstance(content, dict)
    assert content["entity_type"] == "product"
    assert collector.normalize(collect_result.raw_records[0]) == []


@pytest.mark.asyncio
async def test_github_repo_collector_uses_http_policy_and_collects_repo_snapshot() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert_request_policy(request)
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
                "pushed_at": "2026-06-11T00:00:00Z",
                "updated_at": "2026-06-11T00:00:00Z",
                "owner": {"login": "openai"},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        collector = GitHubRepoCollector({"owner": "openai", "repo": "codex"}, client)
        test_result = await collector.test()
        collect_result = await collector.collect()

    assert test_result.status == "ok"
    raw_record = collect_result.raw_records[0]
    content = raw_record.content
    assert isinstance(content, dict)
    assert raw_record.source_url == "https://github.com/openai/codex"
    assert content["full_name"] == "openai/codex"
    assert collector.normalize(raw_record) == []


@pytest.mark.asyncio
async def test_github_repo_collector_retries_transient_upstream_failure() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        assert_request_policy(request)
        if request_count == 1:
            return httpx.Response(502, json={"message": "bad gateway"})
        return httpx.Response(
            200,
            json={
                "name": "codex",
                "full_name": "openai/codex",
                "html_url": "https://github.com/openai/codex",
                "owner": {"login": "openai"},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        collector = GitHubRepoCollector({"owner": "openai", "repo": "codex"}, client)
        collect_result = await collector.collect()

    assert request_count == 2
    content = collect_result.raw_records[0].content
    assert isinstance(content, dict)
    assert content["full_name"] == "openai/codex"


@pytest.mark.asyncio
async def test_github_topic_collector_collects_repository_search_snapshot() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert_request_policy(request)
        assert request.url.params["q"] == "topic:web-scraping"
        return httpx.Response(
            200,
            json={
                "total_count": 1,
                "items": [
                    {
                        "full_name": "example/scraper",
                        "html_url": "https://github.com/example/scraper",
                        "description": "Scraper",
                        "stargazers_count": 42,
                        "forks_count": 3,
                        "updated_at": "2026-06-11T00:00:00Z",
                    }
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        collector = GitHubTopicCollector({"topic": "web-scraping", "max_results": 10}, client)
        test_result = await collector.test()
        collect_result = await collector.collect()

    assert test_result.status == "ok"
    raw_record = collect_result.raw_records[0]
    content = raw_record.content
    assert isinstance(content, dict)
    assert raw_record.record_type == "github_topic"
    assert content["repositories"][0]["full_name"] == "example/scraper"
    assert collector.normalize(raw_record) == []


@pytest.mark.asyncio
async def test_generic_web_collector_collects_html_snapshot() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert_request_policy(request)
        return httpx.Response(
            200,
            text="<html><head><title>Demo</title></head><body><h1>Hello</h1></body></html>",
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        collector = GenericWebCollector({"url": "https://example.com"}, client)
        test_result = await collector.test()
        collect_result = await collector.collect()

    assert test_result.status == "ok"
    raw_record = collect_result.raw_records[0]
    content = raw_record.content
    assert isinstance(content, dict)
    assert raw_record.record_type == "generic_web"
    assert content["title"] == "Demo"
    assert "Hello" in content["text_content"]
    assert collector.normalize(raw_record) == []


@pytest.mark.asyncio
async def test_github_topic_collector_classifies_rate_limit_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert_request_policy(request)
        return httpx.Response(429, headers={"retry-after": "60"}, json={"message": "rate limit"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        collector = GitHubTopicCollector({"topic": "web-scraping", "max_results": 10}, client)
        with pytest.raises(CollectorError, match="http_rate_limited"):
            await collector.collect()


@pytest.mark.asyncio
async def test_generic_web_collector_classifies_connection_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        collector = GenericWebCollector({"url": "https://example.com"}, client)
        with pytest.raises(CollectorError, match="http_connection_failed"):
            await collector.collect()
