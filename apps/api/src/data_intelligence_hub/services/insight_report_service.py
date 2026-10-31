"""``/api/insight`` 的列表、详情与正文服务。

状态计算规则（设计文档 §2.5）：

* ``status=withdrawn`` 的报告不返回。
* 正文表没有行时，列表/详情返回 ``content_missing``，而不是 404。
* 正文端点每次都校验 SHA-256；不一致时 fail-closed。
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.insight_report import InsightReport
from data_intelligence_hub.models.workspace import Workspace
from data_intelligence_hub.repositories.insight_reports import (
    count_reports_by_analysis_type,
    get_content_by_report_id,
    get_report_row,
    list_report_rows,
)
from data_intelligence_hub.schemas.insight_report import (
    InsightAnalysisTypeListResponse,
    InsightAnalysisTypeResponse,
    InsightGenerationStatus,
    InsightReportContentData,
    InsightReportListResponse,
    InsightReportResponse,
    as_utc,
)
from data_intelligence_hub.services.exceptions import (
    InsightReportContentMissingError,
    InsightReportIntegrityError,
    InsightReportNotFoundError,
)
from data_intelligence_hub.services.insight_report_catalog import (
    INSIGHT_ANALYSIS_TYPES,
    SOURCE_NOT_CONNECTED_REASON,
)

logger = structlog.get_logger(__name__)

DEFAULT_LIST_LIMIT = 20
MAX_LIST_LIMIT = 50


class InsightCursorError(ValueError):
    """游标非法。路由捕获后返回 422 ``validation_error``。"""


def encode_cursor(generated_at: datetime, report_id: uuid.UUID) -> str:
    """把 ``(generated_at, id)`` 编成不透明游标。"""
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=UTC)
    raw = f"{generated_at.astimezone(UTC).isoformat()}|{report_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).rstrip(b"=").decode("ascii")


def decode_cursor(value: str) -> tuple[datetime, uuid.UUID]:
    """解析游标。非法游标抛 ``InsightCursorError``，路由转成 422。"""
    try:
        padded = value + "=" * (-len(value) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        generated_at_text, report_id_text = raw.split("|", 1)
        generated_at = datetime.fromisoformat(generated_at_text)
        report_id = uuid.UUID(report_id_text)
    except (ValueError, UnicodeError, binascii.Error) as exc:
        msg = "invalid_cursor"
        raise InsightCursorError(msg) from exc
    if generated_at.tzinfo is None:
        msg = "invalid_cursor"
        raise InsightCursorError(msg)
    return generated_at.astimezone(UTC), report_id


async def list_analysis_types(
    session: AsyncSession,
    workspace: Workspace,
) -> InsightAnalysisTypeListResponse:
    counts = await count_reports_by_analysis_type(session, workspace.id)
    items: list[InsightAnalysisTypeResponse] = []
    for spec in INSIGHT_ANALYSIS_TYPES:
        report_count, latest_report_at = counts.get(spec.key, (0, None))
        items.append(
            InsightAnalysisTypeResponse(
                key=spec.key,
                name=spec.name,
                description=spec.description,
                report_count=report_count,
                latest_report_at=(
                    as_utc(latest_report_at) if latest_report_at is not None else None
                ),
                generation=InsightGenerationStatus(
                    available=False,
                    reason_code="source_not_connected",
                    reason=SOURCE_NOT_CONNECTED_REASON,
                ),
            )
        )
    return InsightAnalysisTypeListResponse(items=items)


async def list_reports(
    session: AsyncSession,
    workspace: Workspace,
    *,
    analysis_type: str | None = None,
    project_id: uuid.UUID | None = None,
    limit: int = DEFAULT_LIST_LIMIT,
    cursor: str | None = None,
) -> InsightReportListResponse:
    cursor_value = decode_cursor(cursor) if cursor is not None else None
    rows = await list_report_rows(
        session,
        workspace.id,
        analysis_type=analysis_type,
        project_id=project_id,
        limit=limit,
        cursor=cursor_value,
    )
    has_more = len(rows) > limit
    visible_rows = rows[:limit]
    items = [
        InsightReportResponse.from_model(report, content)
        for report, content in visible_rows
    ]
    next_cursor = None
    if has_more and visible_rows:
        last_report = visible_rows[-1][0]
        next_cursor = encode_cursor(last_report.generated_at, last_report.id)
    return InsightReportListResponse(items=items, next_cursor=next_cursor)


async def get_report(
    session: AsyncSession,
    workspace: Workspace,
    report_id: uuid.UUID,
) -> InsightReportResponse:
    row = await get_report_row(session, workspace.id, report_id)
    if row is None:
        raise InsightReportNotFoundError
    report, content = row
    return InsightReportResponse.from_model(report, content)


async def get_report_content(
    session: AsyncSession,
    workspace: Workspace,
    report_id: uuid.UUID,
    *,
    request_id: str | None = None,
) -> InsightReportContentData:
    row = await get_report_row(session, workspace.id, report_id)
    if row is None:
        raise InsightReportNotFoundError
    report, content_meta = row
    if content_meta is None:
        raise InsightReportContentMissingError
    content = await get_content_by_report_id(session, report.id)
    if content is None:
        raise InsightReportContentMissingError

    html = content.content_html
    actual_sha256 = hashlib.sha256(html.encode("utf-8")).hexdigest()
    if actual_sha256 != content.content_sha256:
        logger.warning(
            "insight_report_integrity_failed",
            report_id=str(report.id),
            expected_sha256=content.content_sha256,
            actual_sha256=actual_sha256,
            request_id=request_id,
        )
        raise InsightReportIntegrityError

    return InsightReportContentData(
        report=report,
        content=content,
        html=html,
        sha256=actual_sha256,
        filename=_content_filename(report),
    )


def _content_filename(report: InsightReport) -> str:
    slug = report.analysis_type.replace("_", "-")
    safe_version = report.version.replace("/", "-").replace(" ", "-")
    return f"{slug}-{safe_version}.html"


__all__ = [
    "DEFAULT_LIST_LIMIT",
    "MAX_LIST_LIMIT",
    "InsightCursorError",
    "decode_cursor",
    "encode_cursor",
    "get_report",
    "get_report_content",
    "list_analysis_types",
    "list_reports",
]
