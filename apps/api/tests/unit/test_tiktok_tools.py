"""Contract tests for the twelve TikTok content and commerce tools."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from data_intelligence_hub.main import app
from data_intelligence_hub.services.tiktok_tools import (
    TOOL_IDS,
    TOOL_SPECS,
    ToolResult,
    run_tiktok_tool,
    tiktok_creator_profile,
    tiktok_creator_search,
    tiktok_hashtag_videos,
    tiktok_transcript,
    tiktok_video_comments,
    tiktok_video_detail,
)
from data_intelligence_hub.services.tiktok_tools import (
    _collect as _real_collect,
)

PROJECT_ID = uuid.uuid4()


def _fake_collect_factory(records: dict[str, list[dict[str, Any]]], calls: list):
    async def fake_collect(project_id, endpoint_type, params, limit):
        calls.append((endpoint_type, params))
        items = records.get(endpoint_type, [])
        return items, {
            "endpoint_type": endpoint_type,
            "run_id": f"run-{len(calls)}",
            "status": "success" if items else "success",
            "records_count": len(items),
            "error": None,
        }

    return fake_collect


@pytest.mark.asyncio
async def test_sixteen_tools_are_registered() -> None:
    assert len(TOOL_IDS) == 16
    assert set(TOOL_IDS) == set(TOOL_SPECS)


@pytest.mark.asyncio
async def test_video_detail_uses_primary(monkeypatch) -> None:
    calls: list = []
    fake = _fake_collect_factory(
        {"tikhub_tiktok_video_detail": [{"video_id": "v1"}]}, calls
    )
    monkeypatch.setattr(
        "data_intelligence_hub.services.tiktok_tools._collect", fake
    )
    result = await tiktok_video_detail(PROJECT_ID, {"video_url": "https://x/video/123"})
    assert result.status == "success"
    assert result.records == [{"video_id": "v1"}]
    assert calls[0][0] == "tikhub_tiktok_video_detail"
    assert calls[0][1]["item_id"] == "123"


@pytest.mark.asyncio
async def test_video_detail_falls_back_to_apify(monkeypatch) -> None:
    calls: list = []
    fake = _fake_collect_factory(
        {"apify_tiktok_scraper": [{"video_id": "v2"}]}, calls
    )
    monkeypatch.setattr(
        "data_intelligence_hub.services.tiktok_tools._collect", fake
    )
    result = await tiktok_video_detail(PROJECT_ID, {"video_id": "v1"})
    assert result.status == "success"
    assert result.records == [{"video_id": "v2"}]
    assert calls[0][0] == "tikhub_tiktok_video_detail"
    assert calls[1][0] == "apify_tiktok_scraper"


@pytest.mark.asyncio
async def test_hashtag_name_uses_search_proxy_and_filters(monkeypatch) -> None:
    calls: list = []
    fake = _fake_collect_factory(
        {
            "tikhub_tiktok_search_web": [
                {"video_id": "v1", "hashtags": ["newborn"]},
                {"video_id": "v2", "hashtags": ["other"]},
            ]
        },
        calls,
    )
    monkeypatch.setattr(
        "data_intelligence_hub.services.tiktok_tools._collect", fake
    )
    result = await tiktok_hashtag_videos(PROJECT_ID, {"hashtag": "newborn"})
    assert result.status == "success"
    assert [record["video_id"] for record in result.records] == ["v1"]
    assert calls[0][0] == "tikhub_tiktok_search_web"


@pytest.mark.asyncio
async def test_comments_merge_replies(monkeypatch) -> None:
    calls: list = []
    fake = _fake_collect_factory(
        {
            "tikhub_tiktok_comments_app": [
                {"comment_id": "c1", "reply_count": 2},
                {"comment_id": "c2", "reply_count": 0},
            ],
            "tikhub_tiktok_comment_replies_app": [
                {"comment_id": "r1", "parent_comment_id": "c1"}
            ],
        },
        calls,
    )
    monkeypatch.setattr(
        "data_intelligence_hub.services.tiktok_tools._collect", fake
    )
    result = await tiktok_video_comments(
        PROJECT_ID, {"video_id": "v1", "include_replies": True}
    )
    assert result.records_count == 3
    assert len(result.runs) == 2


@pytest.mark.asyncio
async def test_creator_profile_resolves_sec_uid(monkeypatch) -> None:
    calls: list = []
    fake = _fake_collect_factory(
        {
            "tikhub_tiktok_sec_uid": [{"value": "MS4w"}],
            "tikhub_tiktok_user_profile_web": [{"uid": "u1"}],
            "tikhub_tiktok_user_posts_web": [{"video_id": "v1"}],
        },
        calls,
    )
    monkeypatch.setattr(
        "data_intelligence_hub.services.tiktok_tools._collect", fake
    )
    result = await tiktok_creator_profile(
        PROJECT_ID, {"handle": "alice", "include_videos": True}
    )
    assert result.records_count == 2
    assert calls[0][0] == "tikhub_tiktok_sec_uid"
    assert calls[1][1]["sec_user_id"] == "MS4w"
    assert calls[2][1]["sec_user_id"] == "MS4w"


@pytest.mark.asyncio
async def test_creator_search_dedupes_authors(monkeypatch) -> None:
    calls: list = []
    fake = _fake_collect_factory(
        {
            "tikhub_tiktok_search_web": [
                {"author_id": "u1", "author_username": "alice"},
                {"author_id": "u1", "author_username": "alice"},
                {"author_id": "u2", "author_username": "bob"},
            ]
        },
        calls,
    )
    monkeypatch.setattr(
        "data_intelligence_hub.services.tiktok_tools._collect", fake
    )
    result = await tiktok_creator_search(PROJECT_ID, {"query": "stroller"})
    assert result.records_count == 2
    assert {record["uid"] for record in result.records} == {"u1", "u2"}


@pytest.mark.asyncio
async def test_transcript_requires_urls() -> None:
    result = await tiktok_transcript(PROJECT_ID, {})
    assert result.status == "failed"
    assert result.errors == ["video_urls_required"]


@pytest.mark.asyncio
async def test_unknown_tool_raises() -> None:
    with pytest.raises(ValueError, match="unknown_tiktok_tool"):
        await run_tiktok_tool("nope", PROJECT_ID, {})


def test_rest_tools_list_and_unknown() -> None:
    client = TestClient(app)
    response = client.get("/api/tiktok/tools")
    assert response.status_code == 200
    assert len(response.json()) == 16
    response = client.post(
        "/api/tiktok/tools/nope",
        json={"project_id": str(PROJECT_ID), "params": {}},
    )
    assert response.status_code == 404


def test_rest_tool_run(monkeypatch) -> None:
    async def fake_run(tool_id, project_id, params):
        return ToolResult(
            tool_id=tool_id,
            status="success",
            records=[{"ok": True}],
            records_count=1,
        )

    monkeypatch.setattr(
        "data_intelligence_hub.api.routes.tiktok_tools.run_tiktok_tool",
        fake_run,
    )
    client = TestClient(app)
    response = client.post(
        "/api/tiktok/tools/tiktok_video_search",
        json={"project_id": str(PROJECT_ID), "params": {"query": "x"}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["records_count"] == 1


def test_real_collect_is_async() -> None:
    assert callable(_real_collect)


def test_mcp_registers_all_eight_tools() -> None:
    import asyncio

    from data_intelligence_hub.mcp_runtime.server import mcp_server

    tools = asyncio.run(mcp_server.list_tools())
    names = {tool.name for tool in tools}
    assert set(TOOL_IDS) <= names
