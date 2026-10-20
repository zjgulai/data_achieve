"""一次 run 的证据等级。

本模块是纯函数层。它不读库、不联网、不调模型、不读时钟。
调用方必须传入全部输入。

规则来自 PRD 5.4.2。if/elif 顺序不得改变。
工具上限 ``max_evidence_grade`` 属于 tool_catalog。
本模块只给出 execution_kind 到上限的常量映射。
上限的裁剪由 B3/B4 接线时完成。
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Final, Protocol

from data_intelligence_hub.tool_catalog.reachability import ToolExecutionKind


class EvidenceGrade(StrEnum):
    """五个证据等级。值必须与契约冻结 v1 一致。"""

    L0_UNVERIFIED = "L0_unverified"
    L1_CONTRACT = "L1_contract"
    L2_FIXTURE_LOCAL = "L2_fixture_local"
    L3_LIVE_SINGLE = "L3_live_single"
    L4_AUTHORIZED_LIVE = "L4_authorized_live"


GRADE_ORDER: Final[dict[EvidenceGrade, int]] = {
    EvidenceGrade.L0_UNVERIFIED: 0,
    EvidenceGrade.L1_CONTRACT: 1,
    EvidenceGrade.L2_FIXTURE_LOCAL: 2,
    EvidenceGrade.L3_LIVE_SINGLE: 3,
    EvidenceGrade.L4_AUTHORIZED_LIVE: 4,
}

# execution_kind 到工具上限的常量映射。
# 规则来自架构设计：offline→L2，guarded_http/provider_api→L4，
# unsupported→L0。ToolDescriptor 暂不增加 max_evidence_grade 字段（B3/B4）。
MAX_EVIDENCE_GRADE_BY_EXECUTION_KIND: Final[
    Mapping[ToolExecutionKind, EvidenceGrade]
] = MappingProxyType(
    {
        "offline": EvidenceGrade.L2_FIXTURE_LOCAL,
        "guarded_http": EvidenceGrade.L4_AUTHORIZED_LIVE,
        "provider_api": EvidenceGrade.L4_AUTHORIZED_LIVE,
        "unsupported": EvidenceGrade.L0_UNVERIFIED,
    }
)


@dataclass(frozen=True, slots=True)
class RunEvidenceGrade:
    """一次 run 的证据等级计算结果。

    字段必须与 PRD 5.4.2 的 ``RunEvidenceGrade`` 表一致。
    """

    run_id: uuid.UUID
    live_call: bool
    authorization_id: uuid.UUID | None
    sample_n: int
    required_n: int
    window_days: int
    required_window_days: int
    source_count: int
    required_source_count: int
    grade: EvidenceGrade
    # 独立实体数（T4 为达人数）。0 表示模板无此要求。
    entity_count: int = 0
    required_entity_count: int = 0


def compute_run_evidence_grade(
    *,
    run_id: uuid.UUID,
    live_call: bool,
    authorization_id: uuid.UUID | None,
    sample_n: int,
    required_n: int,
    window_days: int,
    required_window_days: int,
    source_count: int,
    required_source_count: int,
    entity_count: int = 0,
    required_entity_count: int = 0,
) -> RunEvidenceGrade:
    """按 PRD 5.4.2 的 if/elif 链计算本次 run 的等级。

    本函数是纯函数。输入全部来自参数。
    ``authorization_id`` 必须由调用方先检查过期。
    使用 :func:`authorization_is_usable`。过期授权回落到 L3。

    ``entity_count`` / ``required_entity_count`` 只服务 T4 的复合阈值。
    它放在样本检查之后，作为样本条件的补充，不改变 PRD 原有四条的顺序。
    """
    # 下面四条规则分别对应 PRD 的四个检查。保持逐条实现，不合并。
    if not live_call:
        grade = EvidenceGrade.L2_FIXTURE_LOCAL
    elif authorization_id is None:  # noqa: SIM114
        grade = EvidenceGrade.L3_LIVE_SINGLE
    elif sample_n < required_n:  # noqa: SIM114
        grade = EvidenceGrade.L3_LIVE_SINGLE
    elif entity_count < required_entity_count:  # noqa: SIM114
        # T4：评论够但达人不够，同样只能写 Directional。
        grade = EvidenceGrade.L3_LIVE_SINGLE
    elif window_days < required_window_days:  # noqa: SIM114
        grade = EvidenceGrade.L3_LIVE_SINGLE
    elif source_count < required_source_count:
        grade = EvidenceGrade.L3_LIVE_SINGLE
    else:
        grade = EvidenceGrade.L4_AUTHORIZED_LIVE
    return RunEvidenceGrade(
        run_id=run_id,
        live_call=live_call,
        authorization_id=authorization_id,
        sample_n=sample_n,
        required_n=required_n,
        window_days=window_days,
        required_window_days=required_window_days,
        source_count=source_count,
        required_source_count=required_source_count,
        grade=grade,
        entity_count=entity_count,
        required_entity_count=required_entity_count,
    )


class ExpiringAuthorization(Protocol):
    """只要求 ``expires_at`` 的授权视图。"""

    @property
    def expires_at(self) -> datetime: ...


def authorization_is_usable(
    authorization: ExpiringAuthorization | None,
    now: datetime,
) -> bool:
    """判断授权是否还能用于新 run。

    过期后授权回落到 L3。``now`` 由调用方传入，本函数不读时钟。
    ``now`` 与 ``expires_at`` 的时区感知必须一致。
    到期瞬间即视为过期。
    """
    if authorization is None:
        return False
    expires_at = authorization.expires_at
    if (now.tzinfo is None) != (expires_at.tzinfo is None):
        raise ValueError("now 与 expires_at 的时区感知必须一致")
    return now < expires_at
