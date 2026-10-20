"""工具目录持久化模型。

本模块把 ``tool_catalog`` 只读契约落成一张快照表。
表以字符串 ``tool_id`` 为主键。契约规定工具标识稳定，不用 uuid。
表不含租户列。目录由种子脚本重放，对所有工作区共享。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base


class ToolCatalogEntry(Base):
    """一行代表目录里的一个工具。

    ``parameters`` 保存完整的参数描述。
    ``required_parameters`` 与 ``optional_parameters`` 保存名称，便于直接筛选。
    ``output_schema`` 保存输出家族的结构。没有匹配家族时为空。
    """

    __tablename__ = "tool_catalog"

    tool_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    platform: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(200), nullable=False)
    provider_group: Mapped[str] = mapped_column(String(100), nullable=False)
    method: Mapped[str] = mapped_column(String(50), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    risk_class: Mapped[str] = mapped_column(String(20), nullable=False)
    output_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    run_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    cancellable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    executable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_alias_view: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    canonical_tool_id: Mapped[str] = mapped_column(String(200), nullable=False)
    cost_summary: Mapped[str | None] = mapped_column(Text)
    cost_source: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")
    catalog_status: Mapped[str] = mapped_column(String(50), nullable=False)
    availability: Mapped[str] = mapped_column(String(30), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(50), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(50), nullable=False)
    parameters: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    required_parameters: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    optional_parameters: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    output_schema: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
