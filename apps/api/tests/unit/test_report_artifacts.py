"""B4-04：报告产物表、五哈希与复核。

覆盖这些事：

1. 两页渲染哈希各自独立。互换两页内容会各自报错。
2. 组合哈希等于两页哈希的拼接哈希。
3. ``strip_hash_placeholders`` 能还原 report、sop 与两者都在的形态。
4. ``verify_artifact`` 只改 report.html 时只报 report 那一项。
5. 合同经 ``model_dump(mode="json")`` 与直接传模型，哈希相同。
6. ``contract_json`` 落库后读出，重新计算哈希与记录一致。
7. 仓储按工作区隔离，且仓储层不调用 ``commit``。

本文件只用内存 SQLite。它不连接真实 Postgres。
"""

from __future__ import annotations

import copy
import hashlib
import runpy
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import JSON, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import data_intelligence_hub.services.report_artifacts as artifact_service
from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.report_artifact import ReportArtifact
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.report_artifacts import (
    create_artifact,
    get_artifact,
    list_artifacts,
)
from data_intelligence_hub.schemas.report_contract import (
    ReportContract,
)
from data_intelligence_hub.schemas.report_contract import (
    contract_sha256 as schema_contract_sha256,
)
from data_intelligence_hub.services.report_artifacts import (
    build_artifact,
    combined_sha256,
    contract_payload,
    data_sha256,
    render_sha256,
    strip_hash_placeholders,
    verify_artifact,
)

API_ROOT = Path(__file__).resolve().parents[2]
REPOSITORIES = API_ROOT / "src/data_intelligence_hub/repositories"
MIGRATION = API_ROOT / "alembic/versions/202610220059_report_artifacts.py"

Scenario = Callable[[AsyncSession], Awaitable[None]]

WORKSPACE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
PROJECT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
RUN_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
EVIDENCE_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
REPORT_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
TASK_ID = uuid.UUID("66666666-6666-6666-6666-666666666666")
OWNER_ID = uuid.UUID("77777777-7777-7777-7777-777777777777")

HASH_COLUMNS = (
    "contract_sha256",
    "data_sha256",
    "report_html_sha256",
    "sop_html_sha256",
    "combined_sha256",
)

# 两页模板都在页脚留两个哈希位置。占位符在渲染后填值。
REPORT_TEMPLATE = (
    '<!doctype html><html><body><h1>报告</h1>'
    '<footer data-render-hash="__REPORT_HASH__">'
    '<span data-render-hash="__SOP_HASH__"></span></footer></body></html>'
)
SOP_TEMPLATE = (
    '<!doctype html><html><body><h1>SOP</h1>'
    '<footer data-render-hash="__REPORT_HASH__">'
    '<span data-render-hash="__SOP_HASH__"></span></footer></body></html>'
)


def _contract_payload() -> dict[str, Any]:
    """一份最小但完整的合同。它带 run、证据与 artifact 组。"""
    return {
        "schema_version": "1.0.0",
        "template_id": "t1_voc",
        "generated_at": "2026-10-21T08:00:00+00:00",
        "identity": {
            "task_id": str(TASK_ID),
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
                "evidence_id": str(EVIDENCE_ID),
                "claim_id": "c-1",
                "role": "support",
                "source_tool_id": "tiktok_search",
                "captured_at": "2026-02-01T00:00:00+00:00",
                "market": "US",
                "locale": "en-US",
                "evidence_grade": "L3_live_single",
            }
        ],
        "run_ledger": [
            {
                "run_id": str(RUN_ID),
                "tool_id": "tiktok_search",
                "endpoint_type": "search",
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


def _contract() -> ReportContract:
    return ReportContract.model_validate(_contract_payload())


def _finalize(html: str, report_digest: str, sop_digest: str) -> str:
    """把两个占位符替换成最终哈希。"""
    return html.replace("__REPORT_HASH__", report_digest).replace(
        "__SOP_HASH__", sop_digest
    )


def _build(
    contract: object | None = None,
    report_template: str = REPORT_TEMPLATE,
    sop_template: str = SOP_TEMPLATE,
) -> tuple[ReportArtifact, str, str]:
    """组装产物，并返回填好哈希的最终 HTML。"""
    contract = _contract() if contract is None else contract
    report_digest = render_sha256(report_template)
    sop_digest = render_sha256(sop_template)
    final_report = _finalize(report_template, report_digest, sop_digest)
    final_sop = _finalize(sop_template, report_digest, sop_digest)
    artifact = build_artifact(
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        run_id=RUN_ID,
        report_id=REPORT_ID,
        template_id="t1_voc",
        contract=contract,
        report_html=final_report,
        sop_html=final_sop,
    )
    return artifact, final_report, final_sop


def _codes(mismatches: list[str]) -> list[str]:
    """取每条说明的列名部分。"""
    return [item.split(" ", 1)[0] for item in mismatches]


async def _with_session(callback: Scenario) -> None:
    """在内存 SQLite 上跑一段用例。"""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            await callback(session)
    finally:
        await engine.dispose()


async def _seed_workspace(
    session: AsyncSession,
    *,
    slug: str,
) -> tuple[Workspace, Project]:
    """建一个最小 workspace + project。"""
    owner = User(
        email=f"{slug}-{uuid.uuid4().hex}@example.com",
        password_hash="x",
        name="Owner",
    )
    session.add(owner)
    await session.flush()
    workspace = Workspace(
        name=slug,
        slug=f"{slug}-{uuid.uuid4().hex}",
        owner_id=owner.id,
    )
    session.add(workspace)
    await session.flush()
    project = Project(
        workspace_id=workspace.id,
        name=f"{slug} project",
        domain="mother_baby",
        owner_id=owner.id,
    )
    session.add(project)
    await session.flush()
    return workspace, project


def test_five_hashes_are_64_hex_characters() -> None:
    """五个哈希列都必须是 64 位小写十六进制。"""
    artifact, _, _ = _build()
    for name in HASH_COLUMNS:
        value = getattr(artifact, name)
        assert len(value) == 64
        assert all(char in "0123456789abcdef" for char in value)


def test_two_page_hashes_are_independent() -> None:
    """两页哈希各自独立。互换内容后各自对调。"""
    first, _, _ = _build()
    second, _, _ = _build(report_template=SOP_TEMPLATE, sop_template=REPORT_TEMPLATE)

    assert first.report_html_sha256 != first.sop_html_sha256
    assert first.report_html_sha256 == second.sop_html_sha256
    assert first.sop_html_sha256 == second.report_html_sha256


def test_combined_sha256_is_concat_hash() -> None:
    """组合哈希等于两页哈希拼接后的 sha256。"""
    artifact, _, _ = _build()
    expected = hashlib.sha256(
        (artifact.report_html_sha256 + artifact.sop_html_sha256).encode("ascii")
    ).hexdigest()

    assert artifact.combined_sha256 == expected
    assert artifact.combined_sha256 == combined_sha256(
        artifact.report_html_sha256,
        artifact.sop_html_sha256,
    )


def test_render_sha256_is_stable_across_placeholder_and_final_html() -> None:
    """带占位符的 HTML 与填好哈希的 HTML 得到同一渲染哈希。"""
    template_digest = render_sha256(REPORT_TEMPLATE)
    final_html = _finalize(REPORT_TEMPLATE, template_digest, "b" * 64)

    assert render_sha256(final_html) == template_digest


def test_render_sha256_hashes_exact_bytes() -> None:
    """渲染哈希按 UTF-8 字节计算。"""
    assert render_sha256("abc") == render_sha256(b"abc")
    assert render_sha256("abc") != render_sha256("abc ")


def test_strip_hash_placeholders_restores_report_form() -> None:
    """report 形态：64 位哈希还原成 __RENDER_HASH__。"""
    html = f'<footer data-render-hash="{"a" * 64}">报告</footer>'

    assert strip_hash_placeholders(html) == (
        '<footer data-render-hash="__RENDER_HASH__">报告</footer>'
    )


def test_strip_hash_placeholders_restores_sop_form() -> None:
    """sop 形态：__SOP_HASH__ 归一到 __RENDER_HASH__。"""
    html = '<footer data-render-hash="__SOP_HASH__">SOP</footer>'

    assert strip_hash_placeholders(html) == (
        '<footer data-render-hash="__RENDER_HASH__">SOP</footer>'
    )


def test_strip_hash_placeholders_restores_both_forms() -> None:
    """两者都在：两个属性各自还原。"""
    html = (
        f'<footer data-render-hash="{"a" * 64}">'
        f'<span data-render-hash="{"b" * 64}"></span></footer>'
    )
    stripped = strip_hash_placeholders(html)

    assert stripped.count('data-render-hash="__RENDER_HASH__"') == 2
    assert "a" * 64 not in stripped
    assert "b" * 64 not in stripped


def test_strip_hash_placeholders_keeps_non_hash_values() -> None:
    """非哈希值原样保留。"""
    html = '<footer data-render-hash="pending"></footer>'

    assert strip_hash_placeholders(html) == html


def test_verify_artifact_returns_empty_when_all_hashes_match() -> None:
    """全部一致时返回空列表。"""
    artifact, final_report, final_sop = _build()

    assert verify_artifact(artifact, _contract(), final_report, final_sop) == []


def test_verify_artifact_reports_only_report_page_change() -> None:
    """只改 report.html 时只报 report 那一项。"""
    artifact, final_report, final_sop = _build()
    changed_report = final_report.replace("<h1>报告</h1>", "<h1>改过的报告</h1>")

    mismatches = verify_artifact(artifact, _contract(), changed_report, final_sop)

    assert _codes(mismatches) == ["report_html_sha256"]
    assert "报告页" in mismatches[0]


def test_verify_artifact_reports_only_sop_page_change() -> None:
    """只改 sop.html 时只报 sop 那一项。"""
    artifact, final_report, final_sop = _build()
    changed_sop = final_sop.replace("<h1>SOP</h1>", "<h1>改过的 SOP</h1>")

    mismatches = verify_artifact(artifact, _contract(), final_report, changed_sop)

    assert _codes(mismatches) == ["sop_html_sha256"]
    assert "执行页" in mismatches[0]


def test_verify_artifact_reports_both_pages_when_swapped() -> None:
    """互换两页内容时，两个渲染哈希各自报错。"""
    artifact, _, _ = _build()

    mismatches = verify_artifact(artifact, _contract(), SOP_TEMPLATE, REPORT_TEMPLATE)

    assert set(_codes(mismatches)) == {"report_html_sha256", "sop_html_sha256"}


def test_verify_artifact_reports_contract_change() -> None:
    """合同改动后，复核必须指出 contract_sha256。"""
    artifact, final_report, final_sop = _build()
    changed = _contract()
    changed.decision.answer = "已确认进入。"

    mismatches = verify_artifact(artifact, changed, final_report, final_sop)

    assert _codes(mismatches) == ["contract_sha256"]


def test_verify_artifact_reports_data_change() -> None:
    """合同里的输入 id 改动后，复核必须指出 contract_sha256 与 data_sha256。"""
    artifact, final_report, final_sop = _build()
    changed = _contract()
    changed.run_ledger[0].run_id = uuid.uuid4()

    mismatches = verify_artifact(artifact, changed, final_report, final_sop)

    assert _codes(mismatches) == ["contract_sha256", "data_sha256"]


def test_contract_hash_is_the_schema_entry_point() -> None:
    """本模块复用契约模块的哈希函数，不保留第二份实现。"""
    assert artifact_service.contract_sha256 is schema_contract_sha256


def test_contract_hash_same_for_model_and_json_dump() -> None:
    """合同经 model_dump(mode="json") 与直接传模型，哈希相同。

    上一版服务自己拼 JSON，时间输出 +00:00。契约模块输出 Z。
    同一份合同因此有两条哈希路径。本用例是回归。
    """
    contract = _contract()

    assert schema_contract_sha256(contract) == schema_contract_sha256(
        contract.model_dump(mode="json")
    )


def test_contract_hash_ignores_generated_at() -> None:
    """合同哈希不得包含生成时间。"""
    first = _contract_payload()
    second = copy.deepcopy(first)
    second["generated_at"] = "2030-01-01T00:00:00Z"

    assert schema_contract_sha256(first) == schema_contract_sha256(second)


def test_contract_payload_rehashes_to_same_digest() -> None:
    """规范化后的合同再次求哈希，结果不变。"""
    contract = _contract()
    payload = contract_payload(contract)

    assert schema_contract_sha256(payload) == schema_contract_sha256(contract)


def test_data_sha256_is_order_insensitive() -> None:
    """同一 id 集合换顺序，得到同一哈希。"""
    run_a, run_b = uuid.uuid4(), uuid.uuid4()
    evidence_a, evidence_b = uuid.uuid4(), uuid.uuid4()
    first = data_sha256([run_a, run_b], [evidence_a, evidence_b])
    second = data_sha256([run_b, run_a], [evidence_b, evidence_a])

    assert first == second


def test_data_sha256_changes_when_one_id_changes() -> None:
    """换一个 run id 或 evidence id，哈希必须变化。"""
    run_a, run_b = uuid.uuid4(), uuid.uuid4()
    evidence_a = uuid.uuid4()
    baseline = data_sha256([run_a, run_b], [evidence_a])

    assert data_sha256([run_a, uuid.uuid4()], [evidence_a]) != baseline
    assert data_sha256([run_a, run_b], [uuid.uuid4()]) != baseline


def _empty_ledger_payload() -> dict[str, Any]:
    """run_ledger 为空的合同。schema 允许空账本。"""
    payload = _contract_payload()
    payload["run_ledger"] = []
    return payload


def test_build_and_verify_agree_when_contract_ledger_is_empty() -> None:
    """空 run_ledger 的合同造出的产物必须能被复核。

    build 在合同没有 run_ledger 时用 ``run_id`` 补输入集合。
    verify 此前只会从合同重取，看到空集合就报 data_sha256 不一致。
    合法的产物因此永远无法通过复核。本用例是缺陷回归。
    """
    contract = ReportContract.model_validate(_empty_ledger_payload())
    artifact, final_report, final_sop = _build(contract)

    assert verify_artifact(artifact, contract, final_report, final_sop) == []


def test_verify_accepts_matching_explicit_input_ids() -> None:
    """verify 显式传入与 build 相同的 id 集合时必须通过。

    build 接受 run_ids/evidence_ids 覆盖参数。verify 此前没有
    对应参数，覆盖集合造出的产物只能报不一致。"""
    extra_run = uuid.uuid4()
    payload = _contract_payload()
    contract = ReportContract.model_validate(payload)
    artifact, final_report, final_sop = _build(contract)
    built = build_artifact(
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        run_id=RUN_ID,
        template_id="t1_voc",
        contract=contract,
        report_html=final_report,
        sop_html=final_sop,
        run_ids=[RUN_ID, extra_run],
        evidence_ids=[EVIDENCE_ID],
    )

    assert verify_artifact(
        built,
        contract,
        final_report,
        final_sop,
        run_ids=[RUN_ID, extra_run],
        evidence_ids=[EVIDENCE_ID],
    ) == []
    # 不传显式集合时仍按合同取 id，覆盖产物必须报不一致。
    mismatches = verify_artifact(built, contract, final_report, final_sop)
    assert _codes(mismatches) == ["data_sha256"]


def test_verify_does_not_invent_ids() -> None:
    """verify 不得凭空发明 id。

    run_id=None 的覆盖产物记录的是空输入集合。verify 不传显式
    集合时按合同取 id，合同里有一个 run，因此必须报不一致。
    verify 不能拿 ``artifact.run_id`` 之外的东西去凑集合。
    """
    payload = _contract_payload()
    contract = ReportContract.model_validate(payload)
    artifact, final_report, final_sop = _build(contract)
    built = build_artifact(
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        run_id=None,
        template_id="t1_voc",
        contract=contract,
        report_html=final_report,
        sop_html=final_sop,
        run_ids=[],
        evidence_ids=[],
    )

    mismatches = verify_artifact(built, contract, final_report, final_sop)

    assert _codes(mismatches) == ["data_sha256"]


@pytest.mark.anyio
async def test_empty_ledger_survives_repository_round_trip() -> None:
    """空账本产物落库再读出，复核仍通过。

    ``run_id`` 是持久化可空列。读出的行带 ``artifact.run_id``，
    verify 的 fallback 在落库后依然可用。
    """
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        workspace, project = await _seed_workspace(session, slug="artifact-empty")
        contract = ReportContract.model_validate(_empty_ledger_payload())
        artifact, final_report, final_sop = _build(contract)
        record = await create_artifact(
            session,
            workspace_id=workspace.id,
            project_id=project.id,
            run_id=RUN_ID,
            report_id=REPORT_ID,
            template_id="t1_voc",
            contract_json=artifact.contract_json,
            contract_sha256=artifact.contract_sha256,
            data_sha256=artifact.data_sha256,
            report_html_sha256=artifact.report_html_sha256,
            sop_html_sha256=artifact.sop_html_sha256,
            combined_sha256=artifact.combined_sha256,
            report_html=final_report,
            sop_html=final_sop,
        )
        loaded = await get_artifact(
            session,
            workspace_id=workspace.id,
            artifact_id=record.id,
        )
        assert loaded is not None
        observed["run_id"] = loaded.run_id
        observed["mismatches"] = verify_artifact(
            loaded, contract, final_report, final_sop
        )

    await _with_session(scenario)

    assert observed["run_id"] == RUN_ID
    assert observed["mismatches"] == []


def test_repository_never_commits() -> None:
    """仓储层不得调用 commit。"""
    source = (REPOSITORIES / "report_artifacts.py").read_text(encoding="utf-8")

    assert "session.commit" not in source


def test_model_pins_new_columns() -> None:
    """模型必须有两个页面哈希、组合哈希、合同 JSON 与版本列。"""
    table = ReportArtifact.__table__

    for name in HASH_COLUMNS:
        column = table.columns[name]
        assert column.nullable is False
        assert isinstance(column.type, String)
        assert column.type.length == 64

    assert "render_sha256" not in table.columns
    assert "report_html_path" not in table.columns
    assert "sop_html_path" not in table.columns
    assert table.columns["contract_json"].nullable is False
    assert isinstance(table.columns["contract_json"].type, JSON)
    assert table.columns["report_html"].nullable is True
    assert isinstance(table.columns["report_html"].type, Text)
    assert table.columns["sop_html"].nullable is True
    assert isinstance(table.columns["sop_html"].type, Text)
    assert table.columns["report_id"].nullable is True
    assert table.columns["version"].nullable is False
    assert table.columns["version"].type.length == 20
    assert table.columns["version"].default.arg == "1.0.0"


def test_migration_declares_new_columns_and_drops_paths() -> None:
    """迁移 053 直接建成新结构。它不建旧路径列与单列渲染哈希。"""
    source = MIGRATION.read_text(encoding="utf-8")

    for name in (
        "contract_json",
        "report_html_sha256",
        "sop_html_sha256",
        "combined_sha256",
        "report_html",
        "sop_html",
        "report_id",
        "version",
    ):
        assert f'"{name}"' in source
    assert '"render_sha256"' not in source
    assert '"report_html_path"' not in source
    assert '"sop_html_path"' not in source


def test_migration_revision_chain_points_to_b4_01() -> None:
    """迁移修订号是 057，前驱是 claims 的 056。"""
    module = runpy.run_path(str(MIGRATION))

    assert module["revision"] == "202610220059"
    assert module["down_revision"] == "202610220058"


@pytest.mark.anyio
async def test_artifact_repository_is_workspace_scoped() -> None:
    """get_artifact 与 list_artifacts 必须按工作区隔离。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        workspace_a, project_a = await _seed_workspace(session, slug="artifact-a")
        workspace_b, _ = await _seed_workspace(session, slug="artifact-b")
        contract = _contract()
        artifact, final_report, final_sop = _build(contract)
        record = await create_artifact(
            session,
            workspace_id=workspace_a.id,
            project_id=project_a.id,
            run_id=None,
            report_id=REPORT_ID,
            template_id="t1_voc",
            contract_json=artifact.contract_json,
            contract_sha256=artifact.contract_sha256,
            data_sha256=artifact.data_sha256,
            report_html_sha256=artifact.report_html_sha256,
            sop_html_sha256=artifact.sop_html_sha256,
            combined_sha256=artifact.combined_sha256,
            report_html=final_report,
            sop_html=final_sop,
        )
        observed["id"] = record.id
        observed["version"] = record.version
        observed["same"] = await get_artifact(
            session,
            workspace_id=workspace_a.id,
            artifact_id=record.id,
        )
        observed["cross"] = await get_artifact(
            session,
            workspace_id=workspace_b.id,
            artifact_id=record.id,
        )
        observed["list_a"] = await list_artifacts(
            session,
            workspace_id=workspace_a.id,
        )
        observed["list_b"] = await list_artifacts(
            session,
            workspace_id=workspace_b.id,
        )

    await _with_session(scenario)

    assert observed["id"] is not None
    assert observed["version"] == "1.0.0"
    assert observed["same"] is not None
    assert observed["cross"] is None
    assert len(observed["list_a"]) == 1
    assert observed["list_b"] == []


@pytest.mark.anyio
async def test_contract_json_round_trip_rehashes_to_same_digest() -> None:
    """contract_json 落库后读出，重新计算哈希与记录一致。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        workspace, project = await _seed_workspace(session, slug="artifact-json")
        contract = _contract()
        artifact = build_artifact(
            workspace_id=workspace.id,
            project_id=project.id,
            run_id=RUN_ID,
            template_id="t1_voc",
            contract=contract,
            report_html=REPORT_TEMPLATE,
            sop_html=SOP_TEMPLATE,
        )
        record = await create_artifact(
            session,
            workspace_id=workspace.id,
            project_id=project.id,
            run_id=RUN_ID,
            template_id="t1_voc",
            contract_json=artifact.contract_json,
            contract_sha256=artifact.contract_sha256,
            data_sha256=artifact.data_sha256,
            report_html_sha256=artifact.report_html_sha256,
            sop_html_sha256=artifact.sop_html_sha256,
            combined_sha256=artifact.combined_sha256,
            report_html=artifact.report_html,
            sop_html=artifact.sop_html,
        )
        loaded = await get_artifact(
            session,
            workspace_id=workspace.id,
            artifact_id=record.id,
        )
        assert loaded is not None
        observed["contract_json"] = loaded.contract_json
        observed["contract_sha256"] = loaded.contract_sha256

    await _with_session(scenario)

    stored = observed["contract_json"]
    assert isinstance(stored, dict)
    # 完整合同落库：生成时间与 artifact 组都在。
    assert "generated_at" in stored
    assert "artifact" in stored
    # 规范化：时间写 Z，Decimal 保留原精度。
    assert str(stored["generated_at"]).endswith("Z")
    ledger = stored["run_ledger"][0]
    assert str(ledger["started_at"]).endswith("Z")
    assert ledger["unit_price"] == "0.010000"
    assert schema_contract_sha256(stored) == observed["contract_sha256"]
