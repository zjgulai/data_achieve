"""MCP 对象归属的项目维度与策略接线。

覆盖三件事：

1. 同一工作区、不同项目的 run / records / stop / deep_research_check /
   enrichment_check 全部返回稳定 not-found（spec §3.2、§7）。
2. 全局 token（identity 为 None）跨项目仍可读取（运维超级权限不回归）。
3. ``governed_mcp_tool`` 的 ``object_project_id`` 不是死参数：显式传参且
   归属不符时必须拒绝。

所有用例走真实 SQLite 表结构与真实服务函数，只替换 session factory 与
身份来源，不 mock 业务逻辑。
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from mcp.client import Client
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from data_intelligence_hub.mcp_runtime import access_control, run_service
from data_intelligence_hub.mcp_runtime import server as server_module
from data_intelligence_hub.mcp_runtime.auth import ProjectApiKeyContext
from data_intelligence_hub.mcp_runtime.server import mcp_server
from data_intelligence_hub.mcp_runtime.tool_registry import TOOL_POLICIES
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.enrichment import EnrichmentJob
from data_intelligence_hub.models.project_api_key import ProjectApiKey
from data_intelligence_hub.models.run import Run
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.services import enrichment_service

pytestmark = pytest.mark.anyio


@dataclass(slots=True)
class _Scope:
    """一套库与两个项目：A 是密钥绑定项目，B 是同工作区的外来项目。"""

    factory: async_sessionmaker[AsyncSession]
    workspace_id: uuid.UUID
    project_a: uuid.UUID
    project_b: uuid.UUID
    run_id: uuid.UUID
    job_id: uuid.UUID
    identity: ProjectApiKeyContext


@pytest_asyncio.fixture()
async def scope(tmp_path) -> AsyncIterator[_Scope]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'object_scope.sqlite3'}",
        poolclass=NullPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    owner_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_a = uuid.uuid4()
    project_b = uuid.uuid4()
    now = datetime.now(UTC)
    run_id = uuid.uuid4()
    job_id = uuid.uuid4()
    key_id = uuid.uuid4()

    async with factory() as session:
        session.add(
            User(
                id=owner_id,
                email="scope@example.com",
                password_hash="x",
                name="Scope",
                status="active",
            )
        )
        session.add(
            Workspace(
                id=workspace_id,
                name="scope-ws",
                slug="scope-ws",
                owner_id=owner_id,
            )
        )
        session.add(
            ProjectApiKey(
                id=key_id,
                project_id=project_a,
                workspace_id=workspace_id,
                label="scope",
                key_prefix="dih_scope",
                key_hash="b" * 64,
                created_by_user_id=owner_id,
                tool_allowlist=list(TOOL_POLICIES),
                daily_collect_quota=10,
            )
        )
        # run 与 enrichment job 都属于项目 A，工作区与密钥相同。
        session.add(
            Run(
                id=run_id,
                workspace_id=workspace_id,
                project_id=project_a,
                status="completed",
                outcome="success",
                execution_mode="live",
                trigger="api",
                records_count=0,
                started_at=now,
                finished_at=now,
                created_at=now,
            )
        )
        session.add(
            EnrichmentJob(
                id=job_id,
                workspace_id=workspace_id,
                project_id=project_a,
                name="scope-job",
                query_template="{q}",
                output_schema={},
                status="completed",
                total=0,
                processed=0,
                failed=0,
            )
        )
        await session.commit()

    identity = ProjectApiKeyContext(
        key_id=key_id,
        workspace_id=workspace_id,
        project_id=project_a,
        key_prefix="dih_scope",
        label="scope",
    )
    yield _Scope(
        factory=factory,
        workspace_id=workspace_id,
        project_a=project_a,
        project_b=project_b,
        run_id=run_id,
        job_id=job_id,
        identity=identity,
    )
    await engine.dispose()


@pytest.fixture()
def bound_key(scope: _Scope, monkeypatch: pytest.MonkeyPatch) -> _Scope:
    """把密钥身份同时打进 access_control 与 server 的解析入口。"""
    identity = scope.identity
    monkeypatch.setattr(access_control, "project_api_key_context", lambda context: identity)
    monkeypatch.setattr(server_module, "project_api_key_context", lambda context: identity)
    monkeypatch.setattr(access_control, "async_session_factory", scope.factory)
    monkeypatch.setattr(server_module, "async_session_factory", scope.factory)
    monkeypatch.setattr(run_service, "async_session_factory", scope.factory)
    monkeypatch.setattr(enrichment_service, "_session_factory", scope.factory)
    return scope


@pytest.fixture()
def global_token(scope: _Scope, monkeypatch: pytest.MonkeyPatch) -> _Scope:
    """全局 token：identity 为 None。"""
    monkeypatch.setattr(access_control, "project_api_key_context", lambda context: None)
    monkeypatch.setattr(server_module, "project_api_key_context", lambda context: None)
    monkeypatch.setattr(access_control, "async_session_factory", scope.factory)
    monkeypatch.setattr(server_module, "async_session_factory", scope.factory)
    monkeypatch.setattr(run_service, "async_session_factory", scope.factory)
    monkeypatch.setattr(enrichment_service, "_session_factory", scope.factory)
    return scope


# ── 负例：同 workspace 不同 project，一律稳定 not-found ──────────────────


async def test_bound_key_reads_own_project_run(bound_key: _Scope) -> None:
    """基线：绑定项目内的 run 可读，证明后面失败的是项目维度而不是接线。"""
    async with Client(mcp_server, raise_exceptions=False) as client:
        detail = await client.call_tool("get_run", {"run_id": str(bound_key.run_id)})
        records = await client.call_tool("list_records", {"run_id": str(bound_key.run_id)})

    assert detail.is_error is False
    assert detail.structured_content is not None
    assert detail.structured_content["run_id"] == str(bound_key.run_id)
    assert records.is_error is False


async def test_bound_key_rejects_foreign_project_run(bound_key: _Scope) -> None:
    """同工作区、不同项目：四个 run 级工具都必须 run_not_found。

    直接调用工具函数取稳定错误码；MCP 传输层会把业务异常统一包成
    ``Error executing tool``，看不到具体码。工具函数本身仍是普通函数。
    """
    # 把 run 搬到项目 B，工作区仍与密钥一致。
    async with bound_key.factory() as session:
        run = await session.get(Run, bound_key.run_id)
        assert run is not None
        run.project_id = bound_key.project_b
        await session.commit()

    context = _stub_context()
    run_id = str(bound_key.run_id)
    with pytest.raises(ValueError, match="run_not_found"):
        await server_module.get_run(context, run_id)
    with pytest.raises(ValueError, match="run_not_found"):
        await server_module.list_records(context, run_id)
    with pytest.raises(ValueError, match="run_not_found"):
        await server_module.stop(context, run_id)
    with pytest.raises(ValueError, match="run_not_found"):
        await server_module.deep_research_check(context, run_id)


async def test_bound_key_rejects_foreign_project_enrichment_job(bound_key: _Scope) -> None:
    async with bound_key.factory() as session:
        job = await session.get(EnrichmentJob, bound_key.job_id)
        assert job is not None
        job.project_id = bound_key.project_b
        await session.commit()

    with pytest.raises(ValueError, match="enrichment_job_not_found"):
        await server_module.enrichment_check(_stub_context(), str(bound_key.job_id))


async def test_bound_key_reads_own_project_enrichment_job(bound_key: _Scope) -> None:
    async with Client(mcp_server, raise_exceptions=False) as client:
        result = await client.call_tool(
            "enrichment_check", {"job_id": str(bound_key.job_id)}
        )

    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["job_id"] == str(bound_key.job_id)


# ── 正例：全局 token 跨项目仍可读 ────────────────────────────────────────


async def test_global_token_reads_run_in_any_project(global_token: _Scope) -> None:
    async with Client(mcp_server, raise_exceptions=False) as client:
        detail = await client.call_tool("get_run", {"run_id": str(global_token.run_id)})
        records = await client.call_tool(
            "list_records", {"run_id": str(global_token.run_id)}
        )

    assert detail.is_error is False
    assert records.is_error is False


async def test_global_token_stops_run_in_any_project(global_token: _Scope) -> None:
    async with global_token.factory() as session:
        run = await session.get(Run, global_token.run_id)
        assert run is not None
        run.status = "running"
        await session.commit()

    async with Client(mcp_server, raise_exceptions=False) as client:
        result = await client.call_tool("stop", {"run_id": str(global_token.run_id)})

    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["cancelled"] is True


# ── 服务层：run_service 的项目维度可单独使用 ─────────────────────────────


def test_run_service_project_scope(scope: _Scope, monkeypatch: pytest.MonkeyPatch) -> None:
    """直接验证服务层的项目过滤，不经 MCP 传输层。"""
    monkeypatch.setattr(run_service, "async_session_factory", scope.factory)

    # 工作区匹配、项目不匹配 → not-found。
    with pytest.raises(ValueError, match="run_not_found"):
        asyncio.run(
            run_service.get_run_detail(
                scope.run_id,
                workspace_id=scope.workspace_id,
                project_id=scope.project_b,
            )
        )
    with pytest.raises(ValueError, match="run_not_found"):
        asyncio.run(
            run_service.list_run_records(
                scope.run_id,
                workspace_id=scope.workspace_id,
                project_id=scope.project_b,
            )
        )
    with pytest.raises(ValueError, match="run_not_found"):
        asyncio.run(
            run_service.stop_run(
                scope.run_id,
                workspace_id=scope.workspace_id,
                project_id=scope.project_b,
            )
        )

    # 两个维度都匹配 → 放行。
    detail = asyncio.run(
        run_service.get_run_detail(
            scope.run_id,
            workspace_id=scope.workspace_id,
            project_id=scope.project_a,
        )
    )
    assert detail["run_id"] == str(scope.run_id)


# ── object_project_id 不是死参数 ─────────────────────────────────────────


async def test_object_project_id_rejects_mismatch(bound_key: _Scope) -> None:
    """显式传 object_project_id 且与绑定项目不符 → object_not_found。

    当前工具面还没有调用方传它；这个用例保证结构防线不被删成死代码。
    """
    entered = False
    with pytest.raises(ValueError, match="object_not_found"):
        async with access_control.governed_mcp_tool(
            _stub_context(),
            "get_run",
            object_project_id=bound_key.project_b,
        ):
            entered = True
    assert entered is False


async def test_object_project_id_accepts_match(bound_key: _Scope) -> None:
    async with access_control.governed_mcp_tool(
        _stub_context(),
        "get_run",
        object_project_id=bound_key.project_a,
    ) as decision:
        assert decision.identity_type == "project_key"


def _stub_context():
    """最小 MCP Context 替身：只提供 request_context.request.scope。"""
    from types import SimpleNamespace

    return SimpleNamespace(
        headers={},
        request_context=SimpleNamespace(
            request=SimpleNamespace(scope={"state": {}}),
        ),
    )
