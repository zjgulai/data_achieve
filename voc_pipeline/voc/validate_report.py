"""Report quality validator.

The validator enforces the reference report's grammar, not its wording:
  - every h2 is a complete conclusion sentence
  - every claim block carries the four evidence cells
  - every exhibit carries Basis / Unit / Limit / Status
  - the six evidence states are present
  - the forbidden-conclusion catalog is rendered as a collapsed tail block
  - every forbidden pattern is absent from the report body and claims.numbers

The forbidden-conclusion scan is a gate, not advice: any hit raises or fails
the suite, and ``python3 -m voc.validate_report <html> <claims>`` exits 1 with
the matched snippets.  Fail closed on scanner errors as well.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .contracts import FORBIDDEN_CONCLUSIONS

ALLOWED_H2_MAX = 200
BANNED_H2 = {"概览", "小结", "结论", "背景", "方法", "目录", "附录"}
ANTI_PATTERNS = [
    r"饼图",
    r"\bNPS\b",
    r"\bROI\b",
    r"净值",
    r"净推荐",
    r"总体情绪率",
    r"满意率",
    r"星级分布",
    r"漏斗图",
]
REQUIRED_GRADES = ["Confirmed", "Directional", "Supported hypothesis", "Evidence gap", "Blocked", "Not authorized"]
# A grade name in claim prose must match the claim's computed grade.  An
# explicitly negated mention ("未达 Directional 门槛") is a comparison, not an
# assertion, so it is not counted as a false claim.
GRADE_NEGATIONS = (
    "未达", "未达到", "尚未", "尚未达到", "未能", "没有", "没有达到",
    "不达", "达不到", "未满足", "不满足", "不是", "并非", "低于", "不及",
    "not", "below", "under",
)
FOUR_CELLS = ["Observed", "Interpretation", "Counterevidence", "Decision implication"]
META_CELLS = ["Basis", "Unit", "Limit", "Status"]
FORBIDDEN_COUNT = len(FORBIDDEN_CONCLUSIONS)
INLINE_CITE_IDS = ("FC-01", "FC-09", "FC-10")
# A precision percentage is only publishable next to its per-source split.
# The merged number may appear as a comparison, but never alone.
PRECISION_MENTION_RE = re.compile(
    r"(?:strict\s+)?precision[^。；\n]{0,28}\d{1,3}(?:\.\d+)?\s*%"
    r"|精确率[^。；\n]{0,28}\d{1,3}(?:\.\d+)?\s*%",
    re.I,
)
PRECISION_SOURCES = ("tiktok_shop", "reddit", "all")
PRECISION_ATTR_RE = re.compile(r"\bdata-(?:source-)?precision\s*=", re.I)
CROSS_MODEL_ROW_RE = re.compile(
    r"<tr\b[^>]*\bdata-cross-model-agreement\s*=\s*[\"']true[\"'][^>]*>",
    re.I,
)
# The five annotators (sol / terra / luna / g55 / mini) all run on the same
# DeepSeek Flash family (deepseek-flash / deepseek-v4.1-flash, routed through
# group/auto-deepseek-flash:max[1m]).  Saying "模型家族" or "独立盲标" without
# "同族自一致" / "同一底座" in the same paragraph reads as external,
# independent validation, which this run did not do.  The rule fails closed
# and quotes the offending paragraph.
MODEL_DIVERSITY_TERMS = ("模型家族", "独立盲标")
MODEL_DIVERSITY_DISCLAIMERS = ("同族自一致", "同一底座")
BLOCK_BOUNDARY = "\x00"

# ---------------------------------------------------------------------------
# Empty-group statistics gate (C16 fail-open regression)
#
# The creator-video baseline can have no usable stratum at all: every layer
# has n<8, or a layer has n>=8 but its complement has n<8.  The renderer used
# to pass missing statistics through ``_flt(None) -> 0.0`` and publish
# "0.00%", "0.00x", "p=0.000" and "CI [0.00, 0.00]" as if a test had run.
# That is fail-open: a missing structure became "tested and not significant".
# These two gates fail closed:
#   A ``no_empty_group_stats``   no empty/small group may carry a statistic.
#   B ``strata_require_min_n``   a stratified statistic needs n>=8 in the
#                                layer and, for a comparison, in the control.
# ---------------------------------------------------------------------------
EMPTY_GROUP_STAT_TERMS = (
    "中位", "中位数", "中位互动率", "倍数", "均值", "平均值",
    "p 值", "p值", "p=", "显著性", "置信区间", "CI",
    "跑赢", "对照", "补充组",
)
EMPTY_GROUP_WINDOW = 48
EMPTY_GROUP_DIMENSIONS = (
    "时长档", "has_link", "ad_disclosure", "platform_is_ad",
    "购买链接", "广告披露", "平台广告",
)
EMPTY_GROUP_LITERAL_RULES = (
    ("0.00x", re.compile(r"0\.00\s*[x×]")),
    ("p=0.000", re.compile(r"(?<![A-Za-z])p\s*[=＝]\s*0\.0{2,}(?!\d)")),
    ("CI [0.00, 0.00]", re.compile(r"CI\s*[\[【]\s*0\.00\s*[,，]\s*0\.00\s*[\]】]")),
)
# When C16 declares that no stratified baseline is available, every
# stratified statistic must be null (or absent), never 0.0 / 0 / a string.
C16_STRATIFIED_STAT_FIELDS = (
    "top_layer_median_interaction_rate",
    "complement_median_interaction_rate",
    "median_multiple",
    "mann_whitney_p",
    "bootstrap_ci_low",
    "bootstrap_ci_high",
    "has_link_false_multiple",
    "ad_disclosure_false_multiple",
)
STRATA_EXEMPT_PHRASES = (
    "本轮无可用分层", "无可用分层", "仅计数", "样本不足",
    "不产出任何分层", "不做分层",
)
STRATA_HAS_DECIMAL_RE = re.compile(
    r"\d+\.\d+\s*%|\d+\.\d+\s*[x×]|p\s*=|CI\s*\["
)
STRATA_COMPARISON_RE = re.compile(r"补充组|对照组|\bvs\.?\b|对比", re.I)
# A named stratum ("31-60s", "has_link=true") makes the clause a stratified
# statement even when the word 分层 is absent.  C17's "2 倍中位数" wording has
# no such layer value, so the descriptive high-performer text is not a strata
# result and is not forced to carry an unrelated n>=8.
STRATA_LAYER_VALUE_RE = re.compile(
    r"(?:<=|<|>|≥|≤)?\d+(?:\s*-\s*\d+)?\s*s(?![A-Za-z0-9])"
    r"|(?:has_link|ad_disclosure|platform_is_ad)\s*[=:]\s*(?:true|false)",
    re.I,
)
STRATA_CONCLUSION_TERMS = ("没有跑赢", "无显著差异", "不显著", "未发现效果", "无差异")
STRATA_SPREAD_CONCLUSION_RE = re.compile(r"没有[^。；\n]{0,40}?跑赢")
STRATA_STAT_VALUE_RES = (
    re.compile(r"(?:中位|倍数|均值)[^。；\n]{0,24}?\d"),
    re.compile(r"(?<![A-Za-z])p\s*[=<>≤≥]\s*[\d.]"),
    re.compile(r"CI\s*[\[【]"),
    re.compile(r"\d+(?:\.\d+)?\s*[x×]"),
)
SMALL_N_RE = re.compile(r"(?<![A-Za-z0-9_])n\s*[=＝]\s*(\d+)")
GE_N_RE = re.compile(r"(?<![A-Za-z0-9_])n\s*[>≥]=?\s*(\d+)")
NON_FINITE_RE = re.compile(r"(?<![A-Za-z])(?:NaN|None|Inf|Infinity|nan|inf)(?![A-Za-z])")


@dataclass(frozen=True)
class ForbiddenHit:
    """One match between a forbidden rule and the rendered report or its data."""

    fc_id: str
    surface: str
    snippet: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.fc_id, "surface": self.surface, "snippet": self.snippet}


class ForbiddenConclusionError(ValueError):
    """Raised by the build-time gate when a forbidden conclusion is present."""

    def __init__(self, message: str, hits: list[ForbiddenHit] | None = None) -> None:
        self.hits = list(hits or [])
        super().__init__(message)


def format_hits(hits: list[ForbiddenHit], limit: int = 8) -> str:
    lines = [f"{h.fc_id} [{h.surface}] {h.snippet}" for h in hits[:limit]]
    if len(hits) > limit:
        lines.append(f"另有 {len(hits) - limit} 条命中未列出")
    return "；".join(lines)


def _mask_non_claim_surfaces(doc: str) -> str:
    """Remove surfaces that are not report claims.

    Masked surfaces: CSS/JS, the collapsed forbidden catalog (it quotes the
    banned shapes by design) and inline ``fc-cite`` spans (they point at the
    catalog by id only).
    """
    doc = re.sub(r"<style\b.*?</style>", " ", doc, flags=re.S | re.I)
    doc = re.sub(r"<script\b.*?</script>", " ", doc, flags=re.S | re.I)
    doc = re.sub(
        r"<details\b(?=[^>]*\bclass\s*=\s*[\"'][^\"']*forbidden-zone)[^>]*>.*?</details>",
        " ",
        doc,
        flags=re.S | re.I,
    )
    doc = re.sub(
        r"<div\b(?=[^>]*\bclass\s*=\s*[\"'][^\"']*\bforbidden\b)[^>]*>.*?</div>",
        " ",
        doc,
        flags=re.S | re.I,
    )
    return re.sub(
        r"<span\b(?=[^>]*\bclass\s*=\s*[\"'][^\"']*\bfc-cite\b)[^>]*>.*?</span>",
        " ",
        doc,
        flags=re.S | re.I,
    )


def strip_for_scan(doc: str) -> str:
    """Remove non-claim surfaces, then flatten the rest to text.

    Block boundaries become sentence breaks so a regex can never match across
    two table cells.
    """
    doc = _mask_non_claim_surfaces(doc)
    doc = re.sub(
        r"</(?:p|li|div|td|th|h1|h2|h3|h4|figcaption|tr|summary|article|section|details)>",
        "。\n",
        doc,
        flags=re.I,
    )
    doc = re.sub(r"<br\s*/?>", "\n", doc, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", doc)
    text = html.unescape(text)
    return re.sub(r"[ \t\r\f\v]+", " ", text)


def _text_blocks(doc: str) -> list[str]:
    """Split the claim surfaces into paragraph-sized blocks.

    Every closing block tag (``p``, ``li``, ``td``, heading, ...) ends a block,
    so a table cell is its own paragraph and a caveat in the next cell cannot
    rescue a claim.  This is the unit the model-diversity rule checks: the
    disclaimer must sit in the same paragraph as the claim it qualifies.
    """
    doc = _mask_non_claim_surfaces(doc)
    doc = re.sub(
        r"</(?:p|li|div|td|th|h1|h2|h3|h4|figcaption|tr|summary|article|section|details)>",
        BLOCK_BOUNDARY,
        doc,
        flags=re.I,
    )
    doc = re.sub(r"<br\s*/?>", BLOCK_BOUNDARY, doc, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", doc)
    text = html.unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    blocks = (re.sub(r"\s+", " ", raw).strip() for raw in text.split(BLOCK_BOUNDARY))
    return [block for block in blocks if block]


def scan_forbidden_text(text: str) -> list[ForbiddenHit]:
    """Match every text rule; compile errors fail closed."""
    hits: list[ForbiddenHit] = []
    for fc in FORBIDDEN_CONCLUSIONS:
        rule = fc.detected_by.text_regex
        if not rule:
            continue
        try:
            pattern = re.compile(rule)
        except re.error as exc:  # pragma: no cover - catalog check catches this first
            raise ForbiddenConclusionError(f"{fc.id} 的 text_regex 无法编译：{exc}") from exc
        for match in pattern.finditer(text):
            start = max(0, match.start() - 36)
            end = min(len(text), match.end() + 36)
            snippet = re.sub(r"\s+", " ", text[start:end]).strip()
            hits.append(ForbiddenHit(fc.id, "text", snippet))
    return hits


def _iter_number_keys(obj: Any, path: str = ""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            child = f"{path}/{key}" if path else str(key)
            yield child, str(key).lower(), value
            yield from _iter_number_keys(value, child)
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            yield from _iter_number_keys(value, f"{path}[{index}]")


_DATA_INDEX = {
    key: fc for fc in FORBIDDEN_CONCLUSIONS for key in fc.detected_by.data_keys
}


def scan_forbidden_data(claims: list[dict[str, Any]]) -> list[ForbiddenHit]:
    """Match forbidden metric keys inside ``claims[].numbers``."""
    hits: list[ForbiddenHit] = []
    for claim in claims:
        claim_id = str(claim.get("claim_id", "?"))
        numbers = claim.get("numbers") or {}
        serialized = json.dumps(numbers, ensure_ascii=False)
        estimated = bool(re.search(r'"is_estimated"\s*:\s*true', serialized, re.I))
        for path, key, value in _iter_number_keys(numbers):
            fc = _DATA_INDEX.get(key)
            if fc is None:
                continue
            extra = "（is_estimated=true）" if estimated else ""
            snippet = f"claims[{claim_id}].numbers/{path} = {json.dumps(value, ensure_ascii=False)[:80]}{extra}"
            hits.append(ForbiddenHit(fc.id, "data", snippet))
    return hits


def scan_document(doc: str, claims: list[dict[str, Any]] | None = None) -> list[ForbiddenHit]:
    hits = scan_forbidden_text(strip_for_scan(doc))
    if claims:
        hits.extend(scan_forbidden_data(claims))
    return hits


def _catalog_problems() -> list[str]:
    problems: list[str] = []
    if FORBIDDEN_COUNT != 12:
        problems.append(f"catalog count={FORBIDDEN_COUNT}, expected 12")
    ids = [fc.id for fc in FORBIDDEN_CONCLUSIONS]
    if len(set(ids)) != len(ids):
        problems.append("duplicate ids")
    for fc in FORBIDDEN_CONCLUSIONS:
        if not re.fullmatch(r"FC-\d{2}", fc.id):
            problems.append(f"{fc.id}: bad id")
        for name in ("pattern", "why", "ref_origin"):
            if not str(getattr(fc, name)).strip():
                problems.append(f"{fc.id}: empty {name}")
        rule = fc.detected_by
        if not rule.text_regex and not rule.data_keys:
            problems.append(f"{fc.id}: no machine detector")
        if rule.text_regex:
            try:
                re.compile(rule.text_regex)
            except re.error as exc:
                problems.append(f"{fc.id}: regex error {exc}")
    return problems


def _render_problems(doc: str) -> list[str]:
    problems: list[str] = []
    tag = re.search(r"<details\b[^>]*\bclass\s*=\s*[\"'][^\"']*forbidden-zone[^\"']*[\"'][^>]*>", doc)
    if not tag:
        return ["missing <details class='forbidden-zone'>"]
    if f'data-forbidden-count="{FORBIDDEN_COUNT}"' not in tag.group(0):
        problems.append(f"missing data-forbidden-count={FORBIDDEN_COUNT}")
    summary = re.search(r"<summary>(.*?)</summary>", doc, re.S)
    expected = f"这份报告不能说的事：{FORBIDDEN_COUNT} 类"
    if not summary or _strip(summary.group(1)) != expected:
        problems.append(f"summary must be {expected}")
    for fc in FORBIDDEN_CONCLUSIONS:
        if f'data-fc-row="{fc.id}"' not in doc:
            problems.append(f"missing row {fc.id}")
    return problems


def _inline_cite_problems(doc: str) -> list[str]:
    ids: list[str] = []
    for tag in re.findall(r"<span\b[^>]*>", doc):
        if "fc-cite" not in tag:
            continue
        match = re.search(r'data-fc="(FC-\d{2})"', tag)
        ids.append(match.group(1) if match else "?")
    problems: list[str] = []
    if len(ids) != 3:
        problems.append(f"inline citations={len(ids)}, expected 3")
    if set(ids) != set(INLINE_CITE_IDS):
        problems.append(f"inline ids={ids}, expected {list(INLINE_CITE_IDS)}")
    return problems


def _precision_split_problems(doc: str) -> list[str]:
    """Fail when a precision number appears without its per-source split.

    The report may state a merged strict precision only as a comparison.  The
    comparison is valid only when the same document also publishes TikTok Shop
    and Reddit rows with their own precision values.  A merged number alone is
    the exact presentation this rule forbids.
    """
    text = strip_for_scan(doc)
    if not PRECISION_MENTION_RE.search(text):
        return []
    table = re.search(
        r"<table\b[^>]*\bdata-precision-table\s*=\s*[\"']source-split[\"'][^>]*>.*?</table>",
        doc,
        re.S,
    )
    if not table:
        return [
            "precision 数字出现，但没有 data-precision-table=source-split 的分信源表"
        ]
    block = table.group(0)
    problems: list[str] = []
    for source in PRECISION_SOURCES:
        row = re.search(
            rf"<tr\b[^>]*\bdata-source\s*=\s*[\"']{re.escape(source)}[\"'][^>]*>.*?</tr>",
            block,
            re.S,
        )
        if not row:
            problems.append(f"分信源表缺 {source} 行")
            continue
        if not re.search(r"data-precision\s*=\s*[\"']\d+(?:\.\d+)?[\"']", row.group(0)):
            problems.append(f"{source} 行缺 data-precision")
    # The merged row may not be the only numeric row: TikTok Shop and Reddit
    # must each carry their own value, not a copy of the merged number.
    if len(problems) == 0:
        values = {
            source: re.search(
                rf"data-source\s*=\s*[\"']{source}[\"'][^>]*data-precision\s*=\s*[\"']([\d.]+)[\"']",
                block,
            )
            for source in PRECISION_SOURCES
        }
        # Attribute order is controlled by the renderer, so also accept the
        # reverse order by searching the row.
        for source in PRECISION_SOURCES:
            if values[source] is None:
                row = re.search(
                    rf"<tr\b[^>]*data-source\s*=\s*[\"']{source}[\"'][^>]*>.*?</tr>",
                    block,
                    re.S,
                )
                values[source] = (
                    re.search(r"data-precision\s*=\s*[\"']([\d.]+)[\"']", row.group(0))
                    if row
                    else None
                )
        if values["tiktok_shop"] and values["reddit"]:
            if values["tiktok_shop"].group(1) == values["reddit"].group(1):
                problems.append("分信源 precision 数值相同，疑似只复制了合并值")
    return problems


def _cross_model_agreement_problems(doc: str) -> list[str]:
    """Fail when precision is published without the cross-model agreement row.

    The old precision basis is LLM-vs-LLM self-证.  A report that keeps the
    precision numbers must also publish the independent cross-model agreement
    row, so a later edit cannot drop the new evidence and leave only the
    self-referential number.
    """
    text = strip_for_scan(doc)
    has_precision = bool(PRECISION_MENTION_RE.search(text)) or bool(
        PRECISION_ATTR_RE.search(doc)
    )
    if not has_precision:
        return []
    if CROSS_MODEL_ROW_RE.search(doc):
        return []
    return [
        "precision 数字出现，但没有跨 5 模型一致率行"
        "（data-cross-model-agreement=true）"
    ]


def _model_diversity_problems(doc: str) -> list[str]:
    """Fail when a paragraph implies independent model validation.

    Trigger words are ``模型家族`` and ``独立盲标``.  The paragraph passes only
    when it also states ``同族自一致`` or ``同一底座``.  The five annotators are
    identities on one model family, so a bare "模型家族" claim would read as
    external validation that never happened.  The failure quotes the paragraph
    so a reader can see the exact sentence.
    """
    problems: list[str] = []
    for index, block in enumerate(_text_blocks(doc)):
        terms = [term for term in MODEL_DIVERSITY_TERMS if term in block]
        if not terms:
            continue
        if any(word in block for word in MODEL_DIVERSITY_DISCLAIMERS):
            continue
        for term in terms:
            at = block.find(term)
            start = max(0, at - 60)
            end = min(len(block), at + len(term) + 60)
            snippet = block[start:end].strip()
            if start:
                snippet = "…" + snippet
            if end < len(block):
                snippet = snippet + "…"
            problems.append(
                f"段落{index} 出现「{term}」但同段没有「同族自一致」或「同一底座」：{snippet}"
            )
    return problems


def _context(text: str, start: int, end: int, width: int = 36) -> str:
    """Return the matched text plus surrounding context, one line."""
    left = max(0, start - width)
    right = min(len(text), end + width)
    snippet = re.sub(r"\s+", " ", text[left:right]).strip()
    if left:
        snippet = "…" + snippet
    if right < len(text):
        snippet = snippet + "…"
    return snippet


def _empty_group_stats_problems(
    doc: str, claims: list[dict[str, Any]] | None = None
) -> list[str]:
    """Rule A: a zero-sample or small-sample group may not carry statistics.

    The report used to render ``0.00%`` / ``0.00x`` / ``p=0.000`` /
    ``CI [0.00, 0.00]`` when the baseline had no usable layer.  A missing
    statistic must stay missing: counts only.  The same rule checks C16's
    ``numbers``: when ``stratified_baseline_available`` is false, every
    stratified statistic must be null or absent, never 0.0.
    """
    problems: list[str] = []
    text = strip_for_scan(doc)

    for label, pattern in EMPTY_GROUP_LITERAL_RULES:
        for match in pattern.finditer(text):
            problems.append(
                f"规则A no_empty_group_stats：报告正文 @{match.start()} 出现「{label}」："
                f"{_context(text, match.start(), match.end())}"
            )

    # n<8 next to a statistic is an empty/insufficient group.  n>=8 does not
    # trigger, so a valid layer sentence passes.
    for match in SMALL_N_RE.finditer(text):
        value = int(match.group(1))
        if value >= 8:
            continue
        left = max(0, match.start() - EMPTY_GROUP_WINDOW)
        right = min(len(text), match.end() + EMPTY_GROUP_WINDOW)
        window = text[left:right]
        if not any(term in window for term in EMPTY_GROUP_STAT_TERMS):
            continue
        problems.append(
            f"规则A no_empty_group_stats：报告正文 @{match.start()} 的 n={value}<8 "
            f"紧邻统计表述：{_context(text, match.start(), match.end())}"
        )

    # An empty layer name renders as "时长档 的…" (a dimension followed by
    # whitespace and 的).  It must be a structural error, not a sentence.
    dimension_re = re.compile(
        r"(?:" + "|".join(re.escape(name) for name in EMPTY_GROUP_DIMENSIONS)
        + r")\s+的"
    )
    for match in dimension_re.finditer(text):
        problems.append(
            f"规则A no_empty_group_stats：报告正文 @{match.start()} 出现空层名："
            f"{_context(text, match.start(), match.end())}"
        )

    # A non-finite placeholder near a statistic is the same fail-open leak.
    for match in NON_FINITE_RE.finditer(text):
        left = max(0, match.start() - EMPTY_GROUP_WINDOW)
        right = min(len(text), match.end() + EMPTY_GROUP_WINDOW)
        if not any(term in text[left:right] for term in EMPTY_GROUP_STAT_TERMS):
            continue
        problems.append(
            f"规则A no_empty_group_stats：报告正文 @{match.start()} 出现非数值统计量："
            f"{_context(text, match.start(), match.end())}"
        )

    for claim in claims or []:
        if str(claim.get("claim_id", "")) != "C16":
            continue
        numbers = claim.get("numbers") or {}
        if numbers.get("stratified_baseline_available") is not False:
            continue
        for field_name in C16_STRATIFIED_STAT_FIELDS:
            value = numbers.get(field_name, None)
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            problems.append(
                "规则A no_empty_group_stats：claims[C16].numbers/"
                f"{field_name} 在无可用分层时必须为 null，实为 "
                f"{json.dumps(value, ensure_ascii=False)}"
            )
    return problems


def _strata_min_n_problems(doc: str) -> list[str]:
    """Rule B: a stratified statistic needs n>=8, and a comparison two groups.

    The report may only publish a stratified median / multiple / p value / CI
    when the layer has n>=8.  A two-group comparison needs a second n>=8 for
    the complement.  A paragraph that explicitly says no stratified baseline
    exists ("本轮无可用分层", "仅计数", "样本不足", ...) is exempt only when it
    carries no decimal percentage, decimal multiple, ``p=`` or ``CI [``.
    """
    problems: list[str] = []
    for block_index, block in enumerate(_text_blocks(doc)):
        for raw_clause in re.split(r"[。；\n]+", block):
            clause = re.sub(r"\s+", " ", raw_clause).strip()
            if not clause:
                continue
            exempt = any(phrase in clause for phrase in STRATA_EXEMPT_PHRASES) and not (
                STRATA_HAS_DECIMAL_RE.search(clause)
            )
            if exempt:
                continue
            comparison = bool(STRATA_COMPARISON_RE.search(clause))
            stratified = (
                "分层" in clause
                or comparison
                or bool(STRATA_LAYER_VALUE_RE.search(clause))
            )
            stat_value = any(pattern.search(clause) for pattern in STRATA_STAT_VALUE_RES)
            if "分层" in clause and re.search(r"\d+(?:\.\d+)?\s*%", clause):
                stat_value = True
            exact_conclusion = any(term in clause for term in STRATA_CONCLUSION_TERMS)
            spread_conclusion = bool(STRATA_SPREAD_CONCLUSION_RE.search(clause))
            conclusion = exact_conclusion or (
                spread_conclusion
                and (
                    "分层" in clause
                    or comparison
                    or "维度" in clause
                    or "内容形态" in clause
                )
            )
            if not ((stat_value and stratified) or conclusion):
                continue
            equality_ns = [int(value) for value in SMALL_N_RE.findall(clause)]
            ge_ns = [int(value) for value in GE_N_RE.findall(clause)]
            qualifying = equality_ns + ge_ns
            if not qualifying or max(qualifying) < 8:
                problems.append(
                    f"规则B strata_require_min_n：块{block_index} 统计表述没有 n>=8 "
                    f"的样本量：{clause[:160]}"
                )
                continue
            if comparison and len(qualifying) < 2:
                problems.append(
                    f"规则B strata_require_min_n：块{block_index} 两组比较只有一个 "
                    f"n>=8 的样本量：{clause[:160]}"
                )
    return problems


def _asserted_grades(text: str) -> list[str]:
    """Grade names asserted in ``text``; explicitly negated mentions are skipped.

    C13's Supported hypothesis headline reads "未达 Directional 门槛，按
    Supported hypothesis 记录".  The negated Directional is a comparison, not
    an assertion of that grade, so it must not trip the rule.  Every other
    mention is treated as an assertion.
    """
    asserted: list[str] = []
    for name in REQUIRED_GRADES:
        for match in re.finditer(re.escape(name), text):
            if match.start() > 0:
                previous = text[match.start() - 1]
                # ``unconfirmed`` is not the grade ``Confirmed``.
                if previous.isascii() and previous.isalpha():
                    continue
            head = text[: match.start()].rstrip().lower()
            if any(head.endswith(negation) for negation in GRADE_NEGATIONS):
                continue
            asserted.append(name)
    return asserted


def claim_text_matches_grade(claims: list[dict[str, Any]]) -> list[str]:
    """Fail when a claim's prose names a grade other than its computed grade.

    This is the C13 regression guard.  Headline and status used to be fixed
    strings, so a claim re-graded to Supported hypothesis still published
    "达到 Directional 门槛" and "Directional · single-coded, pre-G7", and the
    badge disagreed with the sentence.  Any grade name in those two fields
    must match ``claim["grade"]``; a negated mention such as
    "未达 Directional 门槛" is allowed because it asserts the opposite.
    """
    problems: list[str] = []
    for claim in claims:
        claim_id = str(claim.get("claim_id", "?"))
        grade = str(claim.get("grade", ""))
        for field_name in ("headline", "status"):
            text = str(claim.get(field_name, ""))
            wrong = sorted({name for name in _asserted_grades(text) if name != grade})
            if wrong:
                problems.append(
                    f"{claim_id}.{field_name} 写了 {'/'.join(wrong)}，"
                    f"但 grade={grade}：{text[:80]}"
                )
    return problems


def validate_coded_corpus(records, coded) -> None:
    """Fail closed on a forbidden field or aspect combination (E-merge §2.3).

    The merged model has no "conflict" metric.  What remains forbidden is a
    field value outside the enum, an off-target record with aspects, a
    ``scope=none`` record with aspects, and a ``scope=none`` record whose
    source says ``relayed``.
    """
    # Imported lazily: ``build`` imports this module, and ``coder`` imports
    # ``canonical``; a module-level import would create a cycle.
    from .coder import (
        EXPERIENCE_SCOPES,
        EXPERIENCE_SOURCES,
        ON_TOPIC_PRODUCT_MATCH,
        emits_aspects,
    )

    by_id = {record.canonical_id: record for record in records}
    problems: list[str] = []
    product_match_values = ON_TOPIC_PRODUCT_MATCH | {
        "brand_other_product",
        "irrelevant",
    }
    for coded_rec in coded:
        cid = coded_rec.canonical_id
        record = by_id.get(cid)
        if record is None:
            problems.append(f"{cid}: coded record has no canonical record")
            continue
        if not coded_rec.product_match:
            problems.append(f"{cid}: product_match is missing")
        elif coded_rec.product_match not in product_match_values:
            problems.append(
                f"{cid}: unknown product_match {coded_rec.product_match!r}"
            )
        if coded_rec.experience_scope not in EXPERIENCE_SCOPES:
            problems.append(
                f"{cid}: unknown experience_scope {coded_rec.experience_scope!r}"
            )
        if coded_rec.experience_source not in EXPERIENCE_SOURCES:
            problems.append(
                f"{cid}: unknown experience_source {coded_rec.experience_source!r}"
            )
        aspect_count = sum(
            1 for ann in coded_rec.annotations if ann.axis == "aspect"
        )
        if aspect_count and not emits_aspects(
            coded_rec.product_match,
            coded_rec.experience_scope,
            record.text or "",
        ):
            problems.append(
                f"{cid}: {aspect_count} aspect(s) emitted outside the E-merge gate "
                f"(product_match={coded_rec.product_match!r}, "
                f"scope={coded_rec.experience_scope!r}, "
                f"text_empty={not (record.text or '').strip()})"
            )
        if (
            coded_rec.experience_scope == "none"
            and coded_rec.experience_source == "relayed"
        ):
            problems.append(f"{cid}: scope=none cannot carry source=relayed")
    if problems:
        raise ValueError(
            "coded corpus violates E-merge §2.3: " + "; ".join(problems[:10])
        )


def assert_report_clean(html_path: Path, claims_path: Path | None = None) -> None:
    """Build-time gate: raise ForbiddenConclusionError on any hit or missing block."""
    doc = html_path.read_text(encoding="utf-8")
    claims = json.loads(claims_path.read_text()) if claims_path and claims_path.exists() else None
    problems = _catalog_problems() + _render_problems(doc) + _inline_cite_problems(doc)
    problems += _precision_split_problems(doc)
    problems += _cross_model_agreement_problems(doc)
    problems += _model_diversity_problems(doc)
    # Empty or insufficient strata must never carry a statistic.  The two
    # gates also cover C16's claims.numbers, where 0.0 used to stand in for
    # a missing stratified baseline.
    problems += _empty_group_stats_problems(doc, claims)
    problems += _strata_min_n_problems(doc)
    # Claim prose must agree with the computed grade; a stale literal would
    # let the headline keep a grade the counts no longer support.
    problems += claim_text_matches_grade(claims or [])
    # The catch-all grade is banned.  Check both surfaces so a missing claims
    # file cannot hide a rendered fallback reason.
    fallback_ids = [
        str(c.get("claim_id", "?"))
        for c in (claims or [])
        if "兜底" in str(c.get("grade_reason", ""))
    ]
    fallback_rendered = [
        reason for reason in re.findall(r'data-grade-reason="([^"]*)"', doc)
        if "兜底" in reason
    ]
    if fallback_ids or fallback_rendered:
        problems.append(
            "fallback grade reason: claims=" + ",".join(fallback_ids)
            + f" rendered={len(fallback_rendered)}"
        )
    hits: list[ForbiddenHit] = []
    try:
        hits = scan_document(doc, claims)
    except ForbiddenConclusionError as exc:
        problems.append(str(exc))
    if not problems and not hits:
        return
    parts = []
    if problems:
        parts.append("catalog/render: " + "；".join(problems))
    if hits:
        parts.append("forbidden hits: " + format_hits(hits))
    raise ForbiddenConclusionError("；".join(parts), hits)


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


@dataclass
class Suite:
    checks: list[Check] = field(default_factory=list)

    def add(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append(Check(name, passed, detail))

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(c.passed for c in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "PASS" if self.passed else "FAIL",
            "checks": len(self.checks),
            "passed": sum(1 for c in self.checks if c.passed),
            "failed": sum(1 for c in self.checks if not c.passed),
            "results": [c.to_dict() for c in self.checks],
        }


def _strip(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _attr(tag_html: str, name: str) -> str:
    """Read one quoted attribute from a rendered block; missing means empty."""
    match = re.search(rf"""{name}=(?:"([^"]*)"|'([^']*)')""", tag_html)
    return (match.group(1) or match.group(2) or "") if match else ""


def validate_report(html_path: Path, claims_path: Path | None = None) -> Suite:
    suite = Suite()
    if not html_path.exists():
        suite.add("report_exists", False, str(html_path))
        return suite
    doc = html_path.read_text(encoding="utf-8")
    suite.add("report_exists", True, f"{len(doc)} chars")
    claims = (
        json.loads(claims_path.read_text())
        if claims_path and claims_path.exists()
        else None
    )

    h2s = [_strip(m) for m in re.findall(r"<h2[^>]*>(.*?)</h2>", doc, re.S)]
    suite.add("h2_count", len(h2s) >= 4, f"{len(h2s)} h2")
    bad = [
        h
        for h in h2s
        if len(h) < 12
        or h.rstrip()[-1:] not in "。？！"
        or any(h.startswith(b) for b in BANNED_H2)
        or len(h) > ALLOWED_H2_MAX
    ]
    suite.add("h2_are_claim_sentences", not bad, json.dumps(bad, ensure_ascii=False)[:400])

    claim_blocks = re.findall(r'<article class="claim".*?</article>', doc, re.S)
    suite.add("claim_blocks_present", len(claim_blocks) >= 5, f"{len(claim_blocks)} blocks")
    missing_cells = []
    for i, block in enumerate(claim_blocks):
        for cell in FOUR_CELLS:
            if f"<b>{cell}</b>" not in block:
                missing_cells.append(f"block{i}:{cell}")
    suite.add("claim_four_cells", not missing_cells, ",".join(missing_cells)[:400])

    # Every claim block must publish its grade, the mechanical reason, and the
    # counts that fired it -- not just in claims.json, but in the report itself.
    bad_block_grade = []
    bad_block_reason = []
    bad_block_counts = []
    for i, block in enumerate(claim_blocks):
        grade = _attr(block, "data-grade")
        if grade not in REQUIRED_GRADES:
            bad_block_grade.append(f"block{i}:{grade}")
        reason = _attr(block, "data-grade-reason")
        if len(reason.strip()) < 8 or "规则" not in reason:
            bad_block_reason.append(f"block{i}:{reason[:30]}")
        counts = _attr(block, "data-counts")
        counts_ok = (
            bool(re.search(r"n_records=[+-]?\d", counts))
            and bool(re.search(r"n_authors=[+-]?\d", counts))
            and bool(re.search(r"agreement=(?:N/A|[+-]?\d)", counts))
        )
        if not counts_ok:
            bad_block_counts.append(f"block{i}:{counts[:40]}")
    suite.add("claim_blocks_carry_grade", not bad_block_grade, ",".join(bad_block_grade)[:400])
    suite.add("claim_blocks_have_grade_reason", not bad_block_reason, ",".join(bad_block_reason)[:400])
    suite.add("claim_blocks_have_counts", not bad_block_counts, ",".join(bad_block_counts)[:400])

    figures = re.findall(r"<figure[^>]*>.*?</figure>", doc, re.S)
    suite.add("figures_present", len(figures) >= 3, f"{len(figures)} figures")
    fig_problems = []
    for i, fig in enumerate(figures):
        for attr in ("data-basis", "data-unit", "data-limit", "data-status"):
            m = re.search(rf"""{attr}=(?:"([^"]*)"|'([^']*)')""", fig)
            if not m or not (m.group(1) or m.group(2) or "").strip():
                fig_problems.append(f"fig{i}:{attr}")
        for cell in META_CELLS:
            if f"<b>{cell}</b>" not in fig:
                fig_problems.append(f"fig{i}:visible:{cell}")
        caption = re.search(r"<figcaption>(.*?)</figcaption>", fig, re.S)
        if not caption or len(_strip(caption.group(1))) < 12:
            fig_problems.append(f"fig{i}:caption")
    suite.add("figure_contract", not fig_problems, ",".join(fig_problems)[:400])

    bad_captions = []
    for i, fig in enumerate(figures):
        caption = re.search(r"<figcaption>(.*?)</figcaption>", fig, re.S)
        text = _strip(caption.group(1)) if caption else ""
        text = re.sub(r"^EXHIBIT\s*\d+\s*", "", text).strip()
        if len(text) < 12 or text[-1:] not in "。？！":
            bad_captions.append(f"fig{i}:{text[:40]}")
    suite.add("figure_captions_are_claims", not bad_captions, ",".join(bad_captions)[:400])

    # Status must be one of the six grades, not a free-text note.
    bad_status = []
    for i, fig in enumerate(figures):
        m = re.search(r"""data-status=(?:"([^"]*)"|'([^']*)')""", fig)
        status = (m.group(1) or m.group(2) or "") if m else ""
        if status not in REQUIRED_GRADES:
            bad_status.append(f"fig{i}:{status}")
    suite.add("figure_status_is_grade", not bad_status, ",".join(bad_status)[:400])

    # Basis must state the denominator explicitly; the reference report's
    # coverage bars were misread as a funnel because the normaliser was unstated.
    bad_basis = []
    for i, fig in enumerate(figures):
        m = re.search(r"""data-basis=(?:"([^"]*)"|'([^']*)')""", fig)
        basis = (m.group(1) or m.group(2) or "") if m else ""
        if "分母" not in basis:
            bad_basis.append(f"fig{i}:{basis[:40]}")
    suite.add("figure_basis_declares_denominator", not bad_basis, ",".join(bad_basis)[:400])

    # The forbidden-conclusion catalog is a machine-checked contract.
    catalog_problems = _catalog_problems()
    suite.add("forbidden_catalog_complete", not catalog_problems, "；".join(catalog_problems)[:400])
    render_problems = _render_problems(doc)
    suite.add("forbidden_list_rendered", not render_problems, "；".join(render_problems)[:400])
    cite_problems = _inline_cite_problems(doc)
    suite.add("inline_citations_three", not cite_problems, "；".join(cite_problems)[:400])
    precision_problems = _precision_split_problems(doc)
    suite.add("precision_split_required", not precision_problems, "；".join(precision_problems)[:400])
    cross_model_problems = _cross_model_agreement_problems(doc)
    suite.add(
        "cross_model_agreement_required",
        not cross_model_problems,
        "；".join(cross_model_problems)[:400],
    )
    model_diversity_problems = _model_diversity_problems(doc)
    suite.add(
        "no_false_model_diversity",
        not model_diversity_problems,
        "；".join(model_diversity_problems)[:400],
    )
    empty_group_problems = _empty_group_stats_problems(doc, claims)
    suite.add(
        "no_empty_group_stats",
        not empty_group_problems,
        "；".join(empty_group_problems)[:600],
    )
    strata_problems = _strata_min_n_problems(doc)
    suite.add(
        "strata_require_min_n",
        not strata_problems,
        "；".join(strata_problems)[:600],
    )

    # Scan the report body and the claims data.  A scanner failure is a failure.
    scan_error = ""
    hits: list[ForbiddenHit] = []
    try:
        hits = scan_document(doc, claims)
    except Exception as exc:  # fail closed, never skip the gate
        scan_error = f"{type(exc).__name__}: {exc}"
    suite.add(
        "no_forbidden_conclusions",
        not hits and not scan_error,
        format_hits(hits) if hits else scan_error,
    )

    # The catalog quotes the anti-patterns by design; scan everything else.
    body_for_scan = strip_for_scan(doc)
    anti = [p for p in ANTI_PATTERNS if re.search(p, body_for_scan)]
    suite.add("no_anti_patterns", not anti, ",".join(anti))

    missing_grades = [g for g in REQUIRED_GRADES if g not in doc]
    suite.add("six_evidence_states", not missing_grades, ",".join(missing_grades))

    # The catalog must be the last substantive block: nothing structural after it.
    tail_block = re.search(
        r"<details\b[^>]*\bclass\s*=\s*[\"'][^\"']*forbidden-zone[^\"']*[\"'][^>]*>.*?</details>",
        doc,
        re.S,
    )
    structure_after = (
        re.findall(r"<(section|article|figure|table|h[1-6])\b", doc[tail_block.end():], re.I)
        if tail_block
        else ["<details> missing"]
    )
    suite.add(
        "forbidden_list_at_end",
        bool(tail_block) and not structure_after,
        f"blocks after tail: {structure_after[:5]}",
    )

    if claims is not None:
        suite.add("claim_count_matches", len(claims) == len(claim_blocks), f"{len(claims)} vs {len(claim_blocks)}")
        grades = {c["grade"] for c in claims}
        suite.add("claim_grades_valid", grades <= set(REQUIRED_GRADES), ",".join(sorted(grades)))
        text_grade_problems = claim_text_matches_grade(claims)
        suite.add(
            "claim_text_matches_grade",
            not text_grade_problems,
            "；".join(text_grade_problems)[:400],
        )
        no_numbers = [c["claim_id"] for c in claims if not c.get("numbers")]
        suite.add("claims_have_numbers", not no_numbers, ",".join(no_numbers))
        missing_reason = [c["claim_id"] for c in claims if not str(c.get("grade_reason", "")).strip()]
        suite.add("claims_have_grade_reason", not missing_reason, ",".join(missing_reason))
        # Fail closed on the removed catch-all.  A grade reason that says
        # "兜底" is evidence that a claim was assigned the lowest positive
        # grade without meeting a mechanical test.
        fallback_reasons = [
            c["claim_id"] for c in claims if "兜底" in str(c.get("grade_reason", ""))
        ]
        suite.add(
            "claims_have_no_fallback_grade",
            not fallback_reasons,
            ",".join(fallback_reasons),
        )
        bad_counts = [
            c["claim_id"]
            for c in claims
            if not {"n_records", "n_authors", "agreement_pct"} <= set(c.get("counts", {}))
        ]
        suite.add("claims_have_counts", not bad_counts, ",".join(bad_counts))
        by_id = {c["claim_id"]: c for c in claims}
        block_mismatch = []
        for i, block in enumerate(claim_blocks):
            cid_value = _attr(block, "data-claim-id")
            grade_value = _attr(block, "data-grade")
            claim = by_id.get(cid_value)
            if claim is None or claim["grade"] != grade_value:
                block_mismatch.append(f"block{i}:{cid_value}->{grade_value}")
        suite.add(
            "claim_block_grade_matches_json",
            not block_mismatch,
            ",".join(block_mismatch)[:400],
        )
        mismatched = []
        for i, fig in enumerate(figures):
            cid = re.search(r"""data-claim-id=(?:"([^"]*)"|'([^']*)')""", fig)
            if not cid:
                mismatched.append(f"fig{i}:no-claim")
                continue
            cid_value = cid.group(1) or cid.group(2) or ""
            status = re.search(r"""data-status=(?:"([^"]*)"|'([^']*)')""", fig)
            status_value = (status.group(1) or status.group(2) or "") if status else ""
            claim = by_id.get(cid_value)
            if claim is None or claim["grade"] != status_value:
                mismatched.append(f"fig{i}:{cid_value}->{status_value}")
        suite.add("figure_status_matches_claim", not mismatched, ",".join(mismatched)[:400])
    return suite


def validate_spec(spec_dir: Path) -> Suite:
    suite = Suite()
    for name in ("gates.json", "skills.json", "counting.json", "evidence.json"):
        path = spec_dir / name
        suite.add(f"spec_{name}", path.exists(), str(path))
    if (spec_dir / "gates.json").exists():
        gates = json.loads((spec_dir / "gates.json").read_text())
        suite.add("gate_count_11", len(gates) == 11, f"{len(gates)}")
        suite.add("gates_have_rollback", all(g["rollback"] for g in gates))
    if (spec_dir / "skills.json").exists():
        skills = json.loads((spec_dir / "skills.json").read_text())
        suite.add("skill_count_14", len(skills) == 14, f"{len(skills)}")
        suite.add("skills_have_steps", all(s["steps"] for s in skills))
        suite.add("skills_have_handoff", all(s["handoff"] for s in skills))
        suite.add("skills_classified", all(s["automation"] in {"pure_logic", "hybrid", "human_required"} for s in skills))
    if (spec_dir / "counting.json").exists():
        counting = json.loads((spec_dir / "counting.json").read_text())
        suite.add("counting_levels_6", len(counting["levels"]) == 6, f"{len(counting['levels'])}")
        suite.add("deduction_rules_present", len(counting["deduction_rules"]) >= 10)
    if (spec_dir / "evidence.json").exists():
        ev = json.loads((spec_dir / "evidence.json").read_text())
        suite.add("evidence_grades_6", len(ev["rules"]) == 6, f"{len(ev['rules'])}")
    return suite


def main(argv: list[str] | None = None) -> int:
    """Standalone gate: exit 1 and print matched snippets on any hit."""
    parser = argparse.ArgumentParser(prog="voc.validate_report")
    parser.add_argument("html", type=Path)
    parser.add_argument("claims", nargs="?", type=Path)
    args = parser.parse_args(argv)
    suite = validate_report(args.html, args.claims)
    print(json.dumps(suite.to_dict(), ensure_ascii=False, indent=1))
    if suite.passed:
        return 0
    for check in suite.checks:
        if not check.passed:
            print(f"[FAIL] {check.name}: {check.detail}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
