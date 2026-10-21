"""用量与成本汇总。

数据源是 ``task_runs``。成本优先用运行记录里的实际值；
没有实际值时按价格簿估算。

估算口径：每个运行按一次调用计；按记录计价的端点（per_record /
per_review / per_page）用记录数计。``subscription`` 不估算。
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.task import CollectionTask, TaskRun
from data_intelligence_hub.tool_catalog.fixtures import load_price_book

# 这些计价基准按记录数乘单价；其余按每次运行乘单价。
_RECORD_BASES = frozenset({"per_record", "per_review", "per_page"})


def _price_entries() -> dict[str, dict[str, Any]]:
    book = load_price_book()
    entries = book.get("entries")
    return entries if isinstance(entries, dict) else {}


def _estimate_cost(
    endpoint_type: str | None,
    records_count: int,
    actual_cost: Decimal | None,
    entries: dict[str, dict[str, Any]],
) -> Decimal:
    if actual_cost is not None:
        return actual_cost
    if not endpoint_type:
        return Decimal("0")
    entry = entries.get(endpoint_type)
    if not isinstance(entry, dict):
        return Decimal("0")
    basis = entry.get("quantity_basis")
    if basis == "subscription":
        return Decimal("0")
    try:
        unit_price = Decimal(str(entry.get("unit_price") or 0))
    except Exception:  # noqa: BLE001 - 价格簿异常值按 0 处理
        return Decimal("0")
    quantity = records_count if basis in _RECORD_BASES else 1
    if quantity <= 0:
        quantity = 1
    return unit_price * Decimal(quantity)


async def get_usage_summary(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    days: int = 30,
    project_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    since = datetime.now(UTC) - timedelta(days=days)
    statement = (
        select(
            TaskRun.endpoint_type,
            TaskRun.provider,
            TaskRun.records_count,
            TaskRun.total_cost_usd,
            TaskRun.created_at,
        )
        .join(CollectionTask, CollectionTask.id == TaskRun.task_id)
        .where(
            TaskRun.workspace_id == workspace_id,
            TaskRun.created_at >= since,
        )
    )
    if project_id is not None:
        statement = statement.where(CollectionTask.project_id == project_id)
    rows = (await session.execute(statement)).all()

    entries = _price_entries()
    totals = {"runs": 0, "records": 0, "cost_usd": Decimal("0")}
    by_provider: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"runs": 0, "records": 0, "cost_usd": Decimal("0")}
    )
    by_endpoint: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"runs": 0, "records": 0, "cost_usd": Decimal("0")}
    )
    by_day: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"runs": 0, "records": 0, "cost_usd": Decimal("0")}
    )

    for endpoint_type, provider, records_count, actual_cost, created_at in rows:
        cost = _estimate_cost(
            endpoint_type, int(records_count or 0), actual_cost, entries
        )
        provider_key = provider or "unknown"
        endpoint_key = endpoint_type or "unknown"
        day_key = created_at.astimezone(UTC).date().isoformat() if created_at else "unknown"
        for bucket in (
            totals,
            by_provider[provider_key],
            by_endpoint[endpoint_key],
            by_day[day_key],
        ):
            bucket["runs"] += 1
            bucket["records"] += int(records_count or 0)
            bucket["cost_usd"] = bucket["cost_usd"] + cost

    def dump(bucket: dict[str, Any]) -> dict[str, Any]:
        return {
            "runs": bucket["runs"],
            "records": bucket["records"],
            "cost_usd": str(bucket["cost_usd"].quantize(Decimal("0.000001"))),
        }

    return {
        "since": since.date().isoformat(),
        "days": days,
        "project_id": str(project_id) if project_id else None,
        "totals": dump(totals),
        "by_provider": [
            {"provider": key, **dump(value)}
            for key, value in sorted(by_provider.items())
        ],
        "by_endpoint": [
            {"endpoint_type": key, **dump(value)}
            for key, value in sorted(
                by_endpoint.items(), key=lambda item: item[1]["cost_usd"], reverse=True
            )[:50]
        ],
        "by_day": [
            {"date": key, **dump(by_day[key])} for key in sorted(by_day)
        ],
    }