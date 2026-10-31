"""洞察分析报告的持久化模型。

两张表只服务“已生成、已导入的分析报告”这一件事：

* ``insight_reports`` 保存元数据、数据范围与来源状态。
* ``insight_report_contents`` 保存 HTML 正文。正文单独一张表，列表和详情
  在结构上就不会读到正文列。

表结构见 ``docs/design/insight-new-integration.md`` §2。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin

# 生产库用 JSONB；单元测试用 SQLite 内存库，JSONB 无法编译，退回 JSON。
# 两者都是 Pydantic 校验后的字典，读写语义一致。
_JSON_SCOPE = JSON().with_variant(JSONB(), "postgresql")


class InsightReport(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "insight_reports"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "analysis_type",
            "version",
            name="uq_insight_reports_workspace_type_version",
        ),
        CheckConstraint(
            "status IN ('ready', 'withdrawn')",
            name="status",
        ),
        CheckConstraint(
            "source_status IN ('snapshot_only', 'connected', 'unavailable')",
            name="source_status",
        ),
        Index(
            "ix_insight_reports_workspace_type_generated",
            "workspace_id",
            "analysis_type",
            "generated_at",
        ),
        Index("ix_insight_reports_project", "project_id"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    analysis_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ready", nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    data_scope: Mapped[dict[str, Any]] = mapped_column(_JSON_SCOPE, nullable=False)
    source_status: Mapped[str] = mapped_column(
        String(20), default="snapshot_only", nullable=False
    )
    source_note: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class InsightReportContent(Base):
    __tablename__ = "insight_report_contents"
    __table_args__ = (
        CheckConstraint(
            "content_format IN ('html')",
            name="format",
        ),
    )

    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("insight_reports.id", ondelete="CASCADE"),
        primary_key=True,
    )
    content_format: Mapped[str] = mapped_column(
        String(10), default="html", nullable=False
    )
    content_html: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
