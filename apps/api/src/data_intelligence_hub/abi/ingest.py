"""ABI 摄取/导出常驻 worker 的最小骨架。

本模块只做四件事：

1. 启动时校验数据库迁移已到 head，未到就退出，由 ``restart: unless-stopped``
   等待下一次；这样 worker 不会在缺表的环境里空转。
2. 每分钟一个 tick，向 ``meta.worker_heartbeat`` 写心跳。
3. 摄取角色在 Asia/Shanghai 02:15 为每个启用的 Apify 账号入队一条
   T-1 的 ``scan`` 作业。日期由应用算好后传参，SQL 里不出现 ``current_date``。
4. 导出角色目前只写心跳，导出循环见函数内 TODO。

刻意不做的事：不实现清单扫描、不拉 item、不做 PII 遮罩、不写导出文件。
这些属于后续切片，先保证容器能起、心跳可见、调度幂等。

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
from collections.abc import Sequence
from contextlib import suppress
from datetime import UTC, date, datetime, timedelta
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

logger = structlog.get_logger(__name__)

# 方案 §5.1：时区必须显式。容器默认 UTC，不指定会让整条链偏 8 小时。
ABI_TZ = ZoneInfo("Asia/Shanghai")
SCAN_HOUR = 2
SCAN_MINUTE = 15
TICK_SECONDS = 60
WORKER_ROLES = ("ingest", "export")


def compute_target_date(now: datetime) -> date:
    """返回 T-1 的北京日期。

    所有日期由应用算好后作为参数传入 SQL。数据库时区与容器时区不一致时，
    ``current_date`` 会给出不同的日期，这里是唯一口径。
    """
    return now.astimezone(ABI_TZ).date() - timedelta(days=1)


def is_scan_window(now: datetime) -> bool:
    """是否处于 02:15 这一分钟的触发窗口。

    TODO(ABI): 现在只在 02:15 那一分钟触发。停机错过窗口时按方案 §5.4
    用 ``meta.schedule_state.last_target_date`` 补跑：差 N 天就补 N 条
    按日期的 scan，不能只补昨天，否则中间日期的新增 dataset 会落错分区。
    """
    local_now = now.astimezone(ABI_TZ)
    return (local_now.hour, local_now.minute) == (SCAN_HOUR, SCAN_MINUTE)


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
    """为每个启用的 Apify 账号入队一条 T-1 ``scan`` 作业。

    幂等键格式来自方案 §5.2：``scan:{account}:{target_date}``。
    唯一约束 ``uq_ingest_job_idempotency_key`` 会让重复触发命中
    ``ON CONFLICT DO NOTHING``，所以 02:15 所在的那一分钟重复 tick 也安全。

    返回本次真正新插入的行数。没有启用账号时返回 0。

    TODO(ABI): 这里只入队，不扫描。后续切片补齐：
    1. claim ``meta.ingest_job``（``FOR UPDATE SKIP LOCKED`` + ``lease_version``
       fencing，见迁移 202610280060 的说明）；
    2. scan：分页枚举 dataset，按
       ``items:{dataset_id}:{observed_item_count}:{modified_at}`` 入队；
    3. items：显式 ``offset + limit`` 分页拉取，写 ``raw.apify_item``，
       稳态用 ``ON CONFLICT DO NOTHING``；
    4. 写分区前调用 ``meta.ensure_partitions`` 补齐月份，不能只建未来。
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
            WHERE a.enabled
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING id
            """
        ),
        {"target_date": target_date, "target_key": target_date.isoformat()},
    )
    return len(result.all())


async def run_tick(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    worker_id: str,
    role: str,
    now: datetime | None = None,
) -> None:
    """执行一次心跳；摄取角色在 02:15 额外入队 T-1 scan。

    单个 tick 自成一个事务：先写业务行，再写心跳，最后一起 commit。
    任一语句失败时整个 tick 回滚，下一分钟重试。
    """
    current = now or datetime.now(UTC)
    note: str | None = None

    async with session_factory() as session:
        if role == "ingest" and is_scan_window(current):
            target_date = compute_target_date(current)
            enqueued = await enqueue_scan_job(session, target_date)
            note = f"scan enqueued for {target_date}: {enqueued}"
            logger.info(
                "abi_scan_enqueued",
                target_date=target_date.isoformat(),
                enqueued=enqueued,
            )
        await write_heartbeat(session, worker_id=worker_id, role=f"abi-{role}", note=note)
        await session.commit()


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
    return parser.parse_args(argv)


async def _run(*, role: str, once: bool) -> None:
    await ensure_schema_current()
    worker_id = resolve_worker_id(role)
    if once:
        await run_tick(async_session_factory, worker_id=worker_id, role=role)
        return
    if role == "export":
        # TODO(ABI): 导出循环。当前骨架只维持心跳，保证容器可观测。
        # 后续实现顺序：
        # 1. 用 FOR UPDATE SKIP LOCKED 领取 abi.export_job 里 status='queued' 的行；
        # 2. 按 abi.field_policy 做遮罩；pii_class='unknown' 默认拒绝导出；
        # 3. CSV 处理五种注入前缀：= + - @ \t \r；
        # 4. 产物写 settings.abi_export_dir，文件名与路径都要做越界校验
        #    （Path.resolve().relative_to(export_root)）；
        # 5. 成功/失败都写 meta.audit_log，detail 只存 HMAC 后的 filters。
        logger.info("abi_export_worker_skeleton", note="export loop not implemented")
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
    asyncio.run(_run(role=role, once=bool(args.once)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
