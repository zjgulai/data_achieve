"""主张创建与反证完整性校验。

创建 claim 时必须同时给出至少一条 ``counter`` 或 ``gap`` 证据。
若一条 claim 只有 ``gap`` 或 ``context`` 证据，状态只能是 ``hypothesis`` 或
``blocked``。PRD 5.4.1 如此要求。
数据库不能表达这些规则。本层负责它们。
本模块只调用仓储。事务提交权留给调用方。

证据关联的输入可以是三种形式：

- ``ClaimEvidenceInput`` 对象。
- ``{"evidence_id": ..., "role": ...}`` 映射。
- ``(evidence_id, role)`` 二元组。

也可以传入 ``{evidence_id: role}`` 映射。
参数名 ``evidence``、``evidences`` 与 ``evidence_roles`` 等价，只能给一个。
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.claim import Claim, ClaimState, EvidenceRole
from data_intelligence_hub.repositories.claims import (
    COUNTER_EVIDENCE_ROLES,
    create_claim,
    link_evidence,
    list_evidence,
)
from data_intelligence_hub.services.exceptions import (
    ClaimCounterEvidenceRequiredError,
    ClaimGapOnlyStateInvalidError,
)
from data_intelligence_hub.tool_catalog.evidence_grade import EvidenceGrade

# 只有 gap 或 context 证据时允许的状态。来自 PRD 5.4.1。
GAP_ONLY_ALLOWED_STATES: frozenset[ClaimState] = frozenset(
    {ClaimState.HYPOTHESIS, ClaimState.BLOCKED}
)

# 一条 claim 与它的证据角色。批量校验的输入形状。
ClaimWithRoles = tuple[Claim, Iterable[EvidenceRole | str]]


@dataclass(frozen=True, slots=True)
class ClaimEvidenceInput:
    """一条待写入的证据关联。

    ``role`` 在构造时归一为 ``EvidenceRole``。非法值直接拒绝。
    """

    evidence_id: uuid.UUID
    role: EvidenceRole | str

    def __post_init__(self) -> None:
        try:
            role = EvidenceRole(self.role)
        except ValueError as exc:
            raise ValueError(f"未知的证据角色：{self.role!r}") from exc
        object.__setattr__(self, "role", role)


def _as_uuid(value: object) -> uuid.UUID:
    """把输入转成 UUID。只接受 UUID 与 UUID 字符串。"""
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str):
        try:
            return uuid.UUID(value)
        except ValueError as exc:
            raise ValueError(f"evidence_id 不是合法的 UUID：{value!r}") from exc
    raise TypeError("evidence_id 必须是 UUID 或 UUID 字符串")


def _as_role(value: object) -> EvidenceRole | str:
    """把输入限定为角色或字符串。具体取值由 ``ClaimEvidenceInput`` 校验。"""
    if isinstance(value, (EvidenceRole, str)):
        return value
    raise TypeError("role 必须是 EvidenceRole 或字符串")


def _coerce_link(item: object) -> ClaimEvidenceInput:
    """把一条输入转成 ``ClaimEvidenceInput``。"""
    if isinstance(item, ClaimEvidenceInput):
        return item
    if isinstance(item, Mapping):
        if "evidence_id" not in item or "role" not in item:
            raise ValueError("证据关联必须有 evidence_id 与 role")
        return ClaimEvidenceInput(
            evidence_id=_as_uuid(item["evidence_id"]),
            role=_as_role(item["role"]),
        )
    if isinstance(item, tuple) and len(item) == 2:
        return ClaimEvidenceInput(
            evidence_id=_as_uuid(item[0]),
            role=_as_role(item[1]),
        )
    evidence_id = getattr(item, "evidence_id", None)
    role = getattr(item, "role", None)
    if evidence_id is None or role is None:
        raise TypeError("无法解析证据关联。请给出 evidence_id 与 role")
    return ClaimEvidenceInput(
        evidence_id=_as_uuid(evidence_id),
        role=_as_role(role),
    )


def _normalise_evidence(evidence: object | None) -> list[ClaimEvidenceInput]:
    """把各种输入形式归一为证据关联列表。"""
    if evidence is None:
        return []
    if isinstance(evidence, Mapping):
        if "evidence_id" in evidence and "role" in evidence:
            return [_coerce_link(evidence)]
        return [
            ClaimEvidenceInput(
                evidence_id=_as_uuid(evidence_id),
                role=_as_role(role),
            )
            for evidence_id, role in evidence.items()
        ]
    if isinstance(evidence, (str, bytes)):
        raise TypeError("evidence 必须是证据关联序列或映射")
    if not isinstance(evidence, Iterable):
        raise TypeError("evidence 必须是证据关联序列或映射")
    return [_coerce_link(item) for item in evidence]


def _normalise_state(value: ClaimState | str) -> ClaimState:
    """把状态输入归一为 ``ClaimState``。非法值直接拒绝。"""
    try:
        return ClaimState(value)
    except ValueError as exc:
        raise ValueError(f"未知的 claim 状态：{value!r}") from exc


def _role_counts(roles: Iterable[EvidenceRole | str]) -> tuple[int, int]:
    """统计 ``support`` 与 ``counter`` 的条数。

    返回 ``(support_count, counter_count)``。
    其他角色不计入。非法角色直接拒绝。
    """
    support_count = 0
    counter_count = 0
    for role in roles:
        try:
            value = EvidenceRole(role)
        except ValueError as exc:
            raise ValueError(f"未知的证据角色：{role!r}") from exc
        if value is EvidenceRole.SUPPORT:
            support_count += 1
        elif value is EvidenceRole.COUNTER:
            counter_count += 1
    return support_count, counter_count


async def create_claim_with_evidence(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    claim_text: str,
    evidence: object | None = None,
    evidences: object | None = None,
    evidence_roles: object | None = None,
    run_id: uuid.UUID | None = None,
    state: ClaimState | str = ClaimState.HYPOTHESIS,
    evidence_grade: EvidenceGrade | str | None = None,
    confidence: float | None = None,
) -> Claim:
    """创建 claim 并写入全部证据关联。

    规则一：至少要有一种 ``counter`` 或 ``gap`` 角色。否则抛
    ``ClaimCounterEvidenceRequiredError``。
    规则二：若没有 ``support`` 也没有 ``counter``，即只有 ``gap`` 或
    ``context``，状态只能是 ``hypothesis`` 或 ``blocked``。否则抛
    ``ClaimGapOnlyStateInvalidError``。

    两条校验都先于写入。被拒绝时不会留下 claim 行。
    """
    provided = [
        value
        for value in (evidence, evidences, evidence_roles)
        if value is not None
    ]
    if len(provided) > 1:
        raise ValueError("evidence、evidences 与 evidence_roles 只能给一个")
    links = _normalise_evidence(provided[0] if provided else None)
    roles = {link.role for link in links}
    if not roles & COUNTER_EVIDENCE_ROLES:
        raise ClaimCounterEvidenceRequiredError()
    state_value = _normalise_state(state)
    support_count, counter_count = _role_counts(link.role for link in links)
    if (
        support_count == 0
        and counter_count == 0
        and state_value not in GAP_ONLY_ALLOWED_STATES
    ):
        raise ClaimGapOnlyStateInvalidError()
    claim = await create_claim(
        session,
        workspace_id=workspace_id,
        project_id=project_id,
        claim_text=claim_text,
        run_id=run_id,
        state=state_value,
        evidence_grade=evidence_grade,
        confidence=confidence,
    )
    for link in links:
        await link_evidence(
            session,
            claim_id=claim.id,
            evidence_id=link.evidence_id,
            role=link.role,
        )
    return claim


async def assert_counter_evidence_complete(
    session: AsyncSession,
    claims: Sequence[Claim],
) -> list[Claim]:
    """批量校验反证。返回缺少 ``counter`` 或 ``gap`` 关联的 claim。

    结果顺序与输入顺序一致。空输入返回空列表。
    """
    missing: list[Claim] = []
    for claim in claims:
        links = await list_evidence(session, claim_id=claim.id)
        roles = {EvidenceRole(link.role) for link in links}
        if not roles & COUNTER_EVIDENCE_ROLES:
            missing.append(claim)
    return missing


def assert_gap_only_state_valid(
    claims_with_roles: Iterable[ClaimWithRoles],
) -> list[str]:
    """校验「只有 gap 或 context 时状态受限」。

    输入是 ``(claim, roles)`` 二元组的序列。
    ``roles`` 是 ``EvidenceRole`` 或字符串的可迭代对象。
    返回违规说明列表。顺序与输入一致。
    没有违规或空输入时返回空列表。
    """
    violations: list[str] = []
    for claim, roles in claims_with_roles:
        support_count, counter_count = _role_counts(roles)
        if support_count > 0 or counter_count > 0:
            continue
        state = _normalise_state(claim.state)
        if state in GAP_ONLY_ALLOWED_STATES:
            continue
        violations.append(
            f"claim {claim.id}：只有 gap 或 context 证据，状态为 {state.value}，"
            "只能是 hypothesis 或 blocked"
        )
    return violations


__all__ = [
    "GAP_ONLY_ALLOWED_STATES",
    "ClaimCounterEvidenceRequiredError",
    "ClaimEvidenceInput",
    "ClaimGapOnlyStateInvalidError",
    "assert_counter_evidence_complete",
    "assert_gap_only_state_valid",
    "create_claim_with_evidence",
]
