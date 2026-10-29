"""导出 worker 的调度逻辑。

改动前 ``run_job`` 全仓没有调用方，``abi/ingest.py`` 的 export 角色只写
心跳。审批通过后作业停在 ``queued`` 永远不动——导出闭环差最后一环。

这些测试用假 session factory 与假 run_job，不碰数据库，专门固定三件事：
1. 没有排队作业时返回 None（心跳不该被无意义的摘要污染）。
2. 被别的 worker 抢先推进（AbiExportNotReady）记为 skipped，不是 failed。
3. 单个作业失败不影响同批其它作业。

用 count 断言而不是 spawn：spawn 会让 Ctrl-C 变成僵尸进程。
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from data_intelligence_hub.abi import ingest
from data_intelligence_hub.services import abi_export


class _FakeSession:
    """够用的假 session：claim 之外的操作一律视为编程错误。"""

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False


class _FakeSessionFactory:
    def __init__(self, job_ids: list[uuid.UUID]) -> None:
        self._job_ids = job_ids
        self.opened = 0

    def __call__(self) -> _FakeSession:
        self.opened += 1
        return _FakeSession()


@pytest.fixture()
def patched_claim(monkeypatch: pytest.MonkeyPatch):
    """把 claim_queued_export_jobs 换成返回固定 id 列表的假函数。"""

    def _install(job_ids: list[uuid.UUID]) -> None:
        async def _claim(_session: Any, *, limit: int = 5) -> list[uuid.UUID]:
            return job_ids

        monkeypatch.setattr(ingest.abi_repo, "claim_queued_export_jobs", _claim)

    return _install


@pytest.mark.asyncio
async def test_returns_none_when_queue_empty(patched_claim) -> None:
    patched_claim([])
    factory = _FakeSessionFactory([])

    result = await ingest.drain_export_queue(factory, worker_id="w1")  # type: ignore[arg-type]

    assert result is None


@pytest.mark.asyncio
async def test_counts_successful_jobs(patched_claim, monkeypatch) -> None:
    job_id = uuid.uuid4()
    patched_claim([job_id])
    ran: list[uuid.UUID] = []

    async def _run(_session: Any, job_id_arg: uuid.UUID) -> None:
        ran.append(job_id_arg)

    monkeypatch.setattr(ingest.abi_export, "run_job", _run)

    result = await ingest.drain_export_queue(
        _FakeSessionFactory([job_id]), worker_id="w1"  # type: ignore[arg-type]
    )

    assert ran == [job_id]
    assert result == "export claimed=1 ok=1 failed=0 skipped=0"


@pytest.mark.asyncio
async def test_lost_race_counts_as_skipped_not_failed(
    patched_claim, monkeypatch
) -> None:
    """多个 worker 领到同一 id 时，抢输的那个应记 skipped。"""

    job_id = uuid.uuid4()
    patched_claim([job_id])

    async def _run(_session: Any, _job_id: uuid.UUID) -> None:
        raise abi_export.AbiExportNotReady("abi_export_not_queued")

    monkeypatch.setattr(ingest.abi_export, "run_job", _run)

    result = await ingest.drain_export_queue(
        _FakeSessionFactory([job_id]), worker_id="w1"  # type: ignore[arg-type]
    )

    assert result == "export claimed=1 ok=0 failed=0 skipped=1"


@pytest.mark.asyncio
async def test_one_failure_does_not_stop_the_batch(patched_claim, monkeypatch) -> None:
    good = uuid.uuid4()
    bad = uuid.uuid4()
    patched_claim([bad, good])
    ran: list[uuid.UUID] = []

    async def _run(_session: Any, job_id: uuid.UUID) -> None:
        ran.append(job_id)
        if job_id == bad:
            raise RuntimeError("boom")

    monkeypatch.setattr(ingest.abi_export, "run_job", _run)

    result = await ingest.drain_export_queue(
        _FakeSessionFactory([bad, good]), worker_id="w1"  # type: ignore[arg-type]
    )

    # 两个都尝试过：坏的那个失败后，好的仍然执行。
    assert ran == [bad, good]
    assert result == "export claimed=2 ok=1 failed=1 skipped=0"


@pytest.mark.asyncio
async def test_cancellation_propagates(patched_claim, monkeypatch) -> None:
    """CancelledError 必须向上冒泡，否则 SIGTERM 无法停下进程。"""

    import asyncio

    job_id = uuid.uuid4()
    patched_claim([job_id])

    async def _run(_session: Any, _job_id: uuid.UUID) -> None:
        raise asyncio.CancelledError()

    monkeypatch.setattr(ingest.abi_export, "run_job", _run)

    with pytest.raises(asyncio.CancelledError):
        await ingest.drain_export_queue(
            _FakeSessionFactory([job_id]), worker_id="w1"  # type: ignore[arg-type]
        )
