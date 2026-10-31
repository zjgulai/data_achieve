"""``insight_reports`` / ``insight_report_contents`` 的工作区隔离查询。

列表与详情查询 ``outerjoin`` 正文表，但用 ``load_only`` 只取正文的元数据列。
``content_html`` 单行最大 182 KB，页面级查询带上它会成倍放大传输量与内存。
这是契约要求（``docs/design/insight-new-integration.md`` §2）：列表和详情
不读正文列，正文只在 ``get_content_by_report_id`` 读取一次。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from data_intelligence_hub.models.insight_report import (
    InsightReport,
    InsightReportContent,
)

# 列表与详情允许读取的正文列。``content_html`` 故意不在其中。
_CONTENT_METADATA_COLUMNS = (
    InsightReportContent.content_format,
    InsightReportContent.content_sha256,
    InsightReportContent.content_bytes,
)


async def list_report_rows(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    analysis_type: str | None = None,
    project_id: uuid.UUID | None = None,
    limit: int,
    cursor: tuple[datetime, uuid.UUID] | None = None,
) -> list[tuple[InsightReport, InsightReportContent | None]]:
    """按工作区列报告，附带正文元数据（不含 HTML）。

    返回 ``limit + 1`` 行，调用方用多出的一行判断是否还有下一页。
    排序固定 ``generated_at DESC, id DESC``。
    """
    statement = (
        select(InsightReport, InsightReportContent)
        .outerjoin(
            InsightReportContent,
            InsightReportContent.report_id == InsightReport.id,
        )
        .options(load_only(*_CONTENT_METADATA_COLUMNS))
        .where(
            InsightReport.workspace_id == workspace_id,
            InsightReport.status != "withdrawn",
        )
    )
    if analysis_type is not None:
        statement = statement.where(InsightReport.analysis_type == analysis_type)
    if project_id is not None:
        # 项目级过滤包含项目报告与工作区级报告（project_id IS NULL）。
        statement = statement.where(
            or_(
                InsightReport.project_id.is_(None),
                InsightReport.project_id == project_id,
            )
        )
    if cursor is not None:
        cursor_generated_at, cursor_id = cursor
        statement = statement.where(
            or_(
                InsightReport.generated_at < cursor_generated_at,
                and_(
                    InsightReport.generated_at == cursor_generated_at,
                    InsightReport.id < cursor_id,
                ),
            )
        )
    statement = statement.order_by(
        InsightReport.generated_at.desc(),
        InsightReport.id.desc(),
    ).limit(limit + 1)
    result = await session.execute(statement)
    return [(row[0], row[1]) for row in result.all()]


async def get_report_row(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    report_id: uuid.UUID,
) -> tuple[InsightReport, InsightReportContent | None] | None:
    """按工作区取一份未下架的报告，附带正文元数据（不含 HTML）。"""
    result = await session.execute(
        select(InsightReport, InsightReportContent)
        .outerjoin(
            InsightReportContent,
            InsightReportContent.report_id == InsightReport.id,
        )
        .options(load_only(*_CONTENT_METADATA_COLUMNS))
        .where(
            InsightReport.workspace_id == workspace_id,
            InsightReport.id == report_id,
            InsightReport.status != "withdrawn",
        )
    )
    row = result.first()
    if row is None:
        return None
    return row[0], row[1]


async def get_report_by_scope(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    analysis_type: str,
    version: str,
) -> InsightReport | None:
    """导入幂等检查用：按唯一键取报告。"""
    result = await session.execute(
        select(InsightReport).where(
            InsightReport.workspace_id == workspace_id,
            InsightReport.analysis_type == analysis_type,
            InsightReport.version == version,
        )
    )
    return result.scalar_one_or_none()


async def get_content_by_report_id(
    session: AsyncSession,
    report_id: uuid.UUID,
) -> InsightReportContent | None:
    result = await session.execute(
        select(InsightReportContent).where(
            InsightReportContent.report_id == report_id
        )
    )
    return result.scalar_one_or_none()


async def count_reports_by_analysis_type(
    session: AsyncSession,
    workspace_id: uuid.UUID,
) -> dict[str, tuple[int, datetime | None]]:
    """每个分析类型的未下架报告数与最近生成时间。"""
    result = await session.execute(
        select(
            InsightReport.analysis_type,
            func.count(InsightReport.id),
            func.max(InsightReport.generated_at),
        )
        .where(
            InsightReport.workspace_id == workspace_id,
            InsightReport.status != "withdrawn",
        )
        .group_by(InsightReport.analysis_type)
    )
    return {row[0]: (int(row[1]), row[2]) for row in result.all()}
