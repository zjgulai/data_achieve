"""``run_ledger_entries`` 与账本服务的单元守卫。

覆盖五件事：

1. 金额全程 Decimal。写入读回不失精度，0.000001 量级也保持。
2. float 输入被拒绝，不得静默转换。
3. ``sum_cost`` 只汇总 settle 与 release，按 run 隔离。
4. ``remaining_budget`` 用授权上限减已结算成本。
5. 仓储层不调用 ``commit``。

本文件只用内存 SQLite。它不连接真实 Postgres。
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.run import Run
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.run_ledger import add_entry
from data_intelligence_hub.services.run_ledger import (
    record_entry,
    remaining_budget,
    sum_cost,
)

API_ROOT = Path(__file__).resolve().parents[2]
REPOSITORIES = API_ROOT / "src/data_intelligence_hub/repositories"

Scenario = Callable[[AsyncSession], Awaitable[None]]


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


async def _seed_run(
    session: AsyncSession,
    *,
    slug: str = "ledger",
) -> Run:
    """建一个最小 workspace + project + run。"""
    owner = User(email=f"{slug}-{uuid.uuid4().hex}@example.com", password_hash="x", name="Owner")
    session.add(owner)
    await session.flush()
    workspace = Workspace(name=slug, slug=f"{slug}-{uuid.uuid4().hex}", owner_id=owner.id)
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
    run = Run(
        workspace_id=workspace.id,
        project_id=project.id,
        status="running",
        execution_mode="live",
        trigger="manual",
        records_count=0,
    )
    session.add(run)
    await session.flush()
    return run


@pytest.mark.anyio
async def test_amount_round_trip_keeps_six_decimals() -> None:
    """0.000001 写入再读回，仍是 Decimal 且数值不变。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        run = await _seed_run(session)
        entry = await record_entry(
            session,
            run_id=run.id,
            entry_kind="settle",
            amount_usd=Decimal("0.000001"),
            balance_after_usd=Decimal("9.999999"),
            idempotency_key="round-trip-1",
        )
        await session.commit()
        await session.refresh(entry)
        observed["amount"] = entry.amount_usd
        observed["balance"] = entry.balance_after_usd

    await _with_session(scenario)

    assert observed["amount"] == Decimal("0.000001")
    assert isinstance(observed["amount"], Decimal)
    assert observed["balance"] == Decimal("9.999999")
    assert isinstance(observed["balance"], Decimal)


@pytest.mark.anyio
async def test_float_amount_is_rejected() -> None:
    """float 会把二进制误差带进账本，必须拒绝。"""
    async def scenario(session: AsyncSession) -> None:
        run = await _seed_run(session)
        with pytest.raises(TypeError):
            await record_entry(
                session,
                run_id=run.id,
                entry_kind="settle",
                amount_usd=0.1,
                balance_after_usd=Decimal("1"),
                idempotency_key="float-1",
            )

    await _with_session(scenario)


@pytest.mark.anyio
async def test_sum_cost_aggregates_only_settle_and_release_per_run() -> None:
    """成本只来自 settle 与 release。estimate、reserve、accrued 不计入。"""
    observed: dict[str, Decimal] = {}

    async def scenario(session: AsyncSession) -> None:
        run_a = await _seed_run(session, slug="run-a")
        run_b = await _seed_run(session, slug="run-b")
        rows = [
            (run_a, "settle", Decimal("0.1"), "a-settle-1"),
            (run_a, "settle", Decimal("0.2"), "a-settle-2"),
            (run_a, "release", Decimal("-0.05"), "a-release-1"),
            (run_a, "estimate", Decimal("5"), "a-estimate-1"),
            (run_a, "reserve", Decimal("2"), "a-reserve-1"),
            (run_a, "accrued", Decimal("1"), "a-accrued-1"),
            (run_b, "settle", Decimal("1"), "b-settle-1"),
        ]
        for run, kind, amount, key in rows:
            await add_entry(
                session,
                run_id=run.id,
                entry_kind=kind,
                amount_usd=amount,
                balance_after_usd=Decimal("0"),
                idempotency_key=key,
            )
        observed["a"] = await sum_cost(session, run_a.id)
        observed["b"] = await sum_cost(session, run_b.id)

    await _with_session(scenario)

    assert observed["a"] == Decimal("0.25")
    assert observed["b"] == Decimal("1")
    assert isinstance(observed["a"], Decimal)
    assert isinstance(observed["b"], Decimal)


@pytest.mark.anyio
async def test_sum_cost_returns_zero_decimal_for_empty_run() -> None:
    """没有账本行时返回 Decimal("0")，不是 float 0.0。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        run = await _seed_run(session, slug="empty-run")
        observed["value"] = await sum_cost(session, run.id)

    await _with_session(scenario)

    assert observed["value"] == Decimal("0")
    assert isinstance(observed["value"], Decimal)


@pytest.mark.anyio
async def test_remaining_budget_subtracts_settled_cost() -> None:
    """剩余额度 = 授权上限 - 已结算成本。结果保留 Decimal 精度。"""
    observed: dict[str, Decimal] = {}

    async def scenario(session: AsyncSession) -> None:
        run = await _seed_run(session, slug="budget-run")
        await add_entry(
            session,
            run_id=run.id,
            entry_kind="settle",
            amount_usd=Decimal("0.250000"),
            balance_after_usd=Decimal("1.750001"),
            idempotency_key="budget-settle-1",
        )
        observed["remaining"] = await remaining_budget(
            session,
            run_id=run.id,
            max_cost_usd=Decimal("2.000001"),
        )
        observed["overdrawn"] = await remaining_budget(
            session,
            run_id=run.id,
            max_cost_usd=Decimal("0.1"),
        )

    await _with_session(scenario)

    assert observed["remaining"] == Decimal("1.750001")
    assert observed["overdrawn"] == Decimal("-0.15")


@pytest.mark.anyio
async def test_idempotency_key_is_unique() -> None:
    """同一个幂等键只能写一行。第二行被唯一约束拒绝。"""
    rejected: dict[str, bool] = {}

    async def scenario(session: AsyncSession) -> None:
        run = await _seed_run(session, slug="idem-run")
        await add_entry(
            session,
            run_id=run.id,
            entry_kind="settle",
            amount_usd=Decimal("0.1"),
            balance_after_usd=Decimal("0"),
            idempotency_key="same-key",
        )
        await session.commit()
        try:
            await add_entry(
                session,
                run_id=run.id,
                entry_kind="settle",
                amount_usd=Decimal("0.1"),
                balance_after_usd=Decimal("0"),
                idempotency_key="same-key",
            )
            await session.commit()
        except IntegrityError:
            rejected["value"] = True
            await session.rollback()
        else:
            rejected["value"] = False

    await _with_session(scenario)

    assert rejected["value"] is True


@pytest.mark.anyio
async def test_unknown_entry_kind_is_rejected() -> None:
    """entry_kind 只允许契约 §2.7.1 的六个取值。"""

    async def scenario(session: AsyncSession) -> None:
        run = await _seed_run(session, slug="kind-run")
        with pytest.raises(ValueError):
            await record_entry(
                session,
                run_id=run.id,
                entry_kind="charge",
                amount_usd=Decimal("1"),
                balance_after_usd=Decimal("0"),
                idempotency_key="kind-1",
            )

    await _with_session(scenario)


def test_repositories_do_not_commit() -> None:
    """仓储层只 flush。三个新仓储都必须保持 0 次 commit。"""
    for name in ("authorizations.py", "run_ledger.py", "run_evidence_grades.py"):
        source = (REPOSITORIES / name).read_text(encoding="utf-8")
        assert "session.commit" not in source, name


def test_ledger_rows_are_append_only_in_repository() -> None:
    """账本仓储不得更新或删除行。"""
    source = (REPOSITORIES / "run_ledger.py").read_text(encoding="utf-8")
    assert ".delete(" not in source
    assert "session.delete" not in source
