from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from data_intelligence_hub.collectors import anysearch_collector as anysearch_module
from data_intelligence_hub.collectors import exa_collector as exa_module
from data_intelligence_hub.collectors.anysearch_collector import AnySearchCollector
from data_intelligence_hub.collectors.exa_collector import (
    ExaAnswerCollector,
    ExaContentsCollector,
    ExaFindSimilarCollector,
    ExaSearchCollector,
)
from data_intelligence_hub.collectors.registry import COLLECTOR_REGISTRY
from data_intelligence_hub.services.collector_catalog import validate_collector_config


def _client_factory(
    handler: httpx.MockTransport,
) -> Callable[[str], httpx.AsyncClient]:
    def create_client(api_key: str) -> httpx.AsyncClient:
        del api_key
        return httpx.AsyncClient(
            base_url=exa_module.EXA_BASE_URL,
            transport=handler,
        )

    return create_client


@pytest.mark.asyncio
async def test_anysearch_collect_forwards_tag_and_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_payload: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "results": [
                        {
                            "title": "Golang docs",
                            "url": "https://go.dev/doc/",
                            "snippet": "Documentation",
                            "source": "go.dev",
                            "score": 0.98,
                        }
                    ]
                },
                "request_id": "req-anysearch",
            },
        )

    monkeypatch.setenv("ANYSEARCH_API_KEY", "test-key")
    original_async_client = httpx.AsyncClient

    def create_client(**kwargs: Any) -> httpx.AsyncClient:
        return original_async_client(
            transport=httpx.MockTransport(handler),
            **kwargs,
        )

    monkeypatch.setattr(anysearch_module.httpx, "AsyncClient", create_client)

    collector = AnySearchCollector(
        {
            "query": "http client",
            "tag": "code.doc",
            "params": {"library": "golang"},
            "num_results": 3,
        }
    )

    result = await collector.collect()

    assert captured_payload == {
        "query": "http client",
        "num_results": 3,
        "tag": "code.doc",
        "params": {"library": "golang"},
    }
    assert result.errors == []
    assert result.raw_records[0].content["source"] == "go.dev"
    assert result.raw_records[0].content["score"] == 0.98


@pytest.mark.asyncio
async def test_exa_search_collect_builds_text_payload_and_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_payload: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "requestId": "req-exa",
                "resolvedSearchType": "fast",
                "results": [
                    {
                        "id": "doc-1",
                        "title": "Example",
                        "url": "https://example.com/article",
                        "score": 0.91,
                        "text": "Example text",
                    }
                ],
            },
        )

    monkeypatch.setenv("EXA_API_KEY", "test-key")
    monkeypatch.setattr(
        exa_module,
        "_exa_client",
        _client_factory(httpx.MockTransport(handler)),
    )

    collector = ExaSearchCollector(
        {
            "query": "semantic search",
            "search_type": "fast",
            "num_results": 2,
            "contents_mode": "text",
            "text_max_characters": 500,
        }
    )

    result = await collector.collect()

    assert captured_payload == {
        "query": "semantic search",
        "type": "fast",
        "numResults": 2,
        "contents": {"text": {"maxCharacters": 500}},
    }
    assert result.errors == []
    assert result.raw_records[0].record_type == "search_result"
    assert result.raw_records[0].content["request_id"] == "req-exa"
    assert result.raw_records[0].content["resolved_search_type"] == "fast"


def test_exa_collectors_are_registered_and_validate_endpoint_configs() -> None:
    assert COLLECTOR_REGISTRY["exa_search"] is ExaSearchCollector
    assert COLLECTOR_REGISTRY["exa_find_similar"] is ExaFindSimilarCollector
    assert COLLECTOR_REGISTRY["exa_contents"] is ExaContentsCollector
    assert COLLECTOR_REGISTRY["exa_answer"] is ExaAnswerCollector

    search = validate_collector_config(
        "exa_search",
        {
            "query": "company intelligence",
            "search_type": "deep-lite",
            "num_results": 20,
            "contents_mode": "summary",
        },
    )
    contents = validate_collector_config(
        "exa_contents",
        {"urls": [" https://example.com "], "subpages": 2},
    )

    assert search["search_type"] == "deep-lite"
    assert search["num_results"] == 20
    assert contents["urls"] == ["https://example.com"]
    assert contents["subpages"] == 2
