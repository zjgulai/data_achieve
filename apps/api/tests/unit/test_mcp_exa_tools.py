"""Exa MCP Pack：工具注册、端点映射与授权判定。

不触碰网络：collect_capability 被替换为记录器。
"""

from __future__ import annotations

import uuid

import pytest
from mcp.client import Client

from data_intelligence_hub.mcp_runtime import server as server_module
from data_intelligence_hub.mcp_runtime.access_control import assert_tool_allowed
from data_intelligence_hub.mcp_runtime.server import mcp_server
from data_intelligence_hub.services.quick_collect_service import QuickCollectResponse

pytestmark = pytest.mark.anyio


class _CollectRecorder:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def __call__(
        self,
        endpoint_type: str,
        project_id: uuid.UUID,
        params: dict[str, object],
        *,
        workspace_id: uuid.UUID | None = None,
        tool_call: dict[str, object] | None = None,
    ) -> QuickCollectResponse:
        self.calls.append(
            {
                "endpoint_type": endpoint_type,
                "project_id": project_id,
                "params": params,
                "workspace_id": workspace_id,
            }
        )
        return QuickCollectResponse(
            task_run_id=uuid.uuid4(),
            task_id=uuid.uuid4(),
            source_id=uuid.uuid4(),
            status="success",
            records_count=1,
            error_message=None,
        )


@pytest.fixture()
def recorder(monkeypatch: pytest.MonkeyPatch) -> _CollectRecorder:
    rec = _CollectRecorder()
    monkeypatch.setattr(server_module, "collect_capability", rec)
    return rec


async def test_mcp_registers_exa_pack_tools() -> None:
    tools = await mcp_server.list_tools()
    names = {tool.name for tool in tools}
    assert {
        "web_search",
        "web_fetch",
        "answer",
        "deep_research",
        "deep_research_start",
        "deep_research_check",
        "workspace_answer",
        "create_monitor",
        "list_monitors",
        "enrich_list",
        "enrichment_check",
    } <= names


async def test_web_search_maps_type_to_preset_endpoint(recorder: _CollectRecorder) -> None:
    async with Client(mcp_server, raise_exceptions=False) as client:
        result = await client.call_tool(
            "web_search",
            {
                "project_id": str(uuid.uuid4()),
                "query": "exa pricing",
                "search_type": "lite",
                "num_results": 7,
                "objective": "找到定价页",
            },
        )

    assert result.is_error is False
    assert len(recorder.calls) == 1
    call = recorder.calls[0]
    assert call["endpoint_type"] == "exa_search_lite"
    assert call["params"]["query"] == "exa pricing"
    assert call["params"]["num_results"] == 7
    assert call["params"]["objective"] == "找到定价页"


async def test_web_search_rejects_unknown_type_and_provider(
    recorder: _CollectRecorder,
) -> None:
    async with Client(mcp_server, raise_exceptions=False) as client:
        bad_type = await client.call_tool(
            "web_search",
            {"project_id": str(uuid.uuid4()), "query": "q", "search_type": "turbo"},
        )
        bad_provider = await client.call_tool(
            "web_search",
            {"project_id": str(uuid.uuid4()), "query": "q", "provider": "bing"},
        )

    assert bad_type.is_error is True
    assert bad_provider.is_error is True
    assert recorder.calls == []


async def test_web_fetch_routes_to_jina_for_one_url(recorder: _CollectRecorder) -> None:
    async with Client(mcp_server, raise_exceptions=False) as client:
        ok = await client.call_tool(
            "web_fetch",
            {
                "project_id": str(uuid.uuid4()),
                "urls": ["https://example.com/a"],
                "provider": "jina",
            },
        )
        too_many = await client.call_tool(
            "web_fetch",
            {
                "project_id": str(uuid.uuid4()),
                "urls": ["https://example.com/a", "https://example.com/b"],
                "provider": "jina",
            },
        )

    assert ok.is_error is False
    assert too_many.is_error is True
    assert len(recorder.calls) == 1
    call = recorder.calls[0]
    assert call["endpoint_type"] == "jina_page_content"
    assert call["params"]["url"] == "https://example.com/a"


async def test_web_fetch_exa_passes_urls_and_options(recorder: _CollectRecorder) -> None:
    async with Client(mcp_server, raise_exceptions=False) as client:
        result = await client.call_tool(
            "web_fetch",
            {
                "project_id": str(uuid.uuid4()),
                "urls": ["https://example.com/a", "https://example.com/b"],
                "contents_mode": "summary",
                "max_age_hours": -1,
                "summary_query": "定价",
            },
        )

    assert result.is_error is False
    call = recorder.calls[0]
    assert call["endpoint_type"] == "exa_contents"
    assert call["params"]["urls"] == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    assert call["params"]["contents_mode"] == "summary"
    assert call["params"]["max_age_hours"] == -1
    assert call["params"]["summary_query"] == "定价"


def test_tool_allowed_layers() -> None:
    # N1 显式白名单：空白名单拒绝全部工具（语义翻转，默认放行已废除）。
    assert assert_tool_allowed("deep_research", []) is False
    assert assert_tool_allowed("web_search", []) is False
    assert assert_tool_allowed("list_platforms", []) is False
    # 白名单非空时按白名单收窄。
    assert assert_tool_allowed("deep_research", ["deep_research"]) is True
    assert assert_tool_allowed("deep_research", ["web_search"]) is False
    assert assert_tool_allowed("web_search", ["web_search"]) is True
    assert assert_tool_allowed("web_search", ["answer"]) is False


def test_project_key_cannot_switch_project() -> None:
    from data_intelligence_hub.mcp_runtime.auth import ProjectApiKeyContext
    from data_intelligence_hub.mcp_runtime.server import _assert_bound_project

    bound_project = uuid.uuid4()
    identity = ProjectApiKeyContext(
        key_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        project_id=bound_project,
        key_prefix="dih_test",
        label="test",
    )
    assert _assert_bound_project(identity, bound_project) == bound_project
    with pytest.raises(ValueError, match="project_not_found"):
        _assert_bound_project(identity, uuid.uuid4())
    other = uuid.uuid4()
    assert _assert_bound_project(None, other) == other
