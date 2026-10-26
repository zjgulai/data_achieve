"""``claims`` 与 ``claim_evidence`` 的单元守卫。

覆盖以下守卫：

1. claim 状态枚举精确五个值，不含显示别名。
2. 缺 counter 或 gap 证据时创建被拒。
3. 有 counter 证据时创建通过。
4. ``claim_evidence`` 主键只有两列，``role`` 不进主键。
5. 跨工作区查不到对方 claim。
6. 批量校验能指出具体哪条 claim 缺反证。
7. 只有 gap 或 context 时，状态只能是 hypothesis 或 blocked。
8. 报告合同的五列存在、可空，存量行为 None。
9. 模型与迁移 052 的 CHECK 约束名逐字相等。

本文件只用内存 SQLite。它不连接真实 Postgres。
"""

from __future__ import annotations

import ast
import importlib.util
import inspect as python_inspect
import textwrap
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import CheckConstraint, Table
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.claim import (
    Claim,
    ClaimEvidence,
    ClaimState,
    EvidenceRole,
)
from data_intelligence_hub.models.intelligence import Evidence, IntelligenceItem
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.claims import (
    create_claim,
    get_claim,
    link_evidence,
    list_claims,
    list_evidence,
)
from data_intelligence_hub.services.claims import (
    ClaimCounterEvidenceRequiredError,
    ClaimGapOnlyStateInvalidError,
    assert_counter_evidence_complete,
    assert_gap_only_state_valid,
    create_claim_with_evidence,
)

API_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = API_ROOT / "alembic/versions/202610220058_claims.py"

# 报告合同需要的 claim 列。PRD 5.4.1。全部可空。
REPORT_COLUMNS = (
    "owner",
    "scope_market",
    "scope_window_days",
    "scope_sample_n",
    "counterevidence_text",
)

Scenario = Callable[[AsyncSession], Awaitable[None]]


class Seed:
    """一段用例需要的租户数据与证据。"""

    def __init__(
        self,
        *,
        owner: User,
        workspace_a: Workspace,
        workspace_b: Workspace,
        project_a: Project,
        project_b: Project,
        support_evidence: Evidence,
        counter_evidence: Evidence,
        context_evidence: Evidence,
    ) -> None:
        self.owner = owner
        self.workspace_a = workspace_a
        self.workspace_b = workspace_b
        self.project_a = project_a
        self.project_b = project_b
        self.support_evidence = support_evidence
        self.counter_evidence = counter_evidence
        self.context_evidence = context_evidence


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


async def _seed(session: AsyncSession) -> Seed:
    """建两个工作区、两个项目和三条证据。"""
    owner = User(
        email=f"claim-{uuid.uuid4().hex}@example.com",
        password_hash="x",
        name="Owner",
    )
    session.add(owner)
    await session.flush()
    workspace_a = Workspace(
        name="Workspace A",
        slug=f"claim-a-{uuid.uuid4().hex}",
        owner_id=owner.id,
    )
    workspace_b = Workspace(
        name="Workspace B",
        slug=f"claim-b-{uuid.uuid4().hex}",
        owner_id=owner.id,
    )
    session.add_all([workspace_a, workspace_b])
    await session.flush()
    project_a = Project(
        workspace_id=workspace_a.id,
        name="Project A",
        domain="mother_baby",
        owner_id=owner.id,
    )
    project_b = Project(
        workspace_id=workspace_b.id,
        name="Project B",
        domain="mother_baby",
        owner_id=owner.id,
    )
    session.add_all([project_a, project_b])
    await session.flush()
    item = IntelligenceItem(
        workspace_id=workspace_a.id,
        project_id=project_a.id,
        title="Item",
        summary="Summary",
        intelligence_type="signal",
        impact_score=0.5,
        confidence_score=0.5,
        novelty_score=0.5,
        urgency_score=0.5,
        final_score=0.5,
        generated_by="system",
        domain="mother_baby",
    )
    session.add(item)
    await session.flush()
    support = Evidence(
        intelligence_id=item.id,
        evidence_type="web",
        title="Support",
    )
    counter = Evidence(
        intelligence_id=item.id,
        evidence_type="web",
        title="Counter",
    )
    context = Evidence(
        intelligence_id=item.id,
        evidence_type="web",
        title="Context",
    )
    session.add_all([support, counter, context])
    await session.flush()
    return Seed(
        owner=owner,
        workspace_a=workspace_a,
        workspace_b=workspace_b,
        project_a=project_a,
        project_b=project_b,
        support_evidence=support,
        counter_evidence=counter,
        context_evidence=context,
    )


def _kwargs(seed: Seed) -> dict[str, object]:
    return {
        "workspace_id": seed.workspace_a.id,
        "project_id": seed.project_a.id,
    }


def test_claim_state_has_exactly_five_contract_values() -> None:
    """契约 §2.6 只有五个值。显示别名不得出现在枚举。"""
    assert {state.value for state in ClaimState} == {
        "confirmed",
        "directional",
        "hypothesis",
        "evidence_gap",
        "blocked",
    }
    assert len(ClaimState) == 5
    values = {state.value for state in ClaimState}
    assert "verified" not in values
    assert "supported" not in values


def test_evidence_role_has_exactly_four_contract_values() -> None:
    """PRD 5.4.1 只有四个角色。"""
    assert {role.value for role in EvidenceRole} == {
        "support",
        "counter",
        "context",
        "gap",
    }
    assert len(EvidenceRole) == 4


def test_claim_evidence_primary_key_has_exactly_two_columns() -> None:
    """主键只有 claim_id 与 evidence_id。role 是普通列。"""
    primary_key = {column.name for column in ClaimEvidence.__table__.primary_key.columns}
    assert primary_key == {"claim_id", "evidence_id"}
    assert "role" in {column.name for column in ClaimEvidence.__table__.columns}


@pytest.mark.anyio
async def test_create_claim_rejects_evidence_without_counter_or_gap() -> None:
    """只有 support 与 context 时创建被拒。被拒后不留下 claim 行。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        with pytest.raises(ClaimCounterEvidenceRequiredError):
            await create_claim_with_evidence(
                session,
                **_kwargs(seed),
                claim_text="只有支持证据",
                evidence=[
                    (seed.support_evidence.id, "support"),
                    (seed.context_evidence.id, "context"),
                ],
            )
        with pytest.raises(ClaimCounterEvidenceRequiredError):
            await create_claim_with_evidence(
                session,
                **_kwargs(seed),
                claim_text="没有证据",
                evidence=[],
            )
        observed["claims"] = await list_claims(
            session,
            workspace_id=seed.workspace_a.id,
        )

    await _with_session(scenario)

    assert observed["claims"] == []


@pytest.mark.anyio
async def test_create_claim_accepts_counter_evidence() -> None:
    """有 counter 时创建通过。关联行写入两张表。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        claim = await create_claim_with_evidence(
            session,
            **_kwargs(seed),
            claim_text="有反证的主张",
            evidence=[
                (seed.support_evidence.id, "support"),
                (seed.counter_evidence.id, "counter"),
            ],
            evidence_grade="L3_live_single",
            confidence=0.7,
        )
        links = await list_evidence(session, claim_id=claim.id)
        await session.commit()
        await session.refresh(claim)
        observed["state"] = claim.state
        observed["grade"] = claim.evidence_grade
        observed["confidence"] = claim.confidence
        observed["roles"] = sorted(link.role for link in links)

    await _with_session(scenario)

    assert observed["state"] == "hypothesis"
    assert observed["grade"] == "L3_live_single"
    assert observed["confidence"] == 0.7
    assert observed["roles"] == ["counter", "support"]


@pytest.mark.anyio
async def test_create_claim_accepts_gap_evidence() -> None:
    """gap 也算反证。只有 gap 时创建通过。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        claim = await create_claim_with_evidence(
            session,
            **_kwargs(seed),
            claim_text="只有缺口证据",
            evidence=[(seed.context_evidence.id, "gap")],
        )
        links = await list_evidence(session, claim_id=claim.id)
        observed["roles"] = [link.role for link in links]

    await _with_session(scenario)

    assert observed["roles"] == ["gap"]


@pytest.mark.anyio
async def test_create_claim_rejects_gap_only_confirmed_state() -> None:
    """只有 gap 时 confirmed 被拒。被拒后不留下 claim 行。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        with pytest.raises(ClaimGapOnlyStateInvalidError):
            await create_claim_with_evidence(
                session,
                **_kwargs(seed),
                claim_text="只有缺口却声称已确认",
                evidence=[(seed.context_evidence.id, "gap")],
                state="confirmed",
            )
        with pytest.raises(ClaimGapOnlyStateInvalidError):
            await create_claim_with_evidence(
                session,
                **_kwargs(seed),
                claim_text="只有背景却给出方向",
                evidence=[(seed.context_evidence.id, "context"), (seed.support_evidence.id, "gap")],
                state="directional",
            )
        observed["claims"] = await list_claims(
            session,
            workspace_id=seed.workspace_a.id,
        )

    await _with_session(scenario)

    assert observed["claims"] == []


@pytest.mark.anyio
async def test_create_claim_accepts_gap_only_hypothesis_state() -> None:
    """只有 gap 时 hypothesis 通过。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        claim = await create_claim_with_evidence(
            session,
            **_kwargs(seed),
            claim_text="只有缺口，标为假设",
            evidence=[(seed.context_evidence.id, "gap")],
            state="hypothesis",
        )
        observed["state"] = claim.state

    await _with_session(scenario)

    assert observed["state"] == "hypothesis"


@pytest.mark.anyio
async def test_create_claim_accepts_gap_only_blocked_state() -> None:
    """只有 gap 时 blocked 通过。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        claim = await create_claim_with_evidence(
            session,
            **_kwargs(seed),
            claim_text="只有缺口，标为受阻",
            evidence=[(seed.context_evidence.id, "gap")],
            state="blocked",
        )
        observed["state"] = claim.state

    await _with_session(scenario)

    assert observed["state"] == "blocked"


@pytest.mark.anyio
async def test_create_claim_accepts_confirmed_state_with_support_evidence() -> None:
    """有 support 时 confirmed 通过。gap 同时满足反证要求。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        claim = await create_claim_with_evidence(
            session,
            **_kwargs(seed),
            claim_text="有支持证据的已确认主张",
            evidence=[
                (seed.support_evidence.id, "support"),
                (seed.context_evidence.id, "gap"),
            ],
            state="confirmed",
        )
        observed["state"] = claim.state

    await _with_session(scenario)

    assert observed["state"] == "confirmed"


@pytest.mark.anyio
async def test_create_claim_accepts_directional_state_with_counter_evidence() -> None:
    """有 counter 时 directional 通过。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        claim = await create_claim_with_evidence(
            session,
            **_kwargs(seed),
            claim_text="有反证的方向性主张",
            evidence=[(seed.counter_evidence.id, "counter")],
            state="directional",
        )
        observed["state"] = claim.state

    await _with_session(scenario)

    assert observed["state"] == "directional"


@pytest.mark.anyio
async def test_assert_gap_only_state_valid_lists_only_violations() -> None:
    """批量校验只报违规 claim。说明里带 claim ID。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        invalid = await create_claim(
            session,
            **_kwargs(seed),
            claim_text="仓储层写入的违规主张",
            state="confirmed",
        )
        valid_gap = await create_claim(
            session,
            **_kwargs(seed),
            claim_text="只有缺口的假设",
            state="hypothesis",
        )
        valid_support = await create_claim(
            session,
            **_kwargs(seed),
            claim_text="有支持证据的主张",
            state="confirmed",
        )
        violations = assert_gap_only_state_valid(
            [
                (invalid, ["gap"]),
                (valid_gap, ["gap", "context"]),
                (valid_support, ["support", "gap"]),
            ]
        )
        observed["violations"] = violations
        observed["invalid_id"] = str(invalid.id)
        observed["empty"] = assert_gap_only_state_valid([])

    await _with_session(scenario)

    violations = observed["violations"]
    assert isinstance(violations, list)
    assert len(violations) == 1
    assert observed["invalid_id"] in violations[0]
    assert "confirmed" in violations[0]
    assert observed["empty"] == []


def test_claim_report_columns_exist_and_are_nullable() -> None:
    """报告合同的五列存在且可空。"""
    columns = Claim.__table__.columns
    for name in REPORT_COLUMNS:
        assert name in columns
        assert columns[name].nullable is True


@pytest.mark.anyio
async def test_claim_report_columns_default_to_none() -> None:
    """存量写法不填新列时，五列都保持 None。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        claim = await create_claim_with_evidence(
            session,
            **_kwargs(seed),
            claim_text="存量写法的主张",
            evidence=[(seed.counter_evidence.id, "counter")],
        )
        await session.commit()
        await session.refresh(claim)
        observed["values"] = {name: getattr(claim, name) for name in REPORT_COLUMNS}

    await _with_session(scenario)

    assert observed["values"] == {name: None for name in REPORT_COLUMNS}


@pytest.mark.anyio
async def test_claim_is_isolated_by_workspace() -> None:
    """工作区 B 查不到工作区 A 的 claim 与证据关联。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        claim = await create_claim_with_evidence(
            session,
            **_kwargs(seed),
            claim_text="工作区 A 的主张",
            evidence=[(seed.counter_evidence.id, "counter")],
        )
        observed["foreign_get"] = await get_claim(
            session,
            workspace_id=seed.workspace_b.id,
            claim_id=claim.id,
        )
        observed["foreign_list"] = await list_claims(
            session,
            workspace_id=seed.workspace_b.id,
        )
        observed["foreign_evidence"] = await list_evidence(
            session,
            claim_id=claim.id,
            workspace_id=seed.workspace_b.id,
        )
        observed["own_get"] = await get_claim(
            session,
            workspace_id=seed.workspace_a.id,
            claim_id=claim.id,
        )

    await _with_session(scenario)

    assert observed["foreign_get"] is None
    assert observed["foreign_list"] == []
    assert observed["foreign_evidence"] == []
    assert observed["own_get"] is not None


@pytest.mark.anyio
async def test_batch_check_names_the_claim_without_counter_evidence() -> None:
    """批量校验返回缺反证的 claim。完整 claim 不在结果里。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        complete = await create_claim_with_evidence(
            session,
            **_kwargs(seed),
            claim_text="完整主张",
            evidence=[(seed.counter_evidence.id, "counter")],
        )
        incomplete = await create_claim(
            session,
            **_kwargs(seed),
            claim_text="缺少反证的主张",
        )
        await link_evidence(
            session,
            claim_id=incomplete.id,
            evidence_id=seed.support_evidence.id,
            role="support",
        )
        missing = await assert_counter_evidence_complete(
            session,
            [complete, incomplete],
        )
        observed["missing_ids"] = [claim.id for claim in missing]
        observed["incomplete_id"] = incomplete.id
        observed["empty"] = await assert_counter_evidence_complete(session, [])

    await _with_session(scenario)

    assert observed["missing_ids"] == [observed["incomplete_id"]]
    assert observed["empty"] == []


@pytest.mark.anyio
async def test_create_claim_accepts_mapping_and_alias_forms() -> None:
    """证据关联支持映射、字典与 evidence_roles 别名。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        from_mapping = await create_claim_with_evidence(
            session,
            **_kwargs(seed),
            claim_text="映射形式",
            evidence={seed.counter_evidence.id: "counter"},
        )
        from_dict = await create_claim_with_evidence(
            session,
            **_kwargs(seed),
            claim_text="字典形式",
            evidence_roles=[
                {"evidence_id": seed.context_evidence.id, "role": "gap"},
            ],
        )
        mapping_links = await list_evidence(session, claim_id=from_mapping.id)
        dict_links = await list_evidence(session, claim_id=from_dict.id)
        observed["mapping_roles"] = [link.role for link in mapping_links]
        observed["dict_roles"] = [link.role for link in dict_links]

    await _with_session(scenario)

    assert observed["mapping_roles"] == ["counter"]
    assert observed["dict_roles"] == ["gap"]


def _load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "claims_migration",
        MIGRATION_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_follows_current_head_revision() -> None:
    """迁移必须接在当前主链头之后。

    原计划接在 202610210055 之后，与 N1 的 202610220056/057 形成双头。
    2026-10-26 合入时按 n1-change-requests 方案 A 重编号，
    改为挂在 202610220057 之后，claims 落到 058。
    """
    module = _load_migration()
    assert module.revision == "202610220058"
    assert module.down_revision == "202610220057"
    assert "This revision is source-only." in (module.__doc__ or "")


def test_migration_creates_and_drops_tables_in_order() -> None:
    """upgrade 先建 claims。downgrade 先删 claim_evidence。"""
    module = _load_migration()
    upgrade_source = python_inspect.getsource(module.upgrade)
    downgrade_source = python_inspect.getsource(module.downgrade)

    assert upgrade_source.index('create_table(\n        "claims"') < upgrade_source.index(
        'create_table(\n        "claim_evidence"'
    )
    assert downgrade_source.index('drop_table("claim_evidence")') < downgrade_source.index(
        'drop_table("claims")'
    )
    assert "automation_" not in upgrade_source


def _model_check_names(table: Table) -> set[str]:
    """取模型表的 CHECK 约束名。"""
    return {
        str(constraint.name)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }


def _migration_create_table_calls() -> dict[str, ast.Call]:
    """取迁移 upgrade 里的 create_table 调用，按表名索引。"""
    module = _load_migration()
    source = textwrap.dedent(python_inspect.getsource(module.upgrade))
    calls: dict[str, ast.Call] = {}
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "create_table":
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant):
            continue
        calls[str(node.args[0].value)] = node
    return calls


def _migration_check_names() -> dict[str, set[str]]:
    """取迁移里每个表的 CHECK 约束名。"""
    names: dict[str, set[str]] = {}
    for table, call in _migration_create_table_calls().items():
        found: set[str] = set()
        for arg in call.args[1:]:
            if (
                isinstance(arg, ast.Call)
                and isinstance(arg.func, ast.Attribute)
                and arg.func.attr == "CheckConstraint"
            ):
                for keyword in arg.keywords:
                    if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                        found.add(str(keyword.value.value))
        names[table] = found
    return names


def _migration_column_names() -> dict[str, set[str]]:
    """取迁移里每个表的列名。"""
    names: dict[str, set[str]] = {}
    for table, call in _migration_create_table_calls().items():
        found: set[str] = set()
        for arg in call.args[1:]:
            if (
                isinstance(arg, ast.Call)
                and isinstance(arg.func, ast.Attribute)
                and arg.func.attr == "Column"
                and arg.args
                and isinstance(arg.args[0], ast.Constant)
            ):
                found.add(str(arg.args[0].value))
        names[table] = found
    return names


def test_claim_check_constraint_names_match_migration() -> None:
    """模型与迁移 052 的 CHECK 约束名逐字相等。"""
    claim_names = _model_check_names(Claim.__table__)
    evidence_names = _model_check_names(ClaimEvidence.__table__)

    assert claim_names == {
        "ck_claims_state",
        "ck_claims_evidence_grade",
        "ck_claims_confidence_range",
    }
    assert evidence_names == {"ck_claim_evidence_role"}

    migration = _migration_check_names()
    assert migration["claims"] == claim_names
    assert migration["claim_evidence"] == evidence_names


def test_migration_adds_report_claim_columns() -> None:
    """迁移 052 建表时包含报告合同的五列。"""
    columns = _migration_column_names()["claims"]
    assert set(REPORT_COLUMNS) <= columns
