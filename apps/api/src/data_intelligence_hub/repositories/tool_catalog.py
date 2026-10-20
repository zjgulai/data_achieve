"""``tool_catalog`` 表的读写。

仓储只做查询、插入与更新，并调用 ``flush``。
事务提交权留给服务层或脚本入口。
本模块不负责生成目录，目录来源是 ``tool_catalog.service``。
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import NamedTuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.tool_catalog import ToolCatalogEntry
from data_intelligence_hub.tool_catalog.fixtures import (
    family_for_endpoint,
    load_output_schemas,
)
from data_intelligence_hub.tool_catalog.models import ToolDescriptor

DEFAULT_SCHEMA_VERSION = "tool-catalog.v1"


class ToolUpsertResult(NamedTuple):
    """一次 upsert 的数量摘要。"""

    inserted: int
    updated: int
    total: int


def _output_schema_for(tool_id: str) -> dict[str, object] | None:
    """返回工具所属输出家族的结构。

    家族来自只读夹具。没有匹配时返回 None，不猜结构。
    """
    family = family_for_endpoint(tool_id)
    if family is None:
        return None
    families = load_output_schemas()["families"]
    if not isinstance(families, dict):
        return None
    payload = families.get(family)
    if not isinstance(payload, dict):
        return None
    return {"family": family, **payload}


def _row_values(
    descriptor: ToolDescriptor,
    schema_version: str,
) -> dict[str, object]:
    """把只读描述转成表列值的字典。

    ``parameters`` 按 JSON 模式导出，元组会变成列表。
    """
    return {
        "tool_id": descriptor.tool_id,
        "label": descriptor.label,
        "description": descriptor.description,
        "category": descriptor.category,
        "platform": descriptor.platform,
        "provider": descriptor.provider,
        "provider_group": descriptor.provider_group,
        "method": descriptor.method,
        "content_type": descriptor.content_type,
        "risk_class": descriptor.risk_class,
        "output_kind": descriptor.output_kind,
        "run_mode": descriptor.run_mode,
        "cancellable": descriptor.cancellable,
        "executable": descriptor.executable,
        "is_alias_view": descriptor.is_alias_view,
        "canonical_tool_id": descriptor.canonical_tool_id,
        "cost_summary": descriptor.cost.summary,
        "cost_source": descriptor.cost.source,
        "catalog_status": descriptor.availability_view.catalog_status,
        "availability": descriptor.availability_view.availability,
        "contract_version": descriptor.contract_version,
        "schema_version": schema_version,
        "parameters": [
            parameter.model_dump(mode="json") for parameter in descriptor.parameters
        ],
        "required_parameters": list(descriptor.required_parameters),
        "optional_parameters": list(descriptor.optional_parameters),
        "output_schema": _output_schema_for(descriptor.tool_id),
    }


async def upsert_tools(
    session: AsyncSession,
    descriptors: Iterable[ToolDescriptor],
    *,
    schema_version: str = DEFAULT_SCHEMA_VERSION,
) -> ToolUpsertResult:
    """按 ``tool_id`` 写入或更新工具。

    已存在的行只更新列值。新行插入。
    重复调用结果相同，行数不增长。
    """
    items = list(descriptors)
    if not items:
        return ToolUpsertResult(inserted=0, updated=0, total=0)

    tool_ids = [descriptor.tool_id for descriptor in items]
    result = await session.execute(
        select(ToolCatalogEntry).where(ToolCatalogEntry.tool_id.in_(tool_ids))
    )
    existing = {row.tool_id: row for row in result.scalars().all()}

    inserted = 0
    updated = 0
    for descriptor in items:
        values = _row_values(descriptor, schema_version)
        row = existing.get(descriptor.tool_id)
        if row is None:
            session.add(ToolCatalogEntry(**values))
            inserted += 1
            continue
        for key, value in values.items():
            setattr(row, key, value)
        updated += 1

    await session.flush()
    return ToolUpsertResult(inserted=inserted, updated=updated, total=len(items))


async def list_tools(session: AsyncSession) -> list[ToolCatalogEntry]:
    """按 ``tool_id`` 升序返回全部工具。"""
    result = await session.execute(select(ToolCatalogEntry).order_by(ToolCatalogEntry.tool_id))
    return list(result.scalars().all())


async def count_tools(session: AsyncSession) -> int:
    """返回表中的工具行数。"""
    total = await session.scalar(select(func.count()).select_from(ToolCatalogEntry))
    return int(total or 0)


async def get_tool(
    session: AsyncSession,
    tool_id: str,
) -> ToolCatalogEntry | None:
    """按 ``tool_id`` 查一行。未命中时返回 None。"""
    result = await session.execute(
        select(ToolCatalogEntry).where(ToolCatalogEntry.tool_id == tool_id)
    )
    return result.scalar_one_or_none()


__all__ = [
    "DEFAULT_SCHEMA_VERSION",
    "ToolUpsertResult",
    "count_tools",
    "get_tool",
    "list_tools",
    "upsert_tools",
]
