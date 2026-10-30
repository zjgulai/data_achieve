"""Core contracts for the VOC pipeline.

Every number that leaves this package must be traceable to one of the six
counting levels defined here, and every published statement must carry one of
the six evidence grades.  The enums are the machine-readable source of truth;
the JSON specs under ``voc_pipeline/spec`` are rendered from them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CountingLevel(str, Enum):
    RAW_OBJECT = "raw_object"
    OCCURRENCE = "occurrence"
    CANONICAL_RECORD = "canonical_record"
    FRAME_MEMBERSHIP = "frame_membership"
    ANNOTATION = "annotation"
    METRIC_ROW = "metric_row"


class Frame(str, Enum):
    """Sample frames.  A record can belong to several frames at once."""

    NATURAL = "natural"
    DIAGNOSTIC = "diagnostic"
    QUALITATIVE_SEED = "qualitative_seed"
    TIKTOK_SHOP_VERIFIED = "tiktok_shop_verified"
    CLAIM = "claim_asset"
    DISCOVERY = "discovery"
    EXCLUDED = "excluded"


class DataLayer(str, Enum):
    CONSUMER_OBSERVATION_FACT = "consumer_observation_fact"
    CLAIM_ASSET_FACT = "claim_asset_fact"
    MARKET_SIGNAL_FACT = "market_signal_fact"
    DISCOVERY_HOLD_QUEUE = "discovery_hold_queue"
    EXCLUDED_LINEAGE = "excluded_lineage"


class EvidenceGrade(str, Enum):
    """Six grades.  The fifth and sixth are routinely conflated in reports.

    Maturity is a state, not a score: a claim sits in exactly one grade, and
    the rules in ``voc.evidence`` decide which one, first match wins.
    """

    CONFIRMED = "Confirmed"
    DIRECTIONAL = "Directional"
    SUPPORTED_HYPOTHESIS = "Supported hypothesis"
    GAP = "Evidence gap"
    BLOCKED = "Blocked"
    NOT_AUTHORIZED = "Not authorized"


@dataclass(frozen=True)
class DetectionRule:
    """Machine rule behind one forbidden conclusion.

    ``text_regex`` is compiled by ``voc.validate_report`` and matched against
    the rendered report after style/script, the forbidden-list block and inline
    citations are removed.  ``data_keys`` are matched against the ``numbers``
    dictionaries in ``claims.json``.  An empty rule means the ban is declared
    but not machine-detected yet; the validator reports that as incomplete.
    """

    text_regex: str | None = None
    data_keys: tuple[str, ...] = ()
    note: str = ""

    def describe(self) -> str:
        parts: list[str] = []
        if self.text_regex:
            parts.append(f"text_regex {self.text_regex}")
        if self.data_keys:
            parts.append("data_keys " + " / ".join(self.data_keys))
        if self.note:
            parts.append(self.note)
        return "；".join(parts) if parts else "仅声明，未接检测器"

    def to_dict(self) -> dict[str, Any]:
        return {
            "text_regex": self.text_regex,
            "data_keys": list(self.data_keys),
            "note": self.note,
        }


@dataclass(frozen=True)
class ForbiddenConclusion:
    """A conclusion shape this product must never emit.

    ``pattern`` names the data shape or sentence form that is banned, ``why``
    explains the failure it would cause, ``detected_by`` carries the executable
    rule, and ``ref_origin`` pins the item to the reference appendix or to the
    corpus-specific reason it was added.
    """

    id: str
    pattern: str
    why: str
    detected_by: DetectionRule
    ref_origin: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "pattern": self.pattern,
            "why": self.why,
            "detected_by": self.detected_by.to_dict(),
            "ref_origin": self.ref_origin,
        }


FORBIDDEN_CONCLUSIONS: tuple[ForbiddenConclusion, ...] = (
    ForbiddenConclusion(
        id="FC-01",
        pattern="用正负向占比或『X% 的用户满意 / 不满意』表示整体情绪，例如『67% 的用户不满意』。",
        why=(
            "本轮是关键词召回的非概率样本，单编码且 pre-G7；任何情绪占比都没有合法分母，"
            "会把 annotation hits 伪装成人群比例。"
        ),
        detected_by=DetectionRule(
            text_regex=(
                r"(?:\d{1,3}(?:\.\d+)?\s*%[^。；\n]{0,20}(?:用户|妈妈|孕妇|人|样本|记录)?"
                r"[^。；\n]{0,10}(?:满意|不满|正面|负面|正向|负向|情绪|推荐))"
                r"|(?:(?:满意|不满|正面|负面|正向|负向|情绪)[^。；\n]{0,20}\d{1,3}(?:\.\d+)?\s*%)"
            ),
            data_keys=(
                "overall_sentiment_rate",
                "sentiment_rate",
                "positive_share",
                "negative_share",
                "satisfaction_rate",
            ),
            note="百分比必须紧邻情绪词才算命中，避免误伤等级阈值里的 70%。",
        ),
        ref_origin="ref 附录「本报告不能说的话」· 总体情绪率（positive / negative share）",
    ),
    ForbiddenConclusion(
        id="FC-02",
        pattern="用饼图、环形图或百分比构成图展示 Love vs Complaint / 情感构成。",
        why=(
            "annotation 是多标签且可重叠的，各类合计不等于 100%；"
            "互斥构成图会制造一个不存在的整体。"
        ),
        detected_by=DetectionRule(
            text_regex=r"(?:饼图|环形图|甜甜圈图|百分比分布|占比图)",
            note="只抓图表词；正文中的『不比较百分比』不会命中。",
        ),
        ref_origin="ref 附录「本报告不能说的话」· 饼图与百分比构成（pie chart percentage）",
    ),
    ForbiddenConclusion(
        id="FC-03",
        pattern="NPS、CSAT、满意度评分或净推荐值等量表分数。",
        why="本轮没有量表题、样本框和应答率；任何评分都不是消费者调查的结果。",
        detected_by=DetectionRule(
            text_regex=(
                r"(?i)(?:\bNPS\b|\bCSAT\b|净推荐值|满意度(?:评分|得分|指数|调查)"
                r"|满意率[^。；\n]{0,8}\d)"
            ),
            data_keys=("nps", "nps_score", "csat", "csat_score", "satisfaction_score"),
        ),
        ref_origin="ref 附录「本报告不能说的话」· NPS / 满意度评分",
    ),
    ForbiddenConclusion(
        id="FC-04",
        pattern="ROI、ROAS、转化率排名或投资回报排序。",
        why="没有成本、曝光、点击与成交数据；把 VOC 频次映射成商业回报是编造因果。",
        detected_by=DetectionRule(
            text_regex=(
                r"(?i)(?:\bROI\b|\bROAS\b|投资回报率"
                r"|(?:转化率|conversion rate)[^。；\n]{0,8}(?:排名|排行|最高|最低|第一)"
                r"|(?:排名|排行)[^。；\n]{0,8}(?:转化率|ROI))"
            ),
            data_keys=("roi", "roas", "conversion_rate", "roi_rank", "conversion_rank"),
        ),
        ref_origin="ref 附录「本报告不能说的话」· ROI / 转化率排名",
    ),
    ForbiddenConclusion(
        id="FC-05",
        pattern="净推荐值、净情感值、净情绪分等正负相减后的单一得分。",
        why="正负标注不是同一把尺子，相减会抵消多标签与条件性，净分把结构藏起来。",
        detected_by=DetectionRule(
            text_regex=(
                r"(?i)(?:净(?:推荐|情感|情绪)(?:值|分)|net sentiment|net score|净值打分)"
                r"|(?:净分[^。；\n]{0,6}[+\-−]?\d|\d[^。；\n]{0,6}净分)"
            ),
            data_keys=("net_score", "net_sentiment", "net_sentiment_score", "net_promoter"),
        ),
        ref_origin="ref 附录「本报告不能说的话」· 净值打分（net score）",
    ),
    ForbiddenConclusion(
        id="FC-06",
        pattern="把 coverage 写成 conversion：覆盖数逐级变成漏斗率或『转化率』。",
        why="raw→occurrence→canonical 是去重与身份收敛，不是用户旅程；各级不能相乘成漏斗。",
        detected_by=DetectionRule(
            text_regex=(
                r"(?i)(?:(?:覆盖|coverage)[^。；\n]{0,12}(?:漏斗|funnel|转化率|conversion rate)"
                r"|(?:漏斗|funnel|转化率|conversion rate)[^。；\n]{0,12}(?:覆盖|coverage))"
            ),
            data_keys=("funnel_rate", "coverage_conversion_rate"),
            note="只抓『覆盖 + 漏斗/转化率』同句；『不把覆盖当成逐级转化』不命中。",
        ),
        ref_origin="ref 附录「本报告不能说的话」· 把覆盖当漏斗（coverage as funnel）",
    ),
    ForbiddenConclusion(
        id="FC-07",
        pattern="把 natural / diagnostic / qualitative_seed 的比例放在一起比较或排名。",
        why="frame 是回答不同问题的镜头，diagnostic 还是内容派生子集；跨 frame 百分比没有共同分母。",
        detected_by=DetectionRule(
            text_regex=(
                r"(?i)(?:(?:natural|diagnostic|qualitative_seed|自然样本|诊断样本|定性种子)"
                r"[^。；\n]{0,24}(?:比较|对比|高于|低于|多于|少于)[^。；\n]{0,24}"
                r"\d{1,3}(?:\.\d+)?\s*%"
                r"|\d{1,3}(?:\.\d+)?\s*%[^。；\n]{0,24}"
                r"(?:natural|diagnostic|自然样本|诊断样本)[^。；\n]{0,12}(?:比较|对比|高于|低于))"
            ),
            data_keys=("cross_frame_pct", "frame_comparison_pct", "frame_rate_gap"),
            note="必须同时出现 frame 名、比较动词与百分比。",
        ),
        ref_origin="ref 附录「本报告不能说的话」· 跨 frame 比较百分比",
    ),
    ForbiddenConclusion(
        id="FC-08",
        pattern="把单来源（Reddit / Amazon PDP / 单次抓取）的比例写成 prevalence、发生率或普遍率。",
        why="没有概率抽样、抽样框与应答率；单源频次只能说明『在本样本中出现』。",
        detected_by=DetectionRule(
            text_regex=(
                r"(?i)(?:prevalence|普遍率|发生率|渗透率)[^。；\n]{0,10}"
                r"(?:为|达|是|约)\s*\d{1,3}(?:\.\d+)?\s*%"
                r"|(?:Reddit|单一来源|单源)[^。；\n]{0,16}(?:prevalence|普遍率|渗透率|发生率)"
                r"|\d{1,3}(?:\.\d+)?\s*%[^。；\n]{0,8}(?:孕妇|妈妈|用户)[^。；\n]{0,6}(?:都|普遍|大多)"
            ),
            data_keys=("prevalence", "incidence_rate", "penetration_rate"),
            note="『不得估计发生率』这类规范性句子不命中，因为没有数字断言。",
        ),
        ref_origin="ref 附录「本报告不能说的话」扩展 · 单源 prevalence；本语料对象为 Reddit 召回",
    ),
    ForbiddenConclusion(
        id="FC-09",
        pattern="疗效、治愈率、安全率、诊断或临床验证类结论。",
        why="self-report 不是临床证据；报告没有剂量、对照与随访，也没有医学 / 法务 review。",
        detected_by=DetectionRule(
            text_regex=(
                r"(?i)(?:(?:疗效|效果)[^。；\n]{0,6}(?:显著|明显|确切|可靠)"
                r"|(?:治愈|有效率|安全率|诊断准确率|缓解率)[^。；\n]{0,10}(?:达|达到|高达|为|是)\s*\d"
                r"|(?:治愈|有效率|安全率|诊断准确率|缓解率)[^。；\n]{0,4}\d{1,3}(?:\.\d+)?\s*%"
                r"|(?:可以|能够|已|被)(?:治愈|治疗|预防|根治)[^。；\n]{0,10}(?:疾病|症状|疼痛|不适)"
                r"|(?:临床|医学)(?:验证|证明|证实|试验)[^。；\n]{0,6}(?:有效|安全|成功)"
                r"|(?:无副作用|绝对安全|零风险)"
                r"|\b(?:efficacy|cure|clinically proven|safe and effective)\b)"
            ),
            data_keys=("efficacy_rate", "safety_rate", "cure_rate"),
            note="只抓断言形态；『不能变成疗效或安全结论』这类禁写句不命中。",
        ),
        ref_origin="ref 附录「本报告不能说的话」扩展 · 医学 / 疗效 / 安全；本语料对象为 MED.* self-report",
    ),
    ForbiddenConclusion(
        id="FC-10",
        pattern="把『有没有人用过 / Does anyone / 求推荐』这类求助帖说成本人使用体验或体验分布。",
        why="求助帖表达的是需求与问题，不是使用结果；把提问计入体验会系统性放大未满足需求。",
        detected_by=DetectionRule(
            text_regex=(
                r"(?i)(?:(?:求助帖|提问帖|问句|求推荐)[^。；\n]{0,16}"
                r"(?:说明|证明|表明|反映|显示)[^。；\n]{0,12}(?:体验|感受|不满|满意|效果)"
                r"|(?:does anyone|has anyone|anyone else|有人用过|有没有人)"
                r"[^。；\n]{0,16}(?:说明|证明|可见|表明|反映))"
            ),
            note="文本层检测『求助 → 说明体验』的推断句式；数据层由 C11 的 experience 计数约束。",
        ),
        ref_origin="本语料补充：Reddit 召回以求助与比较为主（C11），ref 未单列",
    ),
    ForbiddenConclusion(
        id="FC-11",
        pattern="把 product_snapshot.is_estimated=true 的销量 / GMV / 销售额估算写成实测事实或据此排名。",
        why="本轮没有销量一手数据；估算字段是第三方建模值，写成实测会把模型误差伪装成事实。",
        detected_by=DetectionRule(
            text_regex=(
                r"(?i)(?:(?:销量|销售额|营收|GMV)[^。；\n]{0,10}"
                r"(?:为|达|达到|约)\s*[\d,.]+\s*(?:万|亿|件|台|美元|USD|美金))"
            ),
            data_keys=(
                "sales_units",
                "sales_volume",
                "sales",
                "gmv",
                "gmv_usd",
                "revenue",
                "revenue_usd",
                "monthly_sales",
            ),
            note="claims.numbers 里出现任何销量 / GMV 键即命中；带 is_estimated=true 时片段会标注。",
        ),
        ref_origin=(
            "本语料补充：Amazon 仅有 PDP 身份证据"
            "（source-rights-matrix: amazon_pdp metric_eligible=false），无销量一手数据"
        ),
    ),
    ForbiddenConclusion(
        id="FC-12",
        pattern=(
            "把内容形态与互动率的相关性写成因果，例如『长视频带来更高互动』"
            "或『因为购买链接，所以互动率更高』。"
        ),
        why=(
            "本轮视频层是关键词搜索的非概率样本，内容形态标签由文案与商品锚点派生，"
            "且主要分层与关联质量共线；相关性不能识别因果。"
        ),
        detected_by=DetectionRule(
            text_regex=(
                r"(?i)(?:"
                r"(?:时长档|时长|内容形态|视频形态|内容形式|视频|格式|购买链接|广告披露|达人层级|粉丝量|粉丝数)"
                r"[^。；\n]{0,24}(?:导致|带来|造成|决定|驱动|提升|提高|拉高|增加|降低)"
                r"[^。；\n]{0,16}(?:互动|点赞|评论|分享|播放|转化)"
                r"|(?:互动|点赞|评论|分享|播放|转化)[^。；\n]{0,16}"
                r"(?:由|因为|取决于|归因于)[^。；\n]{0,16}"
                r"(?:时长|内容形态|视频形态|格式|购买链接|广告披露|达人|粉丝)"
                r"|(?:because|due to|caused by|drives|leads to|results in)"
                r"[^.\n]{0,40}(?:engagement|interaction|views|likes)"
                r"|(?:engagement|interaction|views|likes)[^.\n]{0,40}"
                r"(?:because|due to|caused by)"
                r")"
            ),
            data_keys=(
                "causal_format_effect",
                "content_format_causes_engagement",
                "engagement_caused_by_format",
                "format_causal_lift",
            ),
            note="只抓形态词、因果动词与互动词的连写；『不写成因果』这类禁写句不命中。",
        ),
        ref_origin="本语料补充：creator/video_snapshot 首次接入；ref 未单列",
    ),
)


def forbidden_conclusions_payload() -> dict[str, Any]:
    """Serialise the catalog for spec/ and run artifacts."""
    return {
        "schema_version": "voc_forbidden_conclusions_v1",
        "count": len(FORBIDDEN_CONCLUSIONS),
        "note": (
            f"{len(FORBIDDEN_CONCLUSIONS)} 类禁止结论。每条带机器检测规则；"
            "validate_report 在渲染后扫描正文与 claims.numbers，"
            "命中即 fail closed。成熟度是状态，不是评分。"
        ),
        "items": [item.to_dict() for item in FORBIDDEN_CONCLUSIONS],
    }


# Lower-case contract field name consumed by the renderer, validator and specs.
forbidden_conclusions = FORBIDDEN_CONCLUSIONS


class GateStatus(str, Enum):
    PASS = "PASS"
    CONDITIONAL = "CONDITIONAL"
    BLOCKED = "BLOCKED"
    NOT_STARTED = "NOT_STARTED"


class DeductionReason(str, Enum):
    """Why a count went down between two levels.

    The code is stable; the human label is rendered in reports.
    """

    WITHIN_FRAME_OVERLAP = "within_frame_overlap"
    CROSS_FRAME_OVERLAP = "cross_frame_overlap"
    CROSS_SOURCE_SYNDICATED = "cross_source_syndicated_duplicate"
    CROSSPOST_SAME_AUTHOR = "crosspost_same_author"
    NONREPRESENTATIVE_DUPLICATE = "known_duplicate_nonrepresentative"
    LOW_INFORMATION = "low_information"
    PRODUCT_MISMATCH = "product_mismatch"
    NON_CONSUMER_ROLE = "non_consumer_role"
    COMMERCIAL_DISCLOSURE = "commercial_disclosure"
    OUT_OF_WINDOW = "out_of_window"
    LANGUAGE_UNCODABLE = "language_uncodable"
    DELETED_OR_REMOVED = "deleted_or_removed"
    QUOTED_REPOST = "quoted_repost"
    TRANSLATION_DUPLICATE = "translation_duplicate"


DEDUCTION_LABELS: dict[DeductionReason, str] = {
    DeductionReason.WITHIN_FRAME_OVERLAP: "同 frame 内重复成员关系",
    DeductionReason.CROSS_FRAME_OVERLAP: "跨 frame 重叠（不扣 canonical，只影响朴素求和）",
    DeductionReason.CROSS_SOURCE_SYNDICATED: "跨源转载 / 联合发布",
    DeductionReason.CROSSPOST_SAME_AUTHOR: "同一作者跨版转发",
    DeductionReason.NONREPRESENTATIVE_DUPLICATE: "已知重复的非代表记录",
    DeductionReason.LOW_INFORMATION: "低信息量（无体验内容）",
    DeductionReason.PRODUCT_MISMATCH: "产品不匹配",
    DeductionReason.NON_CONSUMER_ROLE: "非消费者角色（品牌 / 创作者 / 自动化）",
    DeductionReason.COMMERCIAL_DISCLOSURE: "商业披露内容",
    DeductionReason.OUT_OF_WINDOW: "超出研究窗口",
    DeductionReason.LANGUAGE_UNCODABLE: "语言不可编码",
    DeductionReason.DELETED_OR_REMOVED: "已删除 / 已移除",
    DeductionReason.QUOTED_REPOST: "引用式转发",
    DeductionReason.TRANSLATION_DUPLICATE: "翻译副本",
}


class Role(str, Enum):
    """Who executes a step.  Used by the skills spec to separate code from people."""

    CODE = "code"
    LLM_ASSISTED = "llm_assisted"
    HUMAN = "human"


@dataclass(frozen=True)
class Actor:
    role: Role
    note: str = ""


@dataclass
class LedgerRow:
    """One reconciliation step between two counting levels."""

    from_level: CountingLevel
    to_level: CountingLevel
    input_count: int
    output_count: int
    deductions: dict[str, int] = field(default_factory=dict)
    note: str = ""

    @property
    def deducted(self) -> int:
        return sum(self.deductions.values())

    def check(self) -> None:
        if self.input_count - self.deducted != self.output_count:
            raise ValueError(
                f"reconciliation failed {self.from_level}->{self.to_level}: "
                f"{self.input_count} - {self.deducted} != {self.output_count}"
            )


@dataclass
class Claim:
    """A statement that can be published, with its evidence contract.

    ``grade_reason`` is mandatory: it names the mechanical rule that fired and
    quotes the counts that made it fire.  ``counts`` always carries
    ``n_records`` / ``n_authors`` / ``agreement_pct`` so a reader can re-derive
    the grade without trusting the author.
    """

    claim_id: str
    section: str
    headline: str
    grade: EvidenceGrade
    observed: str
    interpretation: str
    counterevidence: str
    decision: str
    basis: str
    unit: str
    limit: str
    status: str
    grade_reason: str = ""
    counts: dict[str, Any] = field(default_factory=dict)
    records: list[str] = field(default_factory=list)
    numbers: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "section": self.section,
            "headline": self.headline,
            "grade": self.grade.value,
            "grade_reason": self.grade_reason,
            "counts": self.counts,
            "observed": self.observed,
            "interpretation": self.interpretation,
            "counterevidence": self.counterevidence,
            "decision": self.decision,
            "basis": self.basis,
            "unit": self.unit,
            "limit": self.limit,
            "status": self.status,
            "records": self.records,
            "numbers": self.numbers,
        }
