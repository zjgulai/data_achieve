"""列表富集任务。

输入一组行（JSON 对象）与输出 schema；逐行调用 Exa 搜索的结构化输出，
把结果写回行记录。首批只做非 PII 字段：由 schema 约束。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin


class EnrichmentJob(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "enrichment_jobs"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    query_template: Mapped[str] = mapped_column(Text, nullable=False)
    output_schema: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    project_key_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project_api_keys.id")
    )
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EnrichmentRow(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "enrichment_rows"
    __table_args__ = (
        Index("ix_enrichment_rows_job", "job_id"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enrichment_jobs.id"), nullable=False)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    input: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    citations: Mapped[list[Any] | None] = mapped_column(JSON)
    cost_usd: Mapped[str | None] = mapped_column(String(20))
    error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )