"""报告产物表 ``report_artifacts``。

一行代表一次报告渲染的产物记录。表名来自契约冻结 v1 §1.1。
本表归 M07 报告生成所有。

哈希列共五个，语义分开：

- ``contract_sha256``：规范化合同的 sha256。
- ``data_sha256``：本次报告输入 run 与证据 id 集合的 sha256。
- ``report_html_sha256``：决策者视图 ``report.html`` 的渲染哈希。
- ``sop_html_sha256``：执行者视图 ``sop.html`` 的渲染哈希。
- ``combined_sha256``：两页哈希的拼接哈希，用于快速比对整份产物。
  计算式为 ``sha256(report_html_sha256 + sop_html_sha256)``。

两个页面哈希必须分开存。PRD 5.5.1 要求两个渲染器各自可独立复核。
所以不得只存一个 ``render_sha256``。旧的单列 ``render_sha256`` 已删除。

``contract_json`` 存规范化后的完整合同 JSON。时间写 ``Z``，
``Decimal`` 写字符串。合同哈希只覆盖内容字段：``generated_at``
与 ``artifact`` 被排除。生成时间另存 ``created_at``。
五个哈希存本表的哈希列。

内联 HTML 与路径列的取舍：

PRD 5.5.2 要求合同与 HTML 一起存档。本批不写文件系统。
所以只保留 ``report_html`` 与 ``sop_html`` 两个内联文本列。
旧设计的 ``report_html_path`` 与 ``sop_html_path`` 已删除。
理由：本批没有文件写入方，路径列会永远为空，属于死列。

``report_id`` 为 B5 的报告表预留。本批不建外键。
``version`` 是产物版本，默认 ``1.0.0``。

页脚自引用的占位符约定见
:mod:`data_intelligence_hub.services.report_artifacts`。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from data_intelligence_hub.models.base import Base, UUIDPrimaryKeyMixin


class ReportArtifact(UUIDPrimaryKeyMixin, Base):
    """一行代表一份报告产物。

    ``run_id`` 可空。手工报告可以没有 run。
    ``template_id`` 指向模板注册表。本批不建外键。
    """

    __tablename__ = "report_artifacts"
    __table_args__ = (
        # 报告列表按工作区与项目过滤。
        Index("ix_report_artifacts_workspace_project", "workspace_id", "project_id"),
        # 审计按 run 反查报告。
        Index("ix_report_artifacts_run_id", "run_id"),
        # B5 的报告表按 report_id 反查产物。
        Index("ix_report_artifacts_report_id", "report_id"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("runs.id"))
    # B5 的 reports 表尚未建。本列先留空，不加外键。
    report_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    template_id: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0.0",
        server_default="1.0.0",
    )
    # 规范化后的合同 JSON。内容等于合同哈希覆盖的那一份。
    contract_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    contract_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    data_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    report_html_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    sop_html_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    combined_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    # 本批只存内联 HTML。路径列已删除。
    report_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    sop_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


__all__ = ["ReportArtifact"]
