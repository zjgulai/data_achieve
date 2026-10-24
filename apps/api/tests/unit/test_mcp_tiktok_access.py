"""项目密钥跨工具隔离：collect / TikTok / Exa Pack 的项目绑定与 workspace 归属。

负例：项目密钥 A 绑定项目 A，调用项目 B 的工具必须稳定报错，
且 collect / TikTok / web_search 不得回退 demo workspace。
正例：绑定项目内调用成功，collect_capability 收到密钥工作区，
per_call 额度真实扣减；白名单外的工具拒绝。
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from mcp.client import Client
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from data_intelligence_hub.mcp_runtime import access_control
from data_intelligence_hub.mcp_runtime import server as server_module
from data_intelligence_hub.mcp_runtime.auth import ProjectApiKeyContext
from data_intelligence_hub.mcp_runtime.server import mcp_server
from data_intelligence_hub.mcp_runtime.tool_registry import TOOL_POLICIES
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project_api_key import ProjectApiKey
from data_intelligence_hub.repositories.project_api_keys import create_key
from data_intelligence_hub.services.quick_collect_service import QuickCollectResponse
from data_intelligence_hub.services.tiktok_tools import ToolResult, run_tiktok_tool

pytestmark = pytest.mark.anyio


@dataclass(slots=True)
class _Key:
    identity: ProjectApiKeyContext
    factory: async_sessionmaker[AsyncSession]


def _recorder_response() -> QuickCollectResponse:
    return QuickCollectResponse(
        task_run_id=uuid.uuid4(),
        task_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        status="success",
        records_count=1,
        error_message=None,
    )


@pytest.fixture()
def project_key(monkeypatch: pytest.MonkeyPatch, tmp_path) -> _Key:
    """一把真实入库的项目密钥 + 打进 access_control 的调用身份。

    sqlite 文件库 + NullPool：setup 循环与 anyio 测试循环不共享连接。
    find_by_id / consume_daily_quota 走真实实现，额度扣减可断言。
    """
    identity = ProjectApiKeyContext(
        key_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        key_prefix="dih_n1",
        label="n1",
    )

    async def _setup() -> async_sessionmaker[AsyncSession]:
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{tmp_path / 'mcp_access.sqlite3'}",
            poolclass=NullPool,
        )
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            record = await create_key(
                session,
                project_id=identity.project_id,
                workspace_id=identity.workspace_id,
                label="n1-access",
                key_prefix=identity.key_prefix,
                key_hash="a" * 64,
                created_by_user_id=uuid.uuid4(),
                tool_allowlist=list(TOOL_POLICIES),
                daily_collect_quota=10,
            )
            await session.commit()
        # identity.key_id 必须等于库里的行 id，find_by_id 才能命中。
        object.__setattr__(identity, "key_id", record.id)
        return factory

    factory = asyncio.run(_setup())
    monkeypatch.setattr(access_control, "project_api_key_context", lambda context: identity)
    monkeypatch.setattr(access_control, "async_session_factory", factory)
    return _Key(identity=identity, factory=factory)


# ── 负例：外来项目一律拒绝，业务函数不得执行 ─────────────────────────────


async def test_collect_rejects_foreign_project(
    project_key: _Key, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[dict[str, object]] = []

    async def fake_collect(endpoint_type, project_id, params, **kwargs):
        captured.append({"project_id": project_id, "workspace_id": kwargs.get("workspace_id")})
        raise AssertionError("should not execute")

    monkeypatch.setattr(server_module, "collect_capability", fake_collect)
    async with Client(mcp_server, raise_exceptions=False) as client:
        result = await client.call_tool(
            "collect",
            {
                "endpoint_type": "exa_search_lite",
                "project_id": str(uuid.uuid4()),  # 不是密钥绑定的项目
                "params": {},
            },
        )

    assert result.is_error is True
    assert captured == []


async def test_tiktok_tool_rejects_foreign_project(
    project_key: _Key, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, uuid.UUID]] = []

    async def fake_run_tiktok(tool_name, project_id, params):
        calls.append((tool_name, project_id))
        raise AssertionError("should not execute")

    monkeypatch.setattr(server_module, "run_tiktok_tool", fake_run_tiktok)
    async with Client(mcp_server, raise_exceptions=False) as client:
        result = await client.call_tool(
            "tiktok_video_search",
            {"project_id": str(uuid.uuid4()), "query": "q"},
        )

    assert result.is_error is True
    assert calls == []


async def test_web_search_rejects_foreign_project(
    project_key: _Key, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[dict[str, object]] = []

    async def fake_collect(endpoint_type, project_id, params, **kwargs):
        captured.append({"project_id": project_id})
        raise AssertionError("should not execute")

    monkeypatch.setattr(server_module, "collect_capability", fake_collect)
    async with Client(mcp_server, raise_exceptions=False) as client:
        result = await client.call_tool(
            "web_search",
            {"project_id": str(uuid.uuid4()), "query": "q"},
        )

    assert result.is_error is True
    assert captured == []


# ── 正例：绑定项目内调用成功，workspace 等于密钥工作区 ───────────────────


async def test_collect_allows_bound_project_and_uses_key_workspace(
    project_key: _Key, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[dict[str, object]] = []

    async def fake_collect(endpoint_type, project_id, params, *, workspace_id=None, tool_call=None):
        captured.append(
            {
                "endpoint_type": endpoint_type,
                "project_id": project_id,
                "workspace_id": workspace_id,
            }
        )
        return _recorder_response()

    monkeypatch.setattr(server_module, "collect_capability", fake_collect)
    async with Client(mcp_server, raise_exceptions=False) as client:
        result = await client.call_tool(
            "collect",
            {
                "endpoint_type": "exa_search_lite",
                "project_id": str(project_key.identity.project_id),
                "params": {"query": "q"},
            },
        )

    assert result.is_error is False
    assert captured == [
        {
            "endpoint_type": "exa_search_lite",
            "project_id": project_key.identity.project_id,
            "workspace_id": project_key.identity.workspace_id,
        }
    ]

    # per_call 额度在进体前真实扣减一次。
    async with project_key.factory() as session:
        key = (await session.execute(select(ProjectApiKey))).scalar_one()
    assert key.quota_used == 1
    assert key.quota_date is not None


async def test_tiktok_tool_allows_bound_project(
    project_key: _Key, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, uuid.UUID, dict[str, object]]] = []

    async def fake_run_tiktok(tool_name, project_id, params, *, workspace_id=None):
        calls.append((tool_name, project_id, params))
        return ToolResult(
            tool_id=tool_name, status="success", records=[{"id": "1"}], records_count=1
        )

    monkeypatch.setattr(server_module, "run_tiktok_tool", fake_run_tiktok)
    async with Client(mcp_server, raise_exceptions=False) as client:
        result = await client.call_tool(
            "tiktok_video_search",
            {"project_id": str(project_key.identity.project_id), "query": "q"},
        )

    assert result.is_error is False
    assert calls == [
        (
            "tiktok_video_search",
            project_key.identity.project_id,
            {"query": "q", "limit": 50},
        )
    ]


async def test_web_search_uses_key_workspace_and_metadata(
    project_key: _Key, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[dict[str, object]] = []

    async def fake_collect(endpoint_type, project_id, params, *, workspace_id=None, tool_call=None):
        captured.append(
            {
                "endpoint_type": endpoint_type,
                "project_id": project_id,
                "workspace_id": workspace_id,
                "tool_call": tool_call,
            }
        )
        return _recorder_response()

    monkeypatch.setattr(server_module, "collect_capability", fake_collect)
    async with Client(mcp_server, raise_exceptions=False) as client:
        result = await client.call_tool(
            "web_search",
            {
                "project_id": str(project_key.identity.project_id),
                "query": "exa pricing",
                "search_type": "lite",
            },
        )

    assert result.is_error is False
    assert len(captured) == 1
    call = captured[0]
    assert call["endpoint_type"] == "exa_search_lite"
    assert call["project_id"] == project_key.identity.project_id
    # 项目密钥的采集记录必须落密钥工作区，不回退 demo workspace。
    assert call["workspace_id"] == project_key.identity.workspace_id
    tool_call = call["tool_call"]
    assert tool_call is not None
    assert tool_call["key_id"] == str(project_key.identity.key_id)
    assert tool_call["project_id"] == str(project_key.identity.project_id)


# ── TikTok workspace 透传：collect_capability 层断言 ─────────────────────


async def test_tiktok_passes_key_workspace_to_collect_capability(
    project_key: _Key, monkeypatch: pytest.MonkeyPatch
) -> None:
    """server 边界捕获 run_tiktok_tool 的 workspace_id kwarg。"""
    calls: list[dict[str, object]] = []

    async def fake_run_tiktok(tool_name, project_id, params, *, workspace_id=None):
        calls.append({"tool": tool_name, "project_id": project_id, "workspace_id": workspace_id})
        return ToolResult(
            tool_id=tool_name, status="success", records=[{"id": "1"}], records_count=1
        )

    monkeypatch.setattr(server_module, "run_tiktok_tool", fake_run_tiktok)
    async with Client(mcp_server, raise_exceptions=False) as client:
        result = await client.call_tool(
            "tiktok_video_search",
            {"project_id": str(project_key.identity.project_id), "query": "q"},
        )

    assert result.is_error is False
    assert calls == [
        {
            "tool": "tiktok_video_search",
            "project_id": project_key.identity.project_id,
            "workspace_id": project_key.identity.workspace_id,
        }
    ]


async def test_tiktok_real_chain_passes_workspace_to_collect_capability(
    project_key: _Key, monkeypatch: pytest.MonkeyPatch
) -> None:
    """真实 run_tiktok_tool → _collect → collect_capability 链路。

    项目密钥绑定非 demo 工作区：collect_capability 收到的 workspace_id
    必须是密钥工作区。修复前此处收到 None（demo 回退），业务层会以
    QuickCollectUnknownProjectError 失败。
    """
    from data_intelligence_hub.mcp_runtime import collect_service
    from data_intelligence_hub.services import tiktok_tools

    captured: list[dict[str, object]] = []

    async def fake_collect_capability(
        endpoint_type, project_id, params, *, workspace_id=None, tool_call=None
    ):
        captured.append(
            {
                "endpoint_type": endpoint_type,
                "project_id": project_id,
                "workspace_id": workspace_id,
            }
        )
        return _recorder_response()

    monkeypatch.setattr(collect_service, "collect_capability", fake_collect_capability)
    # _fetch_records 会查库取原始记录；sqlite 里没有 demo workspace，返回空即可。
    monkeypatch.setattr(tiktok_tools, "collect_session_factory", project_key.factory)
    result = await run_tiktok_tool(
        "tiktok_video_search",
        project_key.identity.project_id,
        {"query": "q", "limit": 10},
        workspace_id=project_key.identity.workspace_id,
    )

    # sqlite 里没有原始记录，status 是 empty；本用例断言的是 workspace 透传。
    assert result.status in {"success", "empty"}
    assert captured == [
        {
            "endpoint_type": "tikhub_tiktok_search_web",
            "project_id": project_key.identity.project_id,
            "workspace_id": project_key.identity.workspace_id,
        }
    ]


async def test_tiktok_without_workspace_keeps_demo_fallback(
    project_key: _Key, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HTTP/CDO 路径不设置 workspace：ContextVar 默认 None，行为不变。"""
    from data_intelligence_hub.mcp_runtime import collect_service
    from data_intelligence_hub.services import tiktok_tools

    captured: list[dict[str, object]] = []

    async def fake_collect_capability(
        endpoint_type, project_id, params, *, workspace_id=None, tool_call=None
    ):
        captured.append({"workspace_id": workspace_id})
        return _recorder_response()

    monkeypatch.setattr(collect_service, "collect_capability", fake_collect_capability)
    monkeypatch.setattr(tiktok_tools, "collect_session_factory", project_key.factory)
    result = await run_tiktok_tool(
        "tiktok_video_search",
        project_key.identity.project_id,
        {"query": "q"},
    )

    assert result.status in {"success", "empty"}
    assert captured == [{"workspace_id": None}]


# ── 白名单：显式白名单外的工具拒绝 ───────────────────────────────────────


async def test_tool_outside_allowlist_rejected(
    project_key: _Key, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[dict[str, object]] = []

    async def fake_collect(endpoint_type, project_id, params, **kwargs):
        captured.append({"project_id": project_id})
        raise AssertionError("should not execute")

    async def fake_find(session: object, key_id: uuid.UUID) -> object:
        return SimpleNamespace(revoked_at=None, tool_allowlist=["list_platforms"])

    monkeypatch.setattr(access_control, "find_by_id", fake_find)
    monkeypatch.setattr(server_module, "collect_capability", fake_collect)
    async with Client(mcp_server, raise_exceptions=False) as client:
        result = await client.call_tool(
            "web_search",
            {"project_id": str(project_key.identity.project_id), "query": "q"},
        )

    assert result.is_error is True
    assert captured == []


# ── 额度：per_call 日额度耗尽硬拦（承接原 tool_policy.enforce_quota 语义）──


async def test_per_call_quota_exhaustion_rejects(
    project_key: _Key, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[dict[str, object]] = []

    async def fake_collect(endpoint_type, project_id, params, **kwargs):
        captured.append({"project_id": project_id})
        return _recorder_response()

    monkeypatch.setattr(server_module, "collect_capability", fake_collect)

    # 库里密钥 daily_collect_quota=10，先把额度用到只剩 1。
    # quota_date 必须同时拨到今天，否则 consume_daily_quota 走跨日归零分支。
    async with project_key.factory() as session:
        key = (await session.execute(select(ProjectApiKey))).scalar_one()
        key.quota_date = datetime.now(UTC).date()
        key.quota_used = 9
        await session.commit()

    results: list[bool] = []
    async with Client(mcp_server, raise_exceptions=False) as client:
        for _ in range(2):
            result = await client.call_tool(
                "web_search",
                {
                    "project_id": str(project_key.identity.project_id),
                    "query": "q",
                },
            )
            results.append(result.is_error is False)

    # 第 10 次成功（把 10 用满），第 11 次 quota_exceeded。
    assert results == [True, False]
    assert len(captured) == 1
    async with project_key.factory() as session:
        key = (await session.execute(select(ProjectApiKey))).scalar_one()
    assert key.quota_used == 10


async def test_revoked_key_rejected(project_key: _Key, monkeypatch: pytest.MonkeyPatch) -> None:
    async with project_key.factory() as session:
        key = (await session.execute(select(ProjectApiKey))).scalar_one()
        key.revoked_at = datetime.now(UTC)
        await session.commit()

    async with Client(mcp_server, raise_exceptions=False) as client:
        result = await client.call_tool(
            "web_search",
            {"project_id": str(project_key.identity.project_id), "query": "q"},
        )

    assert result.is_error is True
