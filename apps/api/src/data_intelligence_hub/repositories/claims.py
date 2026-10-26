"""``claims`` 与 ``claim_evidence`` 表的读写。

读写 claim 必须带 ``workspace_id``。跨工作区的 claim 查不到。
仓储只调用 ``flush``。本模块不调用 ``commit``。

``claim_evidence`` 的主键是 ``(claim_id, evidence_id)``。
``role`` 是普通列。同一条证据对同一条 claim 只能有一个 role。
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.claim import (
    Claim,
    ClaimEvidence,
    ClaimState,
    EvidenceRole,
)
from data_intelligence_hub.tool_catalog.evidence_grade import EvidenceGrade

# 满足反证要求的角色。服务层用这个集合做校验。
COUNTER_EVIDENCE_ROLES: frozenset[EvidenceRole] = frozenset(
    {EvidenceRole.COUNTER, EvidenceRole.GAP}
)


def _claim_state(value: ClaimState | str) -> str:
    """把输入转成 claim 状态。非法值直接拒绝。"""
    try:
        return ClaimState(value).value
    except ValueError as exc:
        raise ValueError(f"未知的 claim 状态：{value!r}") from exc


def _evidence_role(value: EvidenceRole | str) -> str:
    """把输入转成证据角色。非法值直接拒绝。"""
    try:
        return EvidenceRole(value).value
    except ValueError as exc:
        raise ValueError(f"未知的证据角色：{value!r}") from exc


def _evidence_grade(value: EvidenceGrade | str | None) -> str | None:
    """把输入转成证据等级。空值保持为空。"""
    if value is None:
        return None
    try:
        return EvidenceGrade(value).value
    except ValueError as exc:
        raise ValueError(f"未知的证据等级：{value!r}") from exc


async def create_claim(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    claim_text: str,
    run_id: uuid.UUID | None = None,
    state: ClaimState | str = ClaimState.HYPOTHESIS,
    evidence_grade: EvidenceGrade | str | None = None,
    confidence: float | None = None,
) -> Claim:
    """写入一行 claim 并 flush。

    本函数不校验反证完整性。调用方必须走 ``services/claims.py`` 的
    ``create_claim_with_evidence``。直接调用本函数会产出不可发布的 claim。

    分层原因：仓储只管持久化，业务规则留给服务层。
    本函数不检查反证，也不检查「只有 gap 时的状态限制」。
    """
    text = claim_text.strip()
    if not text:
        raise ValueError("claim_text 不能为空")
    if confidence is not None and not 0 <= confidence <= 1:
        raise ValueError("confidence 必须在 0 到 1 之间")
    record = Claim(
        workspace_id=workspace_id,
        project_id=project_id,
        run_id=run_id,
        claim_text=text,
        state=_claim_state(state),
        evidence_grade=_evidence_grade(evidence_grade),
        confidence=confidence,
    )
    session.add(record)
    await session.flush()
    return record


async def get_claim(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    claim_id: uuid.UUID,
) -> Claim | None:
    """按工作区取一行 claim。跨工作区返回 None。"""
    result = await session.execute(
        select(Claim).where(
            Claim.id == claim_id,
            Claim.workspace_id == workspace_id,
        )
    )
    return result.scalar_one_or_none()


async def list_claims(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
) -> list[Claim]:
    """按工作区列出 claim。可按项目与运行过滤。结果按创建时间倒序。"""
    statement = select(Claim).where(Claim.workspace_id == workspace_id)
    if project_id is not None:
        statement = statement.where(Claim.project_id == project_id)
    if run_id is not None:
        statement = statement.where(Claim.run_id == run_id)
    result = await session.execute(
        statement.order_by(Claim.created_at.desc(), Claim.id)
    )
    return list(result.scalars().all())


async def link_evidence(
    session: AsyncSession,
    *,
    claim_id: uuid.UUID,
    evidence_id: uuid.UUID,
    role: EvidenceRole | str,
) -> ClaimEvidence:
    """写入一条 claim 与 evidence 的关联并 flush。

    主键是 ``(claim_id, evidence_id)``。重复关联会被主键拒绝。
    """
    record = ClaimEvidence(
        claim_id=claim_id,
        evidence_id=evidence_id,
        role=_evidence_role(role),
    )
    session.add(record)
    await session.flush()
    return record


async def list_evidence(
    session: AsyncSession,
    *,
    claim_id: uuid.UUID,
    workspace_id: uuid.UUID | None = None,
) -> list[ClaimEvidence]:
    """列出 claim 的证据关联。结果按创建时间与证据 ID 排序。

    传入 ``workspace_id`` 时按 claim 的工作区过滤。跨工作区返回空列表。
    """
    statement = select(ClaimEvidence).where(ClaimEvidence.claim_id == claim_id)
    if workspace_id is not None:
        statement = statement.join(
            Claim,
            Claim.id == ClaimEvidence.claim_id,
        ).where(Claim.workspace_id == workspace_id)
    result = await session.execute(
        statement.order_by(ClaimEvidence.created_at, ClaimEvidence.evidence_id)
    )
    return list(result.scalars().all())


__all__ = [
    "COUNTER_EVIDENCE_ROLES",
    "create_claim",
    "get_claim",
    "link_evidence",
    "list_claims",
    "list_evidence",
]
