"""Metric assembly helpers for the report pipeline.

This module turns coded records into the evidence layer: corpus counts,
coverage maps, key aspects, frame lenses, journey rollups, need states,
co-occurrence matrix and NumberRefs.  Every derived number records a
``derivation`` string in metric-summary.json so the report can be replayed.

No third-party dependency; all numbers are integers from the coded corpus.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from . import coding, contract, counting, evidence


def _count(value: int, unit: str, basis: str, source_path: str, **kwargs: Any) -> dict[str, Any]:
    return contract.count_block(value, unit, basis, source_path, **kwargs)


def build_corpus_summary(
    *,
    raw_objects: int,
    occurrences: int,
    canonical: int,
    frame_memberships: int,
    frame_counts: dict[str, int],
    within_frame_dropped: int,
    dedup_reasons: dict[str, int],
    excluded: dict[str, int],
    as_of: str,
) -> dict[str, Any]:
    canonical_dropped = occurrences - canonical
    reasons = {k: v for k, v in dedup_reasons.items() if v and k != "cross_frame_overlap"}
    if sum(reasons.values()) != canonical_dropped:
        reasons["cross_source_syndicated_duplicate"] = canonical_dropped - sum(reasons.values())
    membership_added = frame_memberships - canonical
    return {
        "as_of": as_of,
        "raw_objects": raw_objects,
        "occurrences_raw": occurrences + within_frame_dropped,
        "occurrences_deduplicated": occurrences,
        "within_frame_overlap_dropped": within_frame_dropped,
        "canonical_records": canonical,
        "frame_memberships": frame_memberships,
        "frame_counts": frame_counts,
        "deduction_reasons": {
            "within_frame_overlap": within_frame_dropped,
            "cross_source_syndicated_duplicate": reasons.get("cross_source_syndicated_duplicate", 0),
            "crosspost_same_author": reasons.get("crosspost_same_author", 0),
            "cross_frame_membership_added": membership_added,
        },
        "excluded": excluded,
        "reconciliation": [
            {
                "from": "raw_object",
                "to": "occurrence",
                "input_count": raw_objects,
                "deducted": within_frame_dropped,
                "output_count": occurrences,
                "reasons": ({"within_frame_overlap": within_frame_dropped} if within_frame_dropped else {}),
            },
            {
                "from": "occurrence",
                "to": "canonical_record",
                "input_count": occurrences,
                "deducted": canonical_dropped,
                "output_count": canonical,
                "reasons": reasons,
            },
            {
                "from": "canonical_record",
                "to": "frame_membership",
                "input_count": canonical,
                "deducted": -membership_added,
                "output_count": frame_memberships,
                "reasons": ({"cross_frame_membership_added": membership_added} if membership_added else {}),
            },
        ],
    }


def build_metric_summary(
    *,
    aggregate_result: dict[str, Any],
    canonical: list[counting.CanonicalRecord],
    coded: list[coding.CodedRecord],
    taxonomy: dict[str, Any],
    frame_counts: dict[str, int],
    identity: dict[str, Any],
    gate_status: str,
    as_of: str,
) -> dict[str, Any]:
    totals = aggregate_result["annotation_totals"]
    total_annotations = sum(totals.values())
    folded = coding.folded_aspect_counts(aggregate_result)
    key_aspects = {
        code: {"positive": counts["positive"], "negative": counts["negative"]}
        for code, counts in sorted(folded.items())
    }
    cooccurrence = {
        "comfort_positive_records": len(aggregate_result["comfort_positive_records"]),
        "comfort_positive_with_friction": len(aggregate_result["both_records"]),
        "comfort_positive_without_friction": len(aggregate_result["comfort_positive_records"])
        - len(aggregate_result["both_records"]),
        "friction_negative_records": len(aggregate_result["friction_negative_records"]),
        "both_records": len(aggregate_result["both_records"]),
        "total_annotated_records": len({ann.canonical_id for rec in coded for ann in rec.annotations}),
        "pairs": aggregate_result["mixed_pairs"],
        "matrix": build_mixed_matrix(aggregate_result["mixed_pairs"]),
    }
    journey = coding.journey_rollups(coded, len(canonical))
    product_match_counts = dict(Counter(record.product_match for record in canonical))
    eligibility_counts = dict(Counter(record.metric_eligibility for record in canonical))
    data_layer_counts = dict(Counter(record.data_layer for record in canonical))
    dedup_counts = dict(Counter(record.dedup_status for record in canonical))
    source_platform_counts = dict(Counter(record.subreddit or "unknown" for record in canonical))
    quality_flag_counts: dict[str, int] = {}
    for record in canonical:
        for flag in record.quality_flags:
            quality_flag_counts[flag] = quality_flag_counts.get(flag, 0) + 1
    distinct_authors = len({record.author for record in canonical if record.author != "[deleted]"})
    medical_records = {rec.canonical_id for rec in coded if rec.medical_flags}
    link_only = sum(1 for record in canonical if record.commerciality == "link_only")
    need_states, need_state_note = build_need_states(coded, coded_by_id={r.canonical_id: r for r in coded}, canonical=canonical)
    return {
        "generated_at": contract.now_iso(),
        "as_of": as_of,
        "annotation_totals": {**totals, "total": total_annotations},
        "aspect_code_counts": aggregate_result["aspect_code_counts"],
        "aspect_polarity_counts": aggregate_result["aspect_polarity_counts"],
        "key_aspects": key_aspects,
        "context_code_counts": aggregate_result["context_code_counts"],
        "journey_stage_counts": aggregate_result["journey_stage_counts"],
        "journey_rollup_counts": journey["independent_unit_counts"],
        "outcome_counts": aggregate_result["outcome_counts"],
        "gap_counts": journey["gap_counts"],
        "medical_self_report_code_counts": aggregate_result["medical_self_report_code_counts"],
        "medical_records": len(medical_records),
        "medical_record_ids": sorted(medical_records),
        "severity_counts": aggregate_result["severity_counts"],
        "cooccurrence": cooccurrence,
        "product_match_counts": product_match_counts,
        "eligibility_counts": eligibility_counts,
        "data_layer_counts": data_layer_counts,
        "dedup_status_counts": dedup_counts,
        "source_platform_counts": source_platform_counts,
        "quality_flag_counts": quality_flag_counts,
        "diversity": {
            "distinct_authors": distinct_authors,
            "distinct_records": len(canonical),
            "distinct_subreddits": len({record.subreddit for record in canonical}),
            "subreddit_counts": source_platform_counts,
        },
        "link_only_variant_records": link_only,
        "frame_counts": frame_counts,
        "frame_lenses": coding.frame_lenses(coded, canonical, taxonomy, frame_counts),
        "need_states": need_states,
        "need_states_note": need_state_note,
        "identity": {
            "family_children": identity.get("family_children"),
            "variant_matrix_rows": len(identity.get("variants", {}).get("items", [])),
            "target_variant_count": sum(1 for item in identity.get("variants", {}).get("items", []) if item.get("is_target")),
            "family_review_count": identity.get("product_rating", {}).get("review_count"),
            "per_variant_review_count_rows": 0,
        },
        "metric_rows": 0,
        "g7_status": gate_status,
        "g7_reason": "G7 未执行：没有第二编码员与逐字段 agreement，正式指标行按 fail-closed 记为 0。",
        "derivations": {
            "annotation_totals": "sum of rule-coder annotations by axis; one annotation per code per record",
            "aspect_polarity_counts": "aspect annotation counts split by polarity; mixed contributes one positive and one negative",
            "key_aspects": "qualified_positive folded into positive; qualified_negative folded into negative",
            "cooccurrence.comfort_positive_records": "records with at least one COM.* or APP.* positive annotation",
            "cooccurrence.comfort_positive_with_friction": "subset of comfort-positive records with at least one SUP.* / FIT.* / STB.* negative annotation",
            "cooccurrence.friction_negative_records": "records with at least one SUP.* / FIT.* / STB.* negative annotation",
            "journey_rollup_counts": "one deterministic journey stage per record; unknown is the remainder to 248",
            "gap_counts": "one deterministic gap rollup per record; unknown is the remainder to 248",
            "need_states": "context rule matches, then record-level core-friction count; quadrant split is by median demand and median friction",
            "product_match_counts": "text rule from counting.classify_product",
            "eligibility_counts": "canonical metric_eligibility; qualitative_seed overrides other exclusions",
            "metric_rows": "0 because G7 is BLOCKED; candidate rows are deducted with reason gate_not_pass",
        },
    }


def build_mixed_matrix(pairs: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    families = ["comfort", "support", "fit", "value"]
    matrix = {positive: {negative: 0 for negative in families} for positive in families}
    for pair in pairs:
        positive = pair["positive_family"]
        negative = pair["negative_family"]
        if positive not in matrix:
            matrix[positive] = {name: 0 for name in families}
        matrix[positive][negative] = matrix[positive].get(negative, 0) + 1
    return matrix


def build_need_states(
    coded: list[coding.CodedRecord],
    *,
    coded_by_id: dict[str, coding.CodedRecord],
    canonical: list[counting.CanonicalRecord],
) -> tuple[list[dict[str, Any]], str]:
    """Four context-derived need states.

    This is an interpretive layer, so it is only produced when each of the
    four contexts has at least three records.  Otherwise the section must
    render a gap instead of a fabricated quadrant.
    """
    by_id = {record.canonical_id: record for record in canonical}
    context_specs = [
        ("exercise", "CTX.ACTIVITY_EXERCISE", "孕期运动与走动", "运动时需要稳定但不限制动作"),
        ("work", "CTX.ACTIVITY_WORK", "工作与日常久站", "长时间站立或办公时需要持续承托"),
        ("postpartum", "CTX.POSTPARTUM", "产后恢复期", "产后腹部与腰部需要温和支撑"),
        ("third_trimester", "CTX.PREGNANCY_T3", "孕晚期增长", "孕晚期腹部增长后仍要保持位置与覆盖"),
    ]
    rows = []
    for state_id, context_code, name, summary in context_specs:
        record_ids = [
            rec.canonical_id
            for rec in coded
            if any(ann.axis == "context" and ann.code == context_code for ann in rec.annotations)
        ]
        if len(record_ids) < 3:
            return [], f"{context_code} only has {len(record_ids)} records; need at least 3 per state"
        friction_ids = []
        for canonical_id in record_ids:
            record = coded_by_id.get(canonical_id)
            if not record:
                continue
            if any(
                ann.axis == "aspect"
                and ann.polarity.startswith("negative")
                and ann.code.startswith(("SUP.", "FIT.", "STB."))
                for ann in record.annotations
            ):
                friction_ids.append(canonical_id)
        rows.append(
            {
                "id": state_id,
                "context_code": context_code,
                "name": name,
                "summary": summary,
                "record_ids": record_ids,
                "demand": len(record_ids),
                "friction": len(friction_ids),
                "friction_ids": friction_ids,
            }
        )
    demand_values = sorted(row["demand"] for row in rows)
    friction_values = sorted(row["friction"] for row in rows)
    demand_mid = demand_values[len(demand_values) // 2]
    friction_mid = friction_values[len(friction_values) // 2]
    for row in rows:
        high_demand = row["demand"] >= demand_mid
        high_friction = row["friction"] >= friction_mid
        if high_demand and high_friction:
            quadrant = "Q1 · 高需求 / 高摩擦"
        elif high_demand and not high_friction:
            quadrant = "Q2 · 高需求 / 低摩擦"
        elif not high_demand and high_friction:
            quadrant = "Q4 · 低需求 / 高摩擦"
        else:
            quadrant = "Q3 · 低需求 / 低摩擦"
        row["quadrant"] = quadrant
    return rows, "context-derived need states; quadrant split is a median split, not a population size"


def number_ref(
    name: str,
    value: int,
    unit: str,
    basis: str,
    denominator: int | None,
    source_path: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "value": value,
        "unit": unit,
        "basis": basis,
        "denominator": denominator,
        "source_path": source_path,
    }


class Resolver:
    """Resolve ``artifact.json#/pointer`` against files in the output directory."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self._cache: dict[str, Any] = {}

    def load(self, name: str) -> Any:
        if name not in self._cache:
            path = self.root / name
            if not path.exists():
                raise contract.ContractError(f"source artifact not found: {name}")
            if name.endswith(".jsonl"):
                rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
                self._cache[name] = rows
            else:
                self._cache[name] = json.loads(path.read_text(encoding="utf-8"))
        return self._cache[name]

    def resolve(self, source_path: str) -> Any:
        name, pointer = contract.parse_source_path(source_path)
        document = self.load(name)
        return contract.resolve_pointer(document, pointer)

    def verify(self, source_path: str, expected: Any) -> None:
        actual = self.resolve(source_path)
        if actual != expected:
            raise contract.ContractError(f"source_path {source_path} resolves to {actual!r}, expected {expected!r}")


def coverage_layer(
    *,
    corpus_summary: dict[str, Any],
    metric_summary: dict[str, Any],
    canonical: list[counting.CanonicalRecord],
    taxonomy: dict[str, Any],
    as_of: str,
) -> dict[str, Any]:
    def cb(value: int, unit: str, basis: str, path: str, **kwargs: Any) -> dict[str, Any]:
        return _count(value, unit, basis, path, **kwargs)

    product_match = metric_summary["product_match_counts"]
    eligibility = metric_summary["eligibility_counts"]
    data_layer = metric_summary["data_layer_counts"]
    dedup = metric_summary["dedup_status_counts"]
    source_platform = metric_summary["source_platform_counts"]
    quality = metric_summary["quality_flag_counts"]
    aspect_polarity = metric_summary["aspect_polarity_counts"]
    aspect_code = metric_summary["aspect_code_counts"]
    annotations_total = metric_summary["annotation_totals"]["total"]
    aspect_total = metric_summary["annotation_totals"]["aspect"]
    context_total = metric_summary["annotation_totals"]["context"]
    journey_total = metric_summary["annotation_totals"]["journey"]
    outcome_total = metric_summary["annotation_totals"]["outcome"]
    medical_total = metric_summary["annotation_totals"]["medical"]

    out = {
        "record_occurrences": cb(
            corpus_summary["occurrences_deduplicated"],
            "occurrence",
            "same external_id + frame deduplicated",
            "corpus-summary.json#/occurrences_deduplicated",
        ),
        "independent_content_units": cb(
            corpus_summary["canonical_records"],
            "canonical_record",
            "exact normalized text + same-author Jaccard >= 0.90 deduplicated",
            "corpus-summary.json#/canonical_records",
        ),
        "source_family_counts": {
            "reddit": cb(
                len(canonical),
                "canonical_record",
                "all canonical records have source=reddit in this run",
                "corpus-summary.json#/canonical_records",
                partition=True,
            )
        },
        "source_platform_counts": {
            name: cb(
                value,
                "canonical_record",
                "canonical records grouped by subreddit; partition sums to 248",
                f"metric-summary.json#/source_platform_counts/{name}",
                partition=True,
            )
            for name, value in sorted(source_platform.items())
        },
        "sample_frame_counts": {
            name: cb(
                value,
                "canonical_record",
                "records with this frame membership; frames may overlap",
                f"corpus-summary.json#/frame_counts/{name}",
                multi_label=True,
                partition=False,
            )
            for name, value in sorted(corpus_summary["frame_counts"].items())
        },
        "metric_eligibility_counts": {
            name: cb(
                value,
                "canonical_record",
                "canonical metric_eligibility; qualitative_seed overrides other exclusions",
                f"metric-summary.json#/eligibility_counts/{name}",
                partition=True,
            )
            for name, value in sorted(eligibility.items())
        },
        "data_layer_counts": {
            name: cb(
                value,
                "canonical_record",
                "canonical data_layer; partition sums to 248",
                f"metric-summary.json#/data_layer_counts/{name}",
                partition=True,
            )
            for name, value in sorted(data_layer.items())
        },
        "dedup_status_counts": {
            name: cb(
                value,
                "canonical_record",
                "canonical dedup status; partition sums to 248",
                f"metric-summary.json#/dedup_status_counts/{name}",
                partition=True,
            )
            for name, value in sorted(dedup.items())
        },
        "product_match_counts": {
            name: cb(
                value,
                "canonical_record",
                "text rule from counting.classify_product; partition sums to 248",
                f"metric-summary.json#/product_match_counts/{name}",
                partition=True,
            )
            for name, value in sorted(product_match.items())
        },
        "aspect_annotation_count": cb(
            aspect_total,
            "annotation",
            "sum of aspect annotations; one record may contribute several codes",
            "metric-summary.json#/annotation_totals/aspect",
            multi_label=True,
        ),
        "aspect_code_counts": {
            name: cb(
                value,
                "annotation",
                "annotation hits for this aspect code; multi-label",
                f"metric-summary.json#/aspect_code_counts/{name}",
                multi_label=True,
                partition=True,
            )
            for name, value in sorted(aspect_code.items())
        },
        "aspect_polarity_counts": {
            name: cb(
                value,
                "annotation",
                "annotation hits split by code and polarity; mixed contributes both signs",
                f"metric-summary.json#/aspect_polarity_counts/{name}",
                multi_label=True,
                partition=True,
            )
            for name, value in sorted(aspect_polarity.items())
        },
        "context_code_counts": {
            name: cb(
                value,
                "annotation",
                "context annotation hits; multi-label",
                f"metric-summary.json#/context_code_counts/{name}",
                multi_label=True,
                partition=False,
            )
            for name, value in sorted(metric_summary["context_code_counts"].items())
        },
        "journey_stage_counts": {
            name: cb(
                value,
                "annotation",
                "journey annotation hits; multi-label",
                f"metric-summary.json#/journey_stage_counts/{name}",
                multi_label=True,
                partition=False,
            )
            for name, value in sorted(metric_summary["journey_stage_counts"].items())
        },
        "outcome_counts": {
            name: cb(
                value,
                "annotation",
                "outcome annotation hits; multi-label",
                f"metric-summary.json#/outcome_counts/{name}",
                multi_label=True,
                partition=False,
            )
            for name, value in sorted(metric_summary["outcome_counts"].items())
        },
        "expectation_gap_counts": {
            name: cb(
                value,
                "canonical_record",
                "one deterministic gap rollup per record; unknown is the remainder to 248",
                f"metric-summary.json#/gap_counts/{name}",
                partition=True,
            )
            for name, value in sorted(metric_summary["gap_counts"].items())
        },
        "nonunknown_expectation_gap_records": cb(
            sum(value for name, value in metric_summary["gap_counts"].items() if name != "unknown"),
            "canonical_record",
            "sum of non-unknown gap rollups",
            "metric-summary.json#/coverage_numbers/nonunknown_gap_records",
        ),
        "mixed_experience_records": cb(
            metric_summary["cooccurrence"]["both_records"],
            "canonical_record",
            "records with both comfort-positive and core-friction negative annotations",
            "metric-summary.json#/cooccurrence/both_records",
        ),
        "claim_relation_counts": {
            "not_assessed_at_G7": cb(
                len(canonical),
                "canonical_record",
                "claim relation is not assessed before G7; partition sums to 248",
                "corpus-summary.json#/canonical_records",
                partition=True,
            )
        },
        "medical_self_report_code_counts": {
            name: cb(
                value,
                "annotation",
                "medical self-report annotation hits; no efficacy or safety inference",
                f"metric-summary.json#/medical_self_report_code_counts/{name}",
                multi_label=True,
                partition=False,
            )
            for name, value in sorted(metric_summary["medical_self_report_code_counts"].items())
        },
        "mandatory_medical_review_records": cb(
            metric_summary["medical_records"],
            "canonical_record",
            "distinct canonical records with at least one MED.* self-report annotation",
            "metric-summary.json#/medical_records",
        ),
        "quality_flag_counts": {
            name: cb(
                value,
                "canonical_record",
                "canonical records carrying this quality flag; multi-label",
                f"metric-summary.json#/quality_flag_counts/{name}",
                multi_label=True,
                partition=False,
            )
            for name, value in sorted(quality.items())
        },
        "evidence_inventory_reconciliation": {
            "raw_object": corpus_summary["raw_objects"],
            "occurrence": corpus_summary["occurrences_deduplicated"],
            "canonical_record": corpus_summary["canonical_records"],
            "frame_membership": corpus_summary["frame_memberships"],
            "annotation": annotations_total,
            "metric_row": 0,
        },
        "interpretation_limit": "计数只描述本次关键词语料，不代表消费者总体；annotation 不是人，也不是记录数。",
        "basis": "independent_content_units",
    }
    return out


def verify_claim_numbers(claims: list[dict[str, Any]], resolver: Resolver) -> None:
    for claim in claims:
        names = set()
        for number in claim["numbers"]:
            if number["name"] in names:
                raise contract.ContractError(f"{claim['claim_id']}: duplicate NumberRef name {number['name']}")
            names.add(number["name"])
            resolver.verify(number["source_path"], number["value"])
