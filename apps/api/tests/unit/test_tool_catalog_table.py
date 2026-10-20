"""``tool_catalog`` 表、仓储与迁移的单元守卫。

覆盖五件事：

1. 模型能建表，列名覆盖契约。
2. 种子幂等：连续写两次，行数不变。
3. ``tool_id`` 是唯一主键，重复插入被拒绝。
4. 行数等于 ``get_tool_catalog()`` 的 ``tool_count``。
5. 迁移的 ``downgrade`` 删除表。

本文件只用内存 SQLite。它不连接真实 Postgres。
"""

from __future__ import annotations

import importlib.util
import inspect as python_inspect
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.tool_catalog import ToolCatalogEntry
from data_intelligence_hub.repositories.tool_catalog import (
    count_tools,
    get_tool,
    list_tools,
    upsert_tools,
)
from data_intelligence_hub.tool_catalog.service import get_tool_catalog

Scenario = Callable[[AsyncSession], Awaitable[None]]

API_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = API_ROOT / "alembic/versions/202610200047_tool_catalog.py"

EXPECTED_COLUMNS = {
    "tool_id",
    "label",
    "description",
    "category",
    "platform",
    "provider",
    "provider_group",
    "method",
    "content_type",
    "risk_class",
    "output_kind",
    "run_mode",
    "cancellable",
    "executable",
    "is_alias_view",
    "canonical_tool_id",
    "cost_summary",
    "cost_source",
    "catalog_status",
    "availability",
    "contract_version",
    "schema_version",
    "parameters",
    "required_parameters",
    "optional_parameters",
    "output_schema",
    "updated_at",
}


def _make_engine():
    return create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


async def _with_session(callback: Scenario) -> None:
    """在内存 SQLite 上跑一段用例。"""
    engine = _make_engine()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            await callback(session)
    finally:
        await engine.dispose()


def _row(tool_id: str) -> ToolCatalogEntry:
    """构造一行满足全部非空列的工具。"""
    return ToolCatalogEntry(
        tool_id=tool_id,
        label="Sample",
        description="Sample tool",
        category="web",
        platform="web",
        provider="Sample",
        provider_group="sample",
        method="http",
        content_type="application/json",
        risk_class="read",
        output_kind="records",
        run_mode="sync",
        cancellable=False,
        executable=True,
        is_alias_view=False,
        canonical_tool_id=tool_id,
        cost_summary=None,
        cost_source="unknown",
        catalog_status="verified",
        availability="verified",
        contract_version="tool.v1",
        schema_version="tool-catalog.v1",
        parameters=[],
        required_parameters=[],
        optional_parameters=[],
        output_schema=None,
    )


@pytest.mark.anyio
async def test_create_all_creates_table_with_required_columns() -> None:
    """模型必须建出 tool_catalog 表，并覆盖契约列。"""
    engine = _make_engine()
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            columns = await connection.run_sync(
                lambda sync_connection: {
                    column["name"]
                    for column in sa_inspect(sync_connection).get_columns("tool_catalog")
                }
            )
    finally:
        await engine.dispose()

    assert columns >= EXPECTED_COLUMNS


@pytest.mark.anyio
async def test_seed_is_idempotent_and_count_matches_catalog() -> None:
    """连续种子两次，行数不变，且等于目录的 tool_count。"""
    observed: dict[str, int] = {}

    async def scenario(session: AsyncSession) -> None:
        catalog = await get_tool_catalog(session)

        first = await upsert_tools(
            session,
            catalog.tools,
            schema_version=catalog.schema_version,
        )
        await session.commit()
        first_count = await count_tools(session)

        second = await upsert_tools(
            session,
            catalog.tools,
            schema_version=catalog.schema_version,
        )
        await session.commit()
        second_count = await count_tools(session)

        observed["catalog_count"] = catalog.tool_count
        observed["first_inserted"] = first.inserted
        observed["first_updated"] = first.updated
        observed["second_inserted"] = second.inserted
        observed["second_updated"] = second.updated
        observed["first_count"] = first_count
        observed["second_count"] = second_count

    await _with_session(scenario)

    assert observed["catalog_count"] > 0
    assert observed["first_inserted"] == observed["catalog_count"]
    assert observed["first_updated"] == 0
    assert observed["second_inserted"] == 0
    assert observed["second_updated"] == observed["catalog_count"]
    assert observed["first_count"] == observed["catalog_count"]
    assert observed["second_count"] == observed["catalog_count"]


@pytest.mark.anyio
async def test_tool_id_is_unique() -> None:
    """重复的 tool_id 必须被主键拒绝。"""
    rejected: dict[str, bool] = {}

    async def scenario(session: AsyncSession) -> None:
        session.add(_row("duplicate_tool"))
        await session.commit()

        session.add(_row("duplicate_tool"))
        try:
            await session.commit()
        except IntegrityError:
            rejected["value"] = True
            await session.rollback()
        else:
            rejected["value"] = False

    await _with_session(scenario)
    assert rejected["value"] is True, "重复的 tool_id 未被拒绝"


@pytest.mark.anyio
async def test_get_and_list_read_written_rows() -> None:
    """写入后可以按 id 查到行，列表按 id 排序。"""
    observed: dict[str, object] = {}

    async def scenario(session: AsyncSession) -> None:
        catalog = await get_tool_catalog(session)
        await upsert_tools(session, catalog.tools, schema_version=catalog.schema_version)
        await session.commit()

        sample = catalog.tools[0]
        row = await get_tool(session, sample.tool_id)
        missing = await get_tool(session, "definitely_not_a_tool")
        rows = await list_tools(session)

        observed["row_tool_id"] = None if row is None else row.tool_id
        observed["row_label"] = None if row is None else row.label
        observed["row_canonical"] = None if row is None else row.canonical_tool_id
        observed["missing"] = missing
        observed["ids"] = [item.tool_id for item in rows]

    await _with_session(scenario)

    assert observed["row_tool_id"] is not None
    assert observed["row_label"] is not None
    assert observed["row_canonical"] == observed["row_tool_id"]
    assert observed["missing"] is None
    assert observed["ids"] == sorted(observed["ids"])  # type: ignore[arg-type]


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "tool_catalog_migration",
        MIGRATION_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_downgrade_drops_tool_catalog_table() -> None:
    """downgrade 必须删除 tool_catalog 表。"""
    module = _load_migration()

    assert module.revision == "202610200047"
    assert module.down_revision == "202610200046"

    source = python_inspect.getsource(module.downgrade)
    assert 'drop_table("tool_catalog")' in source
