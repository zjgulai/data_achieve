"""``insight_reports`` 仓储层的查询形状测试。

路由级测试只断言响应 JSON 里没有 ``content_html``，那证明不了 SQL 没读它。
本文件直接看仓储函数：编译出的 SELECT 与 ORM 实例的未加载属性。

正文单行 182 KB。列表页一次 50 条，若带上正文会多读约 9 MB。
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import event, inspect
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from data_intelligence_hub.models import Base
from data_intelligence_hub.models.insight_report import (
    InsightReport,
    InsightReportContent,
)
from data_intelligence_hub.repositories.insight_reports import (
    get_content_by_report_id,
    get_report_row,
    list_report_rows,
)

REPORT_HTML = "<!DOCTYPE html><html><body><h1>正文</h1></body></html>"

DATA_SCOPE = {
    "window_label": "2026-10",
    "window_end": "2026-10-28",
    "sample_size": 288,
    "sampling": "392 个 hashtag × 43 天",
    "source": {
        "environment": "local docker / abi_migtest",
        "database": "abitest",
        "last_write_at": "2026-10-28",
        "tables": [{"schema": "raw", "name": "si_tiktok_video", "rows": 31366}],
    },
}


@pytest_asyncio.fixture()
async def engine() -> AsyncIterator[AsyncEngine]:
    test_engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest_asyncio.fixture()
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db_session:
        yield db_session


@pytest.fixture()
def captured_statements(engine: AsyncEngine) -> list[str]:
    statements: list[str] = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", _record)
    return statements


async def _seed(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    workspace_id = uuid.uuid4()
    report_id = uuid.uuid4()
    payload = REPORT_HTML.encode("utf-8")
    session.add(
        InsightReport(
            id=report_id,
            workspace_id=workspace_id,
            project_id=None,
            analysis_type="tiktok_viral_topic",
            title="下周拍什么",
            summary="一句话结论。",
            status="ready",
            version="2026-10-31",
            data_scope=DATA_SCOPE,
            source_status="snapshot_only",
            source_note=None,
            generated_at=datetime(2026, 10, 31, tzinfo=UTC),
            imported_at=datetime(2026, 10, 31, 10, tzinfo=UTC),
            created_by=None,
        )
    )
    session.add(
        InsightReportContent(
            report_id=report_id,
            content_format="html",
            content_html=REPORT_HTML,
            content_sha256=hashlib.sha256(payload).hexdigest(),
            content_bytes=len(payload),
        )
    )
    await session.commit()
    return workspace_id, report_id


def _select_lists_content_html(statements: list[str]) -> bool:
    """只检查 SELECT 列表，不检查 WHERE 子句。"""
    for statement in statements:
        if not statement.lstrip().upper().startswith("SELECT"):
            continue
        projection = statement.split(" FROM ", 1)[0]
        if "content_html" in projection:
            return True
    return False


async def test_list_query_does_not_read_content_html(
    session: AsyncSession,
    captured_statements: list[str],
) -> None:
    workspace_id, _ = await _seed(session)
    captured_statements.clear()

    rows = await list_report_rows(session, workspace_id, limit=10)

    assert len(rows) == 1
    report, content = rows[0]
    assert content is not None
    # 元数据可用。
    assert content.content_bytes == len(REPORT_HTML.encode("utf-8"))
    assert content.content_sha256
    # 正文没有加载，访问它不会被悄悄补查。
    assert "content_html" in inspect(content).unloaded
    assert not _select_lists_content_html(captured_statements), captured_statements


async def test_detail_query_does_not_read_content_html(
    session: AsyncSession,
    captured_statements: list[str],
) -> None:
    workspace_id, report_id = await _seed(session)
    captured_statements.clear()

    row = await get_report_row(session, workspace_id, report_id)

    assert row is not None
    _, content = row
    assert content is not None
    assert "content_html" in inspect(content).unloaded
    assert not _select_lists_content_html(captured_statements), captured_statements


async def test_content_query_reads_content_html_exactly(
    session: AsyncSession,
    captured_statements: list[str],
) -> None:
    _, report_id = await _seed(session)
    captured_statements.clear()

    content = await get_content_by_report_id(session, report_id)

    assert content is not None
    assert content.content_html == REPORT_HTML
    assert "content_html" not in inspect(content).unloaded
    assert _select_lists_content_html(captured_statements), captured_statements
