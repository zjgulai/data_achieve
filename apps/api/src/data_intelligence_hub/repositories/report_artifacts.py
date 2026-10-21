"""``report_artifacts`` 表的读写。

仓储只调用 ``flush``。本模块不调用 ``commit``。
所有读取都带 ``workspace_id`` 隔离。

一行产物有五个哈希列与两个内联 HTML 列。
写入用 ``create_artifact``。查询用 ``get_artifact`` 或 ``list_artifacts``。
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.report_artifact import ReportArtifact


async def create_artifact(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    template_id: str,
    contract_json: dict[str, Any],
    contract_sha256: str,
    data_sha256: str,
    report_html_sha256: str,
    sop_html_sha256: str,
    combined_sha256: str,
    run_id: uuid.UUID | None = None,
    report_id: uuid.UUID | None = None,
    version: str = "1.0.0",
    report_html: str | None = None,
    sop_html: str | None = None,
) -> ReportArtifact:
    """写入一行报告产物并 flush。

    ``contract_json`` 必须是规范化后的合同对象。
    ``report_html`` 与 ``sop_html`` 存最终 HTML。它们可以为空。
    """
    record = ReportArtifact(
        workspace_id=workspace_id,
        project_id=project_id,
        run_id=run_id,
        report_id=report_id,
        template_id=template_id,
        version=version,
        contract_json=contract_json,
        contract_sha256=contract_sha256,
        data_sha256=data_sha256,
        report_html_sha256=report_html_sha256,
        sop_html_sha256=sop_html_sha256,
        combined_sha256=combined_sha256,
        report_html=report_html,
        sop_html=sop_html,
    )
    session.add(record)
    await session.flush()
    return record


async def get_artifact(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    artifact_id: uuid.UUID,
) -> ReportArtifact | None:
    """按工作区与产物 ID 查一行。跨工作区返回 None。"""
    result = await session.execute(
        select(ReportArtifact).where(
            ReportArtifact.id == artifact_id,
            ReportArtifact.workspace_id == workspace_id,
        )
    )
    return result.scalar_one_or_none()


async def list_artifacts(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    report_id: uuid.UUID | None = None,
    template_id: str | None = None,
) -> list[ReportArtifact]:
    """按工作区列出报告产物。结果按创建时间倒序。"""
    query: Select[tuple[ReportArtifact]] = select(ReportArtifact).where(
        ReportArtifact.workspace_id == workspace_id
    )
    if project_id is not None:
        query = query.where(ReportArtifact.project_id == project_id)
    if run_id is not None:
        query = query.where(ReportArtifact.run_id == run_id)
    if report_id is not None:
        query = query.where(ReportArtifact.report_id == report_id)
    if template_id is not None:
        query = query.where(ReportArtifact.template_id == template_id)
    query = query.order_by(ReportArtifact.created_at.desc(), ReportArtifact.id)
    result = await session.execute(query)
    return list(result.scalars().all())


__all__ = ["create_artifact", "get_artifact", "list_artifacts"]
