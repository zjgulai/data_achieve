"""``/api/insight`` 的响应模型与 ``data_scope`` 校验。

``data_scope`` 的内层形状由这里校验；数据库只存 JSONB，不约束内层结构，
这样以后加字段不用迁移（设计文档 §2.4）。
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from data_intelligence_hub.models.insight_report import (
    InsightReport,
    InsightReportContent,
)

InsightReportStatus = Literal["ready", "content_missing"]
InsightSourceStatus = Literal["snapshot_only", "connected", "unavailable"]


def as_utc(value: datetime) -> datetime:
    """统一成带时区的 UTC。

    PostgreSQL 的 timestamptz 会带回 tzinfo；SQLite 测试库不会。API 契约要求
    ISO 8601 UTC 带 ``Z``，所以在序列化前补齐。
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class InsightSourceTable(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    schema_name: str = Field(alias="schema")
    name: str
    rows: int = Field(ge=0)


class InsightDataSource(BaseModel):
    model_config = ConfigDict(extra="allow")

    environment: str
    database: str
    last_write_at: date
    tables: list[InsightSourceTable] = Field(default_factory=list)


class InsightDataScope(BaseModel):
    model_config = ConfigDict(extra="allow")

    window_label: str
    window_end: date
    sample_size: int = Field(ge=0)
    sampling: str
    source: InsightDataSource


class InsightGenerationStatus(BaseModel):
    """生成能力的声明，不是实时探测。

    v1 恒为不可用：生产没有报告依赖的 ABI 快照。这个字段让页面能直接
    说明边界，而不是渲染一个点了就失败的入口。
    """

    available: bool
    reason_code: str
    reason: str


class InsightAnalysisTypeResponse(BaseModel):
    key: str
    name: str
    description: str
    report_count: int = Field(ge=0)
    latest_report_at: datetime | None
    generation: InsightGenerationStatus


class InsightAnalysisTypeListResponse(BaseModel):
    items: list[InsightAnalysisTypeResponse]


class InsightReportResponse(BaseModel):
    """报告元数据。正文永远不在这里——只有 ``/content`` 返回正文。"""

    id: uuid.UUID
    analysis_type: str
    title: str
    summary: str
    status: InsightReportStatus
    version: str
    data_scope: InsightDataScope
    source_status: InsightSourceStatus
    source_note: str | None
    generated_at: datetime
    imported_at: datetime
    created_by: uuid.UUID | None
    has_content: bool
    content_format: str | None
    content_bytes: int | None
    content_sha256: str | None

    @classmethod
    def from_model(
        cls,
        report: InsightReport,
        content: InsightReportContent | None,
    ) -> InsightReportResponse:
        has_content = content is not None
        return cls(
            id=report.id,
            analysis_type=report.analysis_type,
            title=report.title,
            summary=report.summary,
            status="ready" if has_content else "content_missing",
            version=report.version,
            data_scope=InsightDataScope.model_validate(report.data_scope),
            source_status=report.source_status,
            source_note=report.source_note,
            generated_at=as_utc(report.generated_at),
            imported_at=as_utc(report.imported_at),
            created_by=report.created_by,
            has_content=has_content,
            content_format=content.content_format if content is not None else None,
            content_bytes=content.content_bytes if content is not None else None,
            content_sha256=content.content_sha256 if content is not None else None,
        )


class InsightReportListResponse(BaseModel):
    items: list[InsightReportResponse]
    next_cursor: str | None


class InsightReportContentData(BaseModel):
    """正文端点在服务层与路由之间传递的数据。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    report: InsightReport
    content: InsightReportContent
    html: str
    sha256: str
    filename: str


class InsightReportManifestContent(BaseModel):
    path: str
    format: Literal["html"]
    source_bytes: int = Field(ge=0)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_bytes: int = Field(ge=0)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalize: list[dict[str, str]] = Field(default_factory=list)


class InsightReportManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["insight_report_bundle_v1"]
    analysis_type: str
    version: str
    title: str
    summary: str
    generated_at: datetime
    source_status: InsightSourceStatus
    source_note: str | None = None
    data_scope: InsightDataScope
    content: InsightReportManifestContent
