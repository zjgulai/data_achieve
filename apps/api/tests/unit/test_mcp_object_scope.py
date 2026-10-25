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
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from mcp.client import Client
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.mcp_runtime import access_control, run_service
from data_intelligence_hub.mcp_runtime import server as server_module
from data_intelligence_hub.mcp_runtime.auth import ProjectApiKeyContext
from data_intelligence_hub.mcp_runtime.server import mcp_server
from data_intelligence_hub.mcp_runtime.tool_registry import TOOL_POLICIES
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.enrichment import EnrichmentJob
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.project_api_key import ProjectApiKey
from data_intelligence_hub.models.run import Run
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.workspaces import get_workspace_by_id
from data_intelligence_hub.services import enrichment_service
from data_intelligence_hub.services.quick_collect_service import QuickCollectResponse

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
        session.add(
            Project(
                id=project_a,
                workspace_id=workspace_id,
                name="scope-a",
                domain="ecommerce",
                status="active",
                owner_id=owner_id,
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
    """全局 token：identity 为 None。

    ``_monitor_workspace`` 在全局 token 路径回退 demo workspace；这里把
    demo 解析指到 scope 工作区，测试断言才落在同一租户上。
    """
    monkeypatch.setattr(access_control, "project_api_key_context", lambda context: None)
    monkeypatch.setattr(server_module, "project_api_key_context", lambda context: None)
    monkeypatch.setattr(access_control, "async_session_factory", scope.factory)
    monkeypatch.setattr(server_module, "async_session_factory", scope.factory)
    monkeypatch.setattr(run_service, "async_session_factory", scope.factory)
    monkeypatch.setattr(enrichment_service, "_session_factory", scope.factory)

    async def demo_workspace(session) -> object:
        return await get_workspace_by_id(session, scope.workspace_id)

    monkeypatch.setattr(server_module, "get_demo_workspace", demo_workspace)
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


# ── workspace_answer 的项目级过滤 ────────────────────────────────────────


async def test_workspace_answer_rejects_foreign_project(
    bound_key: _Scope, monkeypatch: pytest.MonkeyPatch
) -> None:
    """密钥身份显式传项目 B（≠ 绑定 A）→ project_not_found，不查库返回。"""
    captured: list[dict[str, object]] = []

    async def fake_answer(session, *, workspace_id, project_id, query, limit=5):
        captured.append({"project_id": project_id})
        return {"answer": "should not run"}

    monkeypatch.setattr(server_module, "run_workspace_answer", fake_answer)

    with pytest.raises(ValueError, match="project_not_found"):
        await server_module.workspace_answer(
            _stub_context(), "q", project_id=str(bound_key.project_b)
        )
    assert captured == []


async def test_workspace_answer_filters_by_bound_project(
    bound_key: _Scope, monkeypatch: pytest.MonkeyPatch
) -> None:
    """不传 project_id → 以绑定项目 A 过滤。"""
    captured: list[dict[str, object]] = []

    async def fake_answer(session, *, workspace_id, project_id, query, limit=5):
        captured.append({"workspace_id": workspace_id, "project_id": project_id})
        return {"answer": "ok"}

    monkeypatch.setattr(server_module, "run_workspace_answer", fake_answer)

    result = await server_module.workspace_answer(_stub_context(), "q")

    assert result == {"answer": "ok"}
    assert captured == [
        {"workspace_id": bound_key.workspace_id, "project_id": bound_key.project_a}
    ]


async def test_workspace_answer_global_token_spans_workspace(
    global_token: _Scope, monkeypatch: pytest.MonkeyPatch
) -> None:
    """全局 token 不传 project_id → 全工作区（project_id 为 None），回归锁定。"""
    captured: list[dict[str, object]] = []

    async def fake_answer(session, *, workspace_id, project_id, query, limit=5):
        captured.append({"workspace_id": workspace_id, "project_id": project_id})
        return {"answer": "ok"}

    monkeypatch.setattr(server_module, "run_workspace_answer", fake_answer)

    await server_module.workspace_answer(_stub_context(), "q")

    assert captured == [{"workspace_id": global_token.workspace_id, "project_id": None}]


async def test_workspace_answer_global_token_may_pick_project(
    global_token: _Scope, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[dict[str, object]] = []

    async def fake_answer(session, *, workspace_id, project_id, query, limit=5):
        captured.append({"project_id": project_id})
        return {"answer": "ok"}

    monkeypatch.setattr(server_module, "run_workspace_answer", fake_answer)

    await server_module.workspace_answer(
        _stub_context(), "q", project_id=str(global_token.project_a)
    )

    assert captured == [{"project_id": global_token.project_a}]


# ── 策略三字段参与运行时判定 ─────────────────────────────────────────────


async def test_requires_project_guard_blocks_global_token_without_project(
    scope: _Scope, monkeypatch: pytest.MonkeyPatch
) -> None:
    """全局 token + bound_project 工具 + 未给 project_id → project_not_found。

    ``web_search`` 的 project_id 是必填参数，正常调用不会走到这里；本用例
    直接调 ``governed_mcp_tool``，把守卫本身当成被测对象（结构性防线）。
    """
    monkeypatch.setattr(access_control, "project_api_key_context", lambda context: None)
    monkeypatch.setattr(access_control, "async_session_factory", scope.factory)

    with pytest.raises(ValueError, match="project_not_found"):
        async with access_control.governed_mcp_tool(_stub_context(), "web_search"):
            pytest.fail("守卫必须在进入工具体之前生效")


async def test_requires_project_guard_allows_global_token_with_project(
    scope: _Scope, monkeypatch: pytest.MonkeyPatch
) -> None:
    """全局 token 给出 project_id 时照旧放行（运维超级权限不回归）。"""
    monkeypatch.setattr(access_control, "project_api_key_context", lambda context: None)
    monkeypatch.setattr(access_control, "async_session_factory", scope.factory)

    async with access_control.governed_mcp_tool(
        _stub_context(), "web_search", project_id=str(scope.project_a)
    ) as decision:
        assert decision.identity_type == "global_operator"


async def test_requires_project_guard_skips_workspace_scope(
    scope: _Scope, monkeypatch: pytest.MonkeyPatch
) -> None:
    """scope=workspace 的工具（workspace_answer）不要求 project_id。"""
    monkeypatch.setattr(access_control, "project_api_key_context", lambda context: None)
    monkeypatch.setattr(access_control, "async_session_factory", scope.factory)

    async with access_control.governed_mcp_tool(
        _stub_context(), "workspace_answer"
    ) as decision:
        assert decision.identity_type == "global_operator"


async def test_requires_project_guard_skips_operator_scope(
    scope: _Scope, monkeypatch: pytest.MonkeyPatch
) -> None:
    """scope=operator 的工具（stop）不要求 project_id。"""
    monkeypatch.setattr(access_control, "project_api_key_context", lambda context: None)
    monkeypatch.setattr(access_control, "async_session_factory", scope.factory)

    async with access_control.governed_mcp_tool(_stub_context(), "stop") as decision:
        assert decision.identity_type == "global_operator"


async def test_control_tool_audit_carries_access_mode(
    scope: _Scope, monkeypatch: pytest.MonkeyPatch
) -> None:
    """stop 的审计事件带 access_mode=control，且不改变行为。"""
    from structlog.testing import capture_logs

    monkeypatch.setattr(access_control, "project_api_key_context", lambda context: None)
    monkeypatch.setattr(access_control, "async_session_factory", scope.factory)

    with capture_logs() as logs:
        async with access_control.governed_mcp_tool(_stub_context(), "stop"):
            pass

    ok_events = [entry for entry in logs if entry["event"] == "mcp_tool_access_ok"]
    assert len(ok_events) == 1
    assert ok_events[0]["access_mode"] == "control"
    assert ok_events[0]["tool"] == "stop"


def test_bound_project_tools_pass_project_id_to_governance() -> None:
    """结构性守卫：requires_project+bound_project 的工具必须在 server.py 传 project_id。

    遍历 TOOL_POLICIES 与 server.py 的 AST，防新工具漏接项目绑定。
    """
    import ast
    import pathlib

    from data_intelligence_hub.mcp_runtime.tool_registry import TOOL_POLICIES

    source = pathlib.Path(server_module.__file__).read_text(encoding="utf-8")
    calls: dict[str, set[str]] = {}
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, "id", None) or getattr(func, "attr", None)
        if name != "governed_mcp_tool":
            continue
        if len(node.args) < 2 or not isinstance(node.args[1], ast.Constant):
            continue
        tool = node.args[1].value
        calls.setdefault(tool, set()).update(
            keyword.arg for keyword in node.keywords if keyword.arg
        )

    expected = {
        name
        for name, policy in TOOL_POLICIES.items()
        if policy.requires_project and policy.project_scope == "bound_project"
    }
    # 清单非空且覆盖 collect / Exa Pack / TikTok / monitor / enrichment。
    assert {"collect", "web_search", "tiktok_video_search", "create_monitor"} <= expected
    for name in sorted(expected):
        assert name in calls, f"{name} 未调用 governed_mcp_tool"
        assert "project_id" in calls[name], f"{name} 未向 governed_mcp_tool 传 project_id"


def test_object_scoped_tools_pass_identity_project_id() -> None:
    """对象归属工具必须按密钥身份传 project_id（F1 的接线清单）。"""
    import inspect

    for name in server_module._BOUND_PROJECT_OBJECT_TOOLS:
        source = inspect.getsource(getattr(server_module, name))
        assert "project_id=_identity_project_id(identity)" in source or (
            "project_id=project_id" in source
        ), name


# ── 端点级白名单（SCRAPY_MCP_COLLECT_ALLOWED_ENDPOINTS）──────────────────


@pytest.fixture()
def endpoint_allowlist(monkeypatch: pytest.MonkeyPatch) -> Callable[[set[str] | None], None]:
    """替换 get_settings，把端点白名单设成给定集合（None = 未配置）。"""

    def apply(allowed: set[str] | None) -> None:
        base = get_settings()
        patched = base.model_copy(update={"mcp_collect_allowed_endpoints": allowed})
        monkeypatch.setattr(access_control, "get_settings", lambda: patched)

    return apply


async def test_collect_rejects_endpoint_outside_allowlist(
    bound_key: _Scope,
    endpoint_allowlist: Callable[[set[str] | None], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """配置白名单后，密钥调 collect 打未授权端点 → tool_not_allowed。"""
    endpoint_allowlist({"exa_search_lite"})
    captured: list[object] = []

    async def fake_collect(*args, **kwargs):
        captured.append(args)
        raise AssertionError("should not execute")

    monkeypatch.setattr(server_module, "collect_capability", fake_collect)

    with pytest.raises(ValueError, match="tool_not_allowed"):
        await server_module.collect(
            _stub_context(),
            "exa_deep_research",
            str(bound_key.project_a),
            {"query": "q"},
        )
    assert captured == []


async def test_collect_allows_endpoint_inside_allowlist(
    bound_key: _Scope,
    endpoint_allowlist: Callable[[set[str] | None], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    endpoint_allowlist({"exa_search_lite"})
    captured: list[dict[str, object]] = []

    async def fake_collect(endpoint_type, project_id, params, **kwargs):
        captured.append({"endpoint_type": endpoint_type})
        raise AssertionError("stop here: gate passed, capability layer mocked out")

    monkeypatch.setattr(server_module, "collect_capability", fake_collect)

    with pytest.raises(AssertionError, match="stop here"):
        await server_module.collect(
            _stub_context(),
            "exa_search_lite",
            str(bound_key.project_a),
            {"query": "q"},
        )
    assert captured == [{"endpoint_type": "exa_search_lite"}]


async def test_default_allowlist_is_no_restriction(
    bound_key: _Scope,
    endpoint_allowlist: Callable[[set[str] | None], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """未配置 → 允许全部端点，行为与改造前一致。"""
    endpoint_allowlist(None)
    captured: list[dict[str, object]] = []

    async def fake_collect(endpoint_type, project_id, params, **kwargs):
        captured.append({"endpoint_type": endpoint_type})
        raise AssertionError("stop here: gate passed")

    monkeypatch.setattr(server_module, "collect_capability", fake_collect)

    with pytest.raises(AssertionError, match="stop here"):
        await server_module.collect(
            _stub_context(),
            "exa_deep_research",
            str(bound_key.project_a),
            {"query": "q"},
        )
    assert captured == [{"endpoint_type": "exa_deep_research"}]


async def test_global_token_ignores_endpoint_allowlist(
    global_token: _Scope,
    endpoint_allowlist: Callable[[set[str] | None], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    endpoint_allowlist({"exa_search_lite"})
    captured: list[dict[str, object]] = []

    async def fake_collect(endpoint_type, project_id, params, **kwargs):
        captured.append({"endpoint_type": endpoint_type})
        raise AssertionError("stop here: gate skipped for global token")

    monkeypatch.setattr(server_module, "collect_capability", fake_collect)

    with pytest.raises(AssertionError, match="stop here"):
        await server_module.collect(
            _stub_context(),
            "exa_deep_research",
            str(global_token.project_a),
            {"query": "q"},
        )
    assert captured == [{"endpoint_type": "exa_deep_research"}]


async def test_tiktok_tool_rejects_endpoint_outside_allowlist(
    bound_key: _Scope,
    endpoint_allowlist: Callable[[set[str] | None], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TikTok 工具按 TOOL_ENDPOINTS 判：必需端点不在白名单即拒绝。"""
    endpoint_allowlist({"tikhub_tiktok_search_web"})
    calls: list[object] = []

    async def fake_tiktok(*args, **kwargs):
        calls.append(args)
        raise AssertionError("should not execute")

    monkeypatch.setattr(server_module, "run_tiktok_tool", fake_tiktok)

    # tiktok_trend_rank 需要 tikhub_tiktok_ads_trends，不在白名单里。
    with pytest.raises(ValueError, match="tool_not_allowed"):
        await server_module.tiktok_trend_rank(_stub_context(), str(bound_key.project_a))
    assert calls == []


async def test_tiktok_allowlist_covers_every_declared_endpoint() -> None:
    """TOOL_ENDPOINTS 必须覆盖全部 16 个 TikTok 工具，且端点真实存在。"""
    from data_intelligence_hub.platform_packages.service import get_capability
    from data_intelligence_hub.services.tiktok_tools import TOOL_ENDPOINTS, TOOL_HANDLERS

    assert set(TOOL_ENDPOINTS) == set(TOOL_HANDLERS)
    for endpoints in TOOL_ENDPOINTS.values():
        assert endpoints
    for endpoints in TOOL_ENDPOINTS.values():
        for endpoint in endpoints:
            await get_capability(endpoint)


def test_every_provider_calling_tool_is_endpoint_gated() -> None:
    """结构性守卫：所有会打 provider 的 MCP 工具都必须在 server.py 里判端点。

    判据用注册表的 ``consumes_quota != "none"``：扣额度等价于会产生外部调用。
    唯一例外是 ``workspace_answer``——它登记为 per_call，但实现只查本地
    raw_records，不调 provider，端点白名单对它没有意义。

    防新执行工具接线时漏掉端点级白名单（本次 F4 的缺口正是这样来的）。
    """
    import ast
    import pathlib

    from data_intelligence_hub.mcp_runtime.tool_registry import TOOL_POLICIES

    local_only = {"workspace_answer"}
    source = pathlib.Path(server_module.__file__).read_text(encoding="utf-8")
    gated: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        tool = None
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            name = getattr(call.func, "id", None) or getattr(call.func, "attr", None)
            if (
                name == "governed_mcp_tool"
                and len(call.args) >= 2
                and isinstance(call.args[1], ast.Constant)
            ):
                tool = call.args[1].value
        if tool is None:
            continue
        text = ast.get_source_segment(source, node) or ""
        if "assert_endpoint_allowed(" in text or "assert_endpoints_allowed(" in text:
            gated.add(tool)

    expected = {
        name
        for name, policy in TOOL_POLICIES.items()
        if policy.consumes_quota != "none"
    } - local_only
    assert {"collect", "web_search", "web_fetch", "answer", "deep_research"} <= expected
    assert {"create_monitor", "enrich_list", "deep_research_start"} <= expected
    assert expected == gated, sorted(expected ^ gated)


# ── 生产环境的匿名 fail-closed ───────────────────────────────────────────


def _settings_patch(monkeypatch: pytest.MonkeyPatch, **overrides: object) -> None:
    """把 get_settings 换成带覆盖值的实例（access_control 独占）。"""
    base = get_settings()
    patched = base.model_copy(update=overrides)
    monkeypatch.setattr(access_control, "get_settings", lambda: patched)


def _stub_context_with_headers(headers: dict[str, str]):
    from types import SimpleNamespace

    return SimpleNamespace(
        headers=headers,
        request_context=SimpleNamespace(
            request=SimpleNamespace(scope={"state": {}}),
        ),
    )


async def test_production_anonymous_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """production + 无凭据 → project_key_not_found（工具入口 fail-closed）。"""
    from pydantic import SecretStr

    _settings_patch(
        monkeypatch,
        app_env="production",
        mcp_token=SecretStr("global-token"),
        mcp_tokens={},
    )
    monkeypatch.setattr(access_control, "project_api_key_context", lambda context: None)

    with pytest.raises(ValueError, match="project_key_not_found"):
        async with access_control.governed_mcp_tool(_stub_context(), "list_platforms"):
            pytest.fail("匿名请求必须在进入工具体之前被拒")


async def test_production_global_token_is_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """production + 全局 token → 放行，身份仍是 global_operator。"""
    from pydantic import SecretStr

    _settings_patch(
        monkeypatch,
        app_env="production",
        mcp_token=SecretStr("global-token"),
        mcp_tokens={},
    )
    monkeypatch.setattr(access_control, "project_api_key_context", lambda context: None)

    async with access_control.governed_mcp_tool(
        _stub_context_with_headers({"authorization": "Bearer global-token"}),
        "list_platforms",
    ) as decision:
        assert decision.identity_type == "global_operator"


async def test_production_wrong_global_token_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """production + 错误的 Bearer → 仍按匿名拒绝，不按全局超级权限执行。"""
    from pydantic import SecretStr

    _settings_patch(
        monkeypatch,
        app_env="production",
        mcp_token=SecretStr("global-token"),
        mcp_tokens={},
    )
    monkeypatch.setattr(access_control, "project_api_key_context", lambda context: None)

    with pytest.raises(ValueError, match="project_key_not_found"):
        async with access_control.governed_mcp_tool(
            _stub_context_with_headers({"authorization": "Bearer wrong"}),
            "list_platforms",
        ):
            pytest.fail("错误的 Bearer 不得进入工具体")


async def test_production_project_key_is_allowed(
    scope: _Scope, monkeypatch: pytest.MonkeyPatch
) -> None:
    """production + 项目密钥 → 放行（这条刀只砍匿名）。"""
    identity = scope.identity
    _settings_patch(monkeypatch, app_env="production", mcp_token=None, mcp_tokens={})
    monkeypatch.setattr(access_control, "project_api_key_context", lambda context: identity)
    monkeypatch.setattr(access_control, "async_session_factory", scope.factory)

    async with access_control.governed_mcp_tool(_stub_context(), "list_platforms") as decision:
        assert decision.identity_type == "project_key"


async def test_development_anonymous_keeps_current_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """dev + 无凭据 → 现行为（放行），本地联调不被这刀砍挂。"""
    _settings_patch(monkeypatch, app_env="development", mcp_token=None, mcp_tokens={})
    monkeypatch.setattr(access_control, "project_api_key_context", lambda context: None)

    async with access_control.governed_mcp_tool(_stub_context(), "list_platforms") as decision:
        assert decision.identity_type == "global_operator"


# ── 进程内 daily_collects 只治理全局 token ───────────────────────────────


@pytest.fixture()
def governance_limit_2(monkeypatch: pytest.MonkeyPatch) -> None:
    """把进程内日采集上限压到 2，并清掉 lru_cache 的全局实例。"""
    from data_intelligence_hub.mcp_runtime import runtime as runtime_module

    base = get_settings()
    patched = base.model_copy(update={"mcp_daily_collects": 2})
    monkeypatch.setattr(runtime_module, "get_settings", lambda: patched)
    runtime_module.get_mcp_governance.cache_clear()
    yield
    runtime_module.get_mcp_governance.cache_clear()


async def test_project_key_not_limited_by_process_collect_budget(
    bound_key: _Scope,
    governance_limit_2: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """密钥身份高频 collect 不受进程内 500/日 限制（真实边界是 DB 额度）。"""
    calls: list[str] = []

    async def fake_collect(endpoint_type, project_id, params, **kwargs):
        calls.append(endpoint_type)
        return QuickCollectResponse(
            task_run_id=uuid.uuid4(),
            task_id=uuid.uuid4(),
            source_id=uuid.uuid4(),
            status="success",
            records_count=1,
            error_message=None,
        )

    monkeypatch.setattr(server_module, "collect_capability", fake_collect)

    # 5 次远超进程内上限 2；每次都被放行。
    for _ in range(5):
        await server_module.collect(
            _stub_context(),
            "exa_search_lite",
            str(bound_key.project_a),
            {"query": "q"},
        )
    assert calls == ["exa_search_lite"] * 5


async def test_global_token_still_limited_by_process_collect_budget(
    global_token: _Scope,
    governance_limit_2: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """全局 token 仍受进程内日采集上限拦（运维路径的治理不回归）。"""
    calls: list[str] = []

    async def fake_collect(endpoint_type, project_id, params, **kwargs):
        calls.append(endpoint_type)
        return QuickCollectResponse(
            task_run_id=uuid.uuid4(),
            task_id=uuid.uuid4(),
            source_id=uuid.uuid4(),
            status="success",
            records_count=1,
            error_message=None,
        )

    monkeypatch.setattr(server_module, "collect_capability", fake_collect)

    for _ in range(2):
        await server_module.collect(
            _stub_context(),
            "exa_search_lite",
            str(global_token.project_a),
            {"query": "q"},
        )
    with pytest.raises(ValueError, match="mcp_daily_collect_budget_exceeded"):
        await server_module.collect(
            _stub_context(),
            "exa_search_lite",
            str(global_token.project_a),
            {"query": "q"},
        )
    assert len(calls) == 2


def _stub_context():
    """最小 MCP Context 替身：只提供 request_context.request.scope。"""
    from types import SimpleNamespace

    return SimpleNamespace(
        headers={},
        request_context=SimpleNamespace(
            request=SimpleNamespace(scope={"state": {}}),
        ),
    )
