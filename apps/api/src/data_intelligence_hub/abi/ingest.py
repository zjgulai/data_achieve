"""ABI 摄取/导出常驻 worker 的最小骨架。

本模块做四件事：

1. 启动时校验数据库迁移已到 head，未到就退出，由 ``restart: unless-stopped``
   等待下一次；这样 worker 不会在缺表的环境里空转。
2. 每分钟一个 tick，向 ``meta.worker_heartbeat`` 写心跳。
3. 摄取角色在 Asia/Shanghai 02:15 为每个启用的 Apify 账号入队一条
   T-1 的 ``scan`` 作业。日期由应用算好后传参，SQL 里不出现 ``current_date``。
4. 导出角色每个 tick 领一批 queued 作业并执行（``drain_export_queue``），
   每个作业独立事务。遮罩、CSV 注入前缀、路径越界校验都在
   ``abi_export.run_job`` 内部完成，这里只负责调度与计数。

刻意不做的事：不实现清单扫描、不拉 item。摄取侧仍是骨架——只入队 scan，
不消费。这些属于后续切片，先保证容器能起、心跳可见、调度幂等。

运行方式：

    python -m data_intelligence_hub.abi.ingest
    python -m data_intelligence_hub.abi.ingest --role export
    python -m data_intelligence_hub.abi.ingest --once    # 联调只跑一个 tick
"""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
import socket
import sys
import uuid
from collections.abc import Sequence
from contextlib import suppress
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import cast
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from data_intelligence_hub.core.config import get_settings
from data_intelligence_hub.core.database import (
    async_session_factory,
    check_database_schema,
)
from data_intelligence_hub.core.logging import configure_logging
from data_intelligence_hub.repositories import abi as abi_repo
from data_intelligence_hub.services import abi_export

logger = structlog.get_logger(__name__)

# 方案 §5.1：时区必须显式。容器默认 UTC，不指定会让整条链偏 8 小时。
ABI_TZ = ZoneInfo("Asia/Shanghai")
TICK_SECONDS = 60
WORKER_ROLES = ("ingest", "export")


def compute_target_date(now: datetime) -> date:
    """返回 T-1 的北京日期。

    所有日期由应用算好后作为参数传入 SQL。数据库时区与容器时区不一致时，
    ``current_date`` 会给出不同的日期，这里是唯一口径。
    """
    return now.astimezone(ABI_TZ).date() - timedelta(days=1)


def backfill_dates(
    last_target_date: date | None,
    latest_target_date: date,
    max_days: int = 7,
) -> list[date]:
    """Return the missing T-1 dates to enqueue, capped at ``max_days``.

    A new account has no schedule state: enqueue only the latest T-1, not a
    week of history. An account that missed a window gets the gap filled.
    """
    if last_target_date is None or last_target_date >= latest_target_date:
        return [] if last_target_date is not None else [latest_target_date]
    floor = latest_target_date - timedelta(days=max(1, max_days) - 1)
    start = max(last_target_date + timedelta(days=1), floor)
    dates: list[date] = []
    current = start
    while current <= latest_target_date:
        dates.append(current)
        current += timedelta(days=1)
    return dates


async def write_heartbeat(
    session: AsyncSession,
    *,
    worker_id: str,
    role: str,
    note: str | None = None,
) -> None:
    """写入 ``meta.worker_heartbeat``。

    主键是 ``worker_id``，同一 worker 重复写入即更新。没有独立自增 id，
    因此不能用 INSERT ... ON CONFLICT DO UPDATE 以外的写法。
    """
    await session.execute(
        text(
            """
            INSERT INTO meta.worker_heartbeat
                (worker_id, role, beat_at, current_job_id, note)
            VALUES
                (:worker_id, :role, clock_timestamp(), NULL, :note)
            ON CONFLICT (worker_id) DO UPDATE
            SET role = EXCLUDED.role,
                beat_at = EXCLUDED.beat_at,
                current_job_id = EXCLUDED.current_job_id,
                note = EXCLUDED.note
            """
        ),
        {"worker_id": worker_id, "role": role, "note": note},
    )


async def enqueue_scan_job(session: AsyncSession, target_date: date) -> int:
    """为尚未完成该日期的启用账号入队一条 ``scan`` 作业。

    幂等键格式来自方案 §5.2：``scan:{account}:{target_date}``。
    唯一约束 ``uq_ingest_job_idempotency_key`` 会让重复触发命中
    ``ON CONFLICT DO NOTHING``。``schedule_state.last_target_date`` 过滤
    已经成功的账号，避免每天重复扫同一日期。

    返回本次真正新插入的行数。
    """
    result = await session.execute(
        text(
            """
            INSERT INTO meta.ingest_job
                (id, idempotency_key, job_type, account_id, target_date, state)
            SELECT
                gen_random_uuid(),
                'scan:' || a.apify_user_id || ':' || :target_key,
                'scan',
                a.id,
                CAST(:target_date AS date),
                'queued'
            FROM meta.apify_account a
            LEFT JOIN meta.schedule_state s ON s.account_id = a.id
            WHERE a.enabled
              AND (
                  s.last_target_date IS NULL
                  OR s.last_target_date < CAST(:target_date AS date)
              )
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING id
            """
        ),
        {"target_date": target_date, "target_key": target_date.isoformat()},
    )
    return len(result.all())


async def backfill_scan_jobs(
    session: AsyncSession,
    *,
    latest_target_date: date,
    max_days: int = 7,
) -> tuple[int, int]:
    """Enqueue every missing T-1 date up to ``latest_target_date``.

    Returns ``(enqueued, days)``. A worker that was down for N days fills the
    gap on the next tick, capped at ``max_days`` to avoid a flood.
    """
    row = await session.execute(
        text(
            """
            SELECT MIN(s.last_target_date)
            FROM meta.apify_account a
            LEFT JOIN meta.schedule_state s ON s.account_id = a.id
            WHERE a.enabled
            """
        )
    )
    last = row.scalar()
    dates = backfill_dates(last, latest_target_date, max_days)
    enqueued = 0
    for target_date in dates:
        enqueued += await enqueue_scan_job(session, target_date)
    return enqueued, len(dates)


async def run_tick(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    worker_id: str,
    role: str,
    now: datetime | None = None,
) -> None:
    """执行一次心跳；摄取角色补齐缺失的 T-1 scan 日期。

    单个 tick 自成一个事务：先写业务行，再写心跳，最后一起 commit。
    任一语句失败时整个 tick 回滚，下一分钟重试。
    """
    current = now or datetime.now(UTC)
    note: str | None = None

    async with session_factory() as session:
        if role == "ingest":
            latest = compute_target_date(current)
            enqueued, days = await backfill_scan_jobs(session, latest_target_date=latest)
            if enqueued:
                note = f"scan backfill days={days} enqueued={enqueued}"
                logger.info(
                    "abi_scan_backfill",
                    latest_target_date=latest.isoformat(),
                    days=days,
                    enqueued=enqueued,
                )
        await write_heartbeat(session, worker_id=worker_id, role=f"abi-{role}", note=note)
        await session.commit()

    if role == "export":
        note = await drain_export_queue(session_factory, worker_id=worker_id)
        if note:
            async with session_factory() as session:
                await write_heartbeat(session, worker_id=worker_id, role="abi-export", note=note)
                await session.commit()

    if role == "ingest":
        note = await drain_scan_queue(session_factory, worker_id=worker_id)
        if note:
            async with session_factory() as session:
                await write_heartbeat(session, worker_id=worker_id, role="abi-ingest", note=note)
                await session.commit()


async def drain_export_queue(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    worker_id: str,
    batch: int = 5,
) -> str | None:
    """领取并执行一批 queued 导出作业，返回给心跳用的摘要。

    每个作业独立事务：一个失败不能拖垮同批其它作业。失败已由
    ``run_job`` 内部写进 ``export_job.error`` 并置 ``failed``，这里只统计。

    并发安全靠 ``run_job`` 的 ``FOR UPDATE`` + 状态重查：多个 worker 同时
    领到同一个 id 时，只有一个能把它从 queued 推进到 running，其余得到
    ``AbiExportNotReady``，按「跳过」处理而不是记成失败。
    """
    async with session_factory() as session:
        job_ids = await abi_repo.claim_queued_export_jobs(session, limit=batch)
    if not job_ids:
        return None

    succeeded = 0
    failed = 0
    skipped = 0
    for job_id in job_ids:
        try:
            async with session_factory() as session:
                await abi_export.run_job(session, job_id)
            succeeded += 1
        except abi_export.AbiExportNotReady:
            # 被别的 worker 抢先推进了，不是错误。
            skipped += 1
        except asyncio.CancelledError:
            raise
        except Exception:
            failed += 1
            logger.exception("abi_export_job_failed", job_id=str(job_id), worker_id=worker_id)

    logger.info(
        "abi_export_drained",
        worker_id=worker_id,
        claimed=len(job_ids),
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
    )
    return f"export claimed={len(job_ids)} ok={succeeded} failed={failed} skipped={skipped}"


async def _claim_scan_job(session: AsyncSession, worker_id: str) -> dict[str, object] | None:
    row = await session.execute(
        text(
            """
            UPDATE meta.ingest_job
            SET state = 'running',
                lease_owner = :worker_id,
                lease_expires_at = clock_timestamp() + interval '30 minutes',
                lease_version = lease_version + 1,
                attempts = attempts + 1,
                started_at = COALESCE(started_at, clock_timestamp())
            WHERE id = (
                SELECT id
                FROM meta.ingest_job
                WHERE state = 'queued'
                  AND job_type = 'scan'
                  AND (not_before IS NULL OR not_before <= clock_timestamp())
                ORDER BY created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING id, account_id, target_date, attempts, max_attempts, lease_version
            """
        ),
        {"worker_id": worker_id},
    )
    mapping = row.mappings().first()
    return dict(mapping) if mapping else None


async def _finish_scan_job(
    session: AsyncSession,
    job: dict[str, object],
    *,
    success: bool,
    error: str | None = None,
) -> None:
    if success:
        await session.execute(
            text(
                """
                UPDATE meta.ingest_job
                SET state = 'succeeded',
                    finished_at = clock_timestamp(),
                    lease_owner = NULL,
                    lease_expires_at = NULL,
                    last_error = NULL
                WHERE id = :id AND lease_version = :lease_version
                """
            ),
            {"id": job["id"], "lease_version": job["lease_version"]},
        )
        await session.execute(
            text(
                """
                INSERT INTO meta.schedule_state
                    (id, account_id, last_target_date, last_success_at, updated_at)
                VALUES
                    (gen_random_uuid(), :account_id, :target_date,
                     clock_timestamp(), clock_timestamp())
                ON CONFLICT (account_id) DO UPDATE
                SET last_target_date = GREATEST(
                        schedule_state.last_target_date,
                        EXCLUDED.last_target_date
                    ),
                    last_success_at = GREATEST(
                        schedule_state.last_success_at,
                        EXCLUDED.last_success_at
                    ),
                    updated_at = clock_timestamp()
                """
            ),
            {"account_id": job["account_id"], "target_date": job["target_date"]},
        )
        return

    attempts = int(cast(int, job["attempts"]))
    max_attempts = int(cast(int, job["max_attempts"]))
    state = "dead" if attempts >= max_attempts else "queued"
    await session.execute(
        text(
            """
            UPDATE meta.ingest_job
            SET state = :state,
                not_before = CASE
                    WHEN :state = 'queued'
                    THEN clock_timestamp() + interval '10 minutes'
                    ELSE not_before
                END,
                finished_at = CASE
                    WHEN :state = 'dead' THEN clock_timestamp()
                    ELSE NULL
                END,
                lease_owner = NULL,
                lease_expires_at = NULL,
                last_error = :error
            WHERE id = :id AND lease_version = :lease_version
            """
        ),
        {
            "state": state,
            "error": (error or "unknown")[:500],
            "id": job["id"],
            "lease_version": job["lease_version"],
        },
    )


async def drain_scan_queue(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    worker_id: str,
    batch: int = 2,
) -> str | None:
    """Claim and execute queued scan jobs.

    A job is bound to an account. The token is read from that account's
    encrypted row in ``meta.apify_token``; if no key or token is configured,
    the job is skipped instead of scanning the wrong account.
    """
    from data_intelligence_hub.abi import scan, tokens

    settings = get_settings()
    key = (
        settings.abi_fernet_key.get_secret_value() if settings.abi_fernet_key is not None else None
    )
    succeeded = 0
    failed = 0
    skipped = 0
    claimed = 0

    for _ in range(batch):
        async with session_factory() as session:
            job = await _claim_scan_job(session, worker_id)
            await session.commit()
        if job is None:
            break
        claimed += 1

        if key is None:
            async with session_factory() as session:
                await _finish_scan_job(session, job, success=False, error="abi_fernet_key_missing")
                await session.commit()
            skipped += 1
            continue

        account_id = cast(uuid.UUID, job["account_id"])
        target_date = cast(date, job["target_date"])
        try:
            async with session_factory() as session:
                token = await tokens.get_active_token(session, account_id=account_id, key=key)
                if token is None:
                    await _finish_scan_job(
                        session, job, success=False, error="abi_token_not_configured"
                    )
                    await session.commit()
                    skipped += 1
                    continue
                await tokens.mark_used(session, account_id=account_id)
                await session.commit()
                result = await scan.scan_once(
                    session,
                    token=token,
                    target_date=target_date,
                    max_datasets=None,
                    max_items=None,
                    dry_run=False,
                )
                await _finish_scan_job(session, job, success=True)
                await session.commit()
            succeeded += 1
            logger.info(
                "abi_scan_job_succeeded",
                job_id=str(job["id"]),
                account_id=str(job["account_id"]),
                target_date=str(job["target_date"]),
                datasets=result.get("datasets"),
                items=result.get("items_written"),
            )
        except Exception as exc:
            failed += 1
            logger.exception("abi_scan_job_failed", job_id=str(job["id"]))
            async with session_factory() as session:
                await _finish_scan_job(session, job, success=False, error=str(exc))
                await session.commit()

    if claimed == 0:
        return None
    return f"scan claimed={claimed} ok={succeeded} failed={failed} skipped={skipped}"


def resolve_worker_id(role: str) -> str:
    """worker 标识。显式 ABI_WORKER_ID 优先，否则用角色 + 主机名。"""
    explicit = os.environ.get("ABI_WORKER_ID", "").strip()
    if explicit:
        return explicit
    return f"abi-{role}:{socket.gethostname()}"


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    """SIGTERM / SIGINT 转为优雅停止。不支持的平台直接跳过。"""
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError, RuntimeError):
            loop.add_signal_handler(sig, stop_event.set)


async def run_forever(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    worker_id: str,
    role: str,
) -> None:
    """常驻循环。单个 tick 的异常只记录，不退出进程。"""
    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event)
    logger.info("abi_worker_started", worker_id=worker_id, role=role)

    while not stop_event.is_set():
        try:
            await run_tick(session_factory, worker_id=worker_id, role=role)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("abi_worker_tick_failed", worker_id=worker_id, role=role)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=TICK_SECONDS)
        except TimeoutError:
            continue

    logger.info("abi_worker_stopped", worker_id=worker_id, role=role)


async def ensure_schema_current() -> None:
    """迁移未到 head 就退出。

    退出码 1 让 compose 的 ``restart: unless-stopped`` 继续重试；
    迁移由一次性 ``abi-migrate`` 服务完成，worker 不代跑 DDL。
    """
    status = await check_database_schema()
    if status.status == "current":
        return
    logger.error(
        "abi_schema_not_current",
        status=status.status,
        current_revision=status.current_revision,
        head_revision=status.head_revision,
    )
    raise SystemExit(1)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。``--role export`` 供 abi-export 容器使用。"""
    parser = argparse.ArgumentParser(description="ABI 常驻 worker 骨架")
    parser.add_argument(
        "--role",
        choices=WORKER_ROLES,
        default="ingest",
        help="ingest=摄取调度；export=导出（当前只有心跳骨架）",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="只跑一个 tick 后退出，用于联调",
    )
    parser.add_argument(
        "--scan-once",
        action="store_true",
        help="执行一次 dataset scan 后退出；不进入常驻循环",
    )
    parser.add_argument(
        "--target-date",
        help="scan 的目标北京时间，YYYY-MM-DD；缺省为 T-1",
    )
    parser.add_argument("--max-datasets", type=int, help="本次最多扫描多少个 dataset")
    parser.add_argument("--max-items", type=int, help="每个 dataset 最多拉多少条 item")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只列出 dataset 与 item 预估数，不写库",
    )
    parser.add_argument("--token", help="Apify token；缺省读 APIFY_API_TOKEN")
    parser.add_argument(
        "--seed-tokens",
        action="store_true",
        help="把 token 文件加密写入 meta.apify_token 后退出",
    )
    parser.add_argument(
        "--token-file",
        help="token 文件（每行 label token）；缺省从 stdin 读",
    )
    return parser.parse_args(argv)


async def _run_seed(args: argparse.Namespace) -> None:
    import httpx

    from data_intelligence_hub.abi import scan, tokens

    settings = get_settings()
    if settings.abi_fernet_key is None:
        raise SystemExit("ABI_FERNET_KEY is required for --seed-tokens")
    key = settings.abi_fernet_key.get_secret_value()
    text_value = (
        Path(args.token_file).read_text(encoding="utf-8") if args.token_file else sys.stdin.read()
    )
    entries = tokens.parse_token_file(text_value)
    if not entries:
        raise SystemExit("no tokens found")

    seeded: list[str] = []
    async with (
        httpx.AsyncClient(timeout=60) as client,
        async_session_factory() as session,
    ):
        for label, token in entries:
            account = await scan.get_account(client, token)
            account_id = await scan.ensure_account(session, account=account)
            await tokens.upsert_token(
                session,
                account_id=account_id,
                label=label,
                token=token,
                key=key,
            )
            seeded.append(f"{label}:{account.get('username')}")
        await session.commit()
    logger.info("abi_tokens_seeded", entries=seeded)
    print({"seeded": seeded})


async def _run_scan(args: argparse.Namespace) -> None:
    from data_intelligence_hub.abi import scan

    token = (args.token or "").strip()
    if not token:
        settings = get_settings()
        if settings.apify_api_token is not None:
            token = settings.apify_api_token.get_secret_value()
    if not token:
        raise SystemExit("APIFY_API_TOKEN is required for --scan-once")

    target = (
        date.fromisoformat(args.target_date)
        if args.target_date
        else compute_target_date(datetime.now(UTC))
    )
    await ensure_schema_current()
    async with async_session_factory() as session:
        result = await scan.scan_once(
            session,
            token=token,
            target_date=target,
            max_datasets=args.max_datasets,
            max_items=args.max_items,
            dry_run=bool(args.dry_run),
        )
        await session.commit()
    logger.info("abi_scan_once_done", **result)
    print(result)


async def _run(*, role: str, once: bool, args: argparse.Namespace) -> None:
    await ensure_schema_current()
    if args.seed_tokens:
        await _run_seed(args)
        return
    if args.scan_once:
        await _run_scan(args)
        return
    worker_id = resolve_worker_id(role)
    if once:
        await run_tick(async_session_factory, worker_id=worker_id, role=role)
        return
    # 导出角色不需要额外预热：run_tick 每轮会调 drain_export_queue。
    await run_forever(async_session_factory, worker_id=worker_id, role=role)


def main(argv: Sequence[str] | None = None) -> int:
    """进程入口。"""
    args = parse_args(argv)
    role = str(args.role)
    configure_logging()
    settings = get_settings()
    logger.info(
        "abi_worker_booting",
        role=role,
        export_dir=settings.abi_export_dir,
        fernet_key_configured=settings.abi_fernet_key is not None,
    )
    asyncio.run(_run(role=role, once=bool(args.once), args=args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
