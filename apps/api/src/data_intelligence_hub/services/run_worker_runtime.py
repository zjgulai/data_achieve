"""运行队列 worker 的装配与启动点。

本模块把三块接起来：

- ``RunQueueWorker`` 负责领取、续期与释放租约；
- ``build_run_executor`` 用 ORM 适配器组装 ``RunExecutor``；
- ``RunWorkerRuntime`` 提供 ``start`` / ``stop`` 后台循环。

循环顺序：``claim_next_run`` → 执行 → ``release_lease``。
领取与释放由 ``RunQueueWorker`` 完成。执行期间的续期也由它完成，
续期复用 ``services/run_queue.renew_lease``。

一次执行的异常不会让循环退出。worker 记录日志后继续下一条。
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, cast

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from data_intelligence_hub.services.run_collector_call import RunCollectorCall
from data_intelligence_hub.services.run_executor import (
    CollectorCall,
    GradeCalculator,
    InvalidRunTransitionError,
    RunExecutor,
    RunNotFoundError,
    RunRepository,
)
from data_intelligence_hub.services.run_executor_adapters import (
    OrmGradeRepository,
    OrmRunLedgerRepository,
    OrmRunRepository,
    OrmRunStepRepository,
    SessionUnitOfWork,
)
from data_intelligence_hub.services.run_queue import ClaimedRun
from data_intelligence_hub.services.run_queue_worker import RunQueueWorker

logger = structlog.get_logger(__name__)

CollectorCallFactory = Callable[[AsyncSession], CollectorCall]


@dataclass(frozen=True, slots=True)
class RunExecutorBundle:
    """一次执行需要的执行器与适配器。"""

    executor: RunExecutor
    collector_call: CollectorCall
    runs: OrmRunRepository


def build_run_executor_bundle(
    session: AsyncSession,
    *,
    collector_call: CollectorCall | None = None,
    grade_calculator: GradeCalculator | None = None,
) -> RunExecutorBundle:
    """用 ORM 适配器组装执行器。

    调用方可以注入 collector 调用与等级计算函数。测试用替身走这条路径。
    """
    call = collector_call if collector_call is not None else RunCollectorCall(session)
    runs = OrmRunRepository(session)
    grade_options: dict[str, Any] = {}
    if grade_calculator is not None:
        grade_options["grade_calculator"] = grade_calculator
    executor = RunExecutor(
        runs=cast("RunRepository", runs),
        steps=OrmRunStepRepository(session),
        ledger=OrmRunLedgerRepository(session),
        grades=OrmGradeRepository(session),
        unit_of_work=SessionUnitOfWork(session),
        collector_call=call,
        **grade_options,
    )
    return RunExecutorBundle(executor=executor, collector_call=call, runs=runs)


def build_run_executor(session: AsyncSession) -> RunExecutor:
    """返回接好 ORM 适配器的 ``RunExecutor``。"""
    return build_run_executor_bundle(session).executor


class RunWorkerRuntime:
    """运行队列 worker 的后台循环。

    默认关闭。启动点由 ``main.py`` 的 lifespan 按配置开关决定。
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        worker_id: str | None = None,
        lease_seconds: float = 300.0,
        renew_interval_seconds: float | None = None,
        poll_interval_seconds: float = 5.0,
        collector_call_factory: CollectorCallFactory | None = None,
        grade_calculator: GradeCalculator | None = None,
        worker: RunQueueWorker | None = None,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds 必须大于 0")
        self._session_factory = session_factory
        self._poll_interval_seconds = poll_interval_seconds
        self._collector_call_factory = collector_call_factory
        self._grade_calculator = grade_calculator
        self._worker = worker or RunQueueWorker(
            session_factory,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
            renew_interval_seconds=renew_interval_seconds,
        )
        self._loop_task: asyncio.Task[None] | None = None

    @property
    def worker(self) -> RunQueueWorker:
        return self._worker

    @property
    def running(self) -> bool:
        return self._loop_task is not None and not self._loop_task.done()

    def start(self) -> None:
        """启动后台循环。重复调用不新建任务。"""
        if self.running:
            return
        self._loop_task = asyncio.create_task(self._run_forever())
        logger.info(
            "run_worker_started",
            worker_id=self._worker.worker_id,
            poll_interval_seconds=self._poll_interval_seconds,
        )

    async def stop(self) -> None:
        """停止后台循环。等待当前迭代收尾。"""
        if self._loop_task is None:
            return
        self._loop_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._loop_task
        self._loop_task = None
        logger.info("run_worker_stopped", worker_id=self._worker.worker_id)

    async def run_once(self) -> bool:
        """领取并执行一条运行。没有可领取的行时返回 False。"""
        return await self._worker.process_next(self._handle)

    async def _run_forever(self) -> None:
        """持续领取。单条运行的异常不退出循环。"""
        while True:
            try:
                processed = await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("run_worker_iteration_failed")
                processed = False
            if not processed:
                await asyncio.sleep(self._poll_interval_seconds)

    async def _handle(self, claimed: ClaimedRun) -> None:
        """执行一条已领取的运行，并提交本次事务。"""
        async with self._session_factory() as session:
            call = (
                self._collector_call_factory(session)
                if self._collector_call_factory is not None
                else None
            )
            bundle = build_run_executor_bundle(
                session,
                collector_call=call,
                grade_calculator=self._grade_calculator,
            )
            try:
                run = await bundle.executor.execute(claimed.run_id)
            except (RunNotFoundError, InvalidRunTransitionError) as exc:
                # 运行已被取消或已终结。保留原状态，不要覆盖。
                logger.warning(
                    "run_worker_skip_run",
                    run_id=str(claimed.run_id),
                    reason=exc.__class__.__name__,
                )
                return

            mirror = getattr(bundle.collector_call, "mirror_evidence_grade", None)
            if callable(mirror):
                try:
                    await mirror(run.id, run.evidence_grade)
                except Exception:
                    # 等级镜像失败不影响运行结果。运行行仍然提交。
                    logger.exception(
                        "run_worker_evidence_mirror_failed",
                        run_id=str(run.id),
                    )
            await session.commit()


__all__ = [
    "CollectorCallFactory",
    "RunExecutorBundle",
    "RunWorkerRuntime",
    "build_run_executor",
    "build_run_executor_bundle",
]
