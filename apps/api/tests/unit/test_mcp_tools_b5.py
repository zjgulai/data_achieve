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
