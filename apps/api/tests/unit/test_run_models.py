"""运行表 ``runs`` 与 ``run_steps`` 的单元守卫。

覆盖五组规则：

1. 三组枚举取值精确。``degraded``、``held``、``partial`` 不得出现。
2. 运行与步骤的状态迁移只允许前向。终态不得回到 ``running``。
3. 同工作区同幂等键只能一行。不同工作区同键各自成立。
4. 数据库 CHECK 约束拒绝非法状态与非法结果。
5. ``run_steps`` 按 ``step_index`` 排序读取。

本文件只用内存 SQLite。它不连接真实 Postgres。
迁移检查只读源文件，不执行 DDL。
"""

from __future__ import annotations

import importlib.util
import inspect as python_inspect
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from types import ModuleType

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base, Project, User, Workspace
from data_intelligence_hub.models.run import (
    Run,
    RunOutcome,
    RunStatus,
    RunStepStatus,
)
from data_intelligence_hub.repositories.runs import (
    add_step,
    create_run,
    get_run,
    list_runs,
    list_steps,
    transition_run,
    transition_step,
)

API_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = API_ROOT / "alembic/versions/202610200049_runs_and_steps.py"
_HASH = "c" * 64

Scenario = Callable[[AsyncSession], Awaitable[None]]


def test_run_status_enum_is_exact() -> None:
    """``runs.status`` 只有五个值。degraded 与 held 不得出现。"""
    values = {item.value for item in RunStatus}
    assert values == {"queued", "running", "completed", "failed", "cancelled"}
    assert "degraded" not in values, "degraded 属于 health_status"
    assert "held" not in values, "held 属于 workflow_plans 与 fixture 运行表"


def test_run_step_status_enum_is_exact() -> None:
    """``run_steps.status`` 只有七个值。"""
    values = {item.value for item in RunStepStatus}
    assert values == {
        "pending",
        "running",
        "success",
        "empty",
        "config_gated",
        "failed",
        "skipped",
    }
    assert "degraded" not in values
    assert "held" not in values


def test_run_outcome_enum_is_exact() -> None:
    """两处 outcome 只有四个值。partial 不得出现。"""
    values = {item.value for item in RunOutcome}
    assert values == {"success", "empty", "config_gated", "failed"}
    assert "partial" not in values, "部分成功用 success 加 records_count 表达"


def _make_engine() -> AsyncEngine:
    return create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


async def _with_session(callback: Scenario) -> None:
    """在内存 SQLite 上跑一段用例。"""
    engine = _make_engine()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            await callback(session)
    finally:
        await engine.dispose()


async def _seed(
    session: AsyncSession,
) -> tuple[Workspace, Project, Workspace, Project]:
    """建两个工作区与两个项目。"""
    owner = User(
        email=f"run-{uuid.uuid4().hex}@example.com",
        password_hash="x",
        name="Run Owner",
    )
    session.add(owner)
    await session.flush()

    workspace_a = Workspace(
        name="Runs A",
        slug=f"runs-a-{uuid.uuid4().hex}",
        owner_id=owner.id,
    )
    workspace_b = Workspace(
        name="Runs B",
        slug=f"runs-b-{uuid.uuid4().hex}",
        owner_id=owner.id,
    )
    session.add_all([workspace_a, workspace_b])
    await session.flush()

    project_a = Project(
        workspace_id=workspace_a.id,
        name="Runs A Project",
        domain="mother_baby",
        owner_id=owner.id,
    )
    project_b = Project(
        workspace_id=workspace_b.id,
        name="Runs B Project",
        domain="mother_baby",
        owner_id=owner.id,
    )
    session.add_all([project_a, project_b])
    await session.flush()
    return workspace_a, project_a, workspace_b, project_b


@pytest.mark.anyio
async def test_database_rejects_forbidden_status_and_outcome() -> None:
    """CHECK 约束必须拒绝 degraded、held 与 partial。"""
    observed: dict[str, bool] = {}

    async def scenario(session: AsyncSession) -> None:
        workspace, project, _, _ = await _seed(session)
        await session.commit()
        workspace_id = workspace.id
        project_id = project.id

        def bad_run(*, status: str, outcome: str | None = None) -> Run:
            return Run(
                workspace_id=workspace_id,
                project_id=project_id,
                status=status,
                outcome=outcome,
                execution_mode="live",
                trigger="manual",
                records_count=0,
            )

        for label, record in (
            ("degraded", bad_run(status="degraded")),
            ("held", bad_run(status="held")),
            ("partial", bad_run(status="completed", outcome="partial")),
        ):
            session.add(record)
            try:
                await session.commit()
            except IntegrityError:
                observed[label] = True
                await session.rollback()
            else:
                observed[label] = False
                await session.rollback()

    await _with_session(scenario)
    assert observed["degraded"] is True, "runs.status 接受了 degraded"
    assert observed["held"] is True, "runs.status 接受了 held"
    assert observed["partial"] is True, "outcome 接受了 partial"


@pytest.mark.anyio
async def test_run_transitions_are_forward_only() -> None:
    """合法迁移通过。终态回到 running 必须被拒绝。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        workspace, project, _, _ = await _seed(session)
        await session.commit()
        workspace_id = workspace.id
        project_id = project.id

        run = await create_run(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        await session.commit()
        run_id = run.id

        running = await transition_run(
            session,
            workspace_id=workspace_id,
            run_id=run_id,
            status=RunStatus.RUNNING,
        )
        # 同一个 Session 返回同一个对象。先记下 running 阶段的值。
        running_status = None if running is None else running.status
        started_at = None if running is None else running.started_at

        completed = await transition_run(
            session,
            workspace_id=workspace_id,
            run_id=run_id,
            status="completed",
            outcome="success",
            records_count=7,
        )
        await session.commit()

        observed["running_status"] = running_status
        observed["started_at"] = started_at
        observed["completed_status"] = None if completed is None else completed.status
        observed["outcome"] = None if completed is None else completed.outcome
        observed["records_count"] = None if completed is None else completed.records_count

        for terminal in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED):
            if terminal is RunStatus.COMPLETED:
                target_id = run_id
            else:
                other = await create_run(
                    session,
                    workspace_id=workspace_id,
                    project_id=project_id,
                    status=terminal,
                )
                await session.commit()
                target_id = other.id
            with pytest.raises(ValueError, match="非法的运行状态迁移"):
                await transition_run(
                    session,
                    workspace_id=workspace_id,
                    run_id=target_id,
                    status=RunStatus.RUNNING,
                )
        observed["terminal_rejected"] = True

    await _with_session(scenario)
    assert observed["running_status"] == "running"
    assert observed["started_at"] is not None, "进入 running 时必须补开始时间"
    assert observed["completed_status"] == "completed"
    assert observed["outcome"] == "success"
    assert observed["records_count"] == 7
    assert observed["terminal_rejected"] is True


@pytest.mark.anyio
async def test_step_transitions_are_forward_only() -> None:
    """步骤状态只允许前向迁移。终态回到 running 必须被拒绝。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        workspace, project, _, _ = await _seed(session)
        await session.commit()
        run = await create_run(
            session,
            workspace_id=workspace.id,
            project_id=project.id,
        )
        await session.commit()

        step = await add_step(
            session,
            run_id=run.id,
            step_index=0,
            endpoint_type="search",
            collector_type="generic_web",
        )
        await session.commit()
        step_id = step.id

        running = await transition_step(
            session,
            run_id=run.id,
            step_id=step_id,
            status=RunStepStatus.RUNNING,
        )
        # 同一个 Session 返回同一个对象。先记下 running 阶段的值。
        running_status = None if running is None else running.status

        success = await transition_step(
            session,
            run_id=run.id,
            step_id=step_id,
            status="success",
            outcome="success",
            records_count=3,
        )
        await session.commit()

        observed["running_status"] = running_status
        observed["final_status"] = None if success is None else success.status
        observed["outcome"] = None if success is None else success.outcome
        observed["finished_at"] = None if success is None else success.finished_at

        with pytest.raises(ValueError, match="非法的步骤状态迁移"):
            await transition_step(
                session,
                run_id=run.id,
                step_id=step_id,
                status=RunStepStatus.RUNNING,
            )
        observed["terminal_rejected"] = True

    await _with_session(scenario)
    assert observed["running_status"] == "running"
    assert observed["final_status"] == "success"
    assert observed["outcome"] == "success"
    assert observed["finished_at"] is not None, "进入终态时必须补结束时间"
    assert observed["terminal_rejected"] is True


@pytest.mark.anyio
async def test_same_workspace_same_idempotency_key_creates_one_row() -> None:
    """同工作区同幂等键只保留一行。直接重复插入被唯一索引拒绝。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        workspace, project, _, _ = await _seed(session)
        await session.commit()
        workspace_id = workspace.id
        project_id = project.id

        first = await create_run(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            idempotency_key_hash=_HASH,
        )
        await session.commit()
        first_id = first.id

        second = await create_run(
            session,
            workspace_id=workspace_id,
            project_id=project_id,
            idempotency_key_hash=_HASH,
        )
        await session.commit()

        total = await session.scalar(
            select(func.count())
            .select_from(Run)
            .where(Run.workspace_id == workspace_id)
        )
        observed["first_id"] = first_id
        observed["second_id"] = second.id
        observed["total"] = int(total or 0)

        # 绕过仓储的先查后插，直接插入重复行。数据库必须拒绝。
        session.add(
            Run(
                workspace_id=workspace_id,
                project_id=project_id,
                status=RunStatus.QUEUED.value,
                execution_mode="live",
                trigger="manual",
                records_count=0,
                idempotency_key_hash=_HASH,
            )
        )
        try:
            await session.commit()
        except IntegrityError:
            observed["db_rejected"] = True
            await session.rollback()
        else:
            observed["db_rejected"] = False
            await session.rollback()

    await _with_session(scenario)
    assert observed["first_id"] == observed["second_id"], "同键必须返回原行"
    assert observed["total"] == 1
    assert observed["db_rejected"] is True, "部分唯一索引未拒绝重复幂等键"


@pytest.mark.anyio
async def test_different_workspaces_allow_the_same_idempotency_key() -> None:
    """不同工作区同键各自成立。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        workspace_a, project_a, workspace_b, project_b = await _seed(session)
        await session.commit()

        run_a = await create_run(
            session,
            workspace_id=workspace_a.id,
            project_id=project_a.id,
            idempotency_key_hash=_HASH,
        )
        run_b = await create_run(
            session,
            workspace_id=workspace_b.id,
            project_id=project_b.id,
            idempotency_key_hash=_HASH,
        )
        await session.commit()

        total = await session.scalar(
            select(func.count())
            .select_from(Run)
            .where(Run.idempotency_key_hash == _HASH)
        )
        observed["run_a"] = run_a.id
        observed["run_b"] = run_b.id
        observed["total"] = int(total or 0)

    await _with_session(scenario)
    assert observed["run_a"] != observed["run_b"]
    assert observed["total"] == 2


@pytest.mark.anyio
async def test_list_steps_orders_by_step_index() -> None:
    """步骤按 ``step_index`` 升序返回。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        workspace, project, _, _ = await _seed(session)
        await session.commit()
        run = await create_run(
            session,
            workspace_id=workspace.id,
            project_id=project.id,
        )
        await session.commit()

        for index in (2, 0, 1):
            await add_step(
                session,
                run_id=run.id,
                step_index=index,
                endpoint_type=f"endpoint-{index}",
                collector_type="generic_web",
            )
        await session.commit()

        steps = await list_steps(session, run_id=run.id)
        observed["order"] = [step.step_index for step in steps]

    await _with_session(scenario)
    assert observed["order"] == [0, 1, 2]


@pytest.mark.anyio
async def test_reads_are_isolated_by_workspace_and_project() -> None:
    """跨工作区读不到运行。列表按项目过滤。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        workspace_a, project_a, workspace_b, project_b = await _seed(session)
        await session.commit()
        run = await create_run(
            session,
            workspace_id=workspace_a.id,
            project_id=project_a.id,
        )
        await session.commit()

        own = await get_run(
            session,
            workspace_id=workspace_a.id,
            run_id=run.id,
        )
        foreign = await get_run(
            session,
            workspace_id=workspace_b.id,
            run_id=run.id,
        )
        own_list = await list_runs(
            session,
            workspace_id=workspace_a.id,
            project_id=project_a.id,
        )
        foreign_list = await list_runs(
            session,
            workspace_id=workspace_b.id,
            project_id=project_b.id,
        )
        observed["own"] = None if own is None else own.id
        observed["foreign"] = foreign
        observed["own_list"] = [item.id for item in own_list]
        observed["foreign_list"] = list(foreign_list)

    await _with_session(scenario)
    assert observed["own"] is not None
    assert observed["foreign"] is None
    assert observed["own_list"] == [observed["own"]]
    assert observed["foreign_list"] == []


def _load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "runs_and_steps_migration",
        MIGRATION_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_revision_chain() -> None:
    """迁移必须接在 202610200048 之后，并进入版本链。"""
    module = _load_migration()
    assert module.revision == "202610200049"
    assert module.down_revision == "202610200048"

    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    revisions = {
        revision.revision for revision in ScriptDirectory.from_config(config).walk_revisions()
    }
    assert "202610200049" in revisions
    assert "This revision is source-only." in MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_downgrade_drops_steps_before_runs() -> None:
    """downgrade 必须先删 run_steps，再删 runs。"""
    module = _load_migration()
    source = python_inspect.getsource(module.downgrade)
    assert source.index('drop_table("run_steps")') < source.index('drop_table("runs")')


def test_migration_creates_contract_tables_only() -> None:
    """迁移只建 runs 与 run_steps。废弃名不得出现。"""
    module = _load_migration()
    upgrade_source = python_inspect.getsource(module.upgrade)
    assert 'create_table(\n        "runs"' in upgrade_source
    assert 'create_table(\n        "run_steps"' in upgrade_source

    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")
    for name in (
        "automation_runs",
        "automation_steps",
        "automation_authorizations",
        "cost_ledger_entries",
    ):
        assert name not in migration_source
