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
    """项目绑定校验的唯一实现是 resolve_bound_project。

    曾经 server.py 里有一份同义的 _assert_bound_project，src 零调用、
    只有本测试引用；已删，测试改为直接打真实实现。
    """
    from data_intelligence_hub.mcp_runtime.access_control import resolve_bound_project
    from data_intelligence_hub.mcp_runtime.auth import ProjectApiKeyContext

    bound_project = uuid.uuid4()
    identity = ProjectApiKeyContext(
        key_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        project_id=bound_project,
        key_prefix="dih_test",
        label="test",
    )
    assert resolve_bound_project(identity, bound_project) == bound_project
    with pytest.raises(ValueError, match="project_not_found"):
        resolve_bound_project(identity, uuid.uuid4())
    other = uuid.uuid4()
    assert resolve_bound_project(None, other) == other


# ── create_monitor 落库归属：密钥身份写 project_key_id，全局 token 留空 ──────


async def test_create_monitor_stores_creating_key_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """项目密钥身份调 MCP create_monitor 后，monitor.project_key_id == identity.key_id。"""
    from datetime import UTC, datetime

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from data_intelligence_hub.mcp_runtime import access_control
    from data_intelligence_hub.mcp_runtime.auth import ProjectApiKeyContext
    from data_intelligence_hub.models import Base, Project, User
    from data_intelligence_hub.models import Monitor as MonitorModel
    from data_intelligence_hub.models.project_api_key import ProjectApiKey
    from data_intelligence_hub.models.workspace import Workspace
    from data_intelligence_hub.repositories.project_api_keys import create_key

    identity = ProjectApiKeyContext(
        key_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        key_prefix="dih_n1",
        label="n1",
    )

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'monitor_key.sqlite3'}",
        poolclass=NullPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        now = datetime.now(UTC)
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="monitor-key@example.com",
            password_hash="x",
            name="Owner",
            status="active",
            created_at=now,
            updated_at=now,
        )
        workspace = Workspace(
            id=identity.workspace_id,
            name="Key WS",
            slug=f"key-ws-{identity.workspace_id}",
            owner_id=user_id,
            created_at=now,
            updated_at=now,
        )
        project = Project(
            id=identity.project_id,
            workspace_id=identity.workspace_id,
            name="Key Project",
            description=None,
            domain="mixed",
            status="active",
            owner_id=user_id,
            created_at=now,
            updated_at=now,
        )
        session.add_all([user, workspace, project])
        await session.flush()
        record = await create_key(
            session,
            project_id=identity.project_id,
            workspace_id=identity.workspace_id,
            label="n1",
            key_prefix=identity.key_prefix,
            key_hash="b" * 64,
            created_by_user_id=user_id,
            tool_allowlist=["create_monitor", "list_monitors"],
            daily_collect_quota=10,
        )
        await session.commit()
    # identity.key_id 必须等于库里的行 id，find_by_id 才能命中。
    object.__setattr__(identity, "key_id", record.id)

    monkeypatch.setattr(access_control, "project_api_key_context", lambda context: identity)
    # server.py 直接引用了 auth.project_api_key_context；_monitor_workspace 读的是
    # server 命名空间里的名字，必须同时打补丁。
    monkeypatch.setattr(server_module, "project_api_key_context", lambda context: identity)
    monkeypatch.setattr(access_control, "async_session_factory", factory)
    monkeypatch.setattr(server_module, "async_session_factory", factory)

    async with Client(mcp_server, raise_exceptions=False) as client:
        result = await client.call_tool(
            "create_monitor",
            {
                "project_id": str(identity.project_id),
                "name": "keyed",
                "endpoint_type": "exa_search_lite",
                "params": {"query": "q"},
                "interval_hours": 1,
            },
        )

    assert result.is_error is False
    async with factory() as session:
        monitor = (
            await session.execute(select(MonitorModel))
        ).scalars().one()
        key = (await session.execute(select(ProjectApiKey))).scalar_one()
    assert monitor.project_key_id == identity.key_id == key.id
    await engine.dispose()


async def test_create_monitor_global_token_leaves_key_id_null(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """全局 token 身份（无密钥上下文）时 project_key_id 落 NULL。"""
    from datetime import UTC, datetime

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from data_intelligence_hub.models import Base, Project, User
    from data_intelligence_hub.models import Monitor as MonitorModel
    from data_intelligence_hub.models.workspace import Workspace

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'monitor_global.sqlite3'}",
        poolclass=NullPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        now = datetime.now(UTC)
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="global@example.com",
            password_hash="x",
            name="Owner",
            status="active",
            created_at=now,
            updated_at=now,
        )
        workspace = Workspace(
            id=uuid.uuid4(),
            name="Global WS",
            slug="data-achieve-demo",
            owner_id=user_id,
            created_at=now,
            updated_at=now,
        )
        project = Project(
            workspace_id=workspace.id,
            name="Global Project",
            description=None,
            domain="mixed",
            status="active",
            owner_id=user_id,
            created_at=now,
            updated_at=now,
        )
        session.add_all([user, workspace, project])
        await session.commit()

    # 全局 token：不注入密钥身份。_monitor_workspace 走 demo workspace 分支。
    # demo workspace 由 slug 命中，上一步已建。
    async with factory() as session:
        demo = (
            await session.execute(
                select(Workspace).where(Workspace.slug == "data-achieve-demo")
            )
        ).scalar_one()
        project_row = (await session.execute(select(Project))).scalar_one()
    assert demo is not None

    # collect_capability 不被打到（create_monitor 不采集），
    # 但 _monitor_workspace 的 async_session_factory 来自 server 模块命名空间。
    monkeypatch.setattr(server_module, "async_session_factory", factory)

    async with Client(mcp_server, raise_exceptions=False) as client:
        result = await client.call_tool(
            "create_monitor",
            {
                "project_id": str(project_row.id),
                "name": "unkeyed",
                "endpoint_type": "exa_search_lite",
                "params": {"query": "q"},
                "interval_hours": 1,
            },
        )

    assert result.is_error is False
    async with factory() as session:
        monitor = (
            await session.execute(select(MonitorModel))
        ).scalars().one()
    assert monitor.project_key_id is None
    await engine.dispose()
