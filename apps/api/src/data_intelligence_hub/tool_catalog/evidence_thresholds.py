"""五个报告模板的证据阈值。

唯一事实源是 PRD 5.4.2 的阈值表。
本模块只提供常量与查询函数。它不读库、不联网、不读时钟。

T1 到 T4 的 ``required_n`` 是每个 frame 的最低样本数。
T5 没有样本条数阈值，只有时间窗要求。见 T5 条目的注释。

``required_entity_count`` 只用于 T4。T4 的阈值是复合条件：
「20 个达人，每人 20 条评论」。只看评论总数会放过「400 条全来自 1 个达人」，
所以达人数必须单独检查。其他模板该字段为 0，检查恒不阻断。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final


@dataclass(frozen=True, slots=True)
class TemplateEvidenceThreshold:
    """一个模板的证据阈值。

    字段含义以 PRD 5.4.2 为准。
    ``n_basis`` 说明 ``required_n`` 的计数口径。
    """

    template_id: str
    required_n: int
    n_basis: str
    required_window_days: int
    required_source_count: int
    # 必须达到的独立实体数（T4 为达人数）。0 表示无此要求。
    required_entity_count: int = 0


# 数值必须与 PRD 5.4.2 的阈值表一致。不得自行调整。
EVIDENCE_THRESHOLDS: Final[Mapping[str, TemplateEvidenceThreshold]] = MappingProxyType(
    {
        "t1_voc": TemplateEvidenceThreshold(
            template_id="t1_voc",
            required_n=30,
            n_basis="帧成员数；每层 30 条",
            required_window_days=60,
            required_source_count=2,
        ),
        "t2_competitor": TemplateEvidenceThreshold(
            template_id="t2_competitor",
            required_n=20,
            n_basis="规范记录数；每 brand×market 20 条商品",
            required_window_days=30,
            required_source_count=2,
        ),
        "t3_selection": TemplateEvidenceThreshold(
            template_id="t3_selection",
            required_n=50,
            n_basis="规范记录数；每价格带 50 条商品",
            required_window_days=90,
            required_source_count=2,
        ),
        "t4_creator": TemplateEvidenceThreshold(
            template_id="t4_creator",
            # PRD 原文是「20 个达人，每人 20 条评论」。这是两个条件，不是一个。
            # required_n 是每个达人的最低可用评论数（20）。
            # required_entity_count 是达人数（20）。
            # 调用方必须按达人分别计数，取最少那位的评论数作为 sample_n。
            required_n=20,
            n_basis="每个达人的可用评论数；需 20 个达人各 20 条",
            required_window_days=30,
            required_source_count=2,
            required_entity_count=20,
        ),
        "t5_compliance": TemplateEvidenceThreshold(
            template_id="t5_compliance",
            # PRD 对 T5 只规定时间窗：「命中或未匹配均需 12 个月窗」。
            # 没有样本条数阈值，所以取 0。样本检查因此恒不阻断。
            # L4 仍由授权、365 天窗和 2 个数据源共同决定。
            required_n=0,
            n_basis="无样本条数阈值；命中或未匹配均需 12 个月窗",
            required_window_days=365,
            required_source_count=2,
        ),
    }
)


def threshold_for(template_id: str) -> TemplateEvidenceThreshold:
    """按模板 ID 取阈值。

    未知模板抛 KeyError，不返回 None。
    """
    return EVIDENCE_THRESHOLDS[template_id]
