"""B3 运行执行器。

本模块执行一行 ``runs``。它不复用 fixture 的 ``workflow_execution``。
依据是架构设计 ADR-02 与 ADR-09。

依赖全部通过参数注入。本模块不导入 B3-01 的 ORM 模型：
- ``runs``、``run_steps``、``run_ledger_entries`` 三个仓储；
- 一个工作单元，只用于 flush；
- 一个 collector 调用。生产实现包装 ``execute_collector_call``。

049 迁移已经创建两张运行表。适配器放在另一个模块。
适配器把 ``runs`` 行与计划版本、授权上下文合并成 RunRecord。
实现只要求同名字段。它可以是组合视图，也可以是 ORM 实例加附加属性。

契约（契约冻结 v1）：
- 表名是 ``runs``、``run_steps``、``run_ledger_entries``。
  不得使用 §1.1 列出的任何废弃名。
- ``runs.status`` 只用 queued / running / completed / failed / cancelled。
- ``runs.outcome`` 与 ``run_steps.outcome`` 只用 success / empty / config_gated / failed。
- ``run_steps.status`` 只用 pending / running / success / empty / config_gated / failed / skipped。
- 等级由 B2 的 ``compute_run_evidence_grade`` 计算。本模块不重写规则。

事务规则：执行器只 flush，从不 commit。事务边界由调用方控制。
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

from data_intelligence_hub.services.exceptions import ServiceError
from data_intelligence_hub.tool_catalog.evidence_grade import (
    RunEvidenceGrade,
    compute_run_evidence_grade,
)
from data_intelligence_hub.tool_catalog.evidence_thresholds import (
    TemplateEvidenceThreshold,
    threshold_for,
)

logger = logging.getLogger(__name__)

RUN_STATUS_QUEUED = "queued"
RUN_STATUS_RUNNING = "running"
RUN_STATUS_COMPLETED = "completed"
RUN_STATUS_FAILED = "failed"
RUN_STATUS_CANCELLED = "cancelled"

# 契约冻结 v1 §2.1。
RUN_STATUSES: frozenset[str] = frozenset(
    {
        RUN_STATUS_QUEUED,
        RUN_STATUS_RUNNING,
        RUN_STATUS_COMPLETED,
        RUN_STATUS_FAILED,
        RUN_STATUS_CANCELLED,
    }
)

OUTCOME_SUCCESS = "success"
OUTCOME_EMPTY = "empty"
OUTCOME_CONFIG_GATED = "config_gated"
OUTCOME_FAILED = "failed"

# 契约冻结 v1 §2.3。只有四值。
RUN_OUTCOMES: frozenset[str] = frozenset(
    {OUTCOME_SUCCESS, OUTCOME_EMPTY, OUTCOME_CONFIG_GATED, OUTCOME_FAILED}
)

# 采集状态到契约结果的映射。
# partial_success 按契约 §2.3 收敛为 success。
OUTCOME_BY_CALL_STATUS: dict[str, str] = {
    "success": OUTCOME_SUCCESS,
    "partial_success": OUTCOME_SUCCESS,
    "empty": OUTCOME_EMPTY,
    "config_gated": OUTCOME_CONFIG_GATED,
    "failed": OUTCOME_FAILED,
}

# 契约冻结 v1 §2.1 与 §2.2。
RUN_STATUS_BY_OUTCOME: dict[str, str] = {
    OUTCOME_SUCCESS: RUN_STATUS_COMPLETED,
    OUTCOME_EMPTY: RUN_STATUS_COMPLETED,
    # 有 config_gated 步骤的运行仍算完成。报告写 gap。见架构状态机规则 1。
    OUTCOME_CONFIG_GATED: RUN_STATUS_COMPLETED,
    OUTCOME_FAILED: RUN_STATUS_FAILED,
}

STEP_STATUS_BY_OUTCOME: dict[str, str] = {
    OUTCOME_SUCCESS: "success",
    OUTCOME_EMPTY: "empty",
    OUTCOME_CONFIG_GATED: "config_gated",
    OUTCOME_FAILED: "failed",
}

# 没有模板时使用全零阈值。未知模板仍让 KeyError 抛出。
_NO_TEMPLATE_THRESHOLD = TemplateEvidenceThreshold(
    template_id="",
    required_n=0,
    n_basis="",
    required_window_days=0,
    required_source_count=0,
)


class RunNotFoundError(ServiceError):
    message = "run_not_found"

    def __init__(self, run_id: uuid.UUID) -> None:
        super().__init__(self.message)
        self.run_id = run_id


class InvalidRunTransitionError(ServiceError):
    """运行状态不允许交给执行器。

    完整的迁移表属于 B3-02 状态机。执行器只接受 queued 与 running。
    """

    message = "invalid_run_transition"

    def __init__(self, run_id: uuid.UUID, status: str) -> None:
        super().__init__(f"{self.message}: {status}")
        self.run_id = run_id
        self.status = status


class RunLeaseLostError(ServiceError):
    """租约已不属于当前 worker。

    旧 worker 不得提交终态。调用方必须回滚本次事务。
    """

    message = "run_lease_lost"

    def __init__(
        self,
        run_id: uuid.UUID,
        expected_worker: str | None,
        actual_worker: str | None,
    ) -> None:
        super().__init__(
            f"{self.message}: expected={expected_worker!r} actual={actual_worker!r}"
        )
        self.run_id = run_id
        self.expected_worker = expected_worker
        self.actual_worker = actual_worker


class RunRecord(Protocol):
    """``runs`` 表的一行，外加适配器补齐的执行上下文。

    ``id``、``status``、``outcome``、``evidence_grade``、``error_message``、
    ``records_count``、``started_at``、``finished_at`` 来自 ``runs`` 表。
    ``template_id``、``authorization_id``、``window_days``、``source_count``
    不在 ``runs`` 表。适配器从计划版本与授权解析它们。
    ``collector_type``、``endpoint_type`` 来自绑定的采集任务与任务配置。
    适配器可以返回 ORM 实例，也可以返回组合视图对象。
    """

    id: uuid.UUID
    status: str
    outcome: str | None
    evidence_grade: str | None
    error_message: str | None
    records_count: int
    total_cost_usd: Decimal | None
    started_at: datetime | None
    finished_at: datetime | None
    template_id: str | None
    authorization_id: uuid.UUID | None
    window_days: int
    source_count: int
    collector_type: str | None
    endpoint_type: str | None


class CollectorCallResultView(Protocol):
    """``execute_collector_call`` 返回值的只读视图。

    生产实现是 ``collector_service.CollectionCallResult``。
    """

    status: str
    outcome: str | None
    records_count: int
    entities_count: int
    error_message: str | None
    live_call: bool
    sample_n: int
    entity_count: int
    source_count: int
    window_days: int
    task_run_id: uuid.UUID | None
    collector_type: str | None
    endpoint_type: str | None
    unit: str | None
    quantity: Decimal | None
    unit_price: Decimal | None
    total_cost_usd: Decimal | None


class RunRepository(Protocol):
    """``runs`` 仓储。

    ``get`` 返回 None 表示运行不存在。
    ``save`` 只写回对象，不提交事务。适配器负责 flush。
    """

    async def get(self, run_id: uuid.UUID) -> RunRecord | None: ...

    async def save(self, run: RunRecord) -> None: ...


class RunStepRepository(Protocol):
    """``run_steps`` 仓储。

    ``next_index`` 返回本运行下一个可用的步骤序号。
    ``add`` 只登记新步骤，不提交事务。
    """

    async def next_index(self, run_id: uuid.UUID) -> int: ...

    async def add(self, step: RunStepWrite) -> None: ...


class RunLedgerRepository(Protocol):
    """``run_ledger_entries`` 仓储。``add`` 只登记新条目，不提交事务。"""

    async def add(self, entry: RunLedgerWrite) -> None: ...


class GradeRepository(Protocol):
    """``run_evidence_grades`` 仓储。

    ``add`` 只登记一行等级记录，不提交事务。
    记录就是 B2 的 ``RunEvidenceGrade``。字段与表列一一对应。
    生产适配器把记录转成 ``create_grade`` 的参数。
    """

    async def add(self, grade: RunEvidenceGrade) -> None: ...


class UnitOfWork(Protocol):
    """事务工作单元。

    执行器只调用 ``flush``。``commit`` 由调用方调用。
    """

    async def flush(self) -> None: ...

    async def commit(self) -> None: ...


class CollectorCall(Protocol):
    """一次 collector 调用的可调用对象。

    生产适配器从 ``runs`` 行解析 task 与 task_run。
    适配器随后调用 ``collector_service.execute_collector_call``。
    """

    async def __call__(self, run: RunRecord) -> CollectorCallResultView: ...


class GradeCalculator(Protocol):
    """证据等级计算函数。

    默认实现是 B2 的 ``compute_run_evidence_grade``。
    测试替身必须返回 ``RunEvidenceGrade``。
    """

    def __call__(
        self,
        *,
        run_id: uuid.UUID,
        live_call: bool,
        authorization_id: uuid.UUID | None,
        sample_n: int,
        required_n: int,
        window_days: int,
        required_window_days: int,
        source_count: int,
        required_source_count: int,
        entity_count: int,
        required_entity_count: int,
    ) -> RunEvidenceGrade: ...


@dataclass(frozen=True, slots=True)
class RunStepWrite:
    """一行待写入的 ``run_steps``。

    字段取契约冻结 v1 与模块设计 §2202 的并集。
    """

    id: uuid.UUID
    run_id: uuid.UUID
    step_index: int
    # 两列在 run_steps 中非空。适配器解析不到时写空串。
    endpoint_type: str
    collector_type: str
    task_run_id: uuid.UUID | None
    status: str
    outcome: str
    records_count: int
    unit: str | None
    quantity: Decimal | None
    unit_price: Decimal | None
    total_cost_usd: Decimal | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime


@dataclass(frozen=True, slots=True)
class RunLedgerWrite:
    """一行待写入的 ``run_ledger_entries``。列名以契约冻结 §2.7.1 为准。"""

    id: uuid.UUID
    run_id: uuid.UUID
    step_id: uuid.UUID | None
    entry_kind: str
    amount_usd: Decimal
    balance_after_usd: Decimal
    idempotency_key: str
    created_at: datetime


class RunExecutor:
    """执行一次 ``runs`` 行。

    流程：
    1. 读取 ``runs`` 行。状态只允许 queued 或 running。
    2. 状态改为 running，flush。
    3. 调注入的 collector 调用。
    4. 写一行 ``run_steps``。
    5. 写一行账本。
    6. 用 B2 的纯函数计算等级。
    7. 写一行 ``run_evidence_grades`` 等级证据。
    8. 更新 ``runs`` 的 status / outcome / evidence_grade，flush。

    ``run_evidence_grades`` 行保留可复核的等级证据。
    证据包括样本数、窗口与来源数。等级因此可审计。

    失败路径不写等级行。失败的运行没有可交付证据。
    此时 ``runs.evidence_grade`` 保持空，等级表也不写。

    ``grades`` 未注入时跳过第 7 步，并记一条 warning。
    该参数默认 ``None``，既有调用不受影响。

    ``task_runs.evidence_grade`` 是同一等级的镜像。
    该列由 collector 调用适配器回写。执行器不持有 task_runs 仓储。

    失败路径写 failed 与 error_message。异常不向外抛出，除非参数非法。
    """

    def __init__(
        self,
        *,
        runs: RunRepository,
        steps: RunStepRepository,
        ledger: RunLedgerRepository,
        unit_of_work: UnitOfWork,
        collector_call: CollectorCall,
        grade_calculator: GradeCalculator = compute_run_evidence_grade,
        grades: GradeRepository | None = None,
    ) -> None:
        self._runs = runs
        self._steps = steps
        self._ledger = ledger
        self._unit_of_work = unit_of_work
        self._collector_call = collector_call
        self._grade_calculator = grade_calculator
        self._grades = grades

    async def execute(self, run_id: uuid.UUID) -> RunRecord:
        run = await self._runs.get(run_id)
        if run is None:
            raise RunNotFoundError(run_id)
        if run.status not in (RUN_STATUS_QUEUED, RUN_STATUS_RUNNING):
            raise InvalidRunTransitionError(run_id, run.status)

        started_at = datetime.now(UTC)
        run.status = RUN_STATUS_RUNNING
        if run.started_at is None:
            run.started_at = started_at
        await self._runs.save(run)
        await self._unit_of_work.flush()

        try:
            call = await self._collector_call(run)
        except Exception as exc:
            error_message = str(exc) or exc.__class__.__name__
            return await self._finish_failed(
                run,
                error_message=error_message,
                started_at=started_at,
            )

        outcome = _resolve_outcome(call)
        step = RunStepWrite(
            id=uuid.uuid4(),
            run_id=run.id,
            step_index=await self._steps.next_index(run.id),
            endpoint_type=call.endpoint_type or run.endpoint_type or "",
            collector_type=call.collector_type or run.collector_type or "",
            task_run_id=call.task_run_id,
            status=STEP_STATUS_BY_OUTCOME[outcome],
            outcome=outcome,
            records_count=call.records_count,
            unit=call.unit,
            quantity=call.quantity,
            unit_price=call.unit_price,
            total_cost_usd=call.total_cost_usd,
            error_message=call.error_message,
            started_at=started_at,
            finished_at=datetime.now(UTC),
        )
        await self._steps.add(step)
        await self._ledger.add(self._build_ledger_entry(run, step, call.total_cost_usd))
        await self._unit_of_work.flush()

        if outcome == OUTCOME_FAILED:
            # 失败的运行没有可交付证据。等级留空，不写等级行。
            run.evidence_grade = None
        else:
            grade = self._compute_grade(run, call)
            await self._record_grade(grade)
            run.evidence_grade = grade.grade.value
        run.status = RUN_STATUS_BY_OUTCOME[outcome]
        run.outcome = outcome
        run.error_message = call.error_message if outcome == OUTCOME_FAILED else None
        run.records_count = call.records_count
        run.total_cost_usd = call.total_cost_usd
        run.finished_at = datetime.now(UTC)
        await self._runs.save(run)
        await self._unit_of_work.flush()
        return run

    async def _finish_failed(
        self,
        run: RunRecord,
        *,
        error_message: str,
        started_at: datetime,
    ) -> RunRecord:
        finished_at = datetime.now(UTC)
        step = RunStepWrite(
            id=uuid.uuid4(),
            run_id=run.id,
            step_index=await self._steps.next_index(run.id),
            endpoint_type=run.endpoint_type or "",
            collector_type=run.collector_type or "",
            task_run_id=None,
            status=STEP_STATUS_BY_OUTCOME[OUTCOME_FAILED],
            outcome=OUTCOME_FAILED,
            records_count=0,
            unit=None,
            quantity=None,
            unit_price=None,
            total_cost_usd=None,
            error_message=error_message,
            started_at=started_at,
            finished_at=finished_at,
        )
        await self._steps.add(step)
        await self._ledger.add(self._build_ledger_entry(run, step, None))
        run.status = RUN_STATUS_FAILED
        run.outcome = OUTCOME_FAILED
        run.error_message = error_message
        run.evidence_grade = None
        run.records_count = 0
        run.total_cost_usd = None
        run.finished_at = finished_at
        await self._runs.save(run)
        await self._unit_of_work.flush()
        return run

    async def _record_grade(self, grade: RunEvidenceGrade) -> None:
        """写一行等级证据。

        ``grades`` 未注入时跳过写入，并记一条 warning。
        警告只提醒接线缺失，不改变运行结果。
        """
        if self._grades is None:
            logger.warning(
                "等级仓储未注入，跳过 run_evidence_grades 写入：run_id=%s",
                grade.run_id,
            )
            return
        await self._grades.add(grade)

    def _build_ledger_entry(
        self,
        run: RunRecord,
        step: RunStepWrite,
        total_cost_usd: Decimal | None,
    ) -> RunLedgerWrite:
        return RunLedgerWrite(
            id=uuid.uuid4(),
            run_id=run.id,
            step_id=step.id,
            entry_kind="accrued",
            amount_usd=total_cost_usd or Decimal("0"),
            # B3 未接额度账户。适配器接管后写真实余额。
            balance_after_usd=Decimal("0"),
            idempotency_key=f"run:{run.id}:step:{step.step_index}:accrued",
            created_at=datetime.now(UTC),
        )

    def _compute_grade(
        self,
        run: RunRecord,
        call: CollectorCallResultView,
    ) -> RunEvidenceGrade:
        """按 B2 规则计算等级。

        ``run.authorization_id`` 必须由适配器先做可用性检查。
        过期授权应返回 None。等级随后回落到 L3。
        """
        threshold = _threshold_for_run(run.template_id)
        return self._grade_calculator(
            run_id=run.id,
            live_call=call.live_call,
            authorization_id=run.authorization_id,
            sample_n=call.sample_n,
            required_n=threshold.required_n,
            window_days=call.window_days or run.window_days,
            required_window_days=threshold.required_window_days,
            source_count=call.source_count or run.source_count,
            required_source_count=threshold.required_source_count,
            entity_count=call.entity_count,
            required_entity_count=threshold.required_entity_count,
        )


def _resolve_outcome(call: CollectorCallResultView) -> str:
    """把一次调用结果收敛为契约结果。

    显式 ``outcome`` 优先。它必须是四个契约值之一。
    """
    if call.outcome is not None:
        if call.outcome not in RUN_OUTCOMES:
            raise ValueError(f"unknown run outcome: {call.outcome}")
        return call.outcome
    try:
        return OUTCOME_BY_CALL_STATUS[call.status]
    except KeyError as exc:
        raise ValueError(f"unknown collector call status: {call.status}") from exc


def _threshold_for_run(template_id: str | None) -> TemplateEvidenceThreshold:
    """按模板 ID 取阈值。没有模板时返回全零阈值。"""
    if template_id is None:
        return _NO_TEMPLATE_THRESHOLD
    return threshold_for(template_id)
