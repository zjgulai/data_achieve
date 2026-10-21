"""``authorizations``、``run_evidence_grades`` 与 ``task_runs`` 扩展列的单元守卫。

覆盖六件事：

1. 授权按工作区隔离。跨工作区查不到，也撤不掉。
2. 授权金额是 Decimal，写入读回不失精度。
3. 过期授权 ``authorization_is_usable`` 返回 False。复用 B2 的纯函数。
4. ``run_evidence_grades`` 保存 B2 dataclass 的全部字段，含 entity_count。
5. ``task_runs`` 的新列全部可空。存量行读取为 None。
6. 迁移 202610200050 接在 049 之后，downgrade 删除三张表。

本文件只用内存 SQLite。它不连接真实 Postgres。
"""

from __future__ import annotations

import importlib.util
import inspect as python_inspect
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.authorization import Authorization
from data_intelligence_hub.models.project import Project
from data_intelligence_hub.models.run import Run
from data_intelligence_hub.models.source import Source
from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.models.user import User
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.authorizations import (
    create_authorization,
    get_authorization,
    list_authorizations,
    revoke_authorization,
)
from data_intelligence_hub.repositories.run_evidence_grades import (
    create_grade,
    get_grade_by_run,
)
from data_intelligence_hub.tool_catalog.evidence_grade import (
    EvidenceGrade,
    authorization_is_usable,
)

API_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = API_ROOT / "alembic/versions/202610200050_authorizations_and_ledger.py"

# 契约冻结 v1 §1.3 的扩展列。idempotency_key_hash 由 B1 的迁移 046 添加。
TASK_RUN_EXTENSION_COLUMNS = {
    "project_id",
    "run_id",
    "step_index",
    "unit",
    "quantity",
    "unit_price",
    "total_cost_usd",
    "remaining_budget",
    "provider",
    "provider_run_id",
    "endpoint_type",
    "evidence_grade",
    "schema_version",
    "idempotency_key_hash",
    "updated_at",
}

Scenario = Callable[[AsyncSession], Awaitable[None]]


class Seed:
    """一段用例需要的租户数据。"""

    def __init__(
        self,
        *,
        owner: User,
        workspace_a: Workspace,
        workspace_b: Workspace,
        project_a: Project,
        project_b: Project,
    ) -> None:
        self.owner = owner
        self.workspace_a = workspace_a
        self.workspace_b = workspace_b
        self.project_a = project_a
        self.project_b = project_b


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
    """建两个工作区与两个项目。"""
    owner = User(
        email=f"auth-{uuid.uuid4().hex}@example.com",
        password_hash="x",
        name="Owner",
    )
    session.add(owner)
    await session.flush()
    workspace_a = Workspace(
        name="Workspace A",
        slug=f"auth-a-{uuid.uuid4().hex}",
        owner_id=owner.id,
    )
    workspace_b = Workspace(
        name="Workspace B",
        slug=f"auth-b-{uuid.uuid4().hex}",
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
    return Seed(
        owner=owner,
        workspace_a=workspace_a,
        workspace_b=workspace_b,
        project_a=project_a,
        project_b=project_b,
    )


def _scope() -> dict[str, object]:
    return {
        "template_id": "t1_voc",
        "markets": ["US", "DE"],
        "window_days": 60,
    }


@pytest.mark.anyio
async def test_authorization_round_trip_keeps_decimal_precision() -> None:
    """授权金额用 Numeric(12, 6)。0.000001 读回仍是 Decimal。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        now = datetime.now(UTC)
        record = await create_authorization(
            session,
            workspace_id=seed.workspace_a.id,
            project_id=seed.project_a.id,
            scope=_scope(),
            max_cost_usd=Decimal("10.000001"),
            approver=seed.owner.id,
            granted_at=now,
            expires_at=now + timedelta(days=1),
        )
        await session.commit()
        await session.refresh(record)
        observed["max_cost_usd"] = record.max_cost_usd
        observed["scope"] = record.scope
        observed["gate_status"] = record.gate_status
        observed["approver"] = record.approver

    await _with_session(scenario)

    assert observed["max_cost_usd"] == Decimal("10.000001")
    assert isinstance(observed["max_cost_usd"], Decimal)
    assert observed["scope"] == _scope()
    assert observed["gate_status"] == "pending"


@pytest.mark.anyio
async def test_authorization_is_isolated_by_workspace() -> None:
    """工作区 B 查不到、也撤不掉工作区 A 的授权。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        now = datetime.now(UTC)
        record = await create_authorization(
            session,
            workspace_id=seed.workspace_a.id,
            project_id=seed.project_a.id,
            scope=_scope(),
            max_cost_usd=Decimal("5"),
            approver=seed.owner.id,
            expires_at=now + timedelta(days=1),
        )
        await session.flush()
        observed["foreign_get"] = await get_authorization(
            session,
            workspace_id=seed.workspace_b.id,
            authorization_id=record.id,
        )
        observed["foreign_list"] = await list_authorizations(
            session,
            workspace_id=seed.workspace_b.id,
        )
        observed["foreign_revoke"] = await revoke_authorization(
            session,
            workspace_id=seed.workspace_b.id,
            authorization_id=record.id,
        )
        observed["own_get"] = await get_authorization(
            session,
            workspace_id=seed.workspace_a.id,
            authorization_id=record.id,
        )
        observed["revoked_at_after_foreign_attempt"] = record.revoked_at

    await _with_session(scenario)

    assert observed["foreign_get"] is None
    assert observed["foreign_list"] == []
    assert observed["foreign_revoke"] is None
    assert observed["own_get"] is not None
    assert observed["revoked_at_after_foreign_attempt"] is None


@pytest.mark.anyio
async def test_revoke_sets_revoked_at_once() -> None:
    """撤销只写一次时间。重复撤销不改变首次时间。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        now = datetime.now(UTC)
        record = await create_authorization(
            session,
            workspace_id=seed.workspace_a.id,
            project_id=seed.project_a.id,
            scope=_scope(),
            max_cost_usd=Decimal("5"),
            approver=seed.owner.id,
            expires_at=now + timedelta(days=1),
        )
        first = await revoke_authorization(
            session,
            workspace_id=seed.workspace_a.id,
            authorization_id=record.id,
            revoked_at=now,
        )
        second = await revoke_authorization(
            session,
            workspace_id=seed.workspace_a.id,
            authorization_id=record.id,
            revoked_at=now + timedelta(hours=1),
        )
        observed["first"] = None if first is None else first.revoked_at
        observed["second"] = None if second is None else second.revoked_at

    await _with_session(scenario)

    assert observed["first"] == observed["second"]


def test_expired_authorization_is_not_usable() -> None:
    """过期授权回落到 L3。判断函数来自 B2，本任务不修改它。"""
    now = datetime.now(UTC)
    granted = now - timedelta(hours=2)
    valid = SimpleNamespace(expires_at=now + timedelta(seconds=1))
    expired = SimpleNamespace(expires_at=now - timedelta(seconds=1))

    assert authorization_is_usable(valid, now) is True
    assert authorization_is_usable(expired, now) is False
    assert authorization_is_usable(None, now) is False
    assert granted < now


def test_authorization_defaults_follow_contract() -> None:
    """门禁默认值来自契约：G-Plan 与 pending。"""
    assert Authorization.__table__.c.gate_id.default.arg == "G-Plan"
    assert Authorization.__table__.c.gate_status.default.arg == "pending"


@pytest.mark.anyio
async def test_evidence_grade_record_matches_b2_dataclass_fields() -> None:
    """等级表保存 B2 dataclass 的全部字段，含 T4 的 entity_count。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        run = Run(
            workspace_id=seed.workspace_a.id,
            project_id=seed.project_a.id,
            status="running",
            execution_mode="live",
            trigger="manual",
            records_count=0,
        )
        session.add(run)
        await session.flush()
        record = await create_grade(
            session,
            run_id=run.id,
            live_call=True,
            authorization_id=None,
            sample_n=20,
            required_n=20,
            window_days=30,
            required_window_days=30,
            source_count=2,
            required_source_count=2,
            entity_count=20,
            required_entity_count=20,
            grade=EvidenceGrade.L4_AUTHORIZED_LIVE,
        )
        await session.commit()
        await session.refresh(record)
        stored = await get_grade_by_run(session, run.id)
        assert stored is not None
        observed["grade"] = stored.grade
        observed["entity_count"] = stored.entity_count
        observed["required_entity_count"] = stored.required_entity_count
        observed["sample_n"] = stored.sample_n

    await _with_session(scenario)

    assert observed["grade"] == EvidenceGrade.L4_AUTHORIZED_LIVE.value
    assert observed["entity_count"] == 20
    assert observed["required_entity_count"] == 20
    assert observed["sample_n"] == 20


def test_task_run_has_all_contract_extension_columns() -> None:
    """契约 §1.3 的列必须全部存在。"""
    names = {column.name for column in TaskRun.__table__.columns}
    assert names >= TASK_RUN_EXTENSION_COLUMNS
    # 契约规定不加 _usd 后缀。
    assert "remaining_budget_usd" not in names


@pytest.mark.anyio
async def test_task_run_extension_columns_are_nullable_for_existing_rows() -> None:
    """存量行没有这些值。全部列必须可空，读取为 None。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        seed = await _seed(session)
        source = Source(
            workspace_id=seed.workspace_a.id,
            project_id=seed.project_a.id,
            name="Source",
            type="manual_json",
            config={},
        )
        session.add(source)
        await session.flush()
        task = CollectionTask(
            workspace_id=seed.workspace_a.id,
            project_id=seed.project_a.id,
            source_id=source.id,
            collector_type="manual_json",
            name="Task",
            status="active",
        )
        session.add(task)
        await session.flush()
        run = TaskRun(
            task_id=task.id,
            workspace_id=seed.workspace_a.id,
            status="success",
            records_count=0,
            entities_count=0,
            logs=[],
            created_at=datetime.now(UTC),
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        observed["nulls"] = {
            name: getattr(run, name) for name in sorted(TASK_RUN_EXTENSION_COLUMNS)
        }

    await _with_session(scenario)

    nulls = observed["nulls"]
    assert isinstance(nulls, dict)
    for name, value in nulls.items():
        assert value is None, name


def _load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "authorizations_and_ledger_migration",
        MIGRATION_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_follows_b3_01_revision() -> None:
    """迁移必须接在 B3-01 的 049 之后。"""
    module = _load_migration()
    assert module.revision == "202610200050"
    assert module.down_revision == "202610200049"


def test_migration_creates_contract_tables_and_downgrade_drops_them() -> None:
    """三张表的表名来自契约。downgrade 必须反向删除。"""
    module = _load_migration()
    upgrade_source = python_inspect.getsource(module.upgrade)
    downgrade_source = python_inspect.getsource(module.downgrade)

    for table in ("authorizations", "run_ledger_entries", "run_evidence_grades"):
        assert f'create_table(\n        "{table}"' in upgrade_source, table
        assert f'drop_table("{table}")' in downgrade_source, table

    # 废弃名不得出现在 upgrade 的建表语句里。
    assert "automation_" not in upgrade_source
    assert 'create_table(\n        "cost_ledger_entries"' not in upgrade_source
