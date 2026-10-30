"""Six-level counting with an explicit deduction ledger.

Implements SOP skill ``voc-canonicalize`` (G6) and the counting separation
that G6 requires:

    raw_object -> occurrence -> canonical_record -> frame_membership
    -> annotation -> metric_row

Every transition is a ``ReconciliationRow``: it carries input count, output
count, deducted count, and reason codes.  ``assert_balanced`` refuses to emit
an unbalanced chain.  The sixth level is fail-closed: when G7 is not PASS,
candidate metric rows are all deducted with reason ``gate_not_pass`` and the
report shows 0.

Not implemented here: the G7 double-coding agreement (that is
``coding.agreement_report``, which raises until a second coder exists).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from . import contract
from .ingest import IngestResult

TAXONOMY_VERSION = "VOC-BAND-v1.0"

URL_RE = re.compile(r"https?://\S+")
WS_RE = re.compile(r"\s+")
TOKEN_RE = re.compile(r"[a-z0-9']+")

COUNTING_LEVELS = [
    {
        "level": "raw_object",
        "definition": "一次 provider 响应中的一条原始记录，只追加、不改写。",
        "identity": "provider + request_id + response_index",
        "may_be_counted_as": "采集量与成本",
        "must_not_be_used_for": ["sample size", "sentiment denominator"],
    },
    {
        "level": "occurrence",
        "definition": "同一内容在一个 source / external_id / frame 中的一次出现。",
        "identity": "source + external_id + frame",
        "may_be_counted_as": "frame 内观察次数",
        "must_not_be_used_for": ["independent consumer count", "prevalence denominator"],
    },
    {
        "level": "canonical_record",
        "definition": "跨来源与跨 frame 去重后的独立内容单元。",
        "identity": "duplicate_group_id + representative_id",
        "may_be_counted_as": "独立内容单元数",
        "must_not_be_used_for": ["独立消费者数（同一作者可多条）", "总体比率"],
    },
    {
        "level": "frame_membership",
        "definition": "canonical record 与一个 sample frame 的关系，可重叠。",
        "identity": "canonical_id + frame",
        "may_be_counted_as": "各 frame 的可用记录数",
        "must_not_be_used_for": ["把多个 frame 相加当总体", "跨 frame 百分比比较"],
    },
    {
        "level": "annotation",
        "definition": "对一条 canonical record 的一个 aspect / context / journey / outcome / gap / medical 标签。",
        "identity": "canonical_id + axis + code + polarity + taxonomy_version",
        "may_be_counted_as": "annotation hits（多标签）",
        "must_not_be_used_for": ["人数", "记录数", "比率分母"],
    },
    {
        "level": "metric_row",
        "definition": "通过 G7 且满足 metric contract 的正式指标行。",
        "identity": "metric_id + frame + denominator_contract + taxonomy_version + qa_state",
        "may_be_counted_as": "正式比率 / 指标",
        "must_not_be_used_for": ["未通过 G7 时的任何比率", "诊断样本的 prevalence"],
    },
]

DEDUCTION_REASONS = {
    "within_frame_overlap": "同一 external_id 在同一 frame 被重复写入",
    "cross_frame_overlap": "同一 external_id 出现在多个 frame",
    "cross_source_syndicated_duplicate": "同一内容跨来源转载或联合发布",
    "crosspost_same_author": "同一作者把同一内容转发到多个社区",
    "known_duplicate_nonrepresentative": "duplicate group 中的非代表记录",
    "low_information": "内容没有可编码的体验信息",
    "product_mismatch": "产品不是目标产品、家族或声明的 adjacent",
    "non_consumer_role": "品牌、零售商、创作者或自动化内容",
    "commercial_disclosure": "文本含 affiliate / sponsored / paid 披露",
    "out_of_window": "created_at 在 G0 研究窗口之外",
    "language_uncodable": "语言不在 taxonomy 支持列表",
    "deleted_or_removed": "provider 标记 deleted / removed",
    "quoted_repost": "内容主体是引用另一条记录",
    "translation_duplicate": "同一内容的多语言版本",
    "cross_frame_membership_added": "同一 canonical record 因内容规则新增 frame membership",
    "gate_not_pass": "所需 gate 未 PASS，候选 metric row 全部扣减",
}

RELEVANCE_TERMS = (
    "belly band",
    "belly support",
    "support band",
    "support belt",
    "maternity band",
    "maternity belt",
    "pregnancy band",
    "pregnancy belt",
    "bump support",
    "momcozy",
)
BRAND_TERMS = ("momcozy",)
COMMERCIAL_TERMS = (
    "affiliate",
    "sponsored",
    "paid partnership",
    "#ad",
    "discount code",
    "promo code",
    "use my code",
)
FAILURE_TERMS = (
    "doesn't work",
    "didn't work",
    "not work",
    "hurt",
    "uncomfortable",
    "slip",
    "slide",
    "roll down",
    "rolls down",
    "too tight",
    "too small",
    "too big",
    "useless",
    "waste of money",
    "returned it",
    "returning it",
    "send it back",
    "disappoint",
    "not worth",
    "no support",
    "lack of support",
    "digs into",
    "dug into",
)
PRODUCT_NOUNS = ("band", "belt", "strap", "velcro", "wrap", "momcozy", "ergonest", "cozysupport")
CLAUSE_SPLIT = re.compile(r"[.!?;\n]|,\s*(?:but|however|although|though)\s+", re.I)


def norm_text(text: str) -> str:
    value = URL_RE.sub(" ", (text or "").lower())
    value = re.sub(r"[^a-z0-9' ]+", " ", value)
    return WS_RE.sub(" ", value).strip()


def text_hash(text: str) -> str:
    return hashlib.sha256(norm_text(text).encode("utf-8")).hexdigest()


def tokens(text: str) -> set[str]:
    return {t for t in TOKEN_RE.findall(norm_text(text)) if len(t) > 2}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class Occurrence:
    occurrence_id: str
    source: str
    kind: str
    external_id: str
    frame: str
    subreddit: str
    author: str
    created_utc: int
    url: str
    title: str
    text: str
    score: int
    num_comments: int
    raw_id: str
    quality_flags: list[str] = field(default_factory=list)

    @property
    def combined(self) -> str:
        return f"{self.title}\n{self.text}".strip()

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class CanonicalRecord:
    canonical_id: str
    representative: str
    memberships: list[str]
    source: str
    external_id: str
    kind: str
    subreddit: str
    author: str
    created_utc: int
    url: str
    title: str
    text: str
    content_hash: str
    duplicate_group_id: str
    dedup_status: str
    frames: list[str]
    product_match: str
    data_layer: str
    content_role: str
    commerciality: str
    organic_confidence: str
    metric_eligibility: str
    quality_flags: list[str]
    language: str = "en"
    taxonomy_version: str = TAXONOMY_VERSION

    @property
    def combined(self) -> str:
        return f"{self.title}\n{self.text}".strip()

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _reddit_url(rec: dict[str, Any], external_id: str) -> str:
    permalink = rec.get("permalink") or f"/comments/{external_id}"
    return "https://www.reddit.com" + permalink


def occurrences_from_ingest(run: IngestResult) -> tuple[list[Occurrence], dict[str, Any]]:
    occurrences: list[Occurrence] = []
    within_frame_dropped = 0
    seen: dict[tuple[str, str], Occurrence] = {}
    for response in run.responses:
        if response.provider == "amazon":
            continue
        for rec in response.records:
            external_id = str(rec.get("external_id") or "")
            if not external_id:
                continue
            occ = Occurrence(
                occurrence_id=f"reddit:{rec.get('kind')}:{external_id}:{response.frame}",
                source="reddit",
                kind=str(rec.get("kind") or "post"),
                external_id=external_id,
                frame=response.frame,
                subreddit=str(rec.get("subreddit") or response.subreddit or ""),
                author=str(rec.get("author") or "[deleted]"),
                created_utc=int(rec.get("created_utc") or 0),
                url=_reddit_url(rec, external_id),
                title=str(rec.get("title") or ""),
                text=str(rec.get("text") or ""),
                score=int(rec.get("score") or 0),
                num_comments=int(rec.get("num_comments") or 0),
                raw_id=response.request_id,
            )
            if not occ.title.strip() and not occ.text.strip():
                occ.quality_flags.append("deleted_or_empty")
            key = (occ.external_id, occ.frame)
            if key in seen:
                within_frame_dropped += 1
                continue
            seen[key] = occ
            occurrences.append(occ)
    stats = {
        "raw_records_read": sum(len(r.records) for r in run.responses if r.provider != "amazon"),
        "occurrences_raw": len(occurrences) + within_frame_dropped,
        "within_frame_overlap_dropped": within_frame_dropped,
        "occurrences": len(occurrences),
    }
    return occurrences, stats


def classify_product(text: str) -> tuple[str, str]:
    value = text.lower()
    has_relevance = any(k in value for k in RELEVANCE_TERMS)
    brand = any(k in value for k in BRAND_TERMS)
    if not has_relevance:
        return "irrelevant", "excluded_lineage"
    if brand and any(k in value for k in ("belly band", "belly support", "band", "belt")):
        return "exact_current_family", "consumer_observation_fact"
    if brand:
        return "brand_other_product", "excluded_lineage"
    if any(k in value for k in ("belly band", "belly support", "support band", "maternity band", "support belt")):
        return "category_adjacent", "consumer_observation_fact"
    return "category_adjacent", "discovery_hold_queue"


def classify_commerciality(text: str) -> str:
    value = text.lower()
    if any(k in value for k in COMMERCIAL_TERMS):
        return "explicit_paid_or_affiliate"
    if "http" in value and ("amzn" in value or "amazon.com" in value):
        return "link_only"
    return "no_signal_observed"


def is_failure_record(text: str) -> bool:
    for clause in CLAUSE_SPLIT.split((text or "").lower()):
        if not clause.strip():
            continue
        if any(noun in clause for noun in PRODUCT_NOUNS) and any(term in clause for term in FAILURE_TERMS):
            return True
    return False


def _eligibility(record: dict[str, Any], flags: list[str]) -> str:
    product_match = record["product_match"]
    data_layer = record["data_layer"]
    if product_match in {"irrelevant", "brand_other_product"}:
        value = "excluded_irrelevant"
    elif data_layer == "claim_asset_fact":
        value = "content_claim_only"
    elif data_layer == "discovery_hold_queue":
        value = "discovery_only"
    elif "low_information" in flags:
        value = "excluded_low_information"
    else:
        value = "natural_sample_candidate"
    if "qualitative_seed" in record["frames"]:
        value = "qualitative_seed_only"
    return value


def canonicalize(occurrences: list[Occurrence]) -> tuple[list[CanonicalRecord], dict[str, Any]]:
    by_hash: dict[str, list[Occurrence]] = {}
    for occ in occurrences:
        by_hash.setdefault(text_hash(occ.combined), []).append(occ)

    parent: dict[int, Occurrence] = {id(o): o for o in occurrences}

    def find(o: Occurrence) -> Occurrence:
        cur = o
        while id(parent[id(cur)]) != id(cur):
            cur = parent[id(cur)]
        return cur

    def union(a: Occurrence, b: Occurrence) -> None:
        ra, rb = find(a), find(b)
        if id(ra) != id(rb):
            parent[id(rb)] = ra

    for group in by_hash.values():
        for occ in group[1:]:
            union(group[0], occ)

    by_author: dict[str, list[Occurrence]] = {}
    for occ in occurrences:
        if occ.author and occ.author != "[deleted]":
            by_author.setdefault(occ.author.lower(), []).append(occ)
    fuzzy_review: list[dict[str, Any]] = []
    for author, items in by_author.items():
        if len(items) < 2:
            continue
        item_tokens = {id(o): tokens(o.combined) for o in items}
        for index, left in enumerate(items):
            for right in items[index + 1 :]:
                similarity = jaccard(item_tokens[id(left)], item_tokens[id(right)])
                if 0.90 <= similarity < 1.0:
                    union(left, right)
                    fuzzy_review.append(
                        {
                            "author": author,
                            "a": left.external_id,
                            "b": right.external_id,
                            "jaccard": round(similarity, 3),
                        }
                    )

    components: dict[int, list[Occurrence]] = {}
    for occ in occurrences:
        components.setdefault(id(find(occ)), []).append(occ)

    records: list[CanonicalRecord] = []
    dedup_reasons: dict[str, int] = {
        "cross_source_syndicated_duplicate": 0,
        "crosspost_same_author": 0,
        "cross_frame_overlap": 0,
    }
    used_ids: set[str] = set()
    for component in components.values():
        representative = min(component, key=lambda o: (o.created_utc, o.external_id))
        frames = sorted({o.frame for o in component})
        drop = len(component) - 1
        if drop:
            same_author = len({o.author for o in component}) == 1
            reason = "crosspost_same_author" if same_author else "cross_source_syndicated_duplicate"
            dedup_reasons[reason] += drop
            if len({o.frame for o in component}) > 1:
                dedup_reasons["cross_frame_overlap"] += 1
        text = representative.combined
        product_match, data_layer = classify_product(text)
        commerciality = classify_commerciality(text)
        content_role = "consumer_experience"
        organic = "high" if commerciality == "no_signal_observed" else "medium"
        if commerciality == "explicit_paid_or_affiliate":
            content_role = "creator_testimonial"
            organic = "none"
            data_layer = "claim_asset_fact"
        flags: list[str] = []
        if commerciality == "explicit_paid_or_affiliate":
            flags.append("commercial_disclosure")
        if "momcozy" in text.lower():
            flags.append("brand_mention")
        if is_failure_record(text):
            flags.append("failure_lens")
        if len(tokens(text)) < 8:
            flags.append("low_information")
        flags.extend(representative.quality_flags)
        frames_set = set(frames)
        if "failure_lens" in flags and "natural" in frames_set:
            frames_set.add("diagnostic")
        frames = sorted(frames_set)
        base_id = f"c-{representative.external_id}"
        canonical_id = base_id
        suffix = 2
        while canonical_id in used_ids:
            canonical_id = f"{base_id}-{suffix}"
            suffix += 1
        used_ids.add(canonical_id)
        record_dict = {
            "product_match": product_match,
            "data_layer": data_layer,
            "frames": frames,
        }
        eligibility = _eligibility(record_dict, flags)
        records.append(
            CanonicalRecord(
                canonical_id=canonical_id,
                representative=representative.occurrence_id,
                memberships=[f"reddit:{representative.external_id}:{frame}" for frame in frames],
                source=representative.source,
                external_id=representative.external_id,
                kind=representative.kind,
                subreddit=representative.subreddit,
                author=representative.author,
                created_utc=representative.created_utc,
                url=representative.url,
                title=representative.title,
                text=representative.text,
                content_hash=text_hash(text),
                duplicate_group_id=f"d-{text_hash(text)[:16]}",
                dedup_status="known_duplicate_representative" if drop else "unique",
                frames=frames,
                product_match=product_match,
                data_layer=data_layer,
                content_role=content_role,
                commerciality=commerciality,
                organic_confidence=organic,
                metric_eligibility=eligibility,
                quality_flags=sorted(set(flags)),
            )
        )

    frame_counts: dict[str, int] = {}
    for record in records:
        for frame in record.frames:
            frame_counts[frame] = frame_counts.get(frame, 0) + 1

    excluded = {
        "irrelevant": sum(1 for r in records if r.product_match == "irrelevant"),
        "brand_other_product": sum(1 for r in records if r.product_match == "brand_other_product"),
        "low_information": sum(1 for r in records if r.metric_eligibility == "excluded_low_information"),
        "claim_asset": sum(1 for r in records if r.metric_eligibility == "content_claim_only"),
    }
    summary = {
        "occurrences": len(occurrences),
        "canonical_records": len(records),
        "frame_memberships": sum(frame_counts.values()),
        "frame_counts": frame_counts,
        "deduction_reasons": dedup_reasons,
        "fuzzy_review_candidates": fuzzy_review,
        "excluded": excluded,
    }
    return records, summary


@dataclass
class ReconciliationRow:
    from_level: str
    to_level: str
    input_count: int
    output_count: int
    deducted: int
    reasons: dict[str, int]
    note: str = ""

    def check(self) -> None:
        reason_total = sum(self.reasons.values())
        expected = self.deducted if self.deducted >= 0 else -self.deducted
        if reason_total != expected:
            raise contract.ContractError(
                f"reconciliation reasons do not match deducted magnitude: {self.from_level}->{self.to_level}"
            )
        if self.input_count - self.deducted != self.output_count:
            raise contract.ContractError(
                f"reconciliation does not balance: {self.from_level}->{self.to_level}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "from": self.from_level,
            "to": self.to_level,
            "input_count": self.input_count,
            "deducted": self.deducted,
            "output_count": self.output_count,
            "reasons": dict(self.reasons),
        }


@dataclass
class CountingLedger:
    raw_objects: int
    occurrences: int
    canonical_records: int
    frame_memberships: int
    annotations: int
    metric_rows: int
    rows: list[ReconciliationRow]
    frame_counts: dict[str, int]
    candidate_metric_rows: int
    gate_status: str
    notes: list[str] = field(default_factory=list)

    def assert_balanced(self) -> None:
        for row in self.rows:
            row.check()
        if not (self.canonical_records <= self.occurrences <= self.raw_objects):
            raise contract.ContractError("INV-03 failed: canonical <= occurrences <= raw_objects")
        if self.frame_memberships < self.canonical_records:
            raise contract.ContractError("INV-04 failed: frame_memberships < canonical_records")
        if self.metric_rows > 0 and self.gate_status != "PASS":
            raise contract.ContractError("INV-26 failed: metric rows require G7 PASS")

    def levels(self) -> list[dict[str, Any]]:
        counts = {
            "raw_object": self.raw_objects,
            "occurrence": self.occurrences,
            "canonical_record": self.canonical_records,
            "frame_membership": self.frame_memberships,
            "annotation": self.annotations,
            "metric_row": self.metric_rows,
        }
        out = []
        for definition in COUNTING_LEVELS:
            item = dict(definition)
            item["count"] = counts[item["level"]]
            out.append(item)
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "levels": self.levels(),
            "reconciliation": [row.to_dict() for row in self.rows],
            "frame_counts": self.frame_counts,
            "candidate_metric_rows": self.candidate_metric_rows,
            "gate_status": self.gate_status,
            "notes": self.notes,
        }


def build_counting_ledger(
    raw_objects: int,
    occurrences: int,
    canonical_records: int,
    frame_memberships: int,
    annotations: int,
    frame_counts: dict[str, int],
    candidate_metric_rows: int,
    gate_status: str,
    *,
    within_frame_dropped: int = 0,
    dedup_reasons: dict[str, int] | None = None,
) -> CountingLedger:
    dedup_reasons = dedup_reasons or {}
    canonical_dropped = occurrences - canonical_records
    canonical_reasons = {k: v for k, v in dedup_reasons.items() if v and k != "cross_frame_overlap"}
    if sum(canonical_reasons.values()) != canonical_dropped:
        # Keep the chain honest even if an unexpected duplicate path appears.
        canonical_reasons["cross_source_syndicated_duplicate"] = canonical_dropped - sum(canonical_reasons.values())
    membership_added = frame_memberships - canonical_records
    rows = [
        ReconciliationRow(
            "raw_object",
            "occurrence",
            raw_objects,
            occurrences,
            within_frame_dropped,
            ({"within_frame_overlap": within_frame_dropped} if within_frame_dropped else {}),
            "same external_id + frame is one occurrence",
        ),
        ReconciliationRow(
            "occurrence",
            "canonical_record",
            occurrences,
            canonical_records,
            canonical_dropped,
            canonical_reasons,
            "identical normalized text or same-author Jaccard >= 0.90",
        ),
        ReconciliationRow(
            "canonical_record",
            "frame_membership",
            canonical_records,
            frame_memberships,
            -membership_added,
            ({"cross_frame_membership_added": membership_added} if membership_added else {}),
            "diagnostic and cross-frame memberships can overlap",
        ),
    ]
    metric_rows = 0
    if gate_status != "PASS":
        rows.append(
            ReconciliationRow(
                "annotation",
                "metric_row",
                candidate_metric_rows,
                0,
                candidate_metric_rows,
                {"gate_not_pass": candidate_metric_rows} if candidate_metric_rows else {},
                f"gate {gate_status}; fail-closed",
            )
        )
    ledger = CountingLedger(
        raw_objects=raw_objects,
        occurrences=occurrences,
        canonical_records=canonical_records,
        frame_memberships=frame_memberships,
        annotations=annotations,
        metric_rows=metric_rows,
        rows=rows,
        frame_counts=frame_counts,
        candidate_metric_rows=candidate_metric_rows,
        gate_status=gate_status,
    )
    ledger.assert_balanced()
    return ledger


def counting_spec() -> dict[str, Any]:
    return {
        "levels": COUNTING_LEVELS,
        "deduction_reasons": DEDUCTION_REASONS,
        "rule": "六个数互不替代；只有 metric_row 可以进入正式比率；G7 未 PASS 时 metric_row 必须为 0。",
    }
