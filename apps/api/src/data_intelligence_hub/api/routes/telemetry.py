"""Telemetry 只读接口(Plan C D5)。

GET /api/telemetry/bot-summary?days=30
按 command/channel 聚合 bot_request_log,给「高频请求 ≥10 次/周」
周报与 Stage 3 自进化统计用。鉴权与 /api/automation 同级(登录用户)。
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Query

from data_intelligence_hub.api.deps import AuthenticatedContextDep, SessionDep
from data_intelligence_hub.models.bot_request_log import BotRequestLog

router = APIRouter(tags=["telemetry"])


@router.get("/bot-summary")
async def bot_summary(
    session: SessionDep,
    _context: AuthenticatedContextDep,
    days: int = Query(default=30, ge=1, le=365),
) -> dict[str, Any]:
    """按 command 与 channel 聚合最近 N 天的 Bot 请求。"""
    since = datetime.now(UTC) - timedelta(days=days)
    rows = (
        await session.execute(
            sa.select(
                BotRequestLog.command,
                BotRequestLog.channel,
                BotRequestLog.trigger,
                sa.func.count(),
            )
            .where(BotRequestLog.created_at >= since)
            .group_by(BotRequestLog.command, BotRequestLog.channel, BotRequestLog.trigger)
        )
    ).all()

    by_command: Counter[str] = Counter()
    by_channel: Counter[str] = Counter()
    by_trigger: Counter[str] = Counter()
    total = 0
    for command, channel, trigger, count in rows:
        by_command[command] += count
        by_channel[channel] += count
        by_trigger[trigger] += count
        total += count

    return {
        "window_days": days,
        "since": since.isoformat(),
        "total_requests": total,
        "by_command": [
            {"command": command, "count": count}
            for command, count in by_command.most_common()
        ],
        "by_channel": [
            {"channel": channel, "count": count}
            for channel, count in by_channel.most_common()
        ],
        "by_trigger": [
            {"trigger": trigger, "count": count}
            for trigger, count in by_trigger.most_common()
        ],
    }
