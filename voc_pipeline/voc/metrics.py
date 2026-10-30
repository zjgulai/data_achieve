"""Metric eligibility and materialised counts.

Nothing here produces a rate.  The module produces annotation hits, record
co-occurrence and frame inventories; a metric row is only materialised when
the G7 gate is PASS and the record satisfies the contract.  In this run G7 is
blocked, so ``metric_rows`` is empty by construction, not by accident.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from .canonical import CanonicalRecord
from .coder import BRAND_MODEL_RE, CodedRecord
from .contracts import DataLayer, Frame


@dataclass
class MetricContract:
    metric_id: str
    frame: str
    numerator_rule: str
    denominator_rule: str
    filters: dict[str, Any]
    qa_state: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__


def eligible(record: CanonicalRecord) -> bool:
    """The admission predicate from the SOP, implemented literally."""
    return (
        record.dedup_status in {"unique", "known_duplicate_representative"}
        and record.data_layer == DataLayer.CONSUMER_OBSERVATION_FACT.value
        and record.product_match in {"exact_current_family", "category_adjacent"}
        and record.content_role == "consumer_experience"
        and record.commerciality == "no_signal_observed"
        and record.metric_eligibility in {
            "natural_sample_candidate",
            "diagnostic_sample_only",
            "qualitative_seed_only",
            "tiktok_verified_candidate",
        }
        and record.organic_confidence in {"high", "medium"}
    )


def frame_inventory(records: list[CanonicalRecord]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    for rec in records:
        for frame in rec.frames:
            counts[frame] += 1
    # Overlap matrix: how many records sit in two frames at once.
    overlap: dict[str, int] = {}
    frames = [f.value for f in Frame if f.value != Frame.EXCLUDED.value]
    for i, a in enumerate(frames):
        for b in frames[i + 1 :]:
            n = sum(1 for r in records if a in r.frames and b in r.frames)
            if n:
                overlap[f"{a}+{b}"] = n
    return {"counts": dict(counts), "overlap": overlap, "distinct_records": len(records)}


def aspect_polarity_counts(coded: Iterable[CodedRecord]) -> dict[str, dict[str, int]]:
    table: dict[str, Counter[str]] = defaultdict(Counter)
    for rec in coded:
        for ann in rec.annotations:
            if ann.axis != "aspect":
                continue
            if ann.polarity in {"positive", "qualified_positive"}:
                table[ann.code]["positive"] += 1
            elif ann.polarity in {"negative", "qualified_negative"}:
                table[ann.code]["negative"] += 1
    return {code: dict(counter) for code, counter in sorted(table.items())}


def annotation_totals(coded: Iterable[CodedRecord]) -> dict[str, int]:
    totals = Counter()
    for rec in coded:
        for ann in rec.annotations:
            totals[ann.axis] += 1
    return dict(totals)


def _cooccurrence_view(rows: list[dict[str, Any]]) -> dict[str, Any]:
    comfort = [row for row in rows if row["comfort_positive"]]
    return {
        "comfort_positive_records": len(comfort),
        "comfort_positive_with_friction": sum(1 for row in comfort if row["both"]),
        "friction_negative_records": sum(1 for row in rows if row["friction_negative"]),
        "both_records": sum(1 for row in rows if row["both"]),
        "total_annotated_records": len(rows),
    }


_BRAND_ALIASES = {
    "frida mom": "frida",
    "frida": "frida",
    "cozy support": "cozysupport",
}


def _brand_positions(text: str) -> list[tuple[int, str]]:
    """Named brands with their offsets in the coded source text.

    Used only by the C05 same-product guard.  A record that evaluates several
    named products in separate sections must not pool a comfort-positive span
    from one product with a support-negative span from another.
    """
    positions: list[tuple[int, str]] = []
    for match in BRAND_MODEL_RE.finditer(text):
        label = " ".join(match.group(0).lower().split())
        positions.append((match.start(), _BRAND_ALIASES.get(label, label)))
    return positions


def _nearest_brand_label(
    positions: list[tuple[int, str]], offset: int
) -> str | None:
    if offset is None or offset < 0:
        return None
    before = [item for item in positions if item[0] <= offset]
    if before:
        return before[-1][1]
    after = [item for item in positions if item[0] > offset]
    return after[0][1] if after else None


def cooccurrence(
    records: list[CanonicalRecord], coded: list[CodedRecord], frame: str = Frame.NATURAL.value
) -> dict[str, Any]:
    """Record-level co-occurrence of comfort-positive and core-friction negative.

    Restricted to one frame: the tension claim is about the natural recall,
    and mixing verified-purchase reviews into it would create a denominator
    that belongs to no frame.

    Decision A: the pooled view is not a distribution.  ``full`` and
    ``partial`` are computed separately and must be reported as layers.  The
    legacy top-level keys keep the pooled counts for backward compatibility.
    """
    by_id = {r.canonical_id: r for r in records}
    comfort_codes = {"COM.GENERAL", "COM.SOFTNESS", "APP.UNDER_CLOTHING", "APP.LOW_PROFILE", "COM.BREATHABILITY_HEAT"}
    friction_codes = {"SUP.GENERAL", "SUP.BACK", "FIT.SIZE_ACCURACY", "FIT.BODY_SHAPE", "STB.STAY_IN_PLACE", "STB.STRAP_POSITION"}
    rows = []
    for rec in coded:
        # E-merge §2.2: the cohort predicate replaces the old boolean.  A
        # full/partial evaluation on an off-target record is real evidence
        # about another product; it must not enter a product claim.
        if not rec.in_cohort:
            continue
        record = by_id.get(rec.canonical_id)
        if record is None or frame not in record.frames:
            continue
        pos_annotations = [
            a
            for a in rec.annotations
            if a.code in comfort_codes and a.polarity in {"positive", "qualified_positive"}
        ]
        neg_annotations = [
            a
            for a in rec.annotations
            if a.code in friction_codes and a.polarity in {"negative", "qualified_negative"}
        ]
        pos = {a.code for a in pos_annotations}
        neg = {a.code for a in neg_annotations}
        if pos or neg:
            product_labels: list[str] = []
            cross_product = False
            if pos_annotations and neg_annotations:
                source_text = (
                    f"{record.title}. {record.text}" if record.title else record.text
                )
                positions = _brand_positions(source_text)
                if len({label for _offset, label in positions}) >= 2:
                    product_labels = sorted({label for _offset, label in positions})
                    pos_labels = {
                        _nearest_brand_label(positions, a.span_start)
                        for a in pos_annotations
                    }
                    neg_labels = {
                        _nearest_brand_label(positions, a.span_start)
                        for a in neg_annotations
                    }
                    if None in pos_labels or None in neg_labels:
                        # An unlocatable span cannot prove cross-product
                        # co-occurrence; keep the conservative pooled value.
                        same_product = True
                    else:
                        same_product = bool(pos_labels & neg_labels)
                    both = same_product
                    cross_product = not same_product
                else:
                    both = True
            else:
                both = False
            rows.append(
                {
                    "canonical_id": rec.canonical_id,
                    "comfort_positive": sorted(pos),
                    "friction_negative": sorted(neg),
                    "both": both,
                    "cross_product": cross_product,
                    "product_labels": product_labels,
                    "experience_scope": rec.experience_scope,
                    "text": by_id[rec.canonical_id].text[:240],
                    "subreddit": by_id[rec.canonical_id].subreddit,
                }
            )
    full_rows = [row for row in rows if row["experience_scope"] == "full"]
    partial_rows = [row for row in rows if row["experience_scope"] == "partial"]
    pooled = _cooccurrence_view(rows)
    return {
        **pooled,
        "full": _cooccurrence_view(full_rows),
        "partial": _cooccurrence_view(partial_rows),
        "pooled": pooled,
        "rows": sorted(rows, key=lambda r: (not r["both"], r["canonical_id"])),
    }


def top_aspects(polarity: dict[str, dict[str, int]], polarity_key: str, limit: int = 8) -> list[tuple[str, int]]:
    items = [(code, counts.get(polarity_key, 0)) for code, counts in polarity.items()]
    items = [x for x in items if x[1] > 0]
    items.sort(key=lambda x: (-x[1], x[0]))
    return items[:limit]


def author_and_thread_diversity(records: list[CanonicalRecord]) -> dict[str, Any]:
    authors = {r.author for r in records if r.author and r.author != "[deleted]"}
    subreddits = {r.subreddit for r in records}
    threads = {(r.subreddit, r.external_id) for r in records}
    return {
        "distinct_authors": len(authors),
        "distinct_subreddits": len(subreddits),
        "distinct_records": len(threads),
        "subreddit_counts": dict(Counter(r.subreddit for r in records).most_common()),
    }


def materialize_metrics(
    records: list[CanonicalRecord],
    coded: list[CodedRecord],
    g7_status: str,
) -> dict[str, Any]:
    frame_stats = frame_inventory(records)
    polarity = aspect_polarity_counts(coded)
    contracts = [
        MetricContract(
            metric_id="natural_support_negative_share",
            frame=Frame.NATURAL.value,
            numerator_rule="records with >=1 SUP/FIT/STB negative annotation",
            denominator_rule="eligible natural canonical consumer records with >=1 aspect annotation",
            filters={
                "product_match": ["exact_current_family", "category_adjacent"],
                "commerciality": ["no_signal_observed"],
                "content_role": ["consumer_experience"],
            },
            qa_state="blocked_g7_not_executed" if g7_status != "PASS" else "accepted",
        ),
        MetricContract(
            metric_id="natural_comfort_positive_share",
            frame=Frame.NATURAL.value,
            numerator_rule="records with >=1 COM/APP positive annotation",
            denominator_rule="eligible natural canonical consumer records with >=1 aspect annotation",
            filters={"product_match": ["exact_current_family", "category_adjacent"]},
            qa_state="blocked_g7_not_executed" if g7_status != "PASS" else "accepted",
        ),
        MetricContract(
            metric_id="tiktok_support_direction_share",
            frame=Frame.TIKTOK_SHOP_VERIFIED.value,
            numerator_rule=(
                "verified-purchase records whose support-family annotations agree on one direction"
            ),
            denominator_rule=(
                "verified-purchase records with >=1 decisive SUP.* annotation in the review window; "
                "one record contributes at most one direction"
            ),
            filters={
                "verified_purchase": [True],
                "identity_noise": ["excluded"],
                "window": ["2026-07-01", "2026-10-29"],
            },
            qa_state="blocked_g7_not_executed" if g7_status != "PASS" else "accepted",
        ),
    ]
    eligible_records = [r for r in records if eligible(r)]
    metric_rows: list[dict[str, Any]] = []
    if g7_status == "PASS":
        # Only here would numerator/denominator be computed and emitted.
        pass
    return {
        "frame_inventory": frame_stats,
        "aspect_polarity_counts": polarity,
        "annotation_totals": annotation_totals(coded),
        "eligible_records": len(eligible_records),
        "eligible_by_frame": {
            f: sum(1 for r in eligible_records if f in r.frames)
            for f in [
                Frame.NATURAL.value,
                Frame.DIAGNOSTIC.value,
                Frame.QUALITATIVE_SEED.value,
                Frame.TIKTOK_SHOP_VERIFIED.value,
            ]
        },
        "contracts": [c.to_dict() for c in contracts],
        "metric_rows": metric_rows,
        "g7_status": g7_status,
        "zero_metric_row_reason": (
            "G7 未执行：没有第二编码员与逐字段 agreement，正式指标行按 fail-closed 记为 0。"
            if g7_status != "PASS"
            else ""
        ),
    }
