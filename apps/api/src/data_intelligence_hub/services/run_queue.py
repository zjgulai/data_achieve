"""持久运行队列。队列数据只存在 ``runs`` 表里。

队列语义：

1. 一行 ``runs`` 代表一次待执行或正在执行的运行。
2. worker 用条件更新领取一行。领取成功即持有租约。
3. worker 必须定期续期。进程崩溃后租约过期，其他 worker 可以重新领取。
4. 本模块只 flush，不 commit。事务边界在调用方。
5. 进程重启不丢任务。``queued`` 行留在数据库里，重启后仍可领取。

``runs`` 表所需列（B3-01 负责建表）：

====================== ================= ==================================
列                     类型              说明
====================== ================= ==================================
``id``                 uuid              主键
``status``             varchar(20)       ``queued`` / ``running`` /
                                         ``completed`` / ``failed`` /
                                         ``cancelled``
``lease_expires_at``   timestamptz 可空  租约到期时间
``created_at``         timestamptz       入队顺序
====================== ================= ==================================

可选列。存在时本模块会使用它们：

- ``worker_id``：持有租约的 worker 标识。存在时续期与释放会校验所有权。
- ``updated_at``：最后更新时间。
- ``started_at``：首次领取时写入。
- ``finished_at``：进入终态时写入。
- ``heartbeat_at``：每次续期时写入。
- ``task_id``：快速采集用它指向 ``collection_tasks`` 行。
- ``payload``：通用执行载荷。快速采集不需要它。

B3-01 的 ``runs`` 表当前没有 ``worker_id``。
此时队列用 ``expected_expires_at`` 做比较并交换。
租约被接管后，旧 worker 的续期会失败。
``RunQueueWorker`` 自动传入这个值。它见 ``run_queue_worker.py``。
本模块的单元测试使用带 ``worker_id`` 的回退表。

B3-01 的模型尚未落地时，本模块使用本地 Core Table 作回退。
回退表用于单元测试与本地开发。生产必须应用 B3-01 的迁移。
回退表与声明式模型不共享 MetaData，因此两者不会冲突。
"""

from __future__ import annotations

import importlib
import uuid
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, runtime_checkable

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Uuid,
    and_,
    case,
    func,
    or_,
    select,
    update,
)
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

RUNS_TABLE_NAME = "runs"

# 契约冻结 §2.1 的运行状态。队列只使用其中四个。
RUN_STATUS_QUEUED = "queued"
RUN_STATUS_RUNNING = "running"
RUN_TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})

_REQUIRED_COLUMNS = frozenset({"id", "status", "lease_expires_at", "created_at"})

# 回退表。独立 MetaData，绝不注册到 Base.metadata。
# 列与 B3-01 的 models/run.py 对齐，另加 worker_id 用于所有权测试。
_FALLBACK_METADATA = MetaData()
_FALLBACK_RUNS = Table(
    RUNS_TABLE_NAME,
    _FALLBACK_METADATA,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("workspace_id", Uuid(as_uuid=True), nullable=False),
    Column("project_id", Uuid(as_uuid=True), nullable=False),
    Column("task_id", Uuid(as_uuid=True)),
    Column("workflow_version_id", Uuid(as_uuid=True)),
    Column("status", String(20), nullable=False),
    Column("outcome", String(20)),
    Column("execution_mode", String(30), default="live", nullable=False),
    Column("trigger", String(30), default="manual", nullable=False),
    Column("idempotency_key_hash", String(64)),
    Column("evidence_grade", String(30)),
    Column("records_count", Integer, default=0, nullable=False),
    Column("error_message", String),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    Column("lease_expires_at", DateTime(timezone=True)),
    Column("worker_id", String(100)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True)),
    Column("heartbeat_at", DateTime(timezone=True)),
    Column("payload", JSON),
)


class RunQueueError(RuntimeError):
    """运行队列的基础异常。"""


class RunQueueSchemaError(RunQueueError):
    """``runs`` 表缺少队列所需列。"""


class RunQueueUnavailableError(RunQueueError):
    """``runs`` 表不存在或数据库不可用。"""


@runtime_checkable
class RunQueueRow(Protocol):
    """``runs`` 行在队列层的最小接口。

    该协议只描述队列必须读取的列。B3-01 的 ORM 模型满足这些列即可接入。
    """

    id: uuid.UUID
    status: str
    lease_expires_at: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class ClaimedRun:
    """一次成功领取的结果。

    支持解包：``run_id, lease_expires_at = claimed``。
    """

    run_id: uuid.UUID
    worker_id: str
    lease_expires_at: datetime
    previous_status: str
    task_id: uuid.UUID | None = None
    payload: dict[str, Any] | None = None

    def __iter__(self) -> Iterator[object]:
        yield self.run_id
        yield self.lease_expires_at


def fallback_runs_table() -> Table:
    """返回回退表。仅供测试与本地开发建表。"""
    return _FALLBACK_RUNS


def resolve_runs_table() -> Table:
    """解析 ``runs`` 表。

    优先使用 B3-01 的声明式模型。模型未落地时返回回退表。
    模型模块存在但找不到 ``runs`` 表时也返回回退表。
    生产缺表会在执行 SQL 时转成 ``RunQueueUnavailableError``。
    """
    for module_name in (
        "data_intelligence_hub.models.run",
        "data_intelligence_hub.models.runs",
    ):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        for value in vars(module).values():
            table = getattr(value, "__table__", None)
            if isinstance(table, Table) and table.name == RUNS_TABLE_NAME:
                return table
    return _FALLBACK_RUNS


async def enqueue_run(
    session: AsyncSession,
    *,
    run_id: uuid.UUID | None = None,
    values: Mapping[str, Any] | None = None,
    payload: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    table: Table | None = None,
) -> uuid.UUID:
    """写入一行 ``status=queued`` 的运行。

    ``values`` 用于补充必填列，例如 ``workspace_id``、``project_id`` 与 ``task_id``。
    队列字段由本函数拥有，调用方不能覆盖。
    ``payload`` 写入 ``runs.payload``。该列不存在时抛 ``RunQueueSchemaError``。

    本函数只 flush，不 commit。
    """
    resolved = _require_table(table)
    current = _as_utc(now or datetime.now(UTC))
    new_id = run_id or uuid.uuid4()

    row: dict[str, Any] = dict(values or {})
    if "execution_mode" in resolved.c:
        row.setdefault("execution_mode", "live")
    if "trigger" in resolved.c:
        row.setdefault("trigger", "manual")
    if "records_count" in resolved.c:
        row.setdefault("records_count", 0)
    row.update(
        {
            "id": new_id,
            "status": RUN_STATUS_QUEUED,
            "lease_expires_at": None,
            "created_at": current,
        }
    )
    if "worker_id" in resolved.c:
        row["worker_id"] = None
    if "updated_at" in resolved.c:
        row["updated_at"] = current
    if payload is not None:
        if "payload" not in resolved.c:
            raise RunQueueSchemaError(
                "runs.payload 列不存在。通用执行载荷需要该列。"
                "快速采集改用 task_id，不需要 payload。"
            )
        row["payload"] = dict(payload)

    try:
        await session.execute(resolved.insert().values(**row))
        await session.flush()
    except OperationalError as exc:
        raise RunQueueUnavailableError(
            "runs 表不可用。请确认已应用 B3-01 的迁移。"
        ) from exc
    except ProgrammingError as exc:
        # Postgres 在表不存在时抛 UndefinedTable，它是 ProgrammingError 的子类。
        # SQLite 走 OperationalError。两者都要按「迁移未应用」处理，
        # 否则生产会在入队处抛出裸的数据库异常。
        raise RunQueueUnavailableError(
            "runs 表不可用。请确认已应用 B3-01 的迁移。"
        ) from exc
    return new_id


async def claim_next_run(
    session: AsyncSession,
    worker_id: str,
    lease_seconds: float,
    *,
    now: datetime | None = None,
    table: Table | None = None,
) -> ClaimedRun | None:
    """领取一行可执行的运行。

    可领取条件：

    - ``status='queued'``；或
    - ``status='running'`` 且租约已过期。

    Postgres 用 ``SELECT ... FOR UPDATE SKIP LOCKED`` 加行锁。
    SQLite 不支持该语法。此时降级为带条件的 ``UPDATE ... WHERE id=(SELECT ...)``。
    条件更新失败说明被其他 worker 抢先。本函数最多重试 3 次。

    返回领取结果。没有可领取的行时返回 ``None``。
    本函数只 flush，不 commit。
    """
    if lease_seconds <= 0:
        raise ValueError("lease_seconds 必须大于 0")
    resolved = _require_table(table)
    current = _as_utc(now or datetime.now(UTC))
    expires_at = current + timedelta(seconds=lease_seconds)
    has_task_id = "task_id" in resolved.c
    has_payload = "payload" in resolved.c

    for _attempt in range(3):
        columns: list[Any] = [
            resolved.c.id,
            resolved.c.status,
            resolved.c.lease_expires_at,
        ]
        if has_task_id:
            columns.append(resolved.c.task_id)
        if has_payload:
            columns.append(resolved.c.payload)

        statement = (
            select(*columns)
            .where(_eligible_clause(resolved, current))
            .order_by(resolved.c.created_at.asc(), resolved.c.id.asc())
            .limit(1)
        )
        if _dialect_name(session) == "postgresql":
            statement = statement.with_for_update(skip_locked=True)

        row = (await session.execute(statement)).first()
        if row is None:
            return None

        previous_status = row[1]
        claimed_values: dict[str, Any] = {
            "status": RUN_STATUS_RUNNING,
            "lease_expires_at": expires_at,
        }
        if "worker_id" in resolved.c:
            claimed_values["worker_id"] = worker_id
        if "updated_at" in resolved.c:
            claimed_values["updated_at"] = current
        if previous_status == RUN_STATUS_QUEUED and "started_at" in resolved.c:
            claimed_values["started_at"] = func.coalesce(resolved.c.started_at, current)

        update_statement = (
            update(resolved)
            .where(
                resolved.c.id == row[0],
                _eligible_clause(resolved, current),
            )
            .values(**claimed_values)
            .returning(resolved.c.id)
        )
        claimed = (await session.execute(update_statement)).first()
        if claimed is None:
            # 另一个 worker 在本事务之前抢走了该行。重试。
            continue

        await session.flush()
        task_index = 3 if has_task_id else None
        payload_index = 3 + (1 if has_task_id else 0) if has_payload else None
        task_id = row[task_index] if task_index is not None else None
        payload = _payload_dict(row[payload_index] if payload_index is not None else None)
        return ClaimedRun(
            run_id=row[0],
            worker_id=worker_id,
            lease_expires_at=expires_at,
            previous_status=previous_status,
            task_id=task_id,
            payload=payload,
        )
    return None


async def renew_lease(
    session: AsyncSession,
    run_id: uuid.UUID,
    worker_id: str,
    lease_seconds: float,
    *,
    now: datetime | None = None,
    expected_expires_at: datetime | None = None,
    table: Table | None = None,
) -> datetime | None:
    """续期。租约不续期是调度器的已知缺陷，本函数是修复原语。

    只有 ``running`` 且仍持有租约的运行可以续期。
    ``runs.worker_id`` 存在时还会校验持有者。
    ``expected_expires_at`` 是调用方上次拿到的到期时间。
    它做比较并交换：另一个 worker 已改过租约时续期失败。
    表没有 ``worker_id`` 时，这个参数提供唯一的所有权校验。

    不匹配或运行已终结时返回 ``None``。返回新的到期时间。
    本函数只 flush，不 commit。
    """
    if lease_seconds <= 0:
        raise ValueError("lease_seconds 必须大于 0")
    resolved = _require_table(table)
    current = _as_utc(now or datetime.now(UTC))
    expires_at = current + timedelta(seconds=lease_seconds)

    renewal_values: dict[str, Any] = {"lease_expires_at": expires_at}
    if "updated_at" in resolved.c:
        renewal_values["updated_at"] = current
    if "heartbeat_at" in resolved.c:
        renewal_values["heartbeat_at"] = current

    conditions: list[Any] = [
        resolved.c.id == run_id,
        resolved.c.status == RUN_STATUS_RUNNING,
        resolved.c.lease_expires_at.is_not(None),
    ]
    if "worker_id" in resolved.c:
        conditions.append(resolved.c.worker_id == worker_id)
    if expected_expires_at is not None:
        conditions.append(
            resolved.c.lease_expires_at == _as_utc(expected_expires_at)
        )

    statement = update(resolved).where(*conditions).values(**renewal_values)
    result = await session.execute(statement)
    await session.flush()
    if int(getattr(result, "rowcount", 0)) == 0:
        return None
    return expires_at


async def release_lease(
    session: AsyncSession,
    run_id: uuid.UUID,
    *,
    worker_id: str | None = None,
    final_status: str | None = None,
    now: datetime | None = None,
    table: Table | None = None,
) -> bool:
    """释放租约。

    两种用法：

    - ``final_status`` 为空：``running`` 行放回队列（``status='queued'``）。
      终态行保持原状态。
    - ``final_status`` 为终态：写入终态并释放租约。

    传入 ``worker_id`` 且表有该列时，只释放自己持有的租约。
    旧 worker 不会误释放新 worker。
    只允许从 ``running`` 释放。终态行或被取消的行不命中。
    返回是否释放成功。
    本函数只 flush，不 commit。
    """
    if final_status is not None and final_status not in RUN_TERMINAL_STATUSES:
        raise ValueError(f"final_status 必须是 {sorted(RUN_TERMINAL_STATUSES)} 之一")
    resolved = _require_table(table)
    current = _as_utc(now or datetime.now(UTC))

    if final_status is None:
        next_status: Any = case(
            (resolved.c.status == RUN_STATUS_RUNNING, RUN_STATUS_QUEUED),
            else_=resolved.c.status,
        )
    else:
        next_status = final_status
    released_values: dict[str, Any] = {
        "status": next_status,
        "lease_expires_at": None,
    }
    if "worker_id" in resolved.c:
        released_values["worker_id"] = None
    if "updated_at" in resolved.c:
        released_values["updated_at"] = current
    if final_status is not None and "finished_at" in resolved.c:
        released_values["finished_at"] = current

    allowed_statuses: Any
    if final_status is None:
        # 执行器已提交终态时，只清租约，不改状态。
        # 仍在 running 时，放回 queued。
        allowed_statuses = or_(
            resolved.c.status == RUN_STATUS_RUNNING,
            resolved.c.status.in_(sorted(RUN_TERMINAL_STATUSES)),
        )
    else:
        # 写终态只允许从 running 进入，不得覆盖已提交的终态。
        allowed_statuses = resolved.c.status == RUN_STATUS_RUNNING
    conditions: list[Any] = [resolved.c.id == run_id, allowed_statuses]
    if worker_id is not None and "worker_id" in resolved.c:
        conditions.append(resolved.c.worker_id == worker_id)

    statement = update(resolved).where(*conditions).values(**released_values)
    result = await session.execute(statement)
    await session.flush()
    return int(getattr(result, "rowcount", 0)) > 0


def _eligible_clause(table: Table, now: datetime) -> Any:
    """可领取条件。queued 或租约已过期的 running。"""
    return or_(
        table.c.status == RUN_STATUS_QUEUED,
        and_(
            table.c.status == RUN_STATUS_RUNNING,
            table.c.lease_expires_at.is_not(None),
            table.c.lease_expires_at < now,
        ),
    )


def _require_table(table: Table | None) -> Table:
    resolved = table if table is not None else resolve_runs_table()
    missing = _REQUIRED_COLUMNS - set(resolved.c.keys())
    if missing:
        raise RunQueueSchemaError(
            "runs 表缺少队列列：" + ", ".join(sorted(missing)) + "。请应用 B3-01 的迁移。"
        )
    return resolved


def _dialect_name(session: AsyncSession) -> str:
    bind = session.get_bind()
    return bind.dialect.name


def _payload_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    return None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
