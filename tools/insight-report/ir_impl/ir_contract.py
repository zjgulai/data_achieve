#!/usr/bin/env python3
"""Shared constants for the VOC insight report generator (isolated module).

This module is the single source of truth for:
  - the six-level evidence status vocabulary
  - the fixed 11-section order
  - the 10 chart types
  - anti-pattern terms and negation-aware exceptions
  - the hero proof rule (ratio or gap only)

No third-party imports. Python 3 standard library only.
"""
from __future__ import annotations

import re

SCHEMA_VERSION = "voc-report-v1.0.0"
VALIDATOR_VERSION = "insight-report-v1.0.0"

STATUS_ORDER = [
    "confirmed",
    "directional",
    "hypothesis",
    "evidence_gap",
    "blocked",
    "not_authorized",
]

STATUS_LABEL = {
    "confirmed": "Confirmed",
    "directional": "Directional",
    "hypothesis": "Supported hypothesis",
    "evidence_gap": "Evidence gap",
    "blocked": "Blocked",
    "not_authorized": "Not authorized",
}

STATUS_CLASS = {
    "confirmed": "confirmed",
    "directional": "directional",
    "hypothesis": "hypothesis",
    "evidence_gap": "gap",
    "blocked": "blocked",
    "not_authorized": "not-authorized",
}

STATUS_RULE = {
    "confirmed": "直接事实 + artifact sha256 + 精确身份 + 无推断",
    "directional": "同一 frame ≥8 条独立记录、≥2 作者、方向一致 ≥70%，仍为单编码",
    "hypothesis": "3–7 条独立记录，或方向一致 55–70%，或只有 1 作者",
    "evidence_gap": "required cell = 0，或关键字段缺失率 = 100%",
    "blocked": "所需 gate 未 PASS，或 prevalence 分母为 null/0",
    "not_authorized": "医学功效、安全、因果、诊断，未经医学/法务 review",
}
STATUS_MAY_USE = {
    "confirmed": "身份、计数、成本、字段值、血缘",
    "directional": "方向判断、实验设计",
    "hypothesis": "提出假设、下一轮采集",
    "evidence_gap": "指出缺口与补证动作",
    "blocked": "解释为什么不能说",
    "not_authorized": "只记录 self-report",
}
STATUS_MAY_NOT_USE = {
    "confirmed": "体验、偏好、因果外推",
    "directional": "prevalence、总体比率、对外承诺、排名",
    "hypothesis": "写成发现、据此改款",
    "evidence_gap": "用相邻 variant / frame / 上一轮结果推断",
    "blocked": "任何比率、排名",
    "not_authorized": "疗效、安全率、诊断、因果",
}

SECTION_SPECS = [
    {"index": "00", "id": "answer", "kicker": "EXECUTIVE ANSWER", "zh": "执行答案"},
    {"index": "01", "id": "experience", "kicker": "CORE TENSION", "zh": "核心张力"},
    {"index": "02", "id": "aspects", "kicker": "EXPERIENCE SIGNATURE", "zh": "体验签名"},
    {"index": "03", "id": "frames", "kicker": "SAMPLE LENSES", "zh": "样本视角"},
    {"index": "04", "id": "mixed", "kicker": "MIXED EXPERIENCE", "zh": "混合体验"},
    {"index": "05", "id": "contexts", "kicker": "NEED STATES", "zh": "需求场景"},
    {"index": "06", "id": "journey", "kicker": "MOMENTS OF TRUTH", "zh": "关键时刻"},
    {"index": "07", "id": "social", "kicker": "SOCIAL FIREWALL", "zh": "社媒防火墙"},
    {"index": "08", "id": "variant", "kicker": "EVIDENCE APPLICABILITY", "zh": "证据适用性"},
    {"index": "09", "id": "agenda", "kicker": "VALIDATION AGENDA", "zh": "验证议程"},
    {"index": "10", "id": "evidence", "kicker": "TRUST & LIMITS", "zh": "信任与边界"},
]
SECTION_BY_INDEX = {s["index"]: s for s in SECTION_SPECS}
SECTION_BY_ID = {s["id"]: s for s in SECTION_SPECS}
SECTION_ORDER = [s["id"] for s in SECTION_SPECS]
EXHIBIT_SECTION = {
    "01": "01", "02": "02", "03": "03", "04": "04", "05": "05",
    "06": "06", "07": "07", "08": "08", "09": "10", "10": "10",
}

CHART_TYPES = {
    "nested_bar", "diverging_bar", "frame_grid", "co_occurrence_matrix",
    "quadrant_2x2", "coverage_bars", "social_flow", "variant_grid",
    "maturity_matrix", "lineage_waterfall",
}

UNITS = {
    "raw_object", "occurrence", "canonical_record", "frame_membership",
    "annotation", "metric_row", "variant", "author", "claim", "currency_usd",
}

ENCODINGS = {"absolute_count", "max_relative", "share_with_denominator"}
GRADES = set(STATUS_ORDER)
REPORT_MODES = {"progress_snapshot", "insight_report", "strategy_report"}

BANNED_TERMS = [
    "总体情绪率", "满意率", "净情绪分", "净推荐值", "NPS",
    "ROI 排名", "ROI排名", "ROI", "净值", "净值打分",
    "饼图", "漏斗", "漏斗图", "转化率",
    "用户都说", "所有人都", "显著", "证明", "导致", "行业第一", "领先",
]

NEGATION_ALLOW = [
    (r"不能(?:据此|由此|直接)?(?:断言|说明|证明|推断|认为|读作)[^。；\n]{0,12}导致", "导致"),
    (r"(?:不是|并非|不代表|不表示|不能证明|不能说明)[^。；\n]{0,8}导致", "导致"),
    (r"不是漏斗|非漏斗|not\s+funnel|coverage,\s*not\s+funnel", "漏斗"),
    (r"不能(?:据此|由此|直接)?证明|不证明|无法证明|不能说明", "证明"),
    (r"不显著|未达显著|不能读作显著", "显著"),
    (r"(?:不表示|不代表|不是|并非|也不能是)[^。；\n]{0,8}满意率", "满意率"),
]

NET_SCORE_PATTERN = re.compile(
    r"(^|[_\\s])(net_score|net_sentiment|net_promoter|nps|roi|roi_rank|sentiment_rate|satisfaction_rate|conversion_rate|funnel)([_\\s]|$)",
    re.I,
)

HERO_RATIO = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*$")
HERO_GAP = re.compile(r"^\s*(\d+)\s*(?:→|->|to|—>)\s*(\d+)\s*$")
HERO_ZERO = re.compile(r"^\s*0(?:\D.*)?$")


class ContractError(ValueError):
    """Raised when a report-data value violates the frozen contract."""


def is_ratio_or_gap(value: str) -> tuple[bool, str]:
    if not isinstance(value, str) or not value.strip():
        return False, "hero proof 的值必须是非空字符串"
    m = HERO_RATIO.match(value)
    if m:
        den = int(m.group(2))
        if den <= 0:
            return False, f"比值分母必须为正整数：{value!r}"
        return True, ""
    if HERO_GAP.match(value):
        return True, ""
    if HERO_ZERO.match(value):
        return True, ""
    return False, (
        f"hero proof 只允许比值（如 3 / 27）、缺口（如 250 → 248）或零缺口"
        f"（如 0 metric rows）；总量型数字 {value!r} 被拒绝"
    )


def badge_text(status: str, scope: str) -> str:
    return f"{STATUS_LABEL[status]} · {scope}".upper()


def status_from_badge(badge: str) -> str | None:
    head = badge.split("·", 1)[0].strip().lower()
    for status, label in STATUS_LABEL.items():
        if head == label.lower():
            return status
    return None
