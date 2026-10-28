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
_EXA_AGENT_FIXED_PRICES = {
    "minimal": Decimal("0.012"),
    "low": Decimal("0.025"),
    "medium": Decimal("0.10"),
    "high": Decimal("0.50"),
    "xhigh": Decimal("1.00"),
}


def _price_entries() -> dict[str, dict[str, Any]]:
    book = load_price_book()
    entries = book.get("entries")
    return entries if isinstance(entries, dict) else {}


def _estimate_cost(
    endpoint_type: str | None,
    records_count: int,
    actual_cost: Decimal | None,
    entries: dict[str, dict[str, Any]],
    task_config: dict[str, Any] | None = None,
) -> Decimal:
    """估算一次运行的成本。无法估算时返回 0。

    保留此函数只为兼容既有 `get_usage_summary` 的累加语义。
    需要区分「免费」与「价格未知」的调用方（逐次运行账本）必须用
    :func:`_resolve_cost`，它同时给出 cost_source。
    """
    return _resolve_cost(
        endpoint_type, records_count, actual_cost, entries, task_config
    )[0]


def _resolve_cost(
    endpoint_type: str | None,
    records_count: int,
    actual_cost: Decimal | None,
    entries: dict[str, dict[str, Any]],
    task_config: dict[str, Any] | None = None,
) -> tuple[Decimal, str]:
    """返回 (金额, 来源)。

    ``cost_source`` 三态：

    - ``actual``：运行记录里有上游回报的真实花费。
    - ``estimated``：按价格簿估算得出。
    - ``unknown``：价格簿没有该端点，或计价方式无法换算成金额
      （订阅制、metered 的 exa 研究、未登记的端点）。

    ``unknown`` 与「金额为 0 的免费端点」必须区分：前者是不知情，
    后者是确知免费。逐次对账时把 unknown 当成 0 会低估总成本。
    """
    if actual_cost is not None:
        return actual_cost, "actual"
    if not endpoint_type:
        return Decimal("0"), "unknown"
    if endpoint_type == "exa_agent_research":
        effort = str((task_config or {}).get("effort") or "medium")
        if effort in _EXA_AGENT_FIXED_PRICES:
            return _EXA_AGENT_FIXED_PRICES[effort], "estimated"
        # auto/ultra 按实际用量计费，上游没回传金额时就无从得知。
        return Decimal("0"), "unknown"
    entry = entries.get(endpoint_type)
    if not isinstance(entry, dict):
        return Decimal("0"), "unknown"
    basis = entry.get("quantity_basis")
    if basis == "subscription":
        # 订阅制端点不按次计费，单次成本确知为 0。
        return Decimal("0"), "estimated"
    try:
        unit_price = Decimal(str(entry.get("unit_price") or 0))
    except Exception:  # noqa: BLE001 - 价格簿异常值按 0 处理
        return Decimal("0"), "unknown"
    quantity = records_count if basis in _RECORD_BASES else 1
    if quantity <= 0:
        quantity = 1
    return unit_price * Decimal(quantity), "estimated"


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
            CollectionTask.config,
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

    for endpoint_type, provider, records_count, actual_cost, created_at, task_config in rows:
        cost = _estimate_cost(
            endpoint_type,
            int(records_count or 0),
            actual_cost,
            entries,
            task_config,
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


async def get_run_ledger(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    days: int = 7,
    limit: int = 200,
    project_id: uuid.UUID | None = None,
    task_run_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """逐次运行账本。回答「每次运行值不值」。

    与 `get_usage_summary` 的区别：聚合只有总数，无法下钻到单次；
    这里一行一次运行，并带 `cost_source`，让调用方知道金额是实测、
    估算还是未知。两者用同一套 `_resolve_cost`，保证口径一致。

    按 `created_at` 倒序；`limit` 上限 500，避免一次拉全库。
    指定 `task_run_id` 时只返回该行（用于运行详情页）。
    """
    since = datetime.now(UTC) - timedelta(days=days)
    statement = (
        select(
            TaskRun.id,
            TaskRun.task_id,
            TaskRun.provider,
            TaskRun.endpoint_type,
            TaskRun.status,
            TaskRun.records_count,
            TaskRun.total_cost_usd,
            TaskRun.unit,
            TaskRun.quantity,
            TaskRun.unit_price,
            TaskRun.started_at,
            TaskRun.finished_at,
            TaskRun.created_at,
            CollectionTask.config,
        )
        .join(CollectionTask, CollectionTask.id == TaskRun.task_id)
        .where(
            TaskRun.workspace_id == workspace_id,
            TaskRun.created_at >= since,
        )
    )
    if project_id is not None:
        statement = statement.where(CollectionTask.project_id == project_id)
    if task_run_id is not None:
        statement = statement.where(TaskRun.id == task_run_id)
    statement = statement.order_by(TaskRun.created_at.desc()).limit(limit)

    rows = (await session.execute(statement)).all()
    entries = _price_entries()

    items: list[dict[str, Any]] = []
    for row in rows:
        (
            run_id,
            task_id,
            provider,
            endpoint_type,
            status,
            records_count,
            actual_cost,
            unit,
            quantity,
            unit_price,
            started_at,
            finished_at,
            created_at,
            task_config,
        ) = row

        cost, cost_source = _resolve_cost(
            endpoint_type,
            int(records_count or 0),
            actual_cost,
            entries,
            task_config,
        )

        duration_ms = None
        if started_at is not None and finished_at is not None:
            duration_ms = round((finished_at - started_at).total_seconds() * 1000)

        items.append(
            {
                "task_run_id": str(run_id),
                "task_id": str(task_id),
                "provider": provider,
                "endpoint_type": endpoint_type,
                "status": status,
                "records_count": int(records_count or 0),
                "cost_usd": str(cost.quantize(Decimal("0.000001"))),
                "cost_source": cost_source,
                "unit": unit,
                # Numeric 列读出来是 Decimal，转字符串避免浮点误差。
                "quantity": _decimal_text(quantity),
                "unit_price": _decimal_text(unit_price),
                "duration_ms": duration_ms,
                "created_at": created_at.isoformat() if created_at else None,
            }
        )

    return {
        "since": since.date().isoformat(),
        "days": days,
        "limit": limit,
        "project_id": str(project_id) if project_id else None,
        "items": items,
        "totals": {
            "runs": len(items),
            "records": sum(item["records_count"] for item in items),
            # 只累加已知金额；unknown 单独计数，不混进总额。
            # sum 的起始值必须是 Decimal：空序列时 sum 返回 int 0，
            # 而 int 没有 quantize。
            "cost_usd": str(
                sum(
                    (
                        Decimal(item["cost_usd"])
                        for item in items
                        if item["cost_source"] != "unknown"
                    ),
                    Decimal("0"),
                ).quantize(Decimal("0.000001"))
            ),
            "unknown_cost_runs": sum(
                1 for item in items if item["cost_source"] == "unknown"
            ),
        },
    }


def _decimal_text(value: Decimal | None) -> str | None:
    """Numeric 列转字符串。None 保持 None，不写成 0。"""
    if value is None:
        return None
    return str(value)
