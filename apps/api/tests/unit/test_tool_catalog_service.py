from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.tool_catalog.service import find_tool, get_tool_catalog


def _session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    return engine


async def _build_catalog():
    engine = _session_factory()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        catalog = await get_tool_catalog(session)
    await engine.dispose()
    return catalog


def test_service_returns_catalog_without_running_any_collection() -> None:
    catalog = asyncio.run(_build_catalog())

    # 空数据库没有任何 [test] 运行证据。
    # 所以不得出现 verified、empty 或 degraded——那些都需要运行记录。
    # 缺配置的条目归 config-gated，也属于「无运行证据」。
    observed = {item.availability_view.availability for item in catalog.tools}
    assert observed <= {"untested", "config-gated", "disabled"}, observed
    assert "verified" not in observed
    assert catalog.tool_count > 0

    # 无证据时不得声称有测试时间或记录数。
    for item in catalog.tools:
        assert item.availability_view.last_test_at is None
        assert item.availability_view.last_records_count is None

    # config-gated 与 disabled 都不可执行。
    for item in catalog.tools:
        if item.availability_view.availability in {"config-gated", "disabled"}:
            assert item.executable is False, item.tool_id


def test_service_catalog_is_stable_across_calls() -> None:
    first = asyncio.run(_build_catalog())
    second = asyncio.run(_build_catalog())

    assert first.catalog_digest == second.catalog_digest
    assert first.tool_count == second.tool_count
    assert [item.tool_id for item in first.tools] == [item.tool_id for item in second.tools]


def test_find_tool_returns_matching_descriptor_and_raises_when_absent() -> None:
    catalog = asyncio.run(_build_catalog())
    known = catalog.tools[0].tool_id

    found = find_tool(catalog, known)
    assert found.tool_id == known

    try:
        find_tool(catalog, "definitely_not_a_real_tool_id")
    except KeyError as exc:
        assert "definitely_not_a_real_tool_id" in str(exc)
    else:
        raise AssertionError("缺失工具必须抛出 KeyError，不能静默返回")


def test_service_output_kinds_stay_read_class_for_collection_catalog() -> None:
    catalog = asyncio.run(_build_catalog())

    # 当前目录全部是采集类。
    # 生成、外发与计算类在对应适配器落地前不得出现。
    assert {item.risk_class for item in catalog.tools} == {"read"}
    assert {item.output_kind for item in catalog.tools} == {"records"}
