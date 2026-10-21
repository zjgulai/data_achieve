"""RunExecutor 的 ORM 生产适配器。

本模块把 ``run_executor.py`` 的 Protocol 接到 B3-01 的 ORM 模型。
每个适配器只读写数据库，并调用 ``flush``。
本模块不调用 ``commit``。事务边界由 worker 或路由负责。

``RunRecord`` 是组合视图。它把 ``runs`` 行与执行上下文合并：

- 采集任务给出 ``collector_type``、``endpoint_type`` 与 ``window_days``；
- 计划版本给出模板键；
- 授权给出 ``authorization_id``。

上下文解析不到时用安全默认值。适配器不编造证据数字。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.authorization import Authorization
from data_intelligence_hub.models.run import Run, RunStep
from data_intelligence_hub.models.run_ledger import ENTRY_KINDS, RunLedgerEntry
from data_intelligence_hub.models.task import CollectionTask
from data_intelligence_hub.models.workflow_plan import WorkflowVersion
from data_intelligence_hub.models.workflow_template import WorkflowTemplate
from data_intelligence_hub.repositories.run_evidence_grades import create_grade
from data_intelligence_hub.services.run_executor import (
    RunLedgerWrite,
    RunRecord,
    RunStepWrite,
)
from data_intelligence_hub.tool_catalog.evidence_grade import (
    RunEvidenceGrade,
    authorization_is_usable,
)
from data_intelligence_hub.tool_catalog.evidence_thresholds import EVIDENCE_THRESHOLDS

_TERMINAL_RUN_STATUSES = frozenset({"completed", "failed", "cancelled"})


class OrmRunRecord:
    """``runs`` 行加执行上下文。

    八个可变字段直接映射到 ``runs`` 列。其余字段是只读上下文。
    执行器可以像普通对象一样读写这些字段。
    """

    __slots__ = (
        "_row",
        "authorization_id",
        "collector_type",
        "endpoint_type",
        "source_count",
        "template_id",
        "window_days",
    )

    def __init__(
        self,
        row: Run,
        *,
        template_id: str | None,
        authorization_id: uuid.UUID | None,
        window_days: int,
        source_count: int,
        collector_type: str | None,
        endpoint_type: str | None,
    ) -> None:
        self._row = row
        self.template_id = template_id
        self.authorization_id = authorization_id
        self.window_days = window_days
        self.source_count = source_count
        self.collector_type = collector_type
        self.endpoint_type = endpoint_type

    @property
    def row(self) -> Run:
        """底层 ORM 行。供适配器写回。"""
        return self._row

    @property
    def id(self) -> uuid.UUID:
        return self._row.id

    @property
    def workspace_id(self) -> uuid.UUID:
        return self._row.workspace_id

    @property
    def project_id(self) -> uuid.UUID:
        return self._row.project_id

    @property
    def task_id(self) -> uuid.UUID | None:
        return self._row.task_id

    @property
    def workflow_version_id(self) -> uuid.UUID | None:
        return self._row.workflow_version_id

    @property
    def status(self) -> str:
        return self._row.status

    @status.setter
    def status(self, value: str) -> None:
        self._row.status = value

    @property
    def outcome(self) -> str | None:
        return self._row.outcome

    @outcome.setter
    def outcome(self, value: str | None) -> None:
        self._row.outcome = value

    @property
    def evidence_grade(self) -> str | None:
        return self._row.evidence_grade

    @evidence_grade.setter
    def evidence_grade(self, value: str | None) -> None:
        self._row.evidence_grade = value

    @property
    def error_message(self) -> str | None:
        return self._row.error_message

    @error_message.setter
    def error_message(self, value: str | None) -> None:
        self._row.error_message = value

    @property
    def records_count(self) -> int:
        return self._row.records_count

    @records_count.setter
    def records_count(self, value: int) -> None:
        self._row.records_count = value

    @property
    def started_at(self) -> datetime | None:
        return self._row.started_at

    @started_at.setter
    def started_at(self, value: datetime | None) -> None:
        self._row.started_at = value

    @property
    def finished_at(self) -> datetime | None:
        return self._row.finished_at

    @finished_at.setter
    def finished_at(self, value: datetime | None) -> None:
        self._row.finished_at = value


class OrmRunRepository:
    """``runs`` 仓储的 ORM 实现。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, run_id: uuid.UUID) -> OrmRunRecord | None:
        """按运行 ID 读取一行并补齐执行上下文。"""
        row = await self._session.get(Run, run_id)
        if row is None:
            return None
        task = await self._load_task(row)
        template_id = await self._resolve_template_id(row, task)
        authorization_id = await self._resolve_authorization_id(row, template_id)
        return OrmRunRecord(
            row,
            template_id=template_id,
            authorization_id=authorization_id,
            window_days=_configured_period_days(task.config if task is not None else None),
            source_count=1 if task is not None else 0,
            collector_type=task.collector_type if task is not None else None,
            endpoint_type=_endpoint_type(task.config if task is not None else None),
        )

    async def save(self, run: RunRecord) -> None:
        """写回运行行并 flush。本方法不提交事务。"""
        if isinstance(run, OrmRunRecord):
            row = run.row
            row.status = run.status
            row.outcome = run.outcome
            row.evidence_grade = run.evidence_grade
            row.error_message = run.error_message
            row.records_count = run.records_count
            row.started_at = run.started_at
            row.finished_at = run.finished_at
        elif isinstance(run, Run):
            row = run
        else:
            raise TypeError(f"不支持的运行记录类型：{type(run).__name__}")

        if row.status in _TERMINAL_RUN_STATUSES:
            total = await self._session.scalar(
                select(func.sum(RunStep.total_cost_usd)).where(RunStep.run_id == row.id)
            )
            row.total_cost_usd = _decimal_or_none(total)
        await self._session.flush()

    async def _load_task(self, row: Run) -> CollectionTask | None:
        """按运行的工作区读取绑定的采集任务。"""
        if row.task_id is None:
            return None
        task: CollectionTask | None = await self._session.scalar(
            select(CollectionTask).where(
                CollectionTask.id == row.task_id,
                CollectionTask.workspace_id == row.workspace_id,
            )
        )
        return task

    async def _resolve_template_id(
        self,
        row: Run,
        task: CollectionTask | None,
    ) -> str | None:
        """解析报告模板键。只返回 B2 阈值表认识的键。"""
        configured = (task.config if task is not None else None) or {}
        candidate = configured.get("template_id")
        if isinstance(candidate, str) and candidate in EVIDENCE_THRESHOLDS:
            return candidate
        if row.workflow_version_id is None:
            return None
        version = await self._session.get(WorkflowVersion, row.workflow_version_id)
        if version is None or version.workflow_template_id is None:
            return None
        template = await self._session.get(
            WorkflowTemplate,
            version.workflow_template_id,
        )
        if template is None:
            return None
        if template.template_key in EVIDENCE_THRESHOLDS:
            return template.template_key
        return None

    async def _resolve_authorization_id(
        self,
        row: Run,
        template_id: str | None,
    ) -> uuid.UUID | None:
        """取本项目可用的授权。过期、撤销或未通过的授权不返回。

        模板已知时还要求授权范围匹配该模板。范围没有模板时视为通用授权。
        """
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(Authorization)
            .where(
                Authorization.workspace_id == row.workspace_id,
                Authorization.project_id == row.project_id,
                Authorization.revoked_at.is_(None),
                Authorization.gate_status == "pass",
            )
            .order_by(Authorization.granted_at.desc(), Authorization.id)
        )
        for authorization in result.scalars().all():
            if (
                authorization.plan_version_id is not None
                and authorization.plan_version_id != row.workflow_version_id
            ):
                continue
            scope_template = (authorization.scope or {}).get("template_id")
            if template_id is not None and scope_template not in (None, template_id):
                continue
            view = SimpleNamespace(expires_at=_as_utc(authorization.expires_at))
            if authorization_is_usable(view, now):
                return authorization.id
        return None


class OrmRunStepRepository:
    """``run_steps`` 仓储的 ORM 实现。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def next_index(self, run_id: uuid.UUID) -> int:
        """返回下一个步骤序号。首个步骤从 0 开始。"""
        value = await self._session.scalar(
            select(func.max(RunStep.step_index)).where(RunStep.run_id == run_id)
        )
        if value is None:
            return 0
        return int(value) + 1

    async def add(self, step: RunStepWrite) -> None:
        """插入一行步骤并 flush。本方法不提交事务。"""
        self._session.add(
            RunStep(
                id=step.id,
                run_id=step.run_id,
                step_index=step.step_index,
                endpoint_type=step.endpoint_type,
                collector_type=step.collector_type,
                task_run_id=step.task_run_id,
                status=step.status,
                outcome=step.outcome,
                records_count=step.records_count,
                unit=step.unit,
                quantity=step.quantity,
                unit_price=step.unit_price,
                total_cost_usd=step.total_cost_usd,
                error_message=step.error_message,
                started_at=step.started_at,
                finished_at=step.finished_at,
            )
        )
        await self._session.flush()


class OrmRunLedgerRepository:
    """``run_ledger_entries`` 仓储的 ORM 实现。账本只追加。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: RunLedgerWrite) -> None:
        """追加一行账本并 flush。本方法不提交事务。"""
        if entry.entry_kind not in ENTRY_KINDS:
            raise ValueError(f"未知的 entry_kind：{entry.entry_kind}")
        self._session.add(
            RunLedgerEntry(
                id=entry.id,
                run_id=entry.run_id,
                step_id=entry.step_id,
                entry_kind=entry.entry_kind,
                amount_usd=entry.amount_usd,
                balance_after_usd=entry.balance_after_usd,
                idempotency_key=entry.idempotency_key,
                created_at=entry.created_at,
            )
        )
        await self._session.flush()


class OrmGradeRepository:
    """``run_evidence_grades`` 仓储的 ORM 实现。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, grade: RunEvidenceGrade) -> None:
        """写入一行等级证据并 flush。本方法不提交事务。"""
        await create_grade(
            self._session,
            run_id=grade.run_id,
            live_call=grade.live_call,
            authorization_id=grade.authorization_id,
            sample_n=grade.sample_n,
            required_n=grade.required_n,
            window_days=grade.window_days,
            required_window_days=grade.required_window_days,
            source_count=grade.source_count,
            required_source_count=grade.required_source_count,
            grade=grade.grade,
            entity_count=grade.entity_count,
            required_entity_count=grade.required_entity_count,
        )


class SessionUnitOfWork:
    """用 ``AsyncSession`` 实现工作单元。

    执行器只调用 ``flush``。``commit`` 供调用方使用。
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def flush(self) -> None:
        await self._session.flush()

    async def commit(self) -> None:
        await self._session.commit()


def _configured_period_days(config: dict[str, object] | None) -> int:
    """取任务配置的时间窗天数。没有配置时返回 0。"""
    raw_period = (config or {}).get("period")
    if isinstance(raw_period, bool):
        return 0
    if isinstance(raw_period, int):
        return raw_period
    if isinstance(raw_period, str):
        try:
            return int(raw_period)
        except ValueError:
            return 0
    return 0


def _endpoint_type(config: dict[str, object] | None) -> str | None:
    """取任务配置的端点类型。没有配置时返回 None。"""
    value = (config or {}).get("endpoint_type")
    return value if isinstance(value, str) else None


def _as_utc(value: datetime) -> datetime:
    """把无时区时间按 UTC 处理。SQLite 会丢时区。"""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _decimal_or_none(value: object) -> Decimal | None:
    """把 SQL 聚合结果转成 Decimal。空值返回 None。"""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


__all__ = [
    "OrmGradeRepository",
    "OrmRunLedgerRepository",
    "OrmRunRecord",
    "OrmRunRepository",
    "OrmRunStepRepository",
    "SessionUnitOfWork",
]
