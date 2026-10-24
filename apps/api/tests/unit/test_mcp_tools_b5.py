"""B5：MCP 工具面。

覆盖六件事：

1. 工具数量快照。新增或删除工具必须更新快照。
2. 五个新工具各有用例。
3. 三个改造工具返回结构化契约。
4. 白名单外的工具返回 ``tool_not_allowed``。
5. 项目额度超额返回明确错误码。
6. 跨项目读运行与记录按未找到处理。无项目身份时行为不变。

本文件只用内存 SQLite。它不连接真实 Postgres。
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from mcp.client import Client
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import data_intelligence_hub.mcp_runtime.server as server_module
from data_intelligence_hub.mcp_runtime import capability_service, run_service, runtime
from data_intelligence_hub.mcp_runtime.auth import ProjectApiKeyContext
from data_intelligence_hub.mcp_runtime.server import mcp_server
from data_intelligence_hub.mcp_runtime.tools import discovery as discovery_tools
from data_intelligence_hub.mcp_runtime.tools import reports as report_tools
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.models.report_artifact import ReportArtifact
from data_intelligence_hub.models.run import Run, RunStep
from data_intelligence_hub.models.task import TaskRun
from data_intelligence_hub.tool_catalog.public import PublicTool, to_public_tool

TEMPLATE_ID = "t1_voc"

EXPECTED_TOOLS = (
    "answer",
    "balance",
    "collect",
    "create_monitor",
    "create_report",
    "deep_research",
    "deep_research_check",
    "deep_research_start",
    "describe_capability",
    "discover",
    "enrich_list",
    "enrichment_check",
    "get_playbook",
    "get_run",
    "inspect",
    "list_capabilities",
    "list_monitors",
    "list_platforms",
    "list_records",
    "stop",
    "tiktok_ads_detail",
    "tiktok_ads_top",
    "tiktok_creator_commerce",
    "tiktok_creator_profile",
    "tiktok_creator_search",
    "tiktok_creator_showcase",
    "tiktok_hashtag_videos",
    "tiktok_product_detail",
    "tiktok_product_reviews",
    "tiktok_product_search",
    "tiktok_transcript",
    "tiktok_trend_rank",
    "tiktok_video_comments",
    "tiktok_video_detail",
    "tiktok_video_products",
    "tiktok_video_search",
    "web_fetch",
    "web_search",
    "workspace_answer",
)


def _make_factory() -> tuple[async_sessionmaker[AsyncSession], object]:
    """建一个内存 SQLite 会话工厂。返回工厂与引擎。"""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    return async_sessionmaker(engine, expire_on_commit=False), engine


async def _create_schema(engine: object) -> None:
    async with engine.begin() as connection:  # type: ignore[attr-defined]
        await connection.run_sync(Base.metadata.create_all)


def _identity(
    *,
    project_id: uuid.UUID | None = None,
    workspace_id: uuid.UUID | None = None,
    allowlist: tuple[str, ...] = (
        "collect",
        "create_report",
        "describe_capability",
        "discover",
        "get_playbook",
        "get_run",
        "inspect",
        "list_capabilities",
        "list_platforms",
        "list_records",
    ),
    quota: int = 100,
) -> ProjectApiKeyContext:
    """构造一个项目密钥身份。它不含明文。"""
    return ProjectApiKeyContext(
        key_id=uuid.uuid4(),
        workspace_id=workspace_id or uuid.uuid4(),
        project_id=project_id or uuid.uuid4(),
        key_prefix="dih_test",
        label="test",
        tool_allowlist=allowlist,
        daily_collect_quota=quota,
    )


async def _seed_run(
    factory: async_sessionmaker[AsyncSession],
    *,
    run_id: uuid.UUID,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    records: int = 2,
    execution_mode: str = "live",
) -> uuid.UUID:
    """写入一次运行、一个步骤、一组记录。返回 task_run_id。"""
    now = datetime.now(UTC)
    task_run_id = uuid.uuid4()
    async with factory() as session:
        session.add(
            Run(
                id=run_id,
                workspace_id=workspace_id,
                project_id=project_id,
                status="completed",
                outcome="success",
                execution_mode=execution_mode,
                trigger="api",
                records_count=records,
                started_at=now,
                finished_at=now,
            )
        )
        session.add(
            TaskRun(
                id=task_run_id,
                task_id=uuid.uuid4(),
                workspace_id=workspace_id,
                status="success",
                records_count=records,
                logs=[],
                created_at=now,
                run_id=run_id,
            )
        )
        session.add(
            RunStep(
                run_id=run_id,
                step_index=0,
                endpoint_type="tikhub_tiktok_video_search",
                collector_type="tikhub_social",
                task_run_id=task_run_id,
                status="success",
                outcome="success",
                records_count=records,
            )
        )
        for index in range(records):
            session.add(
                RawRecord(
                    id=uuid.uuid4(),
                    workspace_id=workspace_id,
                    project_id=project_id,
                    source_id=uuid.uuid4(),
                    task_run_id=task_run_id,
                    record_type="tiktok_video",
                    content={"index": index},
                    content_hash=f"hash-{uuid.uuid4().hex}",
                    collected_at=now,
                    created_at=now,
                )
            )
        await session.commit()
    return task_run_id


async def _seed_running(
    factory: async_sessionmaker[AsyncSession],
    *,
    run_id: uuid.UUID,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    """写入一次可取消的 running 运行（无步骤与记录）。"""
    async with factory() as session:
        session.add(
            Run(
                id=run_id,
                workspace_id=workspace_id,
                project_id=project_id,
                status="running",
                execution_mode="live",
                trigger="api",
                records_count=0,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()


def _contract_payload(
    *,
    run_id: uuid.UUID,
    task_id: uuid.UUID,
    evidence_id: uuid.UUID,
) -> dict[str, object]:
    """一份最小但完整的报告合同。"""
    return {
        "schema_version": "1.0.0",
        "template_id": TEMPLATE_ID,
        "generated_at": "2026-10-21T08:00:00+00:00",
        "identity": {
            "task_id": str(task_id),
            "brand": "Example",
            "category": "baby_bottle",
            "markets": ["US"],
            "window": {
                "start": "2026-01-01",
                "end": "2026-03-01",
                "days": 60,
            },
        },
        "decision": {
            "decision_question": "是否进入该市场？",
            "answer": "先验证需求。",
            "protect": [],
            "resolve": [],
            "prove": [],
        },
        "gates": [],
        "coverage": {"cells": []},
        "metrics": [],
        "claims": [],
        "evidences": [
            {
                "evidence_id": str(evidence_id),
                "claim_id": "c-1",
                "role": "support",
                "source_tool_id": "tikhub_tiktok_video_search",
                "captured_at": "2026-02-01T00:00:00+00:00",
                "market": "US",
                "locale": "en-US",
                "evidence_grade": "L3_live_single",
            }
        ],
        "run_ledger": [
            {
                "run_id": str(run_id),
                "tool_id": "tikhub_tiktok_video_search",
                "endpoint_type": "tikhub_tiktok_video_search",
                "unit": "request",
                "quantity": 1,
                "unit_price": "0.010000",
                "total_cost_usd": "0.010000",
                "evidence_grade": "L3_live_single",
                "started_at": "2026-02-01T00:00:00+00:00",
                "finished_at": "2026-02-01T00:00:05+00:00",
                "outcome": "success",
            }
        ],
        "limits": ["不能推断长期复购。"],
        "unknowns": ["缺少线下渠道数据。"],
        "artifact": {
            "report_html_sha256": "a" * 64,
            "sop_html_sha256": "b" * 64,
            "contract_sha256": "c" * 64,
        },
    }


def _error_text(result: object) -> str:
    """把工具错误结果拼成文本，便于断言错误码。"""
    content = getattr(result, "content", ())
    return " ".join(str(item) for item in content)


async def _seed_balance(
    factory: async_sessionmaker[AsyncSession],
) -> uuid.UUID:
    """写入一次运行、一条授权、一条账本行。返回 project_id。

    形状与 test_mcp_run_service.py 的 ``_seed_balance`` 一致：
    accrued 1.25，授权上限 10。
    """
    from decimal import Decimal

    from data_intelligence_hub.models.authorization import Authorization
    from data_intelligence_hub.models.run_ledger import RunLedgerEntry

    now = datetime.now(UTC)
    project_id = uuid.uuid4()
    run_id = uuid.uuid4()
    async with factory() as session:
        session.add(
            Run(
                id=run_id,
                workspace_id=uuid.uuid4(),
                project_id=project_id,
                status="completed",
                execution_mode="live",
                trigger="api",
                records_count=1,
                created_at=now,
            )
        )
        session.add(
            Authorization(
                workspace_id=uuid.uuid4(),
                project_id=project_id,
                gate_id="G-Plan",
                gate_status="pass",
                scope={},
                max_cost_usd=Decimal("10"),
                approver=uuid.uuid4(),
                granted_at=now,
                expires_at=now.replace(year=now.year + 1),
            )
        )
        session.add(
            RunLedgerEntry(
                run_id=run_id,
                entry_kind="accrued",
                amount_usd=Decimal("1.25"),
                balance_after_usd=Decimal("8.75"),
                idempotency_key=f"b5-balance-{run_id.hex}",
                created_at=now,
            )
        )
        await session.commit()
    return project_id


@pytest.mark.anyio
async def test_tool_count_snapshot() -> None:
    """工具清单是快照。新增或删除工具必须更新本断言。

    PRD 5.7 的「18 个」写于 TikTok R1 之前。
    R1 增加了 8 个 TikTok 工具，B3 增加了 get_run 与 list_records。
    B5 新增 discover、inspect、create_report。main 合入 13 个 Exa 与
    监控、研究、富集工具。实际总数是 39。
    """
    tools = await mcp_server.list_tools()
    names = tuple(sorted(tool.name for tool in tools))
    assert names == EXPECTED_TOOLS
    assert len(names) == 39


@pytest.mark.anyio
async def test_discover_returns_reasoned_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """discover 必须返回带理由的候选。理由来自实际命中字段。"""
    monkeypatch.setattr(runtime, "project_api_key_context", lambda context: None)
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "discover",
            {"query": "tiktok video search", "limit": 5},
        )

    assert result.structured_content is not None
    candidates = result.structured_content["candidates"]
    assert candidates
    assert len(candidates) <= 5
    scores = [item["score"] for item in candidates]
    assert scores == sorted(scores, reverse=True)
    for item in candidates:
        assert set(item) == {"tool_id", "label", "reason", "score"}
        assert item["score"] > 0
        assert "命中" in item["reason"]
        assert any(field in item["reason"] for field in ("label", "platform", "description"))


@pytest.mark.anyio
async def test_discover_rejects_empty_query(monkeypatch: pytest.MonkeyPatch) -> None:
    """空查询按参数错误返回，不返回全目录。"""
    monkeypatch.setattr(runtime, "project_api_key_context", lambda context: None)
    with pytest.raises(ValueError, match="query_required"):
        await discovery_tools.discover("   ")


@pytest.mark.anyio
async def test_inspect_returns_full_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """inspect 必须返回输入 schema、输出字段、成本与风险。"""
    monkeypatch.setattr(runtime, "project_api_key_context", lambda context: None)
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "inspect",
            {"tool_id": "tikhub_tiktok_video_search"},
        )

    assert result.structured_content is not None
    body = result.structured_content
    assert body["tool_id"] == "tikhub_tiktok_video_search"
    assert body["input_schema"]["type"] == "object"
    assert "properties" in body["input_schema"]
    assert body["output_schema"]["fields"]
    assert "cost" in body
    assert body["risk_class"]


@pytest.mark.anyio
async def test_inspect_rejects_unknown_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    """未知工具标识返回 tool_not_found。"""
    monkeypatch.setattr(runtime, "project_api_key_context", lambda context: None)
    with pytest.raises(ValueError, match="tool_not_found"):
        await discovery_tools.inspect_tool("missing_tool")


# 治理字段与其原文。inspect 对外只发布 public projection，这些一律不得出现。
_INSPECT_FORBIDDEN_WORDS: tuple[str, ...] = (
    "authorization",
    "reachability",
    "block_reason",
    "policy_block_reason",
    "collection_policy_denied",
    "demo_workspace",
    "执行入口当前不校验身份",
)


def _serialized_contains(value: object, needle: str) -> bool:
    """把值序列化成文本后搜子串。None 与标量也能安全过。"""
    text = json.dumps(value, ensure_ascii=False, default=repr)
    return needle in text


@pytest.mark.anyio
async def test_inspect_uses_public_projection_without_governance_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """inspect 必须走 public projection，不泄漏 authorization 与 reachability。

    PublicTool 刻意剥掉治理字段：``authorization`` 记录执行入口的鉴权缺口，
    ``reachability.block_reason`` 带策略拒绝原文。把两者发到 MCP 面
    等于对外公告自身弱点。本断言递归扫描整个返回值。
    """
    monkeypatch.setattr(runtime, "project_api_key_context", lambda context: None)
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "inspect",
            {"tool_id": "tikhub_tiktok_video_search"},
        )

    assert result.structured_content is not None
    body = result.structured_content
    for word in _INSPECT_FORBIDDEN_WORDS:
        assert not _serialized_contains(body, word), f"泄漏治理词: {word}"

    expected = set(PublicTool.model_fields) | {"input_schema", "output_schema", "method"}
    assert set(body) == expected
    assert "availability" in body
    assert "availability_view" not in body

    # 投影后的可用性视图不再含 block_reason，执行可达性由布尔回答。
    availability = body["availability"]
    assert "block_reason" not in availability
    assert body["execution_kind"]
    assert isinstance(body["executable_now"], bool)
    assert isinstance(body["permanently_blocked"], bool)


@pytest.mark.anyio
async def test_inspect_public_projection_clean_across_full_catalog() -> None:
    """全部工具经 public projection 投影后均不得含治理词。

    逐工具把 ``to_public_tool`` 结果序列化后搜子串。一个泄漏都不允许。
    """
    catalog = await discovery_tools.load_catalog()
    assert catalog.tools, "目录为空，扫描无意义"
    for tool in catalog.tools:
        payload = to_public_tool(tool).model_dump(mode="json")
        for word in _INSPECT_FORBIDDEN_WORDS:
            assert not _serialized_contains(payload, word), (
                f"{tool.tool_id} 泄漏治理词: {word}"
            )


@pytest.mark.anyio
async def test_inspect_permanently_blocked_tool_reports_booleans_only() -> None:
    """策略拒绝的工具只给布尔信号，不给原文。

    ``aliens_eye_advanced`` 被 collection policy 无条件拒绝。
    投影后 execution_kind 为 unsupported，无输出家族，也不得残留原文。
    """
    body = await discovery_tools.inspect_tool("aliens_eye_advanced")
    assert body["execution_kind"] == "unsupported"
    assert body["permanently_blocked"] is True
    assert body["executable_now"] is False
    assert body["output_schema"] is None
    for word in _INSPECT_FORBIDDEN_WORDS:
        assert not _serialized_contains(body, word), f"泄漏治理词: {word}"


@pytest.mark.anyio
async def test_refactored_catalog_tools_return_structured_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """list_capabilities、describe_capability 与 get_playbook 返回结构化数据。"""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(
        capability_service,
        "async_session_factory",
        async_sessionmaker(engine, expire_on_commit=False),
    )
    monkeypatch.setattr(runtime, "project_api_key_context", lambda context: None)
    try:
        async with Client(mcp_server) as client:
            listing = await client.call_tool("list_capabilities", {"platform_id": "tiktok"})
            described = await client.call_tool(
                "describe_capability",
                {"endpoint_type": "tikhub_tiktok_video_search"},
            )
            playbook = await client.call_tool("get_playbook", {"platform_id": "tiktok"})
    finally:
        await engine.dispose()

    assert listing.structured_content is not None
    capabilities = listing.structured_content["capabilities"]
    assert capabilities
    assert all("tool_id" in item for item in capabilities)
    assert all("availability_view" in item for item in capabilities)

    assert described.structured_content is not None
    assert described.structured_content["input_schema"]["type"] == "object"
    assert described.structured_content["endpoint_type"] == "tikhub_tiktok_video_search"

    assert playbook.structured_content is not None
    structured = playbook.structured_content
    assert structured["platform_id"] == "tiktok"
    assert structured["capabilities"]
    assert structured["steps"]
    assert structured["acceptance"]
    assert structured["risk_boundaries"]
    assert "markdown" not in structured


@pytest.mark.anyio
async def test_get_run_and_list_records_are_project_scoped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """跨项目读运行与记录按未找到处理，不泄露数据。"""
    factory, engine = _make_factory()
    await _create_schema(engine)
    run_a = uuid.uuid4()
    run_b = uuid.uuid4()
    workspace_a = uuid.uuid4()
    project_a = uuid.uuid4()
    workspace_b = uuid.uuid4()
    project_b = uuid.uuid4()
    try:
        await _seed_run(
            factory,
            run_id=run_a,
            workspace_id=workspace_a,
            project_id=project_a,
        )
        await _seed_run(
            factory,
            run_id=run_b,
            workspace_id=workspace_b,
            project_id=project_b,
        )
        monkeypatch.setattr(run_service, "async_session_factory", factory)
        identity = _identity(project_id=project_a, workspace_id=workspace_a)
        monkeypatch.setattr(runtime, "project_api_key_context", lambda context: identity)

        # 服务层给出明确错误码。
        with pytest.raises(ValueError, match="run_not_found"):
            await run_service.get_run_detail(run_b, project_id=project_a)
        with pytest.raises(ValueError, match="run_not_found"):
            await run_service.list_run_records(run_b, project_id=project_a)

        async with Client(mcp_server, raise_exceptions=False) as client:
            own_run = await client.call_tool("get_run", {"run_id": str(run_a)})
            own_records = await client.call_tool(
                "list_records",
                {"run_id": str(run_a), "limit": 1},
            )
            other_run = await client.call_tool("get_run", {"run_id": str(run_b)})
            other_records = await client.call_tool(
                "list_records",
                {"run_id": str(run_b), "limit": 1},
            )
    finally:
        await engine.dispose()  # type: ignore[attr-defined]

    assert own_run.structured_content is not None
    assert own_run.structured_content["status"] == "completed"
    assert own_records.structured_content is not None
    assert own_records.structured_content["records_total"] == 2
    assert other_run.is_error is True
    assert other_records.is_error is True
    assert str(project_b) not in _error_text(other_run)


@pytest.mark.anyio
async def test_global_token_keeps_existing_run_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """无项目身份时，读运行不受项目过滤。"""
    factory, engine = _make_factory()
    await _create_schema(engine)
    run_id = uuid.uuid4()
    try:
        await _seed_run(
            factory,
            run_id=run_id,
            workspace_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
        )
        monkeypatch.setattr(run_service, "async_session_factory", factory)
        monkeypatch.setattr(runtime, "project_api_key_context", lambda context: None)
        async with Client(mcp_server) as client:
            result = await client.call_tool("get_run", {"run_id": str(run_id)})
    finally:
        await engine.dispose()  # type: ignore[attr-defined]

    assert result.structured_content is not None
    assert result.structured_content["status"] == "completed"


@pytest.mark.anyio
async def test_tool_outside_allowlist_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """白名单外的工具返回 tool_not_allowed。"""
    identity = _identity(allowlist=("list_platforms",))
    monkeypatch.setattr(runtime, "project_api_key_context", lambda context: identity)
    context = SimpleNamespace(headers={})
    with pytest.raises(ValueError, match="tool_not_allowed"):
        await server_module.discover(context, "tiktok")
    allowed = await server_module.list_platforms(context, query="TikTok")
    assert allowed["platforms"]


@pytest.mark.anyio
async def test_project_daily_collect_quota_is_enforced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """项目额度用完时返回 project_daily_collect_quota_exceeded。"""
    identity = _identity(allowlist=("collect",), quota=1)
    monkeypatch.setattr(runtime, "project_api_key_context", lambda context: identity)
    context = SimpleNamespace(headers={})
    with pytest.raises(ValueError, match="capability_not_found"):
        await server_module.collect(
            context,
            "missing_endpoint",
            str(identity.project_id),
            {},
        )
    with pytest.raises(ValueError, match="project_daily_collect_quota_exceeded"):
        await server_module.collect(
            context,
            "missing_endpoint",
            str(identity.project_id),
            {},
        )


@pytest.mark.anyio
async def test_collect_rejects_cross_project_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """项目密钥不能替他项目采集。"""
    identity = _identity(allowlist=("collect",))
    monkeypatch.setattr(runtime, "project_api_key_context", lambda context: identity)
    context = SimpleNamespace(headers={})
    with pytest.raises(ValueError, match="project_mismatch"):
        await server_module.collect(
            context,
            "tikhub_tiktok_video_search",
            str(uuid.uuid4()),
            {},
        )


@pytest.mark.anyio
async def test_create_report_requires_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """缺少合同时明确报错，不生成假合同与假产物。"""
    factory, engine = _make_factory()
    await _create_schema(engine)
    run_id = uuid.uuid4()
    try:
        await _seed_run(
            factory,
            run_id=run_id,
            workspace_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
        )
        monkeypatch.setattr(report_tools, "async_session_factory", factory)
        monkeypatch.setattr(runtime, "project_api_key_context", lambda context: None)
        with pytest.raises(ValueError, match="report_contract_incomplete") as exc_info:
            await report_tools.create_report(run_id, TEMPLATE_ID)
        async with factory() as session:
            count = await session.scalar(select(func.count()).select_from(ReportArtifact))
    finally:
        await engine.dispose()  # type: ignore[attr-defined]

    message = str(exc_info.value)
    assert "identity" in message
    assert "decision" in message
    assert count == 0


@pytest.mark.anyio
@pytest.mark.parametrize("template_id", ["t3_selection", "t4_creator"])
async def test_create_report_rejects_unregistered_template(template_id: str) -> None:
    """T3 与 T4 属于 B6。未登记模板必须返回明确错误。"""
    with pytest.raises(ValueError, match="template_not_registered"):
        await report_tools.create_report(uuid.uuid4(), template_id, None)


@pytest.mark.anyio
async def test_create_report_rejects_l4_contract_for_a_fixture_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """夹具运行的合同等级不得高于 L2。create_report 不得绕过构建器。"""
    factory, engine = _make_factory()
    await _create_schema(engine)
    run_id = uuid.uuid4()
    try:
        await _seed_run(
            factory,
            run_id=run_id,
            workspace_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            execution_mode="fixture",
        )
        monkeypatch.setattr(report_tools, "async_session_factory", factory)
        monkeypatch.setattr(runtime, "project_api_key_context", lambda context: None)
        contract = _contract_payload(
            run_id=run_id,
            task_id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
        )
        contract["evidences"][0]["evidence_grade"] = "L4_authorized_live"
        contract["run_ledger"][0]["evidence_grade"] = "L4_authorized_live"
        with pytest.raises(ValueError, match="report_contract_invalid") as exc_info:
            await report_tools.create_report(run_id, TEMPLATE_ID, contract)
        async with factory() as session:
            count = await session.scalar(select(func.count()).select_from(ReportArtifact))
    finally:
        await engine.dispose()  # type: ignore[attr-defined]

    assert "L2" in str(exc_info.value)
    assert count == 0


@pytest.mark.anyio
async def test_create_report_rejects_confirmed_claim_at_l3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """create_report 必须执行 claim 状态上限，不得只做结构校验。"""
    factory, engine = _make_factory()
    await _create_schema(engine)
    run_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    evidence_id = uuid.uuid4()
    try:
        await _seed_run(
            factory,
            run_id=run_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        monkeypatch.setattr(report_tools, "async_session_factory", factory)
        identity = _identity(project_id=project_id, workspace_id=workspace_id)
        monkeypatch.setattr(runtime, "project_api_key_context", lambda context: identity)
        contract = _contract_payload(
            run_id=run_id,
            task_id=uuid.uuid4(),
            evidence_id=evidence_id,
        )
        contract["claims"] = [
            {
                "claim_id": "c-1",
                "text": "防胀气卖点出现频率高。",
                "claim_status": "confirmed",
                "evidence_grade": "L3_live_single",
                "scope": {
                    "market": "US",
                    "window": {
                        "start": "2026-01-01",
                        "end": "2026-03-01",
                        "days": 60,
                    },
                    "sample_n": 80,
                },
                "counterevidence_text": "未发现反证",
                "owner": str(uuid.uuid4()),
                "evidence_ids": [str(evidence_id)],
            }
        ]
        contract["evidences"].append(
            {
                "evidence_id": str(uuid.uuid4()),
                "claim_id": "c-1",
                "role": "gap",
                "source_tool_id": "tikhub_tiktok_video_search",
                "captured_at": "2026-02-02T00:00:00+00:00",
                "market": "US",
                "locale": "en-US",
                "evidence_grade": "L3_live_single",
            }
        )
        with pytest.raises(ValueError, match="report_contract_invalid") as exc_info:
            await report_tools.create_report(run_id, TEMPLATE_ID, contract)
        async with factory() as session:
            count = await session.scalar(select(func.count()).select_from(ReportArtifact))
    finally:
        await engine.dispose()  # type: ignore[attr-defined]

    assert "claim_status" in str(exc_info.value)
    assert count == 0


@pytest.mark.anyio
async def test_create_report_builds_artifact_from_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """完整合同能生成两页产物与五个哈希。"""
    factory, engine = _make_factory()
    await _create_schema(engine)
    run_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    task_id = uuid.uuid4()
    evidence_id = uuid.uuid4()
    try:
        await _seed_run(
            factory,
            run_id=run_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        monkeypatch.setattr(report_tools, "async_session_factory", factory)
        identity = _identity(project_id=project_id, workspace_id=workspace_id)
        monkeypatch.setattr(runtime, "project_api_key_context", lambda context: identity)
        contract = _contract_payload(
            run_id=run_id,
            task_id=task_id,
            evidence_id=evidence_id,
        )
        async with Client(mcp_server, raise_exceptions=False) as client:
            result = await client.call_tool(
                "create_report",
                {
                    "run_id": str(run_id),
                    "template_id": TEMPLATE_ID,
                    "contract": contract,
                },
            )
        async with factory() as session:
            artifacts = list(
                (await session.scalars(select(ReportArtifact))).all()
            )
    finally:
        await engine.dispose()  # type: ignore[attr-defined]

    assert result.is_error is False
    assert result.structured_content is not None
    body = result.structured_content
    assert body["artifact_id"]
    assert body["verification"] == []
    assert body["artifact"]["contract_sha256"]
    assert body["artifact"]["report_html_sha256"]
    assert body["artifact"]["sop_html_sha256"]
    assert body["artifact"]["combined_sha256"]
    assert body["report_html"]
    assert body["sop_html"]
    # 页脚必须写真实合同哈希，不得沿用调用方给的值。
    assert body["artifact"]["contract_sha256"] in body["report_html"]
    assert "c" * 64 not in body["report_html"]
    assert len(artifacts) == 1
    assert artifacts[0].run_id == run_id
    assert artifacts[0].project_id == project_id


@pytest.mark.anyio
async def test_create_report_rejects_cross_project_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """项目密钥不能为其他项目的运行生成报告。"""
    factory, engine = _make_factory()
    await _create_schema(engine)
    run_id = uuid.uuid4()
    try:
        await _seed_run(
            factory,
            run_id=run_id,
            workspace_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
        )
        monkeypatch.setattr(report_tools, "async_session_factory", factory)
        identity = _identity()
        monkeypatch.setattr(runtime, "project_api_key_context", lambda context: identity)
        contract = _contract_payload(
            run_id=run_id,
            task_id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
        )
        with pytest.raises(ValueError, match="run_not_found") as exc_info:
            await report_tools.create_report(
                run_id,
                TEMPLATE_ID,
                contract,
                project_id=identity.project_id,
                workspace_id=identity.workspace_id,
            )
        async with factory() as session:
            count = await session.scalar(select(func.count()).select_from(ReportArtifact))
    finally:
        await engine.dispose()  # type: ignore[attr-defined]

    assert "run_not_found" in str(exc_info.value)
    assert count == 0


@pytest.mark.anyio
async def test_stop_is_scoped_to_calling_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """项目密钥不能取消同工作区其他项目的运行。

    跨项目 stop 必须抛 ``run_not_found``，且对方运行保持原状态。
    错误文本不得包含对方 project_id。
    """
    factory, engine = _make_factory()
    await _create_schema(engine)
    foreign_run_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    other_project_id = uuid.uuid4()
    try:
        await _seed_running(
            factory,
            run_id=foreign_run_id,
            workspace_id=workspace_id,
            project_id=other_project_id,
        )
        monkeypatch.setattr(run_service, "async_session_factory", factory)
        identity = _identity(
            project_id=project_id,
            workspace_id=workspace_id,
            allowlist=("stop", "balance"),
        )
        monkeypatch.setattr(runtime, "project_api_key_context", lambda context: identity)

        # 服务层语义：跨项目按未找到处理。
        with pytest.raises(ValueError, match="run_not_found"):
            await run_service.stop_run(foreign_run_id, project_id=project_id)

        async with Client(mcp_server, raise_exceptions=False) as client:
            stop_other = await client.call_tool(
                "stop",
                {"run_id": str(foreign_run_id)},
            )
        async with factory() as session:
            foreign = await session.get(Run, foreign_run_id)
    finally:
        await engine.dispose()  # type: ignore[attr-defined]

    assert stop_other.is_error is True
    assert str(other_project_id) not in _error_text(stop_other)
    assert foreign is not None
    assert foreign.status == "running"


@pytest.mark.anyio
async def test_stop_rejects_run_in_other_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """跨工作区的运行同样 fail-closed：按未找到处理。"""
    factory, engine = _make_factory()
    await _create_schema(engine)
    foreign_run_id = uuid.uuid4()
    try:
        await _seed_running(
            factory,
            run_id=foreign_run_id,
            workspace_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
        )
        monkeypatch.setattr(run_service, "async_session_factory", factory)
        identity = _identity(allowlist=("stop", "balance"))
        monkeypatch.setattr(runtime, "project_api_key_context", lambda context: identity)
        async with Client(mcp_server, raise_exceptions=False) as client:
            result = await client.call_tool("stop", {"run_id": str(foreign_run_id)})
        async with factory() as session:
            foreign = await session.get(Run, foreign_run_id)
    finally:
        await engine.dispose()  # type: ignore[attr-defined]

    assert result.is_error is True
    assert foreign is not None
    assert foreign.status == "running"


@pytest.mark.anyio
async def test_stop_allows_own_project_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """项目密钥可以取消自己项目的运行。"""
    factory, engine = _make_factory()
    await _create_schema(engine)
    own_run_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    try:
        await _seed_running(
            factory,
            run_id=own_run_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        monkeypatch.setattr(run_service, "async_session_factory", factory)
        identity = _identity(
            project_id=project_id,
            workspace_id=workspace_id,
            allowlist=("stop", "balance"),
        )
        monkeypatch.setattr(runtime, "project_api_key_context", lambda context: identity)
        async with Client(mcp_server, raise_exceptions=False) as client:
            result = await client.call_tool("stop", {"run_id": str(own_run_id)})
    finally:
        await engine.dispose()  # type: ignore[attr-defined]

    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["cancelled"] is True


@pytest.mark.anyio
async def test_balance_is_scoped_to_calling_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """项目密钥查询他人项目余额必须抛 ``project_mismatch``。"""
    factory, engine = _make_factory()
    await _create_schema(engine)
    other_project_id = uuid.uuid4()
    try:
        await _seed_balance(factory)
        await _seed_run(
            factory,
            run_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            project_id=other_project_id,
        )
        monkeypatch.setattr(run_service, "async_session_factory", factory)
        identity = _identity(allowlist=("stop", "balance"))
        monkeypatch.setattr(runtime, "project_api_key_context", lambda context: identity)
        context = SimpleNamespace(headers={})
        with pytest.raises(ValueError, match="project_mismatch"):
            await server_module.balance(context, str(other_project_id))
        async with Client(mcp_server, raise_exceptions=False) as client:
            other_balance = await client.call_tool(
                "balance",
                {"project_id": str(other_project_id)},
            )
    finally:
        await engine.dispose()  # type: ignore[attr-defined]

    assert other_balance.is_error is True
    assert str(other_project_id) not in _error_text(other_balance)


@pytest.mark.anyio
async def test_balance_allows_own_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """项目密钥可以查询自己项目的余额与账本。"""
    factory, engine = _make_factory()
    await _create_schema(engine)
    try:
        own_project_id = await _seed_balance(factory)
        monkeypatch.setattr(run_service, "async_session_factory", factory)
        identity = _identity(
            project_id=own_project_id,
            workspace_id=uuid.uuid4(),
            allowlist=("stop", "balance"),
        )
        monkeypatch.setattr(runtime, "project_api_key_context", lambda context: identity)
        context = SimpleNamespace(headers={})
        body = await server_module.balance(context, str(own_project_id))
        async with Client(mcp_server, raise_exceptions=False) as client:
            result = await client.call_tool(
                "balance",
                {"project_id": str(own_project_id)},
            )
    finally:
        await engine.dispose()  # type: ignore[attr-defined]

    assert body["project_id"] == str(own_project_id)
    assert body["metering_status"] == "accrued_only"
    assert body["accrued_usd"] == "1.250000"
    assert body["authorization_count"] == 1
    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["project_id"] == str(own_project_id)


@pytest.mark.anyio
async def test_balance_rejects_project_in_other_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """跨工作区的项目余额查询同样 fail-closed。"""
    factory, engine = _make_factory()
    await _create_schema(engine)
    foreign_project_id = uuid.uuid4()
    try:
        await _seed_balance(factory)
        await _seed_run(
            factory,
            run_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            project_id=foreign_project_id,
        )
        monkeypatch.setattr(run_service, "async_session_factory", factory)
        identity = _identity(allowlist=("stop", "balance"))
        monkeypatch.setattr(runtime, "project_api_key_context", lambda context: identity)
        context = SimpleNamespace(headers={})
        with pytest.raises(ValueError, match="project_mismatch"):
            await server_module.balance(context, str(foreign_project_id))
    finally:
        await engine.dispose()  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_global_token_keeps_stop_and_balance_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """全局 token（identity=None）不受项目过滤，行为不变。"""
    factory, engine = _make_factory()
    await _create_schema(engine)
    running_run_id = uuid.uuid4()
    try:
        own_project_id = await _seed_balance(factory)
        await _seed_running(
            factory,
            run_id=running_run_id,
            workspace_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
        )
        monkeypatch.setattr(run_service, "async_session_factory", factory)
        monkeypatch.setattr(runtime, "project_api_key_context", lambda context: None)
        async with Client(mcp_server, raise_exceptions=False) as client:
            stop_result = await client.call_tool(
                "stop",
                {"run_id": str(running_run_id)},
            )
            balance_result = await client.call_tool(
                "balance",
                {"project_id": str(own_project_id)},
            )
    finally:
        await engine.dispose()  # type: ignore[attr-defined]

    assert stop_result.is_error is False
    assert stop_result.structured_content is not None
    assert stop_result.structured_content["cancelled"] is True
    assert balance_result.is_error is False
    assert balance_result.structured_content is not None
    assert balance_result.structured_content["project_id"] == str(own_project_id)


@pytest.mark.anyio
async def test_identity_seem_reads_project_context_via_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """接缝守卫：工具体读取身份必须经过 runtime.project_api_key_context。

    打补丁后 project_filter 必须返回身份里的 project_id。
    """
    identity = _identity(allowlist=("stop", "balance"))
    monkeypatch.setattr(runtime, "project_api_key_context", lambda context: identity)
    context = SimpleNamespace(headers={})
    assert server_module.project_filter(context) == identity.project_id
    assert server_module.project_identity(context) is identity


@pytest.mark.anyio
async def test_deep_research_check_is_scoped_to_calling_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """项目密钥不能读同工作区其他项目的运行。

    旧实现只比对 workspace_id，同工作区跨项目的 run 会整体泄漏。
    修复后跨项目按 ``run_not_found`` 处理，错误文本不得含对方
    project_id 或对方 run_id。
    """
    factory, engine = _make_factory()
    await _create_schema(engine)
    foreign_run_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    other_project_id = uuid.uuid4()
    try:
        await _seed_run(
            factory,
            run_id=foreign_run_id,
            workspace_id=workspace_id,
            project_id=other_project_id,
        )
        monkeypatch.setattr(run_service, "async_session_factory", factory)
        identity = _identity(
            project_id=project_id,
            workspace_id=workspace_id,
            allowlist=("deep_research_check",),
        )
        monkeypatch.setattr(runtime, "project_api_key_context", lambda context: identity)

        # 服务层语义：跨项目按未找到处理。
        with pytest.raises(ValueError, match="run_not_found"):
            await run_service.get_run_detail(foreign_run_id, project_id=project_id)
        with pytest.raises(ValueError, match="run_not_found"):
            await run_service.list_run_records(foreign_run_id, project_id=project_id)

        async with Client(mcp_server, raise_exceptions=False) as client:
            other_run = await client.call_tool(
                "deep_research_check",
                {"run_id": str(foreign_run_id)},
            )
    finally:
        await engine.dispose()  # type: ignore[attr-defined]

    assert other_run.is_error is True
    error_text = _error_text(other_run)
    assert str(other_project_id) not in error_text
    assert str(foreign_run_id) not in error_text


@pytest.mark.anyio
async def test_deep_research_check_rejects_run_in_other_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """跨工作区的运行同样 fail-closed：按未找到处理。"""
    factory, engine = _make_factory()
    await _create_schema(engine)
    foreign_run_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    try:
        await _seed_run(
            factory,
            run_id=foreign_run_id,
            workspace_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
        )
        monkeypatch.setattr(run_service, "async_session_factory", factory)
        identity = _identity(
            project_id=project_id,
            workspace_id=workspace_id,
            allowlist=("deep_research_check",),
        )
        monkeypatch.setattr(runtime, "project_api_key_context", lambda context: identity)
        async with Client(mcp_server, raise_exceptions=False) as client:
            result = await client.call_tool(
                "deep_research_check",
                {"run_id": str(foreign_run_id)},
            )
    finally:
        await engine.dispose()  # type: ignore[attr-defined]

    assert result.is_error is True


@pytest.mark.anyio
async def test_deep_research_check_allows_own_project_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """项目密钥可以读自己项目的运行与记录。"""
    factory, engine = _make_factory()
    await _create_schema(engine)
    own_run_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    project_id = uuid.uuid4()
    try:
        await _seed_run(
            factory,
            run_id=own_run_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        monkeypatch.setattr(run_service, "async_session_factory", factory)
        identity = _identity(
            project_id=project_id,
            workspace_id=workspace_id,
            allowlist=("deep_research_check",),
        )
        monkeypatch.setattr(runtime, "project_api_key_context", lambda context: identity)
        async with Client(mcp_server, raise_exceptions=False) as client:
            result = await client.call_tool(
                "deep_research_check",
                {"run_id": str(own_run_id)},
            )
    finally:
        await engine.dispose()  # type: ignore[attr-defined]

    assert result.is_error is False
    assert result.structured_content is not None
    body = result.structured_content
    assert body["run"]["run_id"] == str(own_run_id)
    assert body["run"]["status"] == "completed"
    assert body["records"]["records_total"] == 2
    assert body["records"]["items"]


@pytest.mark.anyio
async def test_global_token_keeps_deep_research_check_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """全局 token（identity=None）不受项目过滤，行为不变。"""
    factory, engine = _make_factory()
    await _create_schema(engine)
    run_id = uuid.uuid4()
    try:
        await _seed_run(
            factory,
            run_id=run_id,
            workspace_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
        )
        monkeypatch.setattr(run_service, "async_session_factory", factory)
        monkeypatch.setattr(runtime, "project_api_key_context", lambda context: None)
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "deep_research_check",
                {"run_id": str(run_id)},
            )
    finally:
        await engine.dispose()  # type: ignore[attr-defined]

    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["run"]["run_id"] == str(run_id)


@pytest.mark.anyio
async def test_deep_research_check_rejects_bad_run_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """坏 run_id 返回 ``run_id_invalid``，与 get_run/list_records 一致。

    SDK 会把工具体 ValueError 包成 UnexpectedToolError，客户端只看到
    is_error；错误码用工具体直调断言。不得暴露 Python 的 badly
    formed hexadecimal 文本。
    """
    factory, engine = _make_factory()
    await _create_schema(engine)
    identity = _identity(allowlist=("deep_research_check",))
    try:
        monkeypatch.setattr(run_service, "async_session_factory", factory)
        monkeypatch.setattr(runtime, "project_api_key_context", lambda context: identity)
        context = SimpleNamespace(headers={})
        with pytest.raises(ValueError, match="run_id_invalid"):
            await server_module.deep_research_check(context, "not-a-uuid")
        async with Client(mcp_server, raise_exceptions=False) as client:
            result = await client.call_tool(
                "deep_research_check",
                {"run_id": "not-a-uuid"},
            )
    finally:
        await engine.dispose()  # type: ignore[attr-defined]

    assert result.is_error is True
    error_text = _error_text(result)
    assert "badly formed" not in error_text
    assert "hexadecimal" not in error_text


@pytest.mark.anyio
async def test_create_report_rejects_empty_run_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """空账本合同不能通过 MCP 面的 run 归属 guard（行为固化）。

    ``create_report`` 要求合同的 ``run_ledger`` 覆盖本次运行。
    合同 ``run_ledger=[]`` 时没有 run 可归属，必须先在
    ``report_run_not_in_contract`` 处失败，且不落任何产物行。
    """
    factory, engine = _make_factory()
    await _create_schema(engine)
    run_id = uuid.uuid4()
    try:
        await _seed_run(
            factory,
            run_id=run_id,
            workspace_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
        )
        monkeypatch.setattr(report_tools, "async_session_factory", factory)
        monkeypatch.setattr(runtime, "project_api_key_context", lambda context: None)
        contract = _contract_payload(
            run_id=run_id,
            task_id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
        )
        contract["run_ledger"] = []
        contract["evidences"] = []
        with pytest.raises(ValueError, match="report_run_not_in_contract") as exc_info:
            await report_tools.create_report(run_id, TEMPLATE_ID, contract)
        async with factory() as session:
            count = await session.scalar(select(func.count()).select_from(ReportArtifact))
    finally:
        await engine.dispose()  # type: ignore[attr-defined]

    assert "report_run_not_in_contract" in str(exc_info.value)
    assert count == 0
