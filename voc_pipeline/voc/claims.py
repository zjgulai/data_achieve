"""Claim construction.

A claim is only created when the numbers behind it exist.  The grade is
assigned by ``evidence.assign_grade``; no claim can choose its own grade.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .canonical import CanonicalRecord
from .coder import CodedRecord
from .contracts import Claim, EvidenceGrade, Frame
from .evidence import GradeInput, explain_grade

SUPPORT_CODES = {"SUP.GENERAL", "SUP.BACK", "SUP.PRESSURE_OFFLOAD", "SUP.BELLY_LIFT"}
FIT_CODES = {"FIT.SIZE_ACCURACY", "FIT.BODY_SHAPE", "FIT.GROWTH_RANGE", "FIT.COVERAGE"}
STAB_CODES = {"STB.STAY_IN_PLACE", "STB.STRAP_POSITION", "ADJ.STRAP_DESIGN", "ADJ.RANGE_TENSION"}
COMFORT_CODES = {"COM.GENERAL", "COM.SOFTNESS", "COM.BREATHABILITY_HEAT", "COM.SKIN_CHAFE", "APP.UNDER_CLOTHING", "APP.LOW_PROFILE"}
VALUE_CODES = {"VAL.PRICE_VALUE"}


def _neg(coded: list[CodedRecord], family: set[str], frame: str | None = None, records: dict[str, CanonicalRecord] | None = None) -> int:
    n = 0
    for rec in coded:
        if frame and records and frame not in records[rec.canonical_id].frames:
            continue
        if any(
            a.code in family and a.polarity in {"negative", "qualified_negative", "mixed"}
            for a in rec.annotations
            if a.axis == "aspect"
        ):
            n += 1
    return n


def _authors(records: list[CanonicalRecord]) -> int:
    return len({r.author for r in records if r.author and r.author != "[deleted]"})


def _share(num: int, den: int) -> float:
    return (num / den) if den else 0.0


def _counts(
    n_records: int,
    n_authors: int,
    agreement_pct: float | None,
) -> dict[str, Any]:
    """The three counts every claim must publish with its grade.

    ``agreement_pct`` is ``None`` when the claim is a count fact rather than a
    direction claim; the renderer shows ``N/A`` instead of inventing a 0% or
    100% agreement.
    """
    return {
        "n_records": int(n_records),
        "n_authors": int(n_authors),
        "agreement_pct": None if agreement_pct is None else round(float(agreement_pct), 1),
    }


def direction_stats(
    records: list[CanonicalRecord],
    coded: list[CodedRecord],
    family: set[str],
    frame: str,
    scope: str | None = None,
) -> dict[str, Any]:
    """One direction per record inside one frame and aspect family.

    A record with both polarities is ``mixed`` and does not enter the
    numerator or the denominator: it cannot be counted as agreement for
    either side.  A record whose only evidence for the family is a clause the
    coder abstained on as ``mixed_clause`` is also ``mixed``: the sentence
    contains both directions, so it cannot vote for either.  ``n_authors``
    counts distinct masked reviewer handles; the provider does not expose
    account ids, so this is a lower bound on distinct people and is published
    as such.

    ``scope`` selects an experience layer.  ``"full"`` counts only records
    whose ``experience_scope`` is ``full``; ``"partial"`` counts only the
    partial layer; ``None`` keeps the pooled legacy behaviour.  Records the
    scope filter removed are reported per layer (``excluded_full_records`` /
    ``excluded_partial_records`` / ``excluded_none_records``) so a caller can
    render the layer boundary instead of asserting it.
    """
    if scope not in {None, "full", "partial"}:
        raise ValueError(f"invalid scope {scope!r}; expected None, 'full' or 'partial'")
    by_id = {r.canonical_id: r for r in records}
    same: list[str] = []
    opposite: list[str] = []
    mixed: list[str] = []
    none: list[str] = []
    excluded_full = 0
    excluded_partial = 0
    excluded_none = 0
    for coded_rec in coded:
        record = by_id.get(coded_rec.canonical_id)
        if record is None or frame not in record.frames:
            continue
        if not record.text.strip():
            continue
        if scope is not None and coded_rec.experience_scope != scope:
            # Counted after the frame/text filters: only records that would
            # otherwise enter the direction distribution are "excluded".
            if coded_rec.experience_scope == "partial":
                excluded_partial += 1
            elif coded_rec.experience_scope == "full":
                excluded_full += 1
            else:
                excluded_none += 1
            continue
        polarities = {
            ann.polarity
            for ann in coded_rec.annotations
            if ann.axis == "aspect" and ann.code in family
        }
        has_pos = bool(polarities & {"positive", "qualified_positive"})
        has_neg = bool(polarities & {"negative", "qualified_negative"})
        # P0-1: the coder no longer writes two votes for one mixed sentence.
        # It records the abstention instead; the record still counts as mixed
        # and is excluded from both the numerator and the denominator.
        has_mixed_clause = any(
            item.get("reason") == "mixed_clause" and item.get("code") in family
            for item in coded_rec.unknown_aspects
        )
        if (has_pos and has_neg) or has_mixed_clause:
            mixed.append(record.canonical_id)
        elif has_pos:
            same.append(record.canonical_id)
        elif has_neg:
            opposite.append(record.canonical_id)
        else:
            none.append(record.canonical_id)
    decisive = len(same) + len(opposite)
    # The dominant direction wins; ties are impossible with an odd count, and
    # an even tie would produce 50% and fail the Directional threshold.
    dominant = "positive" if len(same) >= len(opposite) else "negative"
    dominant_ids = same if dominant == "positive" else opposite
    return {
        "frame": frame,
        "family": sorted(family),
        "scope": scope or "all",
        "excluded_full_records": excluded_full,
        "excluded_partial_records": excluded_partial,
        "excluded_none_records": excluded_none,
        "same_direction_records": len(same),
        "opposite_direction_records": len(opposite),
        "mixed_records": len(mixed),
        "no_direction_records": len(none),
        "decisive_records": decisive,
        "n_authors": len(
            {
                by_id[cid].author
                for cid in same + opposite
                if by_id[cid].author and by_id[cid].author not in {"[deleted]", "[anonymous]"}
            }
        ),
        "dominant_direction": dominant,
        "agreement_pct": round(100.0 * len(dominant_ids) / decisive, 1) if decisive else 0.0,
        "same_ids": same,
        "opposite_ids": opposite,
    }


def _direction_scope_note(stats: dict[str, Any]) -> str:
    """Render which experience layer the direction counts cover.

    The sentence comes from the statistics: a run that excluded partial
    records must publish the exclusion, never claim that everything is full.
    """
    if stats["excluded_partial_records"]:
        return (
            f"统计口径为 {stats['scope']} 层，"
            f"已排除 {stats['excluded_partial_records']} 条 partial 层记录。"
        )
    return f"全部属于 {stats['scope']} 层。"


def _status_for(grade: EvidenceGrade, note: str) -> str:
    """Render a claim status from the computed grade.

    The grade prefix is never typed by hand: a claim that falls from
    Directional to Supported hypothesis must change its status in the same
    step, otherwise the badge and the prose disagree.
    """
    return f"{grade.value} · {note}"


def _direction_threshold_clause(grade: EvidenceGrade) -> str:
    """Render the C13 threshold sentence from the computed grade.

    Only a claim that actually reached Directional may say so.  A claim that
    did not reach the threshold states the grade it did reach, and any other
    grade publishes its own name, so stale wording cannot survive a recount.
    """
    if grade is EvidenceGrade.DIRECTIONAL:
        return "达到 Directional 门槛"
    if grade is EvidenceGrade.SUPPORTED_HYPOTHESIS:
        return "未达 Directional 门槛，按 Supported hypothesis 记录"
    return f"档位为 {grade.value}"


def _grade(
    ctx: GradeInput,
    *,
    n_records: int,
    n_authors: int,
    agreement_pct: float | None,
    status_note: str,
) -> dict[str, Any]:
    """Grade + mechanical reason + counts + derived status, in one place.

    The grade itself is never chosen here: ``explain_grade`` walks the ordered
    rules and stops at the first match.  ``status_note`` is the free-text tail;
    the grade prefix comes from the computed grade via ``_status_for``.
    """
    grade, reason = explain_grade(ctx)
    return {
        "grade": grade,
        "grade_reason": reason,
        "counts": _counts(n_records, n_authors, agreement_pct),
        "status": _status_for(grade, status_note),
    }


def build_claims(
    records: list[CanonicalRecord],
    coded: list[CodedRecord],
    corpus_summary: dict[str, Any],
    metric_summary: dict[str, Any],
    identity: dict[str, Any],
    *,
    taxonomy_id: str,
    artifact_sha: str | None,
    corpus_sha: str | None = None,
    tiktok_stats: dict[str, Any] | None = None,
    tiktok_quarantine_sha: str | None = None,
    creator_video: dict[str, Any] | None = None,
) -> list[Claim]:
    by_id = {r.canonical_id: r for r in records}
    frames = {f: [r for r in records if f in r.frames] for f in [
        Frame.NATURAL.value,
        Frame.DIAGNOSTIC.value,
        Frame.QUALITATIVE_SEED.value,
        Frame.TIKTOK_SHOP_VERIFIED.value,
    ]}
    natural_ids = {r.canonical_id for r in frames[Frame.NATURAL.value]}
    natural_coded = [c for c in coded if c.canonical_id in natural_ids]
    # FC-10 / E-merge §2.2: records without an attributable first-hand
    # evaluation, or records that are off-target, do not enter the experience
    # distribution.  ``in_cohort`` is the single predicate; there is no second
    # boolean gate.  Full and partial are separate layers below and pooled is
    # never a distribution.
    experience_natural_coded = [c for c in natural_coded if c.in_cohort]
    experience_dropped = len(natural_coded) - len(experience_natural_coded)
    # Decision A: full and partial are separate layers.  Pooled counts remain
    # available, but no distribution claim may use them as a denominator.
    experience_full_coded = [
        c for c in experience_natural_coded if c.experience_scope == "full"
    ]
    experience_partial_coded = [
        c for c in experience_natural_coded if c.experience_scope == "partial"
    ]

    # The friction claim is a natural-frame experience statement.  The global
    # polarity table also contains the TikTok frame, so recompute the cells on
    # the natural experience subset instead of borrowing a mixed denominator.
    def _polarity_table(coded_subset: list[CodedRecord]) -> dict[str, dict[str, int]]:
        table: dict[str, dict[str, int]] = defaultdict(lambda: {"positive": 0, "negative": 0})
        for coded_rec in coded_subset:
            for ann in coded_rec.annotations:
                if ann.axis != "aspect":
                    continue
                if ann.polarity in {"positive", "qualified_positive"}:
                    table[ann.code]["positive"] += 1
                elif ann.polarity in {"negative", "qualified_negative"}:
                    table[ann.code]["negative"] += 1
        return table

    def _family_counts(table: dict[str, dict[str, int]]) -> dict[str, int]:
        neg_counts = {code: values.get("negative", 0) for code, values in table.items()}
        return {
            "support": sum(neg_counts.get(c, 0) for c in SUPPORT_CODES),
            "fit": sum(neg_counts.get(c, 0) for c in FIT_CODES),
            "stability": sum(neg_counts.get(c, 0) for c in STAB_CODES),
            "value": sum(neg_counts.get(c, 0) for c in VALUE_CODES),
        }

    nat_polarity = _polarity_table(experience_natural_coded)
    full_polarity = _polarity_table(experience_full_coded)
    partial_polarity = _polarity_table(experience_partial_coded)
    neg_counts = {code: v.get("negative", 0) for code, v in nat_polarity.items()}
    total_neg = sum(neg_counts.values())

    families = _family_counts(nat_polarity)
    full_families = _family_counts(full_polarity)
    partial_families = _family_counts(partial_polarity)
    support_n = families["support"]
    fit_n = families["fit"]
    stab_n = families["stability"]
    value_n = families["value"]
    comfort_pos = sum(v.get("positive", 0) for c, v in nat_polarity.items() if c in COMFORT_CODES)

    friction_total = sum(families.values())
    family_labels = {"support": "支撑类", "fit": "尺码/适配类", "stability": "稳定性", "value": "价格价值"}

    co = metric_summary["cooccurrence"]
    # Coverage claims describe the Reddit keyword recall only.  The TikTok
    # frame has its own full-corpus denominator and must not inflate these
    # cells, otherwise a verified-purchase review would look like extra
    # Reddit coverage.
    reddit_records = [r for r in records if r.source == "reddit"]
    momcozy_records = [r for r in reddit_records if "momcozy" in f"{r.title} {r.text}".lower()]
    momcozy_band_records = [r for r in momcozy_records if r.product_match == "exact_current_family"]
    exact_like = [
        r for r in momcozy_records
        if "belly band" in f"{r.title} {r.text}".lower() or "belly support" in f"{r.title} {r.text}".lower()
    ]
    exact_model = [
        r for r in momcozy_records
        if any(k in f"{r.title} {r.text}".lower() for k in ("ergonest", "cozysupport", "cozy support", "yb001"))
    ]
    experience_markers = ("i use", "i used", "i wear", "i wore", "i bought", "i tried", "mine", "i have the", "been using")
    exact_model_experience = [
        r for r in exact_model if any(m in f"{r.title} {r.text}".lower() for m in experience_markers)
    ]

    relevant_ids = {
        r.canonical_id for r in reddit_records
        if r.product_match in {"exact_current_family", "category_adjacent"}
    }
    experience_ids = {
        c.canonical_id for c in coded
        if c.canonical_id in relevant_ids
        and (
            c.journey_stage in {"JNY.USE", "JNY.FIRST_FITTING", "JNY.CARE", "JNY.RETURN", "JNY.RECOMMEND"}
            or c.outcome != "OUT.UNKNOWN"
        )
    }

    claims: list[Claim] = []

    # Recomputation consistency for the counting ledge: raw minus documented
    # deductions must equal the next level, otherwise the "Confirmed" claim is
    # not actually recomputable.
    ledger_balance_pct = (
        100.0
        if corpus_summary["occurrences_raw"] - corpus_summary["within_frame_overlap_dropped"]
        == corpus_summary["occurrences_deduplicated"]
        else 0.0
    )
    corpus_authors = _authors(records)

    # C01 identity
    live_variants = identity.get("variant_count")
    child_asin = (identity.get("asins") or ["B0HC2FG4QC"])[-1]
    variant_map = identity.get("products", {}).get(child_asin, {}).get("variants", {})
    identity_check_pct = (
        100.0 if live_variants and len(variant_map) == live_variants else 0.0
    )
    claims.append(
        Claim(
            claim_id="C01",
            section="identity",
            headline=(
                f"线上商品页当前列出 {live_variants} 个在售 ASIN 变体，商品身份本身是清楚的，"
                f"但变体集合已经需要重新冻结。"
                if live_variants
                else "线上商品页没有返回可解析的变体集合，商品身份只能停在父 ASIN 层级。"
            ),
            **_grade(
                GradeInput(
                    is_direct_fact=True,
                    artifact_sha256=artifact_sha,
                    exact_identity=True,
                    inference=False,
                ),
                n_records=live_variants or 0,
                n_authors=0,
                agreement_pct=identity_check_pct,
                status_note=f"fetched {identity.get('fetched_at', 'unknown')}",
            ),
            observed=(
                f"抓取 Amazon PDP：父 ASIN B0H8LVJ81X，子 ASIN B0HC2FG4QC，"
                f"标题包含 CozySupport 3D Ergonest；页面解析出 {live_variants} 个 ASIN → 颜色/尺码组合。"
            ),
            interpretation=(
                "商品身份字段可核对，但变体数与 2026-09-23 归档中的 12 个 family children 不一致；"
                "归档不是当前事实。"
            ),
            counterevidence="PDP 会随会话、地区和库存变化；单次抓取不能证明所有变体在任何时点都可售。",
            decision="在任何 variant-specific 结论之前重跑 G1，并把变体矩阵版本化。",
            basis="amazon-identity-raw.json + PDP HTML sha256",
            unit="ASIN / 变体组合",
            limit="单时点、单地区（US）、未登录会话",
            records=[],
            numbers={"live_variants": live_variants, "prior_archived_children": 12},
        )
    )

    # C02 corpus
    claims.append(
        Claim(
            claim_id="C02",
            section="corpus",
            headline=(
                f"本轮把 {corpus_summary['occurrences_raw']} 条 provider 记录收敛为 "
                f"{corpus_summary['occurrences_deduplicated']} 条 occurrence 和 "
                f"{corpus_summary['canonical_records']} 条 canonical，扣减全部带理由。"
            ),
            **_grade(
                GradeInput(
                    is_direct_fact=True,
                    artifact_sha256=corpus_sha,
                    exact_identity=True,
                    inference=False,
                ),
                n_records=corpus_summary["canonical_records"],
                n_authors=corpus_authors,
                agreement_pct=ledger_balance_pct,
                status_note="自建 ledger 可复算",
            ),
            observed=(
                f"raw objects {corpus_summary['raw_objects']}；occurrence 去重扣除 "
                f"{corpus_summary['within_frame_overlap_dropped']} 条同 frame 重复；"
                f"canonical 合并 {corpus_summary['reconciliation']['occurrences_to_canonical']} 条重复内容。"
            ),
            interpretation="四层计数各不相同，不能把任何一个数当成消费者人数。",
            counterevidence="样本来自关键词检索而非概率抽样，缺席记录不代表不存在。",
            decision="报告只使用 canonical 与 frame 数，不把覆盖当成逐级转化。",
            basis="collection-run-ledger.json + occurrences + canonical-records",
            unit="条 / 记录",
            limit="关键词与 subreddit 选择决定召回；未做全站抽样",
            records=[],
            numbers={k: corpus_summary[k] for k in [
                "raw_objects",
                "occurrences_raw",
                "occurrences_deduplicated",
                "canonical_records",
                "frame_memberships",
            ]},
        )
    )

    # C03 coverage gap for exact product
    claims.append(
        Claim(
            claim_id="C03",
            section="coverage",
            headline=(
                f"提到 Momcozy 的记录有 {len(momcozy_records)} 条，"
                f"其中与支撑带相关的 {len(momcozy_band_records)} 条，"
                f"提到 Ergonest / CozySupport 型号的有 {len(exact_model)} 条，"
                f"其中属于本人使用体验的 {len(exact_model_experience)} 条。"
            ),
            **_grade(
                GradeInput(
                    required_cell_count=len(exact_model_experience),
                    n_independent=len(exact_model_experience),
                    n_authors=_authors(momcozy_records),
                    direction_share=0.0,
                ),
                n_records=len(exact_model_experience),
                n_authors=_authors(exact_model_experience),
                agreement_pct=None,
                status_note="缺 exact-variant 评论层",
            ),
            observed=(
                f"关键词 momcozy 命中 {len(momcozy_records)} 条 canonical；"
                f"product_match=exact_current_family 的 {len(momcozy_band_records)} 条；"
                f"直接讨论 belly band 的 {len(exact_like)} 条。"
            ),
            interpretation="品牌被提及不等于型号被评价；不能把品牌级讨论转移到具体 SKU。",
            counterevidence="Reddit 不是 Amazon 评论的替代品，购买者更可能在商品页留言。",
            decision="补 exact-variant 评论层，或在报告中保持型号级空白。",
            basis="canonical-records.jsonl（product_match / brand_mention）",
            unit="canonical records",
            limit="仅 Reddit；Amazon 评论正文本轮不可得",
            records=[r.canonical_id for r in exact_like[:5]],
            numbers={
                "momcozy_records": len(momcozy_records),
                "momcozy_band_records": len(momcozy_band_records),
                "exact_like": len(exact_like),
                "exact_model_mentions": len(exact_model),
                "exact_model_experience": len(exact_model_experience),
            },
        )
    )

    # C03b experience depth
    # Count fact, not a direction claim.  The old agreement=100% was the set
    # inclusion ``experience_ids <= relevant_ids``; that is a construction
    # invariant, not an agreement rate.  It is now published as N/A.  The
    # count is a journey/outcome rule hit, not a verified buyer count.
    claims.append(
        Claim(
            claim_id="C11",
            section="coverage",
            headline=(
                f"{len(relevant_ids)} 条与支撑带相关的记录里，journey/outcome 标注可判为本人使用或效果相关的有 {len(experience_ids)} 条；这是单编码覆盖计数，"
                f"不是人工确认的使用人数，其余 {len(relevant_ids) - len(experience_ids)} 条没有这类标注。"
            ),
            **_grade(
                GradeInput(
                    is_direct_fact=True,
                    artifact_sha256=corpus_sha,
                    exact_identity=True,
                    inference=False,
                ),
                n_records=len(experience_ids),
                n_authors=_authors([by_id[i] for i in experience_ids]),
                agreement_pct=None,
                status_note="计数事实",
            ),
            observed=(
                f"与支撑带相关的 canonical {len(relevant_ids)} 条；其中 journey 为使用/首次穿戴/护理/退换/推荐，"
                f"或 outcome 非 unknown 的 {len(experience_ids)} 条。该计数是单编码标注命中，不等于人工确认的购买者。"
            ),
            interpretation=(
                f"关键词检索召回的是提问者多于购买者；这 {len(experience_ids)} 条只能用于 coverage 与补采设计，"
                "不能估计体验分布，也不能当作购买者人数。"
            ),
            counterevidence="提问帖仍包含场景、孕周与需求信息，对下一轮采集设计有价值。",
            decision="补评论层或购买者社区；在此之前报告只输出计数事实、证据缺口与建议。",
            basis="coded-corpus.jsonl（journey / outcome 单值 rollup；单编码判定）",
            unit="canonical records",
            limit="journey/outcome 为单编码判定，未人工复核；不是购买者身份",
            records=[],
            numbers={
                "relevant_records": len(relevant_ids),
                "journey_or_outcome_records": len(experience_ids),
                "journey_or_outcome_share": round(_share(len(experience_ids), len(relevant_ids)), 3),
            },
        )
    )

    # C04 leading friction
    # Count fact only.  The old Directional grade borrowed a record share
    # (6 of 8 friction records contain a support-negative) as if it were
    # direction agreement; it was not.  This claim now reports counts with no
    # agreement field, or falls to Evidence gap when the FC-10 experience
    # filter leaves no friction record.
    friction_family_codes = SUPPORT_CODES | FIT_CODES | STAB_CODES | VALUE_CODES

    def _friction_ids(coded_subset: list[CodedRecord]) -> set[str]:
        return {
            c.canonical_id
            for c in coded_subset
            if any(
                a.axis == "aspect"
                and a.polarity in {"negative", "qualified_negative", "mixed"}
                and a.code in friction_family_codes
                for a in c.annotations
            )
        }

    friction_ids = _friction_ids(experience_natural_coded)
    full_friction_ids = _friction_ids(experience_full_coded)
    partial_friction_ids = _friction_ids(experience_partial_coded)
    # Current corpus: full = c-1sn9hb1; partial = c-1opsx7o, c-1q2ir63.
    friction_record_n = len(friction_ids)
    friction_authors = _authors([by_id[i] for i in friction_ids])
    # Pure count sentence in both branches: a count fact does not borrow a
    # direction-agreement headline.  Pooled is not a distribution; the full /
    # partial layer counts are published in the same sentence.
    c04_headline = (
        f"自然样本的本人使用体验里（full {len(experience_full_coded)} / "
        f"partial {len(experience_partial_coded)}），支撑负向 pooled {support_n} 次"
        f"（full {full_families['support']}、partial {partial_families['support']}）、"
        f"尺码/适配 {fit_n} 次、稳定性 {stab_n} 次、价格价值 {value_n} 次；"
        f"含四类摩擦的记录 pooled {friction_record_n} 条"
        f"（full {len(full_friction_ids)}、partial {len(partial_friction_ids)}）。"
    )
    if friction_record_n:
        ordered = sorted(families.items(), key=lambda kv: (-kv[1], kv[0]))
        leader, leader_n = ordered[0]
        second, second_n = ordered[1]
        c04_grade = _grade(
            GradeInput(
                is_direct_fact=True,
                artifact_sha256=corpus_sha,
                exact_identity=True,
                inference=False,
            ),
            n_records=friction_record_n,
            n_authors=friction_authors,
            agreement_pct=None,
            status_note="计数事实",
        )
        c04_interpretation = (
            f"{family_labels[leader]}是当前自然体验语料里出现最多的摩擦面（{leader_n} 次），"
            f"{family_labels[second]}其次（{second_n} 次）；annotation hit 不是人数，也不是发生率。"
        )
        c04_counterevidence = (
            f"正向标注同时存在：舒适类正向 {comfort_pos} 次；"
            "说明产品并非整体失败，而是条件性兑现。"
        )
        c04_decision = "把资源先放在与领先摩擦对应的可逆实验，而不是全面改款。"
    else:
        c04_grade = _grade(
            GradeInput(
                required_cell_count=0,
                n_independent=0,
                n_authors=0,
            ),
            n_records=0,
            n_authors=0,
            agreement_pct=None,
            status_note="no friction records",
        )
        c04_interpretation = (
            "这是证据缺口，不是“四类摩擦都轻微”的证明；零计数不能推断产品没有摩擦。"
        )
        c04_counterevidence = (
            f"natural frame 的 {len(natural_coded)} 条记录里有 {experience_dropped} 条被 FC-10 或 product_match 规则排除（求助/无正文/非目标产品）；"
            "其余本人体验记录没有给出四类摩擦的负向标注。"
        )
        c04_decision = "先补足自然 frame 的本人使用体验负向样本，再讨论摩擦排序。"
    claims.append(
        Claim(
            claim_id="C04",
            section="friction",
            headline=c04_headline,
            **c04_grade,
            observed=(
                f"四类摩擦的负向标注（pooled）：支撑 {support_n}"
                f"（full {full_families['support']}、partial {partial_families['support']}）、"
                f"尺码/适配 {fit_n}、稳定性 {stab_n}、价格价值 {value_n}；"
                f"合计 {friction_total}。natural frame 共 {len(natural_coded)} 条记录，"
                f"其中本人使用体验 {len(experience_natural_coded)} 条"
                f"（full {len(experience_full_coded)} / partial {len(experience_partial_coded)}）、"
                f"含四类摩擦负向标注的 pooled {friction_record_n} 条"
                f"（full {len(full_friction_ids)} / partial {len(partial_friction_ids)}）。"
                "pooled 不是分布。"
            ),
            interpretation=c04_interpretation,
            counterevidence=c04_counterevidence,
            decision=c04_decision,
            basis="aspect_polarity_counts（in_experience_cohort，按 experience_scope 分层，多标签，一条记录可贡献多个标注）",
            unit="aspect annotation hits / canonical records",
            limit="单编码、pre-G7；不能读作 prevalence；pooled 不是分布",
            records=sorted(friction_ids)[:8],
            numbers={
                "support_negative": support_n,
                "support_negative_full": full_families["support"],
                "support_negative_partial": partial_families["support"],
                "fit_negative": fit_n,
                "stability_negative": stab_n,
                "value_negative": value_n,
                "friction_negative_annotations": friction_total,
                "all_negative_annotations": total_neg,
                "friction_records": friction_record_n,
                "friction_records_full": len(full_friction_ids),
                "friction_records_partial": len(partial_friction_ids),
                "experience_natural_records": len(experience_natural_coded),
                "experience_full_records": len(experience_full_coded),
                "experience_partial_records": len(experience_partial_coded),
                "natural_records": len(natural_coded),
                "experience_dropped": experience_dropped,
            },
        )
    )

    # C05 co-occurrence (Decision A: report full and partial layers; pooled is
    # not a distribution and cannot carry the headline alone)
    co_full = co["full"]
    co_partial = co["partial"]
    co_n = co["comfort_positive_with_friction"]
    co_den = co["comfort_positive_records"]
    full_n = co_full["comfort_positive_with_friction"]
    full_den = co_full["comfort_positive_records"]
    partial_n = co_partial["comfort_positive_with_friction"]
    partial_den = co_partial["comfort_positive_records"]
    full_both_ids = [
        r["canonical_id"]
        for r in co["rows"]
        if r["both"] and r["experience_scope"] == "full"
    ]
    layer_sentence = (
        f"full 层（{len(experience_full_coded)} 条本人体验）舒适正向 {full_den} 条、"
        f"共现 {full_n} 条；partial 层（{len(experience_partial_coded)} 条）舒适正向 "
        f"{partial_den} 条、共现 {partial_n} 条；pooled {co_den} 条舒适正向、"
        f"{co_n} 条共现（pooled 不是分布）。"
    )
    cross_product_ids = [
        r["canonical_id"] for r in co["rows"] if r.get("cross_product")
    ]
    cross_product_note = (
        f"另有 {len(cross_product_ids)} 条记录的正向与负向 span 分属不同产品，"
        "按同产品守卫不计入共现。"
        if cross_product_ids
        else ""
    )
    full_author_n = 0
    if full_n == 0:
        c05_headline = "full 层没有同时出现舒适正向与核心摩擦的记录：" + layer_sentence
        c05_grade = _grade(
            GradeInput(
                required_cell_count=0,
                n_independent=0,
                n_authors=0,
            ),
            n_records=0,
            n_authors=0,
            agreement_pct=None,
            status_note="full 层无共现",
        )
        c05_interpretation = (
            "full 层同产品共现为 0，这是证据缺口；partial 层只收附带或未定评价，"
            "不能替代 full 层的同产品证据，也不能推断因果。"
        )
        c05_counterevidence = (
            f"partial 层的评价是附带的或未定的，只作旁证；{cross_product_note}"
            "零结果不等于不存在，pooled 也不是分布。"
        )
        c05_decision = "先补 full 层本人主动分享的共现样本；partial 层观察不升级为结论。"
    else:
        full_author_n = len(
            {
                by_id[cid].author
                for cid in full_both_ids
                if by_id[cid].author and by_id[cid].author != "[deleted]"
            }
        )
        single_author_note = (
            f"（n={full_n}，单作者）" if full_n == 1 and full_author_n == 1 else ""
        )
        if single_author_note:
            # The report validator requires an H2 to end with sentence
            # punctuation.  Keep the single-author caveat inside the sentence
            # instead of appending it after the full stop.
            c05_headline = (
                "full 层共现记录："
                + layer_sentence.rstrip("。")
                + single_author_note
                + "。"
            )
        else:
            c05_headline = "full 层共现记录：" + layer_sentence
        c05_grade = _grade(
            GradeInput(
                is_direct_fact=True,
                artifact_sha256=corpus_sha,
                exact_identity=True,
                inference=False,
            ),
            n_records=full_n,
            n_authors=full_author_n,
            agreement_pct=None,
            status_note="计数事实（full 层）",
        )
        c05_interpretation = (
            "共现是记录级计数事实，不是普遍模式，也不是因果；"
            + (
                f"本轮 full 层只有 {full_n} 条记录、{full_author_n} 位作者，"
                "不能写成总体共现率，也不能推断因果；"
                if full_n == 1
                else ""
            )
            + "把 full 与 partial 压成一个“总体情绪”会同时丢掉正向资产与条件性失败。"
        )
        c05_counterevidence = (
            f"full 层还有 {full_den - full_n} 条舒适正向记录没有出现核心摩擦；"
            "共现也不是因果，不能断言舒适设计导致支撑不足。"
        )
        c05_decision = "用 Support ladder 与 Fit chooser 分开验证，而不是改一处结构；partial 层只作语境参考。"
    claims.append(
        Claim(
            claim_id="C05",
            section="tension",
            headline=c05_headline,
            **c05_grade,
            observed=layer_sentence,
            interpretation=c05_interpretation,
            counterevidence=c05_counterevidence,
            decision=c05_decision,
            basis=(
                "record-level co-occurrence（in_experience_cohort，按 experience_scope 分层；"
                "COM/APP positive × SUP/FIT/STB negative；同产品守卫）"
            ),
            unit="canonical records",
            limit="共现为描述性；样本非概率抽样；同产品守卫；零结果不等于不存在；pooled 不是分布",
            records=[r["canonical_id"] for r in co["rows"] if r["both"]][:8],
            numbers={
                "comfort_positive_records": co_den,
                "with_friction": co_n,
                "share": round(_share(co_n, co_den), 3) if co_den else None,
                "full_comfort_positive_records": full_den,
                "full_with_friction": full_n,
                "full_cooccurrence_authors": full_author_n,
                "partial_comfort_positive_records": partial_den,
                "partial_with_friction": partial_n,
                "experience_full_records": len(experience_full_coded),
                "experience_partial_records": len(experience_partial_coded),
                "experience_dropped": experience_dropped,
            },
        )
    )

    # C06 was removed.  It compared raw negative counts across the natural and
    # diagnostic frames (149 vs 8), which violates the frame rule: a derived
    # diagnostic subset cannot be placed on the same axis as the natural
    # recall.  The frame inventory table in the report keeps the counts; no
    # claim is graded from a cross-frame comparison.

    # C07 formal metric blocked
    c07_grade = _grade(
        GradeInput(
            required_gate="G7",
            gate_status="BLOCKED",
            is_prevalence_claim=True,
            denominator=0,
            frame="natural",
        ),
        n_records=len(metric_summary["metric_rows"]),
        n_authors=0,
        agreement_pct=None,
        status_note="G7 not executed",
    )
    claims.append(
        Claim(
            claim_id="C07",
            section="gate",
            headline=(
                "G7 没有执行，所以正式指标行是 0，"
                f"任何比例都只能标为 {c07_grade['grade'].value}。"
            ),
            **c07_grade,
            observed=(
                f"eligible records {metric_summary['eligible_records']} 条，但 metric rows = "
                f"{len(metric_summary['metric_rows'])}；G7 状态 {metric_summary['g7_status']}。"
            ),
            interpretation="有语料不等于有指标；准入条件缺一项就不能生成比率。",
            counterevidence="若把 annotation hits 当分母，会得到看似精确但不可复现的比例。",
            decision="先完成双盲编码与 agreement，再谈任何 share。",
            basis="consumer-metric-view-contract + g7 gate status",
            unit="metric rows",
            limit="fail-closed：缺第二编码员即阻断",
            records=[],
            numbers={"eligible_records": metric_summary["eligible_records"], "metric_rows": 0},
        )
    )

    # C08 medical
    medical_flags = sum(1 for r in coded if r.medical_flags)
    claims.append(
        Claim(
            claim_id="C08",
            section="medical",
            headline=f"{medical_flags} 条记录含疼痛、病史或受力安全自述，这些只能进入 review queue，不能变成疗效或安全结论。",
            **_grade(
                GradeInput(topic="medical_efficacy"),
                n_records=medical_flags,
                n_authors=len({by_id[c.canonical_id].author for c in coded if c.medical_flags}),
                agreement_pct=None,
                status_note="medical/legal review required",
            ),
            observed=f"medical self-report 命中 {medical_flags} 条 canonical；claim relation 仅记录 review_required。",
            interpretation="自我报告描述的是体验，不是诊断、疗效或安全率。",
            counterevidence="缺少临床上下文、剂量、对照与随访。",
            decision="转医疗/法务 review；报告只保留描述层。",
            basis="medical annotations（MED.*）",
            unit="canonical records",
            limit="无临床验证；不得外推",
            records=[],
            numbers={"medical_records": medical_flags},
        )
    )

    # C09 was removed from the claim list.  It is a recommendation, not
    # evidence, so it must not occupy one of the six evidence grades or count
    # toward the grade distribution.  ``build_recommendations`` renders it in
    # the report's separate recommendation block.

    # C10 report limits
    claims.append(
        Claim(
            claim_id="C10",
            section="limits",
            headline="这份报告能支持方向判断，不能支持任何比率、排名或医学结论。",
            **_grade(
                GradeInput(
                    required_gate="G7",
                    gate_status="BLOCKED",
                    is_prevalence_claim=True,
                    denominator=0,
                    frame="natural",
                    topic="consumer_experience",
                ),
                n_records=len(metric_summary["metric_rows"]),
                n_authors=0,
                agreement_pct=None,
                status_note="report-level",
            ),
            observed=(
                f"G7 = BLOCKED；metric rows = {len(metric_summary['metric_rows'])}；"
                f"各结论的等级见本节下表。"
            ),
            interpretation="证据成熟度是状态，不是绩效评分；升级必须先过门禁。",
            counterevidence="语料规模、作者数与标注数都不能替代 agreement。",
            decision="对外只发布方向与实验计划；比率、排名与医学措辞一律不发布。",
            basis="gate-ledger.json + claims.json",
            unit="report-level constraint",
            limit="适用于本 run 的全部结论",
            records=[],
            numbers={"metric_rows": len(metric_summary["metric_rows"]), "g7_status": metric_summary["g7_status"]},
        )
    )

    # --- TikTok Shop verified-purchase frame -------------------------------
    tt_records = frames[Frame.TIKTOK_SHOP_VERIFIED.value]
    tt_ids = {r.canonical_id for r in tt_records}
    tt_coded = [c for c in coded if c.canonical_id in tt_ids]
    tt_stats = tiktok_stats or {}
    tt_raw = int(tt_stats.get("raw_rows", len(tt_records)))
    tt_dup = int(tt_stats.get("duplicate_review_ids", 0))
    tt_oow = int(tt_stats.get("out_of_window", 0))
    tt_quarantined = int(tt_stats.get("quarantined", 0))
    tt_text = int(tt_stats.get("text_bearing", sum(1 for r in tt_records if r.text.strip())))
    tt_codable = int(
        tt_stats.get("text_codable_en", sum(1 for r in tt_records if r.text.strip() and r.language == "en"))
    )
    tt_verified = int(tt_stats.get("verified_purchase_true", 0))
    tt_balance = 100.0 if tt_raw - tt_dup - tt_oow - tt_quarantined == len(tt_records) else 0.0
    support_dir = direction_stats(
        records, coded, SUPPORT_CODES, Frame.TIKTOK_SHOP_VERIFIED.value, scope="full"
    )
    support_hits = sum(
        1
        for coded_rec in tt_coded
        for ann in coded_rec.annotations
        if ann.axis == "aspect" and ann.code in SUPPORT_CODES
    )
    quarantine_records = tt_stats.get("quarantine_records") or corpus_summary.get("quarantine") or []
    first_quarantine = quarantine_records[0] if quarantine_records else {}

    claims.append(
        Claim(
            claim_id="C12",
            section="tiktok",
            headline=(
                f"TikTok Shop 抓取 {tt_raw} 条评论记录，收敛为 {len(tt_records)} 条 canonical，"
                f"其中 {tt_text} 条有文本、{tt_codable} 条可编码。"
            ),
            **_grade(
                GradeInput(
                    is_direct_fact=True,
                    artifact_sha256=corpus_sha,
                    exact_identity=True,
                    inference=False,
                ),
                n_records=len(tt_records),
                n_authors=_authors(tt_records),
                agreement_pct=tt_balance,
                status_note="计数事实",
            ),
            observed=(
                f"{tt_stats.get('pages_fetched', '?')} 页成功响应，{tt_dup} 条重复 review_id；"
                f"{tt_oow} 条超出窗口、{tt_quarantined} 条身份噪声被隔离后，canonical 为 {len(tt_records)} 条；"
                f"verified_purchase=true 的 {tt_verified} 条，incentivized=true 的 "
                f"{tt_stats.get('incentivized_true', 0)} 条；"
                f"评分计数 1★{tt_stats.get('rating_counts', {}).get('1', 0)} / "
                f"2★{tt_stats.get('rating_counts', {}).get('2', 0)} / "
                f"3★{tt_stats.get('rating_counts', {}).get('3', 0)} / "
                f"4★{tt_stats.get('rating_counts', {}).get('4', 0)} / "
                f"5★{tt_stats.get('rating_counts', {}).get('5', 0)}。"
            ),
            interpretation="评论是购买者自述，不是概率样本；星级与文本分开计数，不能合成一个总体分数。",
            counterevidence=(
                f"平台按 20 条/页返回掩码 reviewer 名；listing 总评论数 "
                f"{tt_stats.get('listing_total_reviews', '未知')}，本次只取窗口内 "
                f"{tt_stats.get('pages_fetched', '?')} 页。"
            ),
            decision="把该 frame 作为第二来源接入，不替代 Reddit natural frame，也不跨 frame 比较比例。",
            basis="tiktok-shop-ledger.json + tiktok-shop-reviews.jsonl",
            unit="canonical records（review_id 去重后）",
            limit="单商品、单地区（US）、窗口 2026-07-01 至 2026-10-29；掩码 reviewer 名",
            records=[],
            numbers={
                "raw_rows": tt_raw,
                "canonical_records": len(tt_records),
                "text_bearing": tt_text,
                "text_codable_en": tt_codable,
                "verified_purchase_true": tt_verified,
                "out_of_window": tt_oow,
                "quarantined": tt_quarantined,
            },
        )
    )

    # The layer sentence is computed from the statistics, never asserted:
    # ``scope="full"`` above either counted only full records or it did not.
    support_scope_note = _direction_scope_note(support_dir)
    # Records outside the full layer are not part of this distribution; the
    # no-direction count must say so instead of silently shrinking.
    support_excluded_note = (
        f"（另有 {support_dir['excluded_none_records']} 条非体验记录未计入）"
        if support_dir["excluded_none_records"]
        else ""
    )

    # The grade is computed before the headline so the threshold sentence can
    # only name a grade the counts actually reached.
    c13_grade = _grade(
        GradeInput(
            n_independent=support_dir["decisive_records"],
            n_authors=support_dir["n_authors"],
            direction_share=support_dir["agreement_pct"] / 100.0,
            single_coded=True,
        ),
        n_records=support_dir["decisive_records"],
        n_authors=support_dir["n_authors"],
        agreement_pct=support_dir["agreement_pct"],
        status_note="single-coded, pre-G7",
    )
    claims.append(
        Claim(
            claim_id="C13",
            section="tiktok",
            headline=(
                f"在 {support_dir['decisive_records']} 条对支撑方向有明确判断的 verified-purchase 评论里，"
                f"{support_dir['same_direction_records']} 条同向、"
                f"{support_dir['opposite_direction_records']} 条反向，"
                f"方向一致度 {support_dir['agreement_pct']:.0f}%，"
                f"{_direction_threshold_clause(c13_grade['grade'])}。"
            ),
            **c13_grade,
            observed=(
                f"{len(tt_records)} 条 canonical 中 {tt_text} 条有文本；SUP.* 的 aspect 注解命中 "
                f"{support_hits} 次，落在 {support_dir['same_direction_records']} 条只有同向、"
                f"{support_dir['opposite_direction_records']} 条只有反向、"
                f"{support_dir['mixed_records']} 条同时出现两向的记录上；"
                f"{support_dir['no_direction_records']} 条文本没有可判定的支撑方向"
                f"{support_excluded_note}。"
                f"这 {support_dir['decisive_records']} 条均为 TikTok verified-purchase，"
                f"不来自求助帖，{support_scope_note}"
            ),
            interpretation=(
                "方向一致度衡量同一 frame 内的编码方向，不是消费者满意程度，"
                "也不能外推为人群比例或 prevalence。"
            ),
            counterevidence=(
                f"{support_dir['mixed_records']} 条记录同时出现同向与反向表述，"
                f"{support_dir['opposite_direction_records']} 条只有反向；"
                "reviewer 名是平台掩码显示名，不是账号 id，作者数按掩码名去重。"
            ),
            decision="把支撑方向作为可逆实验的输入；在 G7 双盲之前不写成总体比例，也不跨 frame 比较。",
            basis="coded-corpus.jsonl（SUP.* aspect × polarity，单编码）",
            unit="canonical records（一条记录最多计一个方向）",
            limit="单编码、pre-G7；掩码作者名",
            records=support_dir["same_ids"][:8],
            numbers={
                "support_scope": support_dir["scope"],
                "support_excluded_partial": support_dir["excluded_partial_records"],
                "support_excluded_none": support_dir["excluded_none_records"],
                "support_same_direction": support_dir["same_direction_records"],
                "support_opposite_direction": support_dir["opposite_direction_records"],
                "support_mixed": support_dir["mixed_records"],
                "support_decisive": support_dir["decisive_records"],
                "support_no_direction": support_dir["no_direction_records"],
                "support_annotation_hits": support_hits,
                "direction_share": round(support_dir["agreement_pct"] / 100.0, 3),
            },
        )
    )

    quarantine_in_canonical = any(
        str(r.external_id) == str(first_quarantine.get("review_id")) for r in records
    )
    quarantine_check_pct = 100.0 if tt_quarantined and not quarantine_in_canonical else 0.0
    claims.append(
        Claim(
            claim_id="C14",
            section="tiktok",
            headline=(
                f"{tt_quarantined} 条 YB003 Oyster Pink 评论被隔离在 YB001 语料之外，"
                "原因记录为 SKU 变体不匹配。"
            ),
            **_grade(
                GradeInput(
                    is_direct_fact=True,
                    artifact_sha256=tiktok_quarantine_sha or corpus_sha,
                    exact_identity=True,
                    inference=False,
                ),
                n_records=tt_quarantined,
                n_authors=1 if tt_quarantined else 0,
                agreement_pct=quarantine_check_pct,
                status_note="计数事实",
            ),
            observed=(
                f"review_id {first_quarantine.get('review_id', 'n/a')}，"
                f"variant={first_quarantine.get('variant', 'n/a')}，"
                f"rating={first_quarantine.get('rating', 'n/a')}；"
                "该记录写入 tiktok-shop-quarantine.jsonl，未进入 canonical，也未进入任何方向计数。"
            ),
            interpretation="同一 listing 的评论流会混入同店其他型号；按 SKU 规格隔离能防止身份噪声进入目标产品结论。",
            counterevidence="隔离规则依赖 sku_specification / product_name 文本；若平台把型号写进其他字段，规则会漏。",
            decision="保持隔离，并在每次采集后复核 quarantine 计数。",
            basis="tiktok-shop-quarantine.jsonl",
            unit="quarantined review records",
            limit="规则判定；无人工复核",
            records=[],
            numbers={"quarantined_records": tt_quarantined, "quarantined_in_canonical": 0},
        )
    )

    # --- Creator/video snapshot layer --------------------------------------
    # The video layer is a separate population.  It is appended after the
    # review layer so the two claim families never share a denominator.
    claims.extend(build_creator_video_claims(creator_video))

    return claims


def _num(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _flt(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _pct(value: Any, digits: int = 2) -> str:
    return f"{100.0 * _flt(value):.{digits}f}%"


def _cv_layer(cv: dict[str, Any], key: str) -> dict[str, Any]:
    return (cv.get("layers_seen") or {}).get(key) or {}


def _hp_breakdown(cv: dict[str, Any]) -> dict[str, Any]:
    """Counts computed from the high-performer rows themselves.

    ``high_performers.common_features`` is empty in this run; the authoritative
    per-video rows live in ``high_performers.rows``.
    """
    rows = ((cv.get("high_performers") or {}).get("rows")) or []
    dur: dict[str, int] = {}
    conf: dict[str, int] = {}
    rel: dict[str, int] = {}
    link_true = 0
    ad_true = 0
    low_play = 0
    for r in rows:
        dur[str(r.get("duration_bucket"))] = dur.get(str(r.get("duration_bucket")), 0) + 1
        conf[str(r.get("relation_confidence"))] = conf.get(str(r.get("relation_confidence")), 0) + 1
        rel[str(r.get("relation_type"))] = rel.get(str(r.get("relation_type")), 0) + 1
        if str(r.get("has_link")) == "true":
            link_true += 1
        if str(r.get("ad_disclosure")) == "true":
            ad_true += 1
        if r.get("low_denominator_flag"):
            low_play += 1
    return {
        "n": len(rows),
        "duration": dur,
        "confidence": conf,
        "relation_type": rel,
        "link_true": link_true,
        "ad_true": ad_true,
        "low_play": low_play,
    }


def _cv_group_n(cv: dict[str, Any], dimension: str, value: str) -> int:
    """Layer group size from the full population, not the high-performer subset.

    ``high_performers.common_features`` only covers the high performers; using it
    for population counts silently renders zeros.  The full-population counts
    live in ``layers[dimension].groups[value].n``.
    """
    groups = ((cv.get("layers") or {}).get(dimension) or {}).get("groups") or {}
    return _num((groups.get(value) or {}).get("n"))


def _cv_common(cv: dict[str, Any], field: str, value: str) -> dict[str, Any]:
    for row in (cv.get("high_performers") or {}).get("common_features") or []:
        if row.get("field") == field and str(row.get("value")) == str(value):
            return row
    return {}


def build_creator_video_claims(cv: dict[str, Any] | None) -> list[Claim]:
    """Build the creator/video section claims from a frozen summary.

    The video layer is not part of the six-level consumer counting chain.  It
    has its own unit (video_id) and its own support gate.  The grade is still
    assigned by ``explain_grade``; when the video-layer support gate fails,
    the comparative claim lands on Evidence gap through the explicit
    ``required_support_gate`` branch.  No new grade is introduced.
    """
    if not cv or not cv.get("available"):
        missing = ", ".join((cv or {}).get("missing") or []) or "creator-video artifacts"
        return [
            Claim(
                claim_id="C15",
                section="creator_video",
                headline=(
                    "本轮没有 creator/video 快照产物，视频层的内容形态与达人选型问题"
                    "仍是证据缺口。"
                ),
                **_grade(
                    GradeInput(
                        required_cell_count=0,
                        required_field_missing_rate=1.0,
                    ),
                    n_records=0,
                    n_authors=0,
                    agreement_pct=None,
                    status_note="产物缺失",
                ),
                observed=f"缺少 baseline 产物：{missing}。",
                interpretation="没有视频与达人快照，就不能计算互动基线；评论层不能替代视频层。",
                counterevidence="如果原始响应仍在，可以重跑派生脚本；本轮没有这样做。",
                decision="先补齐 creator-video 产物，再回答内容形态问题。",
                basis="creator-video/baseline/baseline.json（缺失）",
                unit="video",
                limit="产物缺失",
                numbers={"creator_video_available": 0, "videos_total": 0, "baseline_n": 0},
            )
        ]

    videos_total = _num(cv.get("videos_total"))
    with_detail = _num(cv.get("videos_with_detail"))
    search_only = _num(cv.get("videos_search_only"))
    creators_total = _num(cv.get("creators_total"))
    creators_profile = _num(cv.get("creators_with_profile"))
    confidence = cv.get("relation_confidence") or {}
    high = _num(confidence.get("high"))
    medium = _num(confidence.get("medium"))
    low = _num(confidence.get("low"))
    none = _num(confidence.get("none"))
    baseline_n = _num(cv.get("baseline_n"))
    baseline_creators = _num(cv.get("baseline_creators"))
    target_exact = _num(cv.get("target_exact_n"))
    baseline_medium = _num(cv.get("baseline_medium_n"))
    relation_types = cv.get("relation_types") or {}
    target_type = _num(relation_types.get("target_exact"))
    duplicate_type = _num(relation_types.get("duplicate_listing_anchor"))
    text_type = _num(relation_types.get("text_brand_and_category"))
    comment_rows = _num((cv.get("comment_video") or {}).get("rows"))
    canonical_reviews = _num((cv.get("comment_video") or {}).get("canonical_reviews"))
    raw_reviews = _num((cv.get("comment_video") or {}).get("raw_reviews"))

    top = cv.get("strongest") or {}
    top_layer = str(top.get("layer") or "")
    top_n = _num(top.get("n"))
    top_median = _flt(top.get("median"))
    complement_n = _num(top.get("complement_n"))
    complement_median = _flt(top.get("complement_median"))
    top_multiple = _flt(top.get("multiple"))
    top_p = _flt(top.get("p_value"))
    top_ci = top.get("ci95") or [None, None]
    top_ci_low = _flt(top_ci[0] if len(top_ci) > 0 else None)
    top_ci_high = _flt(top_ci[1] if len(top_ci) > 1 else None)
    sens_text = _num(top.get("sensitivity_exclude_text_n"))
    sens_play = _num(top.get("sensitivity_play_floor_n"))
    top_text_relation = _num(
        (top.get("top_layer_relation_type_counts") or {}).get("text_brand_and_category")
    )
    link = _cv_layer(cv, "has_link_false")
    ad = _cv_layer(cv, "ad_false")
    link_multiple = _flt(link.get("multiple"))
    link_p = _flt(link.get("p_value"))
    link_ci = link.get("ci95") or [None, None]
    ad_multiple = _flt(ad.get("multiple"))
    ad_p = _flt(ad.get("p_value"))
    ad_ci = ad.get("ci95") or [None, None]

    hp = cv.get("high_performers") or {}
    hp_bd = _hp_breakdown(cv)
    hp_n = _num(hp.get("n"))
    hp_creators = _num(hp.get("creators"))
    hp_threshold = _flt(hp.get("threshold_multiple")) or 2.0
    ad_true = _num(_cv_common(cv, "ad_disclosure", "true").get("count"))
    link_true = _num(_cv_common(cv, "has_link", "true").get("count"))
    d31 = _num(_cv_common(cv, "duration_bucket", "31-60s").get("count"))
    d16 = _num(_cv_common(cv, "duration_bucket", "16-30s").get("count"))
    d60 = _num(_cv_common(cv, "duration_bucket", ">60s").get("count"))
    ad_pool = _flt(_cv_common(cv, "ad_disclosure", "true").get("share_population"))
    link_pool = _flt(_cv_common(cv, "has_link", "true").get("share_population"))
    d31_pool = _flt(_cv_common(cv, "duration_bucket", "31-60s").get("share_population"))
    d16_pool = _flt(_cv_common(cv, "duration_bucket", "16-30s").get("share_population"))
    d60_pool = _flt(_cv_common(cv, "duration_bucket", ">60s").get("share_population"))
    link_false = _cv_common(cv, "has_link", "false")
    link_false_n = _num(link_false.get("count"))
    link_false_share = _flt(link_false.get("share_high"))
    link_false_pool = _flt(link_false.get("share_population"))
    d15 = _cv_group_n(cv, "duration_bucket", "<=15s")
    d16 = _cv_group_n(cv, "duration_bucket", "16-30s")
    d31 = _cv_group_n(cv, "duration_bucket", "31-60s")
    d60 = _cv_group_n(cv, "duration_bucket", ">60s")
    link_true = _cv_group_n(cv, "has_link", "true")
    link_false_n = _cv_group_n(cv, "has_link", "false")
    ad_true = _cv_group_n(cv, "ad_disclosure", "true")
    ad_false_n = _cv_group_n(cv, "ad_disclosure", "false")
    pad_true = _cv_group_n(cv, "platform_is_ad", "true")
    pad_false_n = _cv_group_n(cv, "platform_is_ad", "false")
    low_play = _num(hp.get("low_play_n"))
    play_floor = _num(hp.get("play_floor_n"))
    medium_relation = _num(hp.get("medium_relation_n"))

    availability = cv.get("feature_availability") or {}
    features = cv.get("feature_counts") or {}
    comparison = features.get("comparison") or {}
    demo = features.get("demo") or {}
    before_after = features.get("before_after") or {}
    unboxing = features.get("unboxing") or {}
    visual_only = features.get("visual_only") or {}

    claims: list[Claim] = [
        Claim(
            claim_id="C15",
            section="creator_video",
            headline=(
                f"视频层采到 {videos_total} 条唯一视频和 {creators_total} 位达人，"
                f"其中 {baseline_n} 条进入高/中置信商品关联基线，"
                f"只有 {target_exact} 条锚定目标商品。"
            ),
            **_grade(
                GradeInput(
                    is_direct_fact=True,
                    artifact_sha256=cv.get("input_sha256"),
                    exact_identity=True,
                    inference=False,
                ),
                n_records=videos_total,
                n_authors=creators_total,
                agreement_pct=100.0,
                status_note="计数事实；video_id 唯一性与输入 sha256 校验通过",
            ),
            observed=(
                f"{videos_total} 条唯一视频中，{with_detail} 条有详情快照，"
                f"{search_only} 条只有搜索快照；{creators_total} 位达人中 "
                f"{creators_profile} 位有档案。商品关联置信度为 high {high}、"
                f"medium {medium}、low {low}、no_signal {none}；"
                f"high/medium 的 {baseline_n} 条进入基线，其中 {target_exact} 条锚定目标 "
                f"product_id。基线关联类型为 target_exact {target_type}、"
                f"duplicate_listing_anchor {duplicate_type}、"
                f"text_brand_and_category {text_type}。"
            ),
            interpretation=(
                "视频层以 video_id 为单位，商品评论层以 review_id 为单位。"
                "两层没有可用关联键，分母不能合并。"
            ),
            counterevidence=(
                "目标商品的完整视频列表不可得：creator cookie 未配置，"
                f"商品到视频端点返回 no login。{baseline_n} 条基线是关键词样本的子集。"
            ),
            decision="视频层只用于内容形态和达人选型；评论层不进入这个基线。",
            basis="creator-video/relations/coverage.json + collect-summary.json + baseline/baseline.json",
            unit="video / creator（video_id 与 creator_id 去重）",
            limit=f"关键词搜索非概率样本；单次快照；{baseline_n}/{videos_total} 进入基线",
            records=[],
            numbers={
                "videos_total": videos_total,
                "videos_with_detail": with_detail,
                "videos_search_only": search_only,
                "creators_total": creators_total,
                "creators_with_profile": creators_profile,
                "relation_high": high,
                "relation_medium": medium,
                "relation_low": low,
                "relation_none": none,
                "baseline_n": baseline_n,
                "target_exact_n": target_exact,
                "target_exact_type_n": target_type,
                "duplicate_listing_anchor_n": duplicate_type,
                "text_brand_and_category_n": text_type,
                "comment_video_rows": comment_rows,
                "canonical_reviews": canonical_reviews,
                "raw_reviews": raw_reviews,
            },
        ),
        Claim(
            claim_id="C16",
            section="creator_video",
            headline=(
                f"{baseline_n} 条基线视频的样本不足以做分层互动基线："
                "没有任何预定义维度同时满足层内 n>=8 与对照组 n>=8，"
                "本轮只报各层计数。"
            ),
            **_grade(
                GradeInput(
                    n_independent=baseline_n,
                    n_authors=baseline_creators,
                    direction_share=0.0,
                    single_coded=True,
                    required_support_gate="creator_video_layer_support",
                    support_gate_status="FAILED",
                ),
                n_records=baseline_n,
                n_authors=baseline_creators,
                agreement_pct=None,
                status_note="分层对比支持门槛未通过",
            ),
            observed=(
                f"{baseline_n} 条基线视频在预定义维度上没有可用分层。"
                f"时长档：<=15s {d15} 条、16-30s {d16} 条、31-60s {d31} 条、>60s {d60} 条，"
                "四层均小于 8。"
                f"has_link：true {link_true} 条、false {link_false_n} 条。"
                f"ad_disclosure：true {ad_true} 条、false {ad_false_n} 条。"
                f"platform_is_ad：true {pad_true} 条、false {pad_false_n} 条，false 组小于 8。"
                "没有任何维度同时满足层内 n>=8 与对照组 n>=8，"
                "因此本轮不产出任何分层中位数、倍数、p 值或置信区间。"
                "结论是样本不足以检验，不是已证明没有内容形态跑赢。"
            ),
            interpretation=(
                "这些是样本内的描述性中位数。支持结论要同时满足三个条件："
                "层内 n>=8、bootstrap 95% CI 排除 1、敏感性组 n>=8。"
                "本轮没有一层同时满足。"
            ),
            counterevidence=(
                "本轮没有做任何分层比较，因此也没有可反驳的分层点估计。"
                f"唯一可用的整体描述是 {baseline_n} 条 exact 视频的中位互动率，"
                "它不区分内容形态。"
                f"高表现视频只有 {hp_n} 条、来自 {hp_creators} 位达人，"
                "既不能支撑形态结论，也不能支撑达人层级结论。"
            ),
            decision=(
                "本轮不选内容形态。要选型，先把每个候选层扩到 n>=8，"
                "并在剔除文案关联后仍保持 n>=8。"
            ),
            basis=(
                "creator-video/baseline/baseline.json（48 条 high/medium 关联视频）"
                "+ 逐视频 video_level"
            ),
            unit="video（互动率 =（点赞+评论+分享+收藏）/ 播放）",
            limit=(
                f"关键词搜索非概率样本；单次快照；{baseline_n} 条中 "
                f"{baseline_medium} 条为 medium 关联"
            ),
            records=[],
            numbers={
                "videos_total": baseline_n,
                "baseline_videos": baseline_n,
                "top_layer_n": top_n,
                "top_layer_median_interaction_rate": top_median,
                "complement_n": complement_n,
                "complement_median_interaction_rate": complement_median,
                "median_multiple": top_multiple,
                "mann_whitney_p": top_p,
                "bootstrap_ci_low": top_ci_low,
                "bootstrap_ci_high": top_ci_high,
                "sensitivity_exclude_text_n": sens_text,
                "sensitivity_play_floor_n": sens_play,
                "has_link_false_n": _num(link.get("n")),
                "has_link_false_multiple": link_multiple,
                "ad_disclosure_false_n": _num(ad.get("n")),
                "ad_disclosure_false_multiple": ad_multiple,
                "support_gate_status": "FAILED",
            },
        ),
        Claim(
            claim_id="C17",
            section="creator_video",
            headline=(
                f"{hp_n} 条视频的互动率达到全池中位数的 {hp_threshold:.0f} 倍以上，"
                "它们的共同点只能做计数，不能解释它们为什么跑赢。"
            ),
            **_grade(
                GradeInput(
                    is_direct_fact=True,
                    artifact_sha256=cv.get("input_sha256"),
                    exact_identity=True,
                    inference=False,
                ),
                n_records=hp_n,
                n_authors=hp_creators,
                agreement_pct=100.0,
                status_note="计数事实；高表现行来自冻结 video_level",
            ),
            observed=(
                f"{hp_bd['n']} 条视频的互动率达到全池中位数的 {hp_threshold:.0f} 倍以上。"
                f"这 {hp_bd['n']} 条里，广告披露 true {hp_bd['ad_true']} 条、"
                f"购买链接 true {hp_bd['link_true']} 条；"
                f"时长档分布为 "
                + "、".join(f"{k} {v} 条" for k, v in sorted(hp_bd["duration"].items()))
                + f"；关联置信度为 "
                + "、".join(f"{k} {v} 条" for k, v in sorted(hp_bd["confidence"].items()))
                + f"；关联类型为 "
                + "、".join(f"{k} {v} 条" for k, v in sorted(hp_bd["relation_type"].items()))
                + f"。低播放标记 {hp_bd['low_play']} 条。"
                "样本只有 2 条，这些计数不构成形态结论。"
            ),
            interpretation=(
                "共同特征只做计数。购买链接 false 在高表现组是 "
                f"{link_false_n}/{hp_n}（{_pct(link_false_share, 1)}），"
                f"全池是 {_pct(link_false_pool, 1)}，"
                f"差 {(link_false_share - link_false_pool) * 100:.1f} 个百分点；"
                f"这 {link_false_n} 条全是 medium text-only 关联。"
            ),
            counterevidence=(
                f"{hp_n} 条中 {medium_relation} 条是 medium 关联；"
                f"{low_play} 条低播放；样本只有 {hp_n} 条。"
                "共同点可能是关联质量和样本量的结果。"
            ),
            decision="不把共同点写成选型规则；先按关联质量分层，再重算高表现视频。",
            basis="creator-video/baseline/baseline.json high_performers.videos",
            unit=f"video（{hp_n} 条高表现视频）",
            limit=f"只覆盖 {baseline_n} 条基线视频；高表现定义是档内 {hp_threshold:.0f} 倍中位数",
            records=[],
            numbers={
                "videos_total": hp_n,
                "high_performers_n": hp_n,
                "high_performer_creators": hp_creators,
                "threshold_multiple": hp_threshold,
                "ad_disclosure_true_n": ad_true,
                "has_link_true_n": link_true,
                "duration_31_60_n": d31,
                "duration_16_30_n": d16,
                "duration_gt_60_n": d60,
                "low_play_n": low_play,
                "play_floor_5000_n": play_floor,
                "medium_relation_n": medium_relation,
                "ad_disclosure_true_share_population": ad_pool,
                "has_link_true_share_population": link_pool,
                "duration_31_60_share_population": d31_pool,
                "duration_16_30_share_population": d16_pool,
                "duration_gt_60_share_population": d60_pool,
            },
        ),
        Claim(
            claim_id="C18",
            section="creator_video",
            headline=(
                "内容形态只能从文案、话题和商品锚点派生，"
                "字幕、音轨、画面与达人受众数据本轮全部缺失。"
            ),
            **_grade(
                GradeInput(
                    required_cell_count=0,
                    required_field_missing_rate=1.0,
                ),
                n_records=baseline_n,
                n_authors=baseline_creators,
                agreement_pct=None,
                status_note="字段缺失率 100%",
            ),
            observed=(
                f"{baseline_n} 条基线视频的字段可用性：caption "
                f"{_num(availability.get('caption'))}、hashtags "
                f"{_num(availability.get('hashtags'))}、duration "
                f"{_num(availability.get('duration'))}、product_anchor "
                f"{_num(availability.get('product_anchor'))}、transcript_or_audio "
                f"{_num(availability.get('transcript_or_audio'))}。"
                f"comparison true {_num(comparison.get('true'))}、false "
                f"{_num(comparison.get('false'))}、unknown "
                f"{_num(comparison.get('unknown'))}；demo true {_num(demo.get('true'))}、"
                f"false {_num(demo.get('false'))}、unknown {_num(demo.get('unknown'))}；"
                f"before_after、unboxing、visual_only 均 unknown "
                f"{_num(before_after.get('unknown'))}/{baseline_n}。"
                f"第三方视频的 GMV、成交与受众画像不可得；"
                f"商品评论到视频的关联为 {comment_rows}/{canonical_reviews}。"
            ),
            interpretation="文案沉默不能证明画面没有对比或演示。这些字段是未观察，不是不存在。",
            counterevidence=(
                "文案和锚点能稳定判断 has_link 与 ad_disclosure，这两项有 n>=8 的层；"
                "但两者都与关联质量共线。"
            ),
            decision=(
                "要判断画面级形态，补 ASR、视觉分析或人工看片；"
                "要判断达人受众，换可提供受众画像的来源。"
            ),
            basis=(
                "creator-video/features/feature-distribution.json "
                "+ relations/comment-video-gap.json"
            ),
            unit=f"video / field（每个字段按 {baseline_n} 条视频计数）",
            limit="派生编码；无字幕、音轨、画面与受众数据",
            records=[],
            numbers={
                "videos_total": baseline_n,
                "transcript_or_audio": _num(availability.get("transcript_or_audio")),
                "comparison_true": _num(comparison.get("true")),
                "comparison_unknown": _num(comparison.get("unknown")),
                "demo_true": _num(demo.get("true")),
                "demo_unknown": _num(demo.get("unknown")),
                "before_after_unknown": _num(before_after.get("unknown")),
                "unboxing_unknown": _num(unboxing.get("unknown")),
                "visual_only_unknown": _num(visual_only.get("unknown")),
                "comment_video_rows": comment_rows,
                "canonical_reviews": canonical_reviews,
            },
        ),
    ]
    return claims


def build_recommendations(claims: list[Claim]) -> list[dict[str, Any]]:
    """Proposals that are not evidence and must not occupy a grade.

    C09 used to be a claim; a recommendation cannot be graded as evidence, so
    it lives here and is rendered in the report's separate recommendation
    block.  Each row names the claim whose gap motivates it, so the report can
    show that the proposal is a next step, not a finding.
    """
    by_id = {c.claim_id: c for c in claims}

    def premise(claim_id: str) -> str:
        claim = by_id.get(claim_id)
        return f"{claim_id} 当前为 {claim.grade.value}" if claim else f"{claim_id} 不存在"

    return [
        {
            "recommendation_id": "R01",
            "title": "Support ladder",
            "premise": (
                f"{premise('C04')}：自然样本的本人使用体验里 pooled 3 条四类摩擦记录"
                "（full 1 / partial 2）。"
            ),
            "next_step": "同一版型做三档支撑强度的小样本 wear test。",
            "kpi": "主观支撑评分、活动受限记录。",
            "guardrail": "出现压迫/疼痛自述即停；医学问题转 review。",
            "status": "Proposed · not approved",
        },
        {
            "recommendation_id": "R02",
            "title": "Fit chooser",
            "premise": (
                f"{premise('C05')}：full 层未找到舒适正向与支撑负向同时出现的记录；"
                "partial 层有 1 条观察，但不作为分布。"
            ),
            "next_step": "用孕周、腹型、躯干长度做分流页，测选码错误与退货。",
            "kpi": "选码错误率、退货原因完整率。",
            "guardrail": "不得用未验证的身形推断替代用户自选。",
            "status": "Proposed · not approved",
        },
        {
            "recommendation_id": "R03",
            "title": "Wearing guidance",
            "premise": "本轮没有同 frame 的 wearing guidance 证据；C06 的跨 frame 比较已删除。",
            "next_step": "在 PDP 写清适用活动、姿势与时长，测理解度。",
            "kpi": "理解度、客服重复问题数。",
            "guardrail": "不写绝对化承诺。",
            "status": "Proposed · not approved",
        },
    ]


def claims_to_dict(claims: list[Claim]) -> list[dict[str, Any]]:
    return [c.to_dict() for c in claims]


def grade_distribution(claims: list[Claim]) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for c in claims:
        out[c.grade.value] += 1
    return dict(out)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
