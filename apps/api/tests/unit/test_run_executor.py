"""RunExecutor 的单元测试。

用假仓储验证契约行为。不建库，不联网。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

import pytest

from data_intelligence_hub.services.collector_service import CollectionCallResult
from data_intelligence_hub.services.run_executor import (
    CollectorCallResultView,
    GradeCalculator,
    InvalidRunTransitionError,
    RunExecutor,
    RunLedgerWrite,
    RunNotFoundError,
    RunRecord,
    RunStepWrite,
)
from data_intelligence_hub.tool_catalog.evidence_grade import (
    EvidenceGrade,
    RunEvidenceGrade,
)


@dataclass
class FakeRun:
    """``runs`` 行的测试替身。字段与 RunRecord Protocol 一致。"""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    status: str = "queued"
    outcome: str | None = None
    evidence_grade: str | None = None
    error_message: str | None = None
    records_count: int = 0
    total_cost_usd: Decimal | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    template_id: str | None = "t1_voc"
    authorization_id: uuid.UUID | None = None
    window_days: int = 60
    source_count: int = 2
    collector_type: str | None = "tikhub_social"
    endpoint_type: str | None = "tikhub_tiktok_video_search"


class FakeRunRepository:
    def __init__(self, run: FakeRun | None) -> None:
        self.run = run
        self.status_history: list[str] = []

    async def get(self, run_id: uuid.UUID) -> FakeRun | None:
        if self.run is None or self.run.id != run_id:
            return None
        return self.run

    async def save(self, run: RunRecord) -> None:
        self.status_history.append(run.status)


class FakeStepRepository:
    def __init__(self) -> None:
        self.steps: list[RunStepWrite] = []

    async def next_index(self, run_id: uuid.UUID) -> int:
        return len(self.steps)

    async def add(self, step: RunStepWrite) -> None:
        self.steps.append(step)


class FakeLedgerRepository:
    def __init__(self) -> None:
        self.entries: list[RunLedgerWrite] = []

    async def add(self, entry: RunLedgerWrite) -> None:
        self.entries.append(entry)


class FakeGradeRepository:
    """记录写入的等级证据行。"""

    def __init__(self) -> None:
        self.grades: list[RunEvidenceGrade] = []

    async def add(self, grade: RunEvidenceGrade) -> None:
        self.grades.append(grade)


class FakeUnitOfWork:
    """记录 flush 与 commit 的调用次数。"""

    def __init__(self) -> None:
        self.flush_calls = 0
        self.commit_calls = 0

    async def flush(self) -> None:
        self.flush_calls += 1

    async def commit(self) -> None:
        self.commit_calls += 1


class FakeCollectorCall:
    """返回固定结果或抛出固定异常。"""

    def __init__(
        self,
        result: CollectionCallResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[uuid.UUID] = []

    async def __call__(self, run: RunRecord) -> CollectorCallResultView:
        self.calls.append(run.id)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


class FakeGradeCalculator:
    """固定返回一个等级，并记录收到的参数。"""

    def __init__(self, grade: EvidenceGrade) -> None:
        self.grade = grade
        self.received: dict[str, object] = {}

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
    ) -> RunEvidenceGrade:
        self.received.update(
            {
                "run_id": run_id,
                "live_call": live_call,
                "authorization_id": authorization_id,
                "sample_n": sample_n,
                "required_n": required_n,
                "window_days": window_days,
                "required_window_days": required_window_days,
                "source_count": source_count,
                "required_source_count": required_source_count,
                "entity_count": entity_count,
                "required_entity_count": required_entity_count,
            }
        )
        return RunEvidenceGrade(
            run_id=run_id,
            live_call=live_call,
            authorization_id=authorization_id,
            sample_n=sample_n,
            required_n=required_n,
            window_days=window_days,
            required_window_days=required_window_days,
            source_count=source_count,
            required_source_count=required_source_count,
            entity_count=entity_count,
            required_entity_count=required_entity_count,
            grade=self.grade,
        )


ExecutorBundle = tuple[
    RunExecutor,
    FakeRunRepository,
    FakeStepRepository,
    FakeLedgerRepository,
    FakeUnitOfWork,
]


def _build(
    run: FakeRun,
    *,
    call: FakeCollectorCall,
    grade_calculator: GradeCalculator | None = None,
    grades: FakeGradeRepository | None = None,
) -> ExecutorBundle:
    runs = FakeRunRepository(run)
    steps = FakeStepRepository()
    ledger = FakeLedgerRepository()
    uow = FakeUnitOfWork()
    if grade_calculator is None:
        executor = RunExecutor(
            runs=runs,
            steps=steps,
            ledger=ledger,
            unit_of_work=uow,
            collector_call=call,
            grades=grades,
        )
    else:
        executor = RunExecutor(
            runs=runs,
            steps=steps,
            ledger=ledger,
            unit_of_work=uow,
            collector_call=call,
            grade_calculator=grade_calculator,
            grades=grades,
        )
    return executor, runs, steps, ledger, uow


def _success_result(**overrides: object) -> CollectionCallResult:
    values: dict[str, object] = {
        "status": "success",
        "records_count": 12,
        "entities_count": 5,
        "sample_n": 12,
        "window_days": 60,
        "source_count": 2,
        "collector_type": "tikhub_social",
        "endpoint_type": "tikhub_tiktok_video_search",
    }
    values.update(overrides)
    return CollectionCallResult(**values)  # type: ignore[arg-type]


async def test_success_run_mirrors_total_cost_to_run() -> None:
    run = FakeRun(status="queued")
    executor, _, steps, ledger, _ = _build(
        run,
        call=FakeCollectorCall(
            _success_result(
                unit="run",
                quantity=Decimal("1"),
                unit_price=Decimal("0.1"),
                total_cost_usd=Decimal("0.1"),
            )
        ),
    )

    result = await executor.execute(run.id)

    assert result.total_cost_usd == Decimal("0.1")
    assert steps.steps[0].total_cost_usd == Decimal("0.1")
    assert ledger.entries[0].amount_usd == Decimal("0.1")


async def test_success_run_transitions_queued_running_completed() -> None:
    """成功运行按 queued → running → completed 迁移。"""
    run = FakeRun(status="queued")
    executor, runs, steps, ledger, _ = _build(
        run,
        call=FakeCollectorCall(_success_result()),
    )

    result = await executor.execute(run.id)

    assert runs.status_history == ["running", "completed"]
    assert result.status == "completed"
    assert result.outcome == "success"
    assert result.records_count == 12
    assert result.started_at is not None
    assert result.finished_at is not None
    assert steps.steps[0].status == "success"
    assert steps.steps[0].outcome == "success"
    assert steps.steps[0].records_count == 12
    assert steps.steps[0].collector_type == "tikhub_social"
    assert steps.steps[0].endpoint_type == "tikhub_tiktok_video_search"
    assert len(ledger.entries) == 1
    assert ledger.entries[0].entry_kind == "accrued"


async def test_step_links_task_run() -> None:
    """run_steps 记录关联的 task_runs 行。"""
    run = FakeRun()
    task_run_id = uuid.uuid4()
    executor, _, steps, _, _ = _build(
        run,
        call=FakeCollectorCall(_success_result(task_run_id=task_run_id)),
    )

    await executor.execute(run.id)

    assert steps.steps[0].task_run_id == task_run_id


async def test_partial_success_is_outcome_success() -> None:
    """契约冻结 §2.3 禁止 partial。部分成功收敛为 success。"""
    run = FakeRun()
    executor, _, steps, _, _ = _build(
        run,
        call=FakeCollectorCall(
            _success_result(status="partial_success", records_count=2)
        ),
    )

    result = await executor.execute(run.id)

    assert result.status == "completed"
    assert result.outcome == "success"
    assert steps.steps[0].status == "success"
    assert steps.steps[0].outcome == "success"


async def test_failed_call_writes_failed_and_error_message() -> None:
    """采集异常时运行写 failed 与 error_message。"""
    run = FakeRun()
    executor, runs, steps, ledger, _ = _build(
        run,
        call=FakeCollectorCall(error=RuntimeError("upstream exploded")),
    )

    result = await executor.execute(run.id)

    assert runs.status_history == ["running", "failed"]
    assert result.status == "failed"
    assert result.outcome == "failed"
    assert result.error_message == "upstream exploded"
    assert steps.steps[0].status == "failed"
    assert steps.steps[0].outcome == "failed"
    assert steps.steps[0].error_message == "upstream exploded"
    assert len(ledger.entries) == 1


async def test_failed_result_writes_failed() -> None:
    """采集器返回 failed 结果时运行同样写 failed。"""
    run = FakeRun()
    executor, runs, _, _, _ = _build(
        run,
        call=FakeCollectorCall(
            CollectionCallResult(
                status="failed",
                records_count=0,
                entities_count=0,
                error_message="http_timeout",
            )
        ),
    )

    result = await executor.execute(run.id)

    assert runs.status_history == ["running", "failed"]
    assert result.status == "failed"
    assert result.outcome == "failed"
    assert result.error_message == "http_timeout"


async def test_empty_result_writes_empty_step_and_outcome() -> None:
    """空结果写 run_steps.status=empty、outcome=empty。

    契约冻结 §2.1 没有 runs.status=empty。
    运行状态写 completed，结果写 outcome=empty。
    """
    run = FakeRun()
    executor, runs, steps, _, _ = _build(
        run,
        call=FakeCollectorCall(
            CollectionCallResult(
                status="empty",
                records_count=0,
                entities_count=0,
                sample_n=0,
                window_days=60,
                source_count=2,
            )
        ),
    )

    result = await executor.execute(run.id)

    assert runs.status_history == ["running", "completed"]
    assert result.status == "completed"
    assert result.outcome == "empty"
    assert steps.steps[0].status == "empty"
    assert steps.steps[0].outcome == "empty"


async def test_grade_comes_from_compute_run_evidence_grade() -> None:
    """等级由注入的 B2 计算函数决定。替身返回 L3 时 runs 写 L3。"""
    run = FakeRun()
    calculator = FakeGradeCalculator(EvidenceGrade.L3_LIVE_SINGLE)

    executor, _, _, _, _ = _build(
        run,
        call=FakeCollectorCall(_success_result()),
        grade_calculator=calculator,
    )

    result = await executor.execute(run.id)

    assert result.evidence_grade == "L3_live_single"
    assert calculator.received["run_id"] == run.id
    # 阈值来自 B2 的 t1_voc 条目。
    assert calculator.received["required_n"] == 30
    assert calculator.received["required_window_days"] == 60
    assert calculator.received["required_source_count"] == 2


async def test_default_calculator_uses_b2_rules() -> None:
    """默认计算器就是 B2 的纯函数。无授权时 L3。"""
    run = FakeRun(authorization_id=None)
    executor, _, _, _, _ = _build(
        run,
        call=FakeCollectorCall(_success_result()),
    )

    result = await executor.execute(run.id)

    assert result.evidence_grade == "L3_live_single"


async def test_success_writes_grade_row_with_computed_fields() -> None:
    """成功运行写一行等级证据。字段与计算结果一一对应。"""
    run = FakeRun()
    grades = FakeGradeRepository()
    executor, _, _, _, _ = _build(
        run,
        call=FakeCollectorCall(_success_result()),
        grades=grades,
    )

    result = await executor.execute(run.id)

    assert result.evidence_grade == "L3_live_single"
    assert len(grades.grades) == 1
    grade = grades.grades[0]
    assert grade.run_id == run.id
    assert grade.live_call is True
    assert grade.authorization_id is None
    assert grade.sample_n == 12
    assert grade.required_n == 30
    assert grade.window_days == 60
    assert grade.required_window_days == 60
    assert grade.source_count == 2
    assert grade.required_source_count == 2
    assert grade.entity_count == 0
    assert grade.required_entity_count == 0
    assert grade.grade == EvidenceGrade.L3_LIVE_SINGLE


async def test_failed_exception_does_not_write_grade_row() -> None:
    """采集异常时不写等级行。runs.evidence_grade 保持空。"""
    run = FakeRun()
    grades = FakeGradeRepository()
    executor, _, _, _, _ = _build(
        run,
        call=FakeCollectorCall(error=RuntimeError("upstream exploded")),
        grades=grades,
    )

    result = await executor.execute(run.id)

    assert result.evidence_grade is None
    assert grades.grades == []


async def test_failed_outcome_does_not_write_grade_row() -> None:
    """采集器返回 failed 时同样不写等级行。"""
    run = FakeRun()
    grades = FakeGradeRepository()
    executor, _, _, _, _ = _build(
        run,
        call=FakeCollectorCall(
            CollectionCallResult(
                status="failed",
                records_count=0,
                entities_count=0,
                error_message="http_timeout",
            )
        ),
        grades=grades,
    )

    result = await executor.execute(run.id)

    assert result.evidence_grade is None
    assert grades.grades == []


async def test_executor_works_without_grade_repository() -> None:
    """不注入等级仓储时执行器仍能工作。默认参数保持向后兼容。"""
    run = FakeRun()
    executor, _, _, _, _ = _build(
        run,
        call=FakeCollectorCall(_success_result()),
    )

    result = await executor.execute(run.id)

    assert result.status == "completed"
    assert result.outcome == "success"
    assert result.evidence_grade == "L3_live_single"


async def test_executor_flushes_and_never_commits() -> None:
    """执行器只 flush，不 commit。"""
    run = FakeRun()
    executor, _, _, _, uow = _build(
        run,
        call=FakeCollectorCall(_success_result()),
    )

    await executor.execute(run.id)

    assert uow.flush_calls > 0
    assert uow.commit_calls == 0


async def test_failed_executor_flushes_and_never_commits() -> None:
    """失败路径也只 flush。"""
    run = FakeRun()
    executor, _, _, _, uow = _build(
        run,
        call=FakeCollectorCall(error=RuntimeError("boom")),
    )

    await executor.execute(run.id)

    assert uow.flush_calls > 0
    assert uow.commit_calls == 0


async def test_missing_run_raises() -> None:
    """运行不存在时抛 RunNotFoundError。"""
    missing_id = uuid.uuid4()
    executor, _, _, _, _ = _build(
        FakeRun(),
        call=FakeCollectorCall(_success_result()),
    )

    with pytest.raises(RunNotFoundError):
        await executor.execute(missing_id)


async def test_invalid_status_raises() -> None:
    """completed 运行不得再次执行。"""
    run = FakeRun(status="completed")
    executor, _, _, _, _ = _build(
        run,
        call=FakeCollectorCall(_success_result()),
    )

    with pytest.raises(InvalidRunTransitionError):
        await executor.execute(run.id)
