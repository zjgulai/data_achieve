"""B5 报告模板注册表。

本模块登记 B5 的三个模板：T1、T5、T2。
阈值不在本模块定义。每个模板的 ``threshold`` 属性直接读
``tool_catalog.evidence_thresholds``。改阈值表，模板立即跟着变。

本模块是纯数据层。它不读库、不联网、不读时钟。

``required_tools`` 只列达到 ``required_source_count`` 所必需的 endpoint_type。
备用源、风险源与单列的社媒源不入列。它们见 Playbook 的采集配方。
``required_params`` 列模板开工前必须给出的输入槽位。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from data_intelligence_hub.tool_catalog.evidence_thresholds import (
    TemplateEvidenceThreshold,
    threshold_for,
)


@dataclass(frozen=True, slots=True)
class ReportTemplate:
    """一个报告模板的注册项。

    ``threshold`` 不存副本。它是只读属性，每次从唯一阈值表读取。
    """

    template_id: str
    label: str
    description: str
    required_tools: tuple[str, ...]
    required_params: tuple[str, ...]

    @property
    def threshold(self) -> TemplateEvidenceThreshold:
        """返回当前阈值。阈值表变化后，本属性立即返回新值。"""
        return threshold_for(self.template_id)


_T1_VOC: Final = ReportTemplate(
    template_id="t1_voc",
    label="T1 新品 VOC",
    description="上市前 6–8 周找主要摩擦与预期错配。",
    required_tools=(
        "apify_amazon_reviews_axesso",
        "apify_trustpilot_reviews_scraper",
    ),
    required_params=("brand", "category", "markets", "window", "decision_question"),
)

_T5_COMPLIANCE: Final = ReportTemplate(
    template_id="t5_compliance",
    label="T5 合规预警",
    description="每周例行或事件触发，把公开通报状态挂到每条结论上。",
    required_tools=("public_feed", "generic_web"),
    required_params=("brand", "category", "markets", "window", "decision_question"),
)

_T2_COMPETITOR: Final = ReportTemplate(
    template_id="t2_competitor",
    label="T2 竞品追踪",
    description="月度例行或竞品动作触发，还原货架、定价与定位。",
    required_tools=(
        "apify_amazon_product_scraper",
        "apify_amazon_price_tracker",
    ),
    required_params=(
        "brand",
        "category",
        "competitors",
        "markets",
        "window",
        "decision_question",
    ),
)

# B5 只登记这三个模板。T3 / T4 属于 B6。
_TEMPLATES: Final[Mapping[str, ReportTemplate]] = MappingProxyType(
    {
        template.template_id: template
        for template in (_T1_VOC, _T5_COMPLIANCE, _T2_COMPETITOR)
    }
)


def list_templates() -> tuple[ReportTemplate, ...]:
    """按登记顺序返回 B5 的三个模板。"""
    return (_T1_VOC, _T5_COMPLIANCE, _T2_COMPETITOR)


def get_template(template_id: str) -> ReportTemplate:
    """按模板 ID 取模板。

    未知模板抛 KeyError。本函数不返回 None。
    """
    try:
        return _TEMPLATES[template_id]
    except KeyError:
        raise KeyError(f"未知报告模板：{template_id}") from None


__all__ = ["ReportTemplate", "get_template", "list_templates"]
