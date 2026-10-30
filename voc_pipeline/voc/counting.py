"""Six counting levels and the rules that move a record between them.

The levels are deliberately not a funnel.  A record can be in several frames,
one canonical record can carry many annotations, and an annotation is not a
consumer.  Only the last level (metric row) may be used in a rate.

The rules below are executable: ``Reconciler`` raises when a count does not
balance, and ``explain_deduction`` returns the reason code that must accompany
every decrease.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .contracts import DEDUCTION_LABELS, CountingLevel, DeductionReason

COUNTING_LEVELS: list[dict[str, Any]] = [
    {
        "level": CountingLevel.RAW_OBJECT.value,
        "definition": "一次 provider 响应中的一条原始记录，只追加、不改写。",
        "identity": "provider + endpoint + request_id + response_index",
        "required_fields": ["provider", "endpoint", "request_id", "fetched_at", "payload_sha256"],
        "may_be_counted_as": "采集量与成本，不是样本量",
        "must_not_be_used_for": ["sample size", "sentiment denominator"],
        "judgement_rule": "每保存一条 payload 计 1；同一 payload 重跑产生新 raw object，但 request_id 不同。",
    },
    {
        "level": CountingLevel.OCCURRENCE.value,
        "definition": "同一内容在一个 source / URL / frame 中的一次出现。",
        "identity": "source + external_id + frame",
        "required_fields": ["source", "external_id", "url", "frame", "content_hash", "created_at"],
        "may_be_counted_as": "frame 内观察次数",
        "must_not_be_used_for": ["independent consumer count", "prevalence denominator"],
        "judgement_rule": "同一 external_id 在同一 frame 只算 1 个 occurrence；跨 frame 各自计 1，因为回答的问题不同。",
    },
    {
        "level": CountingLevel.CANONICAL_RECORD.value,
        "definition": "跨 source 与 frame 去重后的独立内容单元。",
        "identity": "duplicate_group_id + representative_id",
        "required_fields": ["canonical_id", "representative_occurrence", "duplicate_group_id", "normalized_text_hash"],
        "may_be_counted_as": "独立内容单元数",
        "must_not_be_used_for": ["独立消费者数（同一作者可多条）", "总体情绪率"],
        "judgement_rule": "exact normalized-hash 相同即同组；fuzzy Jaccard ≥ 0.90 进入 review，未裁决前不合并。每组恰好一个代表。",
    },
    {
        "level": CountingLevel.FRAME_MEMBERSHIP.value,
        "definition": "canonical record 与一个 sample frame 的关系，可重叠。",
        "identity": "canonical_id + frame",
        "required_fields": ["canonical_id", "frame", "purpose", "denominator_rule"],
        "may_be_counted_as": "各 frame 的可用记录数",
        "must_not_be_used_for": ["把多个 frame 相加当总体", "跨 frame 百分比比较"],
        "judgement_rule": "natural / diagnostic / qualitative_seed / claim / discovery 各自独立；一个 canonical 可同时属于多个 frame，但同一 frame 内只算 1 次。",
    },
    {
        "level": CountingLevel.ANNOTATION.value,
        "definition": "对一条 canonical record 的一个 aspect / polarity / context / journey / outcome / gap 标签。",
        "identity": "canonical_id + axis + code + polarity + taxonomy_version",
        "required_fields": ["canonical_id", "axis", "code", "polarity", "taxonomy_version", "coder_id"],
        "may_be_counted_as": "annotation hits（多标签）",
        "must_not_be_used_for": ["人数", "记录数", "比率分母"],
        "judgement_rule": "一条记录可贡献多个 annotation；mixed 记录保留正负两个 component；unknown 不计入任何 polarity 分子。",
    },
    {
        "level": CountingLevel.METRIC_ROW.value,
        "definition": "通过 G7 且满足 metric contract 的正式指标行。",
        "identity": "metric_id + frame + denominator_contract + taxonomy_version + qa_state",
        "required_fields": [
            "metric_id",
            "numerator",
            "denominator",
            "filters",
            "frame",
            "date_range",
            "source_coverage",
            "missingness",
            "taxonomy_version",
            "qa_state",
        ],
        "may_be_counted_as": "正式比率 / 指标",
        "must_not_be_used_for": ["未通过 G7 时的任何比率", "诊断样本的 prevalence"],
        "judgement_rule": "只有 G7 = PASS、duplicate_representative = true、frame = natural、data_layer = consumer_observation_fact 且 denominator > 0 时才能生成。",
    },
]

DEDUCTION_RULES: list[dict[str, Any]] = [
    {
        "code": DeductionReason.WITHIN_FRAME_OVERLAP.value,
        "from": CountingLevel.FRAME_MEMBERSHIP.value,
        "to": CountingLevel.OCCURRENCE.value,
        "condition": "同一 external_id 在同一 frame 被多次写入 membership。",
        "detect": "group by (frame, external_id) having count > 1",
        "action": "保留 1 个 occurrence，其余计入 within_frame_overlap。",
    },
    {
        "code": DeductionReason.CROSS_FRAME_OVERLAP.value,
        "from": CountingLevel.FRAME_MEMBERSHIP.value,
        "to": CountingLevel.OCCURRENCE.value,
        "condition": "同一 external_id 出现在多个 frame。",
        "detect": "group by external_id having count(distinct frame) > 1",
        "action": "occurrence 按 frame 各计一次；只在把 memberships 朴素相加时才扣。不得把扣减后的数当作总体样本。",
    },
    {
        "code": DeductionReason.CROSS_SOURCE_SYNDICATED.value,
        "from": CountingLevel.OCCURRENCE.value,
        "to": CountingLevel.CANONICAL_RECORD.value,
        "condition": "同一内容在两个 source 同步发布（转载、联合发布、同文多站）。",
        "detect": "exact normalized hash equal across distinct sources",
        "action": "合并为 1 个 canonical，代表取最早发布且在允许来源内的一条。",
    },
    {
        "code": DeductionReason.CROSSPOST_SAME_AUTHOR.value,
        "from": CountingLevel.OCCURRENCE.value,
        "to": CountingLevel.CANONICAL_RECORD.value,
        "condition": "同一作者把同一内容转发到多个 subreddit / 社区。",
        "detect": "same author + Jaccard(title+body) ≥ 0.90",
        "action": "合并；代表取最早 created_utc。",
    },
    {
        "code": DeductionReason.NONREPRESENTATIVE_DUPLICATE.value,
        "from": CountingLevel.CANONICAL_RECORD.value,
        "to": CountingLevel.CANONICAL_RECORD.value,
        "condition": "duplicate group 中非代表记录被误计入编码语料。",
        "detect": "record.duplicate_representative == false",
        "action": "从编码语料扣 1，保留 lineage edge。",
    },
    {
        "code": DeductionReason.LOW_INFORMATION.value,
        "from": CountingLevel.CANONICAL_RECORD.value,
        "to": CountingLevel.CANONICAL_RECORD.value,
        "condition": "内容没有可编码的体验信息（仅链接、仅表情、仅问题无描述）。",
        "detect": "normalized_text token count < 8 or no aspect lexicon hit",
        "action": "进入 exclusion_quarantine，reason=low_information；不计入编码语料。",
    },
    {
        "code": DeductionReason.PRODUCT_MISMATCH.value,
        "from": CountingLevel.CANONICAL_RECORD.value,
        "to": CountingLevel.CANONICAL_RECORD.value,
        "condition": "产品不是目标产品、家族或声明的 adjacent。",
        "detect": "product_match ∈ {irrelevant, other_product}",
        "action": "excluded_lineage；不得进入任何 denominator。",
    },
    {
        "code": DeductionReason.NON_CONSUMER_ROLE.value,
        "from": CountingLevel.CANONICAL_RECORD.value,
        "to": CountingLevel.CANONICAL_RECORD.value,
        "condition": "作者是品牌、零售商、自动化账号或创作者 commercial 内容。",
        "detect": "content_role ∈ {brand_claim, retailer_message, creator_testimonial, automation} and commerciality != none",
        "action": "进入 claim_asset_fact 或 market_signal_fact，隔离出 consumer metric。",
    },
    {
        "code": DeductionReason.COMMERCIAL_DISCLOSURE.value,
        "from": CountingLevel.CANONICAL_RECORD.value,
        "to": CountingLevel.CANONICAL_RECORD.value,
        "condition": "文本含 affiliate / sponsored / paid 披露。",
        "detect": "lexicon match (affiliate, sponsored, paid partnership, #ad)",
        "action": "标记 commerciality=explicit，禁止进入 organic consumer denominator。",
    },
    {
        "code": DeductionReason.OUT_OF_WINDOW.value,
        "from": CountingLevel.OCCURRENCE.value,
        "to": CountingLevel.OCCURRENCE.value,
        "condition": "created_at 在 G0 研究窗口之外。",
        "detect": "created_at < window_start or > window_end",
        "action": "保留 raw 与 occurrence 以便审计，但不进入 canonical 语料。",
    },
    {
        "code": DeductionReason.LANGUAGE_UNCODABLE.value,
        "from": CountingLevel.CANONICAL_RECORD.value,
        "to": CountingLevel.CANONICAL_RECORD.value,
        "condition": "语言不在 taxonomy 支持列表，且无批准翻译。",
        "detect": "language not in taxonomy.languages",
        "action": "exclusion_quarantine；不得用机器翻译直接补齐。",
    },
    {
        "code": DeductionReason.DELETED_OR_REMOVED.value,
        "from": CountingLevel.OCCURRENCE.value,
        "to": CountingLevel.OCCURRENCE.value,
        "condition": "provider 标记 deleted / removed / [removed]。",
        "detect": "body in {[deleted], [removed]}",
        "action": "保留 occurrence 计数，canonical 排除并记录原因。",
    },
    {
        "code": DeductionReason.QUOTED_REPOST.value,
        "from": CountingLevel.OCCURRENCE.value,
        "to": CountingLevel.CANONICAL_RECORD.value,
        "condition": "内容主体是引用另一条记录，未新增体验。",
        "detect": "quoted block ratio > 0.6",
        "action": "合并到被引用记录，保留 lineage edge。",
    },
    {
        "code": DeductionReason.TRANSLATION_DUPLICATE.value,
        "from": CountingLevel.CANONICAL_RECORD.value,
        "to": CountingLevel.CANONICAL_RECORD.value,
        "condition": "同一内容的多语言版本由同一作者发布。",
        "detect": "same author + cross-lingual embedding similarity ≥ 0.90 (review)",
        "action": "合并；代表取原语言版本。",
    },
]


@dataclass
class Reconciler:
    """Accumulates ledger rows and refuses to emit an unbalanced chain."""

    rows: list[Any] = field(default_factory=list)

    def add(self, row: Any) -> None:
        row.check()
        self.rows.append(row)

    def chain(self) -> dict[str, int]:
        if not self.rows:
            return {}
        chain = {self.rows[0].from_level.value: self.rows[0].input_count}
        for row in self.rows:
            chain[row.to_level.value] = row.output_count
        return chain

    def to_dict(self) -> dict[str, Any]:
        return {
            "chain": self.chain(),
            "rows": [
                {
                    "from": row.from_level.value,
                    "to": row.to_level.value,
                    "input": row.input_count,
                    "output": row.output_count,
                    "deducted": row.deducted,
                    "deductions": row.deductions,
                    "note": row.note,
                }
                for row in self.rows
            ],
        }


def counting_spec() -> dict[str, Any]:
    return {
        "levels": COUNTING_LEVELS,
        "deduction_rules": DEDUCTION_RULES,
        "deduction_labels": {k.value: v for k, v in DEDUCTION_LABELS.items()},
        "invariants": [
            "level counts are never interchangeable",
            "memberships are not a funnel",
            "annotations are not people",
            "metric rows require G7 PASS and a non-empty denominator",
            "every deduction carries one reason code",
        ],
    }


def explain_deduction(code: str) -> str:
    try:
        return DEDUCTION_LABELS[DeductionReason(code)]
    except ValueError as exc:
        raise KeyError(f"unknown deduction reason: {code}") from exc


def assert_levels_distinct(counts: dict[str, int], levels: Iterable[str] | None = None) -> None:
    """Guard against the most common error: reusing one number at two levels.

    Identical values are allowed; identical *labels* for different levels are
    allowed.  What is forbidden is publishing a lower level under a higher
    level's name, which is checked in the report validator instead.
    """
    levels = list(levels or [lvl["level"] for lvl in COUNTING_LEVELS])
    missing = [lvl for lvl in levels if lvl not in counts]
    if missing:
        raise ValueError(f"missing counting levels: {missing}")
