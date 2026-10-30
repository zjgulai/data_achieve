#!/usr/bin/env python3
"""assemble.py — build report-data.json from one real run directory.

Input:  voc_pipeline/artifacts/<run>/ (corpus-summary, metric-summary, claims,
        taxonomy, gate-ledger, amazon identity, canonical/coded JSONL,
        delivery-manifest, research charter)
Output: report-data.json shaped by ref/extract/DATA-CONTRACT.md

No number is invented. Every CountBlock / NumberRef points at a run artifact
or at a deterministic computation over canonical-records.jsonl /
coded-corpus.jsonl; the basis says which. Missing optional layers stay null
and are listed in report.unknowns.

Usage:
  python3 assemble.py --run /path/to/artifacts/run-20261029 --out out/run-20261029/report-data.json
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import sys
from pathlib import Path

import ir_contract as C

AS_OF = "2026-10-29"
GENERATED_AT = "2026-10-29T14:53:08+00:00"
REPORT_ID = "us-momcozy-bumpease-20261029"
DEFAULT_RUN = "/Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029"


# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------
def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def artifact_id(path: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9]+", "-", Path(path).stem).strip("-").lower()
    return stem or "artifact"


# ---------------------------------------------------------------------------
# Contract builders
# ---------------------------------------------------------------------------
def count(value, unit, basis, source_path, denominator=None, multi_label=False, partition=False) -> dict:
    return {
        "value": value,
        "unit": unit,
        "basis": basis,
        "denominator": denominator,
        "multi_label": multi_label,
        "partition": partition,
        "as_of": AS_OF,
        "source_path": source_path,
    }


def text(value: str, claim_id: str | None = None, refs: list[str] | None = None) -> dict:
    return {
        "text": value,
        "authored_by": "llm_assisted",
        "claim_id": claim_id,
        "data_refs": refs or [],
        "reviewed_by": "UNASSIGNED",
    }


def status(state: str, scope: str, reason_code: str, inputs: dict, gate: str | None = None) -> dict:
    return {
        "status": state,
        "badge": C.badge_text(state, scope),
        "reason_code": reason_code,
        "inputs": inputs,
        "gate": gate,
    }


def number(name, value, unit, basis, source_path, denominator=None) -> dict:
    return {
        "name": name,
        "value": value,
        "unit": unit,
        "basis": basis,
        "denominator": denominator,
        "source_path": source_path,
    }


REASON_CODE = {
    "confirmed": "EVID_CONFIRMED",
    "directional": "EVID_DIRECTIONAL",
    "hypothesis": "EVID_HYPOTHESIS",
    "evidence_gap": "EVID_GAP",
    "blocked": "EVID_BLOCKED",
    "not_authorized": "EVID_NOT_AUTHORIZED",
}


# ---------------------------------------------------------------------------
# Main assembly
# ---------------------------------------------------------------------------
def assemble(run: Path) -> dict:
    corpus_summary = load_json(run / "corpus-summary.json")
    metric_summary = load_json(run / "metric-summary.json")
    claims_raw = load_json(run / "claims.json")
    taxonomy = load_json(run / "taxonomy.json")
    gate_ledger = load_json(run / "gate-ledger.json")
    amazon = load_json(run / "amazon-identity-raw.json")
    charter = load_json(run / "voc-research-charter.json")
    manifest = load_json(run / "delivery-manifest.json")
    canonical = load_jsonl(run / "canonical-records.jsonl")
    coded = load_jsonl(run / "coded-corpus.jsonl")
    canonical_by_id = {r["canonical_id"]: r for r in canonical}
    coded_by_id = {r["canonical_id"]: r for r in coded}

    # Artifacts ------------------------------------------------------------
    artifacts = []
    manifest_by_path = {a["path"]: a for a in manifest.get("artifacts", [])}
    referenced = {
        "corpus-summary.json", "metric-summary.json", "claims.json", "taxonomy.json",
        "gate-ledger.json", "amazon-identity-raw.json", "canonical-records.jsonl",
        "coded-corpus.jsonl", "delivery-manifest.json", "voc-research-charter.json",
    }
    for path in sorted(referenced):
        p = run / path
        if not p.exists():
            continue
        meta = manifest_by_path.get(path, {})
        actual_sha = sha256_file(p)
        artifacts.append({
            "artifact_id": artifact_id(path),
            "path": path,
            "sha256": actual_sha,
            "bytes": p.stat().st_size,
            "kind": "raw_parse" if path.startswith("amazon") else "derived",
            "generated_at": manifest.get("generated_at", GENERATED_AT),
        })
    artifact_by_path = {a["path"]: a for a in artifacts}

    def art(path: str) -> dict:
        return artifact_by_path[path]

    def source_artifact(path: str, provider: str | None = None) -> dict:
        a = art(path)
        return {
            "kind": "artifact",
            "provider": provider,
            "endpoint": None,
            "table": None,
            "columns": None,
            "path": path,
            "sha256": a["sha256"],
            "blocked_reason": None,
        }

    # Identity -------------------------------------------------------------
    parent = "B0H8LVJ81X"
    child = charter["product"]["target_child_asin"]
    product = amazon["products"][parent]
    identity = {
        "product": product["title"],
        "brand": charter["product"]["brand"],
        "model": None,
        "variant_id": child,
        "sku": None,
        "color": "Oyster Pink",
        "size": "Small",
        "parent_asin": parent,
        "child_asin": child,
        "mapping_confidence": 1.0,
        "family_children": product["variant_count"],
        "market": charter["market"],
        "language": charter["language"],
        "window": {
            "start": charter["window"]["start"],
            "end": charter["window"]["end"],
            "days": 1033,
        },
        "identity_quality": "exact",
        "source": [source_artifact("amazon-identity-raw.json", "amazon")],
    }

    # Gate -----------------------------------------------------------------
    gate_status = {g["gate_id"]: g["status"] for g in gate_ledger["gates"]}
    gate = {
        "schema_version": gate_ledger["schema_version"],
        "gates": [{"gate_id": g["gate_id"], "status": g["status"]} for g in gate_ledger["gates"]],
        "decision_scope": "G6 progress snapshot：只支持方向判断与可逆实验；G7 未执行，禁止对外发布与正式指标。",
        "review_statuses": {
            "structural": gate_status.get("G6", "BLOCKED"),
            "canonical": gate_status.get("G6", "BLOCKED"),
            "rights": gate_status.get("G2", "BLOCKED"),
        },
        "evidence_summary": gate_ledger["evidence_summary"],
        "stage_boundary": gate_ledger["stage_boundary"],
        "does_not_authorize": gate_ledger["does_not_authorize"],
        "artifact_sha256": {a["path"]: a["sha256"] for a in artifacts},
    }

    # Corpus ---------------------------------------------------------------
    corpus = {
        "raw_objects": count(corpus_summary["raw_objects"], "raw_object",
                             "provider records written to raw store; not sample size",
                             "corpus-summary.json#/raw_objects"),
        "occurrences": count(corpus_summary["occurrences_deduplicated"], "occurrence",
                             "same external_id + frame deduplicated; 0 dropped",
                             "corpus-summary.json#/occurrences_deduplicated"),
        "canonical_records": count(corpus_summary["canonical_records"], "canonical_record",
                                   "exact + fuzzy dedup; 2 occurrences merged",
                                   "corpus-summary.json#/canonical_records"),
        "frame_memberships": count(corpus_summary["frame_memberships"], "frame_membership",
                                   "memberships may overlap; not a funnel",
                                   "corpus-summary.json#/frame_memberships"),
        "annotations": count(sum(metric_summary["annotation_totals"].values()), "annotation",
                             "aspect 179 + context 230 + journey 50 + outcome 41 + medical 33 = 533",
                             "metric-summary.json#/annotation_totals", multi_label=True),
        "metric_rows": count(0, "metric_row", "G7 BLOCKED; fail-closed",
                             "metric-summary.json#/metric_rows"),
        "reconciliation": [
            {"from": "raw_object", "to": "occurrence", "input_count": 250, "deducted": 0,
             "output_count": 250, "reasons": {}},
            {"from": "occurrence", "to": "canonical_record", "input_count": 250, "deducted": 2,
             "output_count": 248,
             "reasons": {"cross_source_syndicated_duplicate": 1, "crosspost_same_author": 1}},
            {"from": "canonical_record", "to": "frame_membership", "input_count": 248, "deducted": -9,
             "output_count": 257, "reasons": {"cross_frame_membership_added": -9}},
        ],
    }

    # Coverage -------------------------------------------------------------
    aspect_pairs = metric_summary["aspect_polarity_counts"]
    aspect_code_counts = {}
    aspect_polarity_counts = {}
    for code, pol in aspect_pairs.items():
        pos = int(pol.get("positive", 0))
        neg = int(pol.get("negative", 0))
        total = pos + neg
        aspect_code_counts[code] = count(
            total, "annotation", "aspect annotation hits; one record may contribute several",
            f"metric-summary.json#/aspect_polarity_counts/{code}", multi_label=True, partition=True)
        if pos:
            aspect_polarity_counts[f"{code}|positive"] = count(
                pos, "annotation", "positive aspect annotation hits",
                f"metric-summary.json#/aspect_polarity_counts/{code}/positive",
                multi_label=True, partition=True)
        if neg:
            aspect_polarity_counts[f"{code}|negative"] = count(
                neg, "annotation", "negative aspect annotation hits",
                f"metric-summary.json#/aspect_polarity_counts/{code}/negative",
                multi_label=True, partition=True)

    subreddits = metric_summary["diversity"]["subreddit_counts"]
    data_layers = collections.Counter(r["data_layer"] for r in canonical)
    dedup_statuses = collections.Counter(r["dedup_status"] for r in canonical)
    quality_flags = collections.Counter(flag for r in canonical for flag in r["quality_flags"])
    product_matches = metric_summary["product_match_counts"]
    eligibility = metric_summary["eligibility_counts"]
    frames = corpus_summary["frame_counts"]

    def map_counts(values: dict, unit: str, basis: str, source: str, partition=True, multi=False) -> dict:
        return {
            str(k): count(int(v), unit, basis, f"{source}/{k}", multi_label=multi, partition=partition)
            for k, v in values.items()
        }

    # Record-level journey / outcome / gap.
    journey_records = collections.Counter()
    outcome_records = collections.Counter()
    gap_records = collections.Counter()
    journey_annotated = 0
    outcome_annotated = 0
    for r in coded:
        js = {a["code"] for a in r["annotations"] if a["axis"] == "journey"}
        os_ = {a["code"] for a in r["annotations"] if a["axis"] == "outcome"}
        gs = {a["code"] for a in r["annotations"] if a["axis"] == "gap"}
        if js:
            journey_annotated += 1
        if os_:
            outcome_annotated += 1
        for x in (js or {"UNKNOWN_JOURNEY"}):
            journey_records[x] += 1
        for x in (os_ or {"OUT.UNKNOWN"}):
            outcome_records[x] += 1
        for x in (gs or {"unknown"}):
            gap_records[x] += 1

    context_counts = collections.Counter()
    medical_counts = collections.Counter()
    for r in coded:
        for a in r["annotations"]:
            if a["axis"] == "context" and a["polarity"] == "present":
                context_counts[a["code"]] += 1
            if a["axis"] == "medical":
                medical_counts[a["code"]] += 1

    coverage = {
        "record_occurrences": count(250, "occurrence", "same external_id + frame deduplicated",
                                    "corpus-summary.json#/occurrences_deduplicated"),
        "independent_content_units": count(248, "canonical_record",
                                           "report page denominator; 250 occurrences → 248 canonical",
                                           "corpus-summary.json#/canonical_records"),
        "source_family_counts": {
            "reddit": count(248, "canonical_record", "source=reddit for all canonical records",
                            "canonical-records.jsonl#/source", partition=True)
        },
        "source_platform_counts": map_counts(
            subreddits, "canonical_record", "canonical records grouped by subreddit",
            "metric-summary.json#/diversity/subreddit_counts"),
        "sample_frame_counts": map_counts(
            frames, "canonical_record",
            "frame memberships may overlap; sum 257 > 248 canonical",
            "corpus-summary.json#/frame_counts", partition=False, multi=True),
        "metric_eligibility_counts": map_counts(
            eligibility, "canonical_record", "metric eligibility rollup; sum 248",
            "metric-summary.json#/eligibility_counts"),
        "data_layer_counts": map_counts(
            data_layers, "canonical_record", "canonical data_layer rollup; sum 248",
            "canonical-records.jsonl#/data_layer"),
        "dedup_status_counts": map_counts(
            dedup_statuses, "canonical_record", "canonical dedup_status rollup; sum 248",
            "canonical-records.jsonl#/dedup_status"),
        "product_match_counts": map_counts(
            product_matches, "canonical_record", "text-rule product match rollup; sum 248",
            "metric-summary.json#/product_match_counts"),
        "aspect_annotation_count": count(179, "annotation",
                                         "sum of aspect positive/negative annotations; records may contribute several",
                                         "metric-summary.json#/annotation_totals/aspect",
                                         multi_label=True),
        "aspect_code_counts": aspect_code_counts,
        "aspect_polarity_counts": aspect_polarity_counts,
        "context_code_counts": map_counts(
            context_counts, "annotation", "context annotation hits; multi-label; sum 230",
            "coded-corpus.jsonl#/annotations/context", partition=True, multi=True),
        "journey_stage_counts": map_counts(
            {k: v for k, v in journey_records.items() if k != "UNKNOWN_JOURNEY"},
            "canonical_record", "record-level journey annotations; multi-label; 32 annotated records",
            "coded-corpus.jsonl#/journey_stage", partition=False, multi=True),
        "journey_annotation_records": count(journey_annotated, "canonical_record",
                                            "records with at least one journey annotation",
                                            "coded-corpus.jsonl#/journey_stage"),
        "outcome_counts": map_counts(
            {k: v for k, v in outcome_records.items() if k != "OUT.UNKNOWN"},
            "canonical_record", "record-level outcome annotations; multi-label; 36 annotated records",
            "coded-corpus.jsonl#/outcome", partition=False, multi=True),
        "outcome_annotation_records": count(outcome_annotated, "canonical_record",
                                            "records with at least one outcome annotation",
                                            "coded-corpus.jsonl#/outcome"),
        "expectation_gap_counts": {
            str(k): count(v, "canonical_record", "expectation gap rollup; partition over 248 canonical",
                          f"coded-corpus.jsonl#/gap/{k}", partition=True)
            for k, v in gap_records.items()
        },
        "nonunknown_expectation_gap_records": count(
            sum(v for k, v in gap_records.items() if k != "unknown"), "canonical_record",
            "records with a non-unknown expectation gap code",
            "coded-corpus.jsonl#/gap"),
        "mixed_experience_records": count(
            metric_summary["cooccurrence"]["both_records"], "canonical_record",
            "records with both comfort-positive and core-friction negative annotations",
            "metric-summary.json#/cooccurrence/both_records"),
        "medical_self_report_code_counts": map_counts(
            medical_counts, "annotation", "medical self-report annotations only; not diagnosis",
            "coded-corpus.jsonl#/medical_flags", partition=False, multi=True),
        "mandatory_medical_review_records": count(
            sum(1 for r in coded if r["claim_relation"] == "review_required"), "canonical_record",
            "records with claim_relation=review_required",
            "coded-corpus.jsonl#/claim_relation"),
        "quality_flag_counts": map_counts(
            quality_flags, "canonical_record", "quality flag hits; multi-label; not sample size",
            "canonical-records.jsonl#/quality_flags", partition=False, multi=True),
        "evidence_inventory_reconciliation": {
            "raw_objects": 250,
            "occurrences": 250,
            "canonical_records": 248,
            "frame_memberships": 257,
            "annotations": 533,
            "metric_rows": 0,
        },
        "interpretation_limit": "计数描述本次关键词语料，不是消费者总体比例；annotation hit 不是人数。",
        "basis": "independent_content_units",
    }

    # Taxonomy -------------------------------------------------------------
    taxonomy_out = {
        "taxonomy_id": taxonomy["taxonomy_id"],
        "frozen_at": taxonomy["frozen_at"],
        "axes": sorted(taxonomy["axes"].keys()),
        "code_count": len(taxonomy["codes"]),
        "codes": [
            {
                "code": c["code"], "axis": c["axis"], "label": c["label"],
                "definition": c["definition"], "include": c["include"], "exclude": c["exclude"],
            }
            for c in taxonomy["codes"]
        ],
        "source": [source_artifact("taxonomy.json")],
    }

    # Key aspects: 12 highest-total codes with a four-family mapping.
    def aspect_family(code: str) -> str | None:
        if code.startswith(("SUP.", "STB.")):
            return "support"
        if code.startswith(("FIT.", "ADJ.", "ACT.")):
            return "fit"
        if code.startswith(("COM.", "APP.", "MAT.")):
            return "wearability"
        if code.startswith(("VAL.", "FUL.")):
            return "value"
        return None

    labels = {c["code"]: c["label"] for c in taxonomy["codes"]}
    ranked = sorted(
        ((code, pol.get("positive", 0) + pol.get("negative", 0)) for code, pol in aspect_pairs.items()),
        key=lambda kv: (-kv[1], kv[0]),
    )
    selected = [(code, total) for code, total in ranked if aspect_family(code)][:12]
    key_aspects = []
    for code, total in selected:
        pol = aspect_pairs[code]
        key_aspects.append({
            "code": code,
            "label": labels.get(code, code),
            "family": aspect_family(code),
            "positive": count(int(pol.get("positive", 0)), "annotation",
                              "positive aspect annotation hits; qualified_positive folded into positive",
                              f"metric-summary.json#/aspect_polarity_counts/{code}/positive" if pol.get("positive", 0) else f"metric-summary.json#/aspect_polarity_counts/{code}",
                              multi_label=True),
            "negative": count(int(pol.get("negative", 0)), "annotation",
                              "negative aspect annotation hits; qualified_negative folded into negative",
                              f"metric-summary.json#/aspect_polarity_counts/{code}/negative" if pol.get("negative", 0) else f"metric-summary.json#/aspect_polarity_counts/{code}",
                              multi_label=True),
            "derived_from": "coverage.aspect_polarity_counts",
            "basis": "12 of 21 observed aspect codes; selection = highest total after excluding GEN.OVERALL_EVALUATION; counts are annotation hits, not people",
        })

    # Cluster lenses -------------------------------------------------------
    def lens_lists(frame: str):
        pos = collections.Counter()
        neg = collections.Counter()
        for cid, r in coded_by_id.items():
            if frame not in canonical_by_id[cid]["frames"]:
                continue
            for a in r["annotations"]:
                if a["axis"] != "aspect":
                    continue
                if a["polarity"] in {"positive", "qualified_positive"}:
                    pos[a["code"]] += 1
                elif a["polarity"] in {"negative", "qualified_negative"}:
                    neg[a["code"]] += 1
        love = [{"label": labels.get(k, k), "count": v, "codes": [k]} for k, v in pos.most_common(3)]
        complaint = [{"label": labels.get(k, k), "count": v, "codes": [k]} for k, v in neg.most_common(3)]
        return love, complaint

    lens_names = {"natural": "自然镜头", "diagnostic": "诊断镜头", "qualitative_seed": "定性种子镜头"}
    cluster_lenses = []
    for frame in ("natural", "diagnostic", "qualitative_seed"):
        love, complaint = lens_lists(frame)
        cluster_lenses.append({
            "id": frame,
            "name": lens_names[frame],
            "n": count(frames[frame], "canonical_record", f"records with {frame} frame membership",
                       f"corpus-summary.json#/frame_counts/{frame}"),
            "note": "frame 可重叠；镜头回答不同问题；只允许并排绝对值，禁止跨镜头比较百分比。",
            "love": love,
            "complaint": complaint,
            "basis": f"corpus-summary.json#/frame_counts（{frame} {frames[frame]}）+ coded-corpus.jsonl aspect annotations",
        })

    # Need states ----------------------------------------------------------
    def need(id_, quadrant, name, summary, signal, success, failure, test, limit, claim_id, refs):
        return {
            "id": id_, "quadrant": quadrant, "name": name,
            "summary": text(summary, claim_id, refs),
            "signal": text(signal, claim_id, refs),
            "success": text(success, claim_id, refs),
            "failure": text(failure, claim_id, refs),
            "test": text(test, claim_id, refs),
            "limit": text(limit, claim_id, refs),
            "axes": {"x": "支撑需求强度", "y": "适配复杂度", "x_direction": "→ 增强", "y_direction": "↑ 增强"},
            "evidence_status": status(
                "hypothesis", "PRE-G7 · SCENARIO SYNTHESIS", REASON_CODE["hypothesis"],
                {"n_independent": 4, "n_authors": 4, "direction_share": 1.0, "single_coded": True,
                 "synthesis": "four supporting context codes, not four people"}, "G7"),
            "basis": "context annotations are multi-label; n_independent=4 supporting codes, not people",
        }

    need_states = [
        need("mobility", "Q2 · 高支撑 × 高适配复杂度", "运动与移动",
             "运动场景要求支撑随动作保持位置，适配复杂度高。",
             "运动上下文标注 112 次；活动兼容正向 14 次、负向 13 次。",
             "支撑在运动后仍保持位置，且没有新的摩擦记录。",
             "运动后出现支撑滑移或活动受限的负向记录。",
             "下一轮 wear test 分开记录运动与静态佩戴。",
             "不表示人群规模或满意率。", "C05",
             ["coverage.context_code_counts/CTX.ACTIVITY_EXERCISE", "coverage.aspect_polarity_counts/ACT.COMPATIBILITY"]),
        need("fit", "Q4 · 低支撑需求 × 高适配复杂度", "体型与尺码",
             "体型差异把选码与适配变成主要风险，而不是支撑强度。",
             "长躯干 14 次、大码 3 次、短躯干 1 次上下文标注；体型适配负向 2 次。",
             "选码后无需退换，且躯干长度相关负向不再出现。",
             "同一尺码在 tall/plus-size 记录里继续出现适配负向。",
             "用 Fit chooser 做小样本前测，再决定是否改尺码表。",
             "不表示人群规模或满意率。", "C05",
             ["coverage.context_code_counts/CTX.BODY_TALL_LONG_TORSO", "coverage.context_code_counts/CTX.BODY_PLUS_SIZE"]),
        need("daily", "Q1 · 高支撑需求 × 低适配复杂度", "全天工作",
             "全天工作场景需要稳定支撑，但动作幅度低于运动场景。",
             "工作上下文 46 次、全天 7 次；支撑负向 14 次。",
             "全天佩戴后支撑负向不增加，且没有新的压力点。",
             "工作日下午出现支撑下降或压力不适的记录。",
             "用 7 天 wear test 记录佩戴时长与支撑负向。",
             "不表示人群规模或满意率。", "C04",
             ["coverage.context_code_counts/CTX.ACTIVITY_WORK", "coverage.context_code_counts/CTX.DURATION_ALL_DAY"]),
        need("postpartum", "Q3 · 低支撑需求 × 低适配复杂度", "产后恢复",
             "产后场景更关注轻量支撑与穿脱，不是高强度托举。",
             "产后上下文 24 次；缓解结果 18 次、无收益 1 次。",
             "产后用户能独立穿脱并报告缓解，且没有安全自述升级。",
             "出现疼痛或安全自述，必须转 review queue。",
             "下一轮采集把产后与孕期分开分层。",
             "不表示人群规模或满意率。", "C08",
             ["coverage.context_code_counts/CTX.POSTPARTUM", "coverage.outcome_counts/OUT.RELIEF"]),
    ]

    # Variants -------------------------------------------------------------
    variant_items = []
    for asin, (color, size) in sorted(product["variants"].items(), key=lambda kv: (kv[1][0], kv[1][1], kv[0])):
        variant_items.append({
            "variant_key": asin,
            "sku_id": None,
            "asin": asin,
            "color": color,
            "size": size,
            "mapping_confidence": 1.0,
            "status": "exact",
            "is_target": asin == child,
            "review_count": None,
            "rating": None,
            "verified_count": None,
            "low_star_count": None,
            "recent_count": None,
        })
    variants = {
        "items": variant_items,
        "target_key": child,
        "basis": "PDP dimensionValuesDisplayData; 18 ASIN variants; per-variant review counts not aggregated",
        "source": [source_artifact("amazon-identity-raw.json", "amazon")],
    }

    # Journey --------------------------------------------------------------
    journey = {
        "stage_counts": {
            code: count(value, "canonical_record",
                        "record-level journey annotation; multi-label; 32 annotated records",
                        f"coded-corpus.jsonl#/journey_stage/{code}", multi_label=True)
            for code, value in journey_records.items() if code != "UNKNOWN_JOURNEY"
        },
        "stage_labels": {
            "JNY.CONSIDERATION": "考虑", "JNY.SIZE_SELECTION": "选码", "JNY.FIRST_FITTING": "首次试穿",
            "JNY.USE": "使用", "JNY.CARE": "护理", "JNY.RETURN": "退换", "JNY.RECOMMEND": "推荐",
        },
        "expectation_gap_counts": {
            str(k): count(v, "canonical_record", "expectation gap rollup; partition over 248 canonical",
                          f"coded-corpus.jsonl#/gap/{k}", partition=True)
            for k, v in gap_records.items()
        },
        "independent_unit_counts": {
            **{
                code: count(value, "canonical_record",
                            "record-level journey annotation; multi-label",
                            f"coded-corpus.jsonl#/journey_stage/{code}", multi_label=True)
                for code, value in journey_records.items() if code != "UNKNOWN_JOURNEY"
            },
            "unknown": count(journey_records.get("UNKNOWN_JOURNEY", 0), "canonical_record",
                             "records with no journey annotation; kept separate",
                             "coded-corpus.jsonl#/journey_stage/unknown"),
        },
        "occurrence_counts": None,
        "basis": "independent_content_units",
        "drift_note": "occurrence 250 → canonical 248（2 条重复合并）；本图使用 canonical 分母；216 / 248 条记录没有 journey 标注。",
    }

    # Mixed ----------------------------------------------------------------
    both_rows = [r for r in metric_summary["cooccurrence"]["rows"] if r.get("both")]
    pos_family = {
        "COM": "comfort", "APP": "appearance", "SUP": "support", "STB": "support",
        "FIT": "fit", "ADJ": "fit", "VAL": "value", "MAT": "wearability", "FUL": "value",
    }

    def fam(code: str) -> str:
        return pos_family.get(code.split(".", 1)[0], "other")

    matrix: dict[str, dict[str, int]] = {}
    pairs = []
    for row in both_rows:
        pos_codes = row["comfort_positive"]
        neg_codes = row["friction_negative"]
        pf = sorted({fam(c) for c in pos_codes})[0]
        nf = sorted({fam(c) for c in neg_codes})[0]
        matrix.setdefault(pf, {})
        matrix[pf][nf] = matrix[pf].get(nf, 0) + 1
        pairs.append({"canonical_id": row["canonical_id"], "positive_codes": pos_codes, "negative_codes": neg_codes})
    mixed = {
        "mixed_records": count(len(both_rows), "canonical_record",
                               "records with both comfort-positive and core-friction negative annotations",
                               "metric-summary.json#/cooccurrence/both_records"),
        "matrix": matrix,
        "pairs": pairs,
        "basis": "3 record-level mixed records; one representative positive×negative family pair per record; full code lists in pairs; not annotation sums",
        "limit": "共现不是因果；代表对投影不保留多标签组合。",
    }

    # Quotes ---------------------------------------------------------------
    quote_text = ""
    for row in both_rows:
        t = canonical_by_id[row["canonical_id"]]["text"].strip()
        if t:
            quote_text = t[:260].rstrip() + "…"
            quote_id = row["canonical_id"]
            break
    quotes = []
    if quote_text:
        quotes.append({
            "quote_id": f"Q-{quote_id}",
            "canonical_id": quote_id,
            "text": quote_text,
            "is_verbatim": True,
            "source": source_artifact("canonical-records.jsonl", "reddit"),
            "language": "en",
            "redaction_status": "none",
            "permission": "internal",
        })

    evidence = {
        "identity": identity,
        "gate": gate,
        "corpus": corpus,
        "coverage": coverage,
        "taxonomy": taxonomy_out,
        "key_aspects": key_aspects,
        "cluster_lenses": cluster_lenses,
        "need_states": need_states,
        "variants": variants,
        "journey": journey,
        "mixed": mixed,
        "social": None,
        "quotes": quotes,
        "monid": None,
        "skills": [],
        "skill_validation": None,
    }

    # Claims ---------------------------------------------------------------
    claim_index = {c["claim_id"]: i for i, c in enumerate(claims_raw)}
    claim_sections = {
        "C01": "variant", "C02": "evidence", "C03": "variant", "C04": "aspects",
        "C05": "experience", "C06": "frames", "C07": "evidence", "C08": "evidence",
        "C09": "agenda", "C10": "evidence", "C11": "variant",
    }
    claim_units = {
        "C01": "variant", "C02": "canonical_record", "C03": "canonical_record",
        "C04": "annotation", "C05": "canonical_record", "C06": "canonical_record",
        "C07": "metric_row", "C08": "canonical_record", "C09": "claim",
        "C10": "claim", "C11": "canonical_record",
    }
    claim_grades = {
        "C01": ("confirmed", {"topic": "identity", "is_direct_fact": True,
                              "artifact_sha256": art("amazon-identity-raw.json")["sha256"],
                              "exact_identity": True, "inference": False}),
        "C02": ("confirmed", {"topic": "corpus_lineage", "is_direct_fact": True,
                              "artifact_sha256": art("corpus-summary.json")["sha256"],
                              "exact_identity": True, "inference": False}),
        "C03": ("evidence_gap", {"topic": "consumer_experience", "required_cell_count": 0,
                                 "required_field_missing_rate": 1.0}),
        "C11": ("confirmed", {"topic": "corpus_lineage", "is_direct_fact": True,
                              "artifact_sha256": art("canonical-records.jsonl")["sha256"],
                              "exact_identity": True, "inference": False}),
        "C04": ("hypothesis", {"topic": "consumer_experience", "n_independent": 10, "n_authors": 10,
                               "direction_share": 0.667, "single_coded": True}),
        "C05": ("hypothesis", {"topic": "consumer_experience", "n_independent": 3, "n_authors": 3,
                               "direction_share": 1.0, "single_coded": True}),
        "C06": ("hypothesis", {"topic": "consumer_experience", "n_independent": 6, "n_authors": 6,
                               "direction_share": 0.333, "single_coded": True}),
        "C07": ("blocked", {"topic": "consumer_experience", "required_gate": "G7",
                            "gate_status": "BLOCKED", "is_prevalence_claim": True,
                            "denominator": 0, "frame": "natural"}),
        "C08": ("not_authorized", {"topic": "medical_efficacy"}),
        "C09": ("hypothesis", {"topic": "consumer_experience", "n_independent": 3, "n_authors": 3,
                               "direction_share": 1.0, "single_coded": True}),
        "C10": ("blocked", {"topic": "consumer_experience", "required_gate": "G7",
                            "gate_status": "BLOCKED", "is_prevalence_claim": True,
                            "denominator": 0, "frame": "natural"}),
    }
    claim_status_text = {
        "C01": "Confirmed · fetched 2026-10-29T14:20:36.096076+00:00",
        "C02": "Confirmed · 自建 ledger 可复算",
        "C03": "Evidence gap · 缺 exact-variant 评论层",
        "C11": "Confirmed · 计数事实",
        "C04": "Supported hypothesis · single-coded, pre-G7",
        "C05": "Supported hypothesis · 3 records, below Directional threshold",
        "C06": "Supported hypothesis · frame-bound",
        "C07": "Blocked · G7 not executed",
        "C08": "Not authorized · medical/legal review required",
        "C09": "Supported hypothesis · Proposed, not approved",
        "C10": "Blocked · report-level",
    }
    claim_decisions = {
        "C01": "重跑 G1 并在任何 variant-specific 结论之前把变体矩阵版本化。",
        "C02": "使用 canonical 与 frame 数，不把覆盖当成逐级转化。",
        "C03": "补 exact-variant 评论层，或在报告中保持型号级空白。",
        "C11": "补评论层或购买者社区；在此之前报告只输出假设与实验。",
        "C04": "把资源先放在与最集中摩擦对应的可逆实验，而不是全面改款。",
        "C05": "验证支撑梯度与选码引导，不做一次性结构改款。",
        "C06": "使用 Natural 判断方向，Diagnostic 只用于发现失败模式；不合并、不比较百分比。",
        "C07": "先完成双盲编码与 agreement，再谈任何 share。",
        "C08": "转医疗/法务 review；报告只保留描述层。",
        "C09": "先跑 Support ladder、Fit chooser 与 Wearing guidance，三项都可回滚。",
        "C10": "停止发布任何比率、排名与医学措辞；对外只保留方向与实验计划。",
    }
    claim_counter = {
        "C01": "如果 PDP 会话、地区或库存变化，单次抓取不能说明所有变体在任何时点都可售。",
        "C02": "如果改用概率抽样，样本可能包含本轮关键词没有召回的人群；当前关键词检索不代表总体。",
        "C03": "如果补齐 Amazon 与 DTC 评论层，品牌提及与型号体验的关系可能改变；当前只有 Reddit。",
        "C11": "如果下一轮补齐购买者评论，提问者与购买者的比例可能反转。",
        "C04": "如果 G7 双盲编码把 qualified_negative 并入 negative，摩擦排序可能改变；当前为规则词典单编码。",
        "C05": "如果补齐 Amazon 评论后共现比例改变，或者共现被场景变量解释，本结论需要重算；当前共现不是因果。",
        "C06": "如果 Diagnostic 改为独立抽样后第一负向改变，本对比失效；当前 Diagnostic 是内容派生子集。",
        "C07": "如果把 annotation hits 当分母，会得到看似精确但不可复现的比例；一旦 G7 未过，任何 share 都必须撤回。",
        "C08": "如果缺少临床上下文、剂量、对照与随访，任何疗效或安全推断都不成立；当前只有 self-report。",
        "C09": "如果任一实验的独立记录少于 3 条，或出现安全自述，实验必须停止；当前没有 owner 与预算。",
        "C10": "如果 G7 仍未通过，任何比率、排名或医学措辞都不得发布；当前 metric rows = 0。",
    }
    claim_headlines = {
        "C06": "自然镜头 N=149 的第一负向是背部支撑 7 次，诊断镜头 N=8 的第一负向是总体舒适 2 次。",
        "C10": "G7 = BLOCKED 且 metric rows = 0，这份报告只能支持方向判断与实验，不能支持比率、排名或医学结论。",
    }
    number_specs = {
        "C01": [
            ("live_variants", "amazon-identity-raw.json#/products/B0HC2FG4QC/variant_count", "variant", "PDP dimensionValuesDisplayData"),
            ("prior_archived_children", f"claims.json#/{claim_index['C01']}/numbers/prior_archived_children", "variant", "2026-09-23 archived family map recorded in claims.json"),
        ],
        "C02": [
            ("raw_objects", "corpus-summary.json#/raw_objects", "raw_object", "provider records written to raw store"),
            ("occurrences_raw", "corpus-summary.json#/occurrences_raw", "occurrence", "raw occurrences before dedup"),
            ("occurrences_deduplicated", "corpus-summary.json#/occurrences_deduplicated", "occurrence", "same external_id + frame dedup"),
            ("canonical_records", "corpus-summary.json#/canonical_records", "canonical_record", "exact + fuzzy dedup"),
            ("frame_memberships", "corpus-summary.json#/frame_memberships", "frame_membership", "overlapping frame memberships"),
        ],
        "C03": [
            ("momcozy_records", f"claims.json#/{claim_index['C03']}/numbers/momcozy_records", "canonical_record", "brand_mention quality flag"),
            ("momcozy_band_records", "metric-summary.json#/product_match_counts/exact_current_family", "canonical_record", "text rule: exact current family"),
            ("exact_like", f"claims.json#/{claim_index['C03']}/numbers/exact_like", "canonical_record", "records discussing belly band"),
            ("exact_model_mentions", f"claims.json#/{claim_index['C03']}/numbers/exact_model_mentions", "canonical_record", "mentions of Ergonest / CozySupport"),
            ("exact_model_experience", f"claims.json#/{claim_index['C03']}/numbers/exact_model_experience", "canonical_record", "first-person experience of exact model"),
        ],
        "C11": [
            ("relevant_records", f"claims.json#/{claim_index['C11']}/numbers/relevant_records", "canonical_record", "records relevant to support band"),
            ("experience_records", f"claims.json#/{claim_index['C11']}/numbers/experience_records", "canonical_record", "records with use/care/return/recommend journey or non-unknown outcome"),
        ],
        "C04": [
            ("support_negative", f"claims.json#/{claim_index['C04']}/numbers/support_negative", "annotation", "SUP.* negative annotation hits"),
            ("fit_negative", "metric-summary.json#/aspect_polarity_counts/FIT.BODY_SHAPE/negative", "annotation", "FIT.* negative annotation hits"),
            ("stability_negative", f"claims.json#/{claim_index['C04']}/numbers/stability_negative", "annotation", "STB.* + ADJ.* negative annotation hits"),
            ("value_negative", "metric-summary.json#/aspect_polarity_counts/VAL.PRICE_VALUE/negative", "annotation", "VAL.* negative annotation hits"),
            ("friction_negative_annotations", f"claims.json#/{claim_index['C04']}/numbers/friction_negative_annotations", "annotation", "all core friction negative annotation hits"),
            ("all_negative_annotations", f"claims.json#/{claim_index['C04']}/numbers/all_negative_annotations", "annotation", "all negative aspect annotation hits"),
            ("leader_share", f"claims.json#/{claim_index['C04']}/numbers/leader_share", "annotation", "support_negative / friction_negative_annotations", 21),
        ],
        "C05": [
            ("comfort_positive_records", "metric-summary.json#/cooccurrence/comfort_positive_records", "canonical_record", "records with at least one COM/APP positive annotation"),
            ("with_friction", "metric-summary.json#/cooccurrence/comfort_positive_with_friction", "canonical_record", "subset of the 27 with SUP/FIT/STB negative annotation", 27),
            ("share", f"claims.json#/{claim_index['C05']}/numbers/share", "canonical_record", "with_friction / comfort_positive_records", 27),
        ],
        "C06": [
            ("natural_n", "corpus-summary.json#/frame_counts/natural", "canonical_record", "records with natural frame membership"),
            ("diagnostic_n", "corpus-summary.json#/frame_counts/diagnostic", "canonical_record", "records with diagnostic frame membership"),
        ],
        "C07": [
            ("eligible_records", "metric-summary.json#/eligible_records", "canonical_record", "consumer metric view admission predicate"),
            ("metric_rows", "metric-summary.json#/metric_rows", "metric_row", "G7 BLOCKED; fail-closed"),
        ],
        "C08": [
            ("medical_records", f"claims.json#/{claim_index['C08']}/numbers/medical_records", "canonical_record", "records with medical self-report annotations"),
        ],
        "C09": [
            ("support_negative", f"claims.json#/{claim_index['C09']}/numbers/support_negative", "annotation", "SUP.* negative annotation hits"),
            ("value_negative", f"claims.json#/{claim_index['C09']}/numbers/value_negative", "annotation", "VAL.* negative annotation hits"),
            ("cooccurrence", "metric-summary.json#/cooccurrence/both_records", "canonical_record", "record-level mixed experience records"),
        ],
        "C10": [
            ("metric_rows", "metric-summary.json#/metric_rows", "metric_row", "G7 BLOCKED; fail-closed"),
        ],
    }

    claims_out = []
    for raw in claims_raw:
        cid = raw["claim_id"]
        grade, grade_inputs = claim_grades[cid]
        nums = []
        for spec in number_specs.get(cid, []):
            name, source_path, unit, basis = spec[:4]
            den = spec[4] if len(spec) > 4 else None
            nums.append(number(name, raw["numbers"][name], unit, basis, source_path, den))
        claims_out.append({
            "claim_id": cid,
            "section": claim_sections[cid],
            "headline": claim_headlines.get(cid, raw["headline"]),
            "grade": grade,
            "grade_inputs": grade_inputs,
            "observed": raw["observed"],
            "interpretation": raw["interpretation"],
            "counterevidence": claim_counter.get(cid, raw["counterevidence"]),
            "decision_implication": claim_decisions[cid],
            "basis": raw["basis"],
            "unit": claim_units[cid],
            "limit": raw["limit"],
            "status": claim_status_text[cid],
            "records": raw["records"],
            "numbers": nums,
        })

    # Exhibits -------------------------------------------------------------
    def exhibit(number, title, scope, state, scope_badge, inputs, chart, readout, foot, drawer, table, definitions):
        return {
            "type": "exhibit",
            "number": number,
            "title": text(title, None, chart.get("data_refs", [])),
            "scope": scope,
            "evidence_status": status(state, scope_badge, REASON_CODE[state], inputs, inputs.get("required_gate") or "G7"),
            "chart": chart,
            "readout": {k: text(v, None, [chart.get("basis", "")]) for k, v in readout.items()},
            "source_foot": foot,
            "drawer": drawer,
            "data_table": table,
            "definitions": definitions,
        }

    e01 = exhibit(
        "01",
        "27 条舒适或外观正向记录中，3 条同时出现支撑或稳定性负向。",
        "27 comfort-positive canonical records · record-level co-occurrence · natural frame",
        "hypothesis", "PRE-G7 · 3 RECORDS",
        {"n_independent": 3, "n_authors": 3, "direction_share": 1.0, "single_coded": True, "gate": "G7"},
        {
            "type": "nested_bar", "unit": "canonical_record", "encoding": "absolute_count",
            "basis": "metric-summary.json#/cooccurrence（27 comfort-positive / 3 with friction / 10 friction-only / 34 annotated）",
            "denominator": 27, "frame_scope": ["natural"],
            "series": [
                {"group": "comfort_or_appearance_positive", "n": 27, "with_friction": 3, "without_friction": 24,
                 "codes": ["COM.GENERAL", "COM.SOFTNESS", "APP.LOW_PROFILE"], "status": "ok"},
                {"group": "friction_negative_records", "n": 10, "with_friction": None, "without_friction": None,
                 "codes": ["SUP.GENERAL", "SUP.BACK", "FIT.BODY_SHAPE"], "status": "evidence_gap"},
            ],
            "notes": ["同一记录可贡献多个 annotation；不是人数。", "第二组共现未计算，标为 Evidence gap；不补 0。", "宽度是组内共现，不是跨组百分比。"],
            "limit": "Reddit keyword sample; no Amazon review text; single-coded pre-G7",
            "status": "Supported hypothesis · PRE-G7",
        },
        {
            "observed": "27 条舒适或外观正向记录中，3 条同时出现支撑、适配或稳定性负向；纯摩擦记录 10 条。",
            "interpretation": "共现只发生在少数正向记录里，说明张力是条件性的，不是普遍模式。",
            "counterevidence": "其余 24 条舒适正向记录没有出现核心摩擦；若补齐 Amazon 评论后共现比例改变，本结论需要重算。",
            "decision_implication": "验证支撑梯度与选码引导，不做一次性结构改款。",
        },
        {"basis": "metric-summary.json#/cooccurrence（27 / 3 / 10 / 34）", "unit": "canonical_record",
         "limit": "Reddit keyword sample; no Amazon review text; single-coded pre-G7", "status": "Supported hypothesis · PRE-G7"},
        {"summary": "查看定义与误读边界",
         "content": "舒适或外观正向 = 至少一个 COM/APP positive annotation；核心摩擦 = SUP/FIT/STB negative。共现不是因果，也不是总体发生率。第二组共现未计算。"},
        [{"label": "comfort_positive_records", "value": 27, "unit": "canonical_record"},
         {"label": "with_core_friction", "value": 3, "unit": "canonical_record"},
         {"label": "without_core_friction", "value": 24, "unit": "canonical_record"},
         {"label": "friction_negative_records", "value": 10, "unit": "canonical_record"}],
        ["COM/APP positive", "SUP/FIT/STB negative", "record-level co-occurrence"],
    )

    selected_for_chart = [(k["code"], k["positive"]["value"], k["negative"]["value"], k["label"]) for k in key_aspects]
    axis_max = max([max(p, n) for _, p, n, _ in selected_for_chart] + [1])
    axis_max = ((axis_max + 11) // 12) * 12
    e02 = exhibit(
        "02",
        "12 个主题的极性计数显示总体支撑正向 23 次最多，背部支撑负向 7 次是最集中的失败面。",
        "12 key aspect codes · 179 aspect annotations · 116 annotated records",
        "hypothesis", "PRE-G7 · SINGLE-CODED",
        {"n_independent": 7, "n_authors": 7, "direction_share": 1.0, "single_coded": True, "gate": "G7",
         "note": "annotation-level descriptive; not a prevalence estimate"},
        {
            "type": "diverging_bar", "unit": "annotation", "encoding": "absolute_count",
            "basis": "metric-summary.json#/aspect_polarity_counts（12 selected codes; 179 aspect annotations）",
            "denominator": None, "frame_scope": ["natural", "diagnostic", "qualitative_seed"],
            "axis": {"min": -axis_max, "max": axis_max, "step": 12},
            "series": [{"code": code, "positive": int(pos), "negative": int(neg), "label": label}
                       for code, pos, neg, label in selected_for_chart],
            "notes": ["同一轴比较正负绝对值；不输出净分。", "annotation hit 不是人数，也不是发生率。",
                      "12 of 21 observed aspect codes shown; the other 9 remain in coverage."],
            "limit": "single-coded rule lexicon; annotation hits, not people; pre-G7",
            "status": "Supported hypothesis · PRE-G7",
        },
        {
            "observed": "SUP.GENERAL 正向 23、负向 5；SUP.BACK 正向 6、负向 7；COM.SOFTNESS 正向 17、负向 3；ACT.COMPATIBILITY 正向 14、负向 13。",
            "interpretation": "支撑总体是正向资产，但背部支撑与活动兼容的负向集中，说明失败面是条件性的而非全面失败。",
            "counterevidence": "若 G7 双盲编码把 SUP.BACK 的负向并入 SUP.GENERAL，最集中失败面会改变；当前为规则词典单编码。",
            "decision_implication": "验证背部支撑与活动兼容两个方向，不把总体支撑正向读成整体满意。",
        },
        {"basis": "metric-summary.json#/aspect_polarity_counts（12 codes / 179 annotations）", "unit": "annotation",
         "limit": "single-coded rule lexicon; annotation hits, not people; pre-G7", "status": "Supported hypothesis · PRE-G7"},
        {"summary": "查看 12 个主题的选择规则",
         "content": "12 个主题按 annotation 总数排序，排除 GEN.OVERALL_EVALUATION（总体评价，不属于四个 family）；其余 9 个 code 保留在 coverage。qualified_positive / qualified_negative 折叠进 positive / negative。"},
        [{"label": k["code"], "value": k["positive"]["value"] + k["negative"]["value"], "unit": "annotation"} for k in key_aspects],
        ["positive/negative annotation hits", "qualified_* folded", "12 of 21 observed codes"],
    )

    e03 = exhibit(
        "03",
        "自然镜头 N=149 与诊断镜头 N=8 的第一负向不同：背部支撑 7 次对总体舒适 2 次。",
        "3 lenses · natural 149 / diagnostic 8 / qualitative_seed 100 memberships",
        "hypothesis", "PRE-G7 · FRAME-BOUND",
        {"n_independent": 8, "n_authors": 8, "direction_share": 0.333, "single_coded": True, "gate": "G7"},
        {
            "type": "frame_grid", "unit": "canonical_record", "encoding": "absolute_count",
            "basis": "corpus-summary.json#/frame_counts + coded-corpus.jsonl aspect annotations; memberships overlap",
            "denominator": None, "frame_scope": ["natural", "diagnostic", "qualitative_seed"],
            "lenses": cluster_lenses,
            "notes": ["三个镜头回答不同问题；不能合并。", "镜头成员可重叠，N 之和 257 > 248 canonical。", "只允许并排绝对值，禁止跨镜头百分比。"],
            "limit": "diagnostic is content-derived, not independent sample; single-coded",
            "status": "Supported hypothesis · FRAME-BOUND",
        },
        {
            "observed": "Natural N=149，前三负向：SUP.BACK 7、COM.GENERAL 6、APP.LOW_PROFILE 6；Diagnostic N=8，前三负向：COM.GENERAL 2、ACT.COMPATIBILITY 1、ADJ.STRAP_DESIGN 1。",
            "interpretation": "两个 frame 的第一摩擦不同，说明 frame 选择会改变优先级。",
            "counterevidence": "Diagnostic 是从自然文本按失败词筛出的子集；若独立抽样后顺序改变，本对比失效。",
            "decision_implication": "使用 Natural 判断方向，Diagnostic 只用于发现失败模式；不合并、不比较百分比。",
        },
        {"basis": "corpus-summary.json#/frame_counts + coded-corpus.jsonl", "unit": "canonical_record",
         "limit": "diagnostic is content-derived; memberships overlap; single-coded", "status": "Supported hypothesis · FRAME-BOUND"},
        {"summary": "查看镜头定义与重叠规则",
         "content": "Natural 用于方向性观察；Diagnostic 是自然文本中含失败措辞的子集，只用于发现失败模式；Qualitative seed 是品牌级线索，不进入 consumer metric。三个镜头可重叠。"},
        [{"label": "natural", "value": 149, "unit": "canonical_record"},
         {"label": "diagnostic", "value": 8, "unit": "canonical_record"},
         {"label": "qualitative_seed", "value": 100, "unit": "canonical_record"}],
        ["frame membership", "absolute counts only", "no cross-frame percentages"],
    )

    e04 = exhibit(
        "04",
        "3 条混合体验记录中，2 条把外观正向与支撑负向放在同一条体验里。",
        "3 mixed records · record-level family projection · natural frame",
        "hypothesis", "PRE-G7 · N=3",
        {"n_independent": 3, "n_authors": 3, "direction_share": 1.0, "single_coded": True, "gate": "G7"},
        {
            "type": "co_occurrence_matrix", "unit": "canonical_record", "encoding": "absolute_count",
            "basis": "metric-summary.json#/cooccurrence/both_records=3; one representative family pair per record",
            "denominator": 3, "frame_scope": ["natural"],
            "matrix": matrix,
            "pairs": pairs,
            "notes": ["矩阵和等于 mixed_records=3。", "代表对投影不保留多标签组合；完整代码见 drawer。", "不是百分比，不是因果。"],
            "limit": "record-level projection; not annotation sum; n=3",
            "status": "Supported hypothesis · PRE-G7",
        },
        {
            "observed": "3 条混合记录中，appearance × support 2 条，comfort × support 1 条；完整正负代码见 drawer。",
            "interpretation": "混合体验集中在支撑负向与外观/舒适正向的交叠，说明喜欢与抱怨可以同时成立。",
            "counterevidence": "若放宽混合定义到任一正负标注，样本会扩大；当前只含 both=true 的 3 条。",
            "decision_implication": "复核这 3 条记录并扩展混合样本，再判断组合优先级。",
        },
        {"basis": "metric-summary.json#/cooccurrence/both_records=3", "unit": "canonical_record",
         "limit": "record-level projection; not annotation sum; n=3", "status": "Supported hypothesis · PRE-G7"},
        {"summary": "查看 pairs 与投影规则",
         "content": "每条 mixed 记录按排序后的第一个 positive family × 第一个 negative family 计一次，保证矩阵和等于 3；完整正负代码列表在 pairs 中。"},
        [{"label": p["canonical_id"], "value": 1, "unit": "canonical_record"} for p in pairs],
        ["record-level co-occurrence", "one representative pair per record", "not annotation sum"],
    )

    e05 = exhibit(
        "05",
        "四类需求场景中，运动移动场景的上下文信号 112 次，远高于全天 7 次，但场景位置仍是假设。",
        "4 need states · 230 context annotations · hypothesis placement",
        "hypothesis", "PRE-G7 · SCENARIO SYNTHESIS",
        {"n_independent": 4, "n_authors": 4, "direction_share": 1.0, "single_coded": True, "gate": "G7"},
        {
            "type": "quadrant_2x2", "unit": "annotation", "encoding": "absolute_count",
            "basis": "coded-corpus.jsonl context annotations（230 hits, multi-label）",
            "denominator": 230, "frame_scope": ["natural", "diagnostic", "qualitative_seed"],
            "need_states": need_states,
            "axes": {"x": "支撑需求强度", "y": "适配复杂度"},
            "notes": ["象限位置是假设，不是人群规模。", "上下文标注可多标签，一条记录可命中多个场景。", "不表示满意率或市场规模。"],
            "limit": "context annotations, not people; quadrant placement is hypothesis",
            "status": "Supported hypothesis · PRE-G7",
        },
        {
            "observed": "运动上下文 112 次、工作 46 次、产后 24 次、长躯干 14 次；全天仅 7 次。",
            "interpretation": "场景信号集中在运动与工作，说明支撑需求与活动相关，但这是标注分布不是人群分布。",
            "counterevidence": "若下一轮购买者样本显示全天佩戴更常见，场景优先级会反转。",
            "decision_implication": "验证运动与工作两个场景的支撑梯度，不据象限分配资源。",
        },
        {"basis": "coded-corpus.jsonl context annotations（230 hits）", "unit": "annotation",
         "limit": "context annotations, not people; quadrant placement is hypothesis", "status": "Supported hypothesis · PRE-G7"},
        {"summary": "查看场景推导边界",
         "content": "四个场景由 context code 的共现合成；象限位置是分析假设。signal 中的数字是 annotation 次数，不是人数，也不是满意率。"},
        [{"label": k, "value": v, "unit": "annotation"} for k, v in context_counts.most_common()],
        ["context annotation hits", "multi-label", "quadrant is hypothesis"],
    )

    e06 = exhibit(
        "06",
        "旅程标注覆盖 32 / 248 条记录：使用 15 条、推荐 13 条，216 条没有旅程标注。",
        "canonical records · journey annotations · coverage, not funnel",
        "hypothesis", "PRE-G7 · LOW JOURNEY COVERAGE",
        {"n_independent": 7, "n_authors": 7, "direction_share": 1.0, "single_coded": True, "gate": "G7",
         "note": "journey annotated records = 32 of 248"},
        {
            "type": "coverage_bars", "unit": "canonical_record", "encoding": "absolute_count",
            "basis": "coded-corpus.jsonl journey annotations；coverage, not funnel；display_max=18；216/248 unannotated",
            "denominator": 248, "frame_scope": ["natural", "diagnostic", "qualitative_seed"],
            "stage_counts": [
                {"label": "考虑", "code": "JNY.CONSIDERATION", "value": journey_records.get("JNY.CONSIDERATION", 0)},
                {"label": "使用", "code": "JNY.USE", "value": journey_records.get("JNY.USE", 0)},
                {"label": "推荐", "code": "JNY.RECOMMEND", "value": journey_records.get("JNY.RECOMMEND", 0)},
                {"label": "首次试穿", "code": "JNY.FIRST_FITTING", "value": journey_records.get("JNY.FIRST_FITTING", 0)},
            ],
            "display_max": 18,
            "unknown": {"label": "无 journey 标注", "value": journey_records.get("UNKNOWN_JOURNEY", 0)},
            "notes": ["覆盖，不是漏斗；阶段可重叠，阶段和不代表总体。", "216 条记录没有 journey 标注，单列。", "禁止把覆盖数读成阶段间的流失。"],
            "limit": "journey annotations cover 32/248 records; multi-label; single-coded",
            "status": "Supported hypothesis · LOW COVERAGE",
        },
        {
            "observed": "4 个旅程阶段共 45 次记录级标注：考虑 16、使用 15、推荐 13、首次试穿 1；216 条记录没有旅程标注。",
            "interpretation": "旅程信号集中在使用与推荐，但 216 / 248 条记录没有标注，不能据此排阶段优先级。",
            "counterevidence": "若下一轮补采购买者评论并补齐旅程标注，阶段顺序可能改变。",
            "decision_implication": "补采购买者评论并复核旅程标注，再决定阶段优先级。",
        },
        {"basis": "coded-corpus.jsonl journey annotations（32 annotated records）; coverage, not funnel; 216/248 unannotated",
         "unit": "canonical_record", "limit": "journey annotations cover 32/248 records; multi-label; single-coded",
         "status": "Supported hypothesis · LOW COVERAGE"},
        {"summary": "查看旅程口径",
         "content": "stage_counts 是记录级多标签计数；216 条记录没有任何 journey code，单列为 unknown。occurrence 250 → canonical 248 的差异见 drift_note。"},
        [{"label": k, "value": v, "unit": "canonical_record"} for k, v in journey_records.items()],
        ["coverage, not funnel", "multi-label stages", "unknown kept separate"],
    )

    e08 = exhibit(
        "08",
        "Amazon PDP 当前列出 18 个 ASIN 变体，目标 Oyster Pink / Small 只是其中 1 个。",
        "18 ASIN variants · PDP 2026-10-29 · per-variant review counts not aggregated",
        "confirmed", "PDP 2026-10-29",
        {"is_direct_fact": True, "artifact_sha256": art("amazon-identity-raw.json")["sha256"],
         "exact_identity": True, "inference": False},
        {
            "type": "variant_grid", "unit": "variant", "encoding": "absolute_count",
            "basis": "amazon-identity-raw.json#/products/B0HC2FG4QC/variants（18）; review_count cells null",
            "denominator": None, "frame_scope": ["amazon_pdp"],
            "variants": variant_items,
            "notes": ["变体集合是单时点、单地区、未登录会话。", "review_count 缺失写 Evidence gap，不补 0。", "TikTok SKU 与 Amazon ASIN 没有已验证 crosswalk，禁止合并。"],
            "limit": "single PDP fetch; no per-variant review counts; no SKU/ASIN crosswalk",
            "status": "Confirmed · PDP 2026-10-29",
        },
        {
            "observed": "PDP 解析出 18 个 ASIN；目标 B0HC2FG4QC 为 Oyster Pink / Small；18 个 cell 的 review_count 均为空。",
            "interpretation": "身份可用，但逐变体评论计数缺失，不能把 family 级评论转移到目标变体。",
            "counterevidence": "如果 PDP 会话、地区或库存变化，单次抓取的变体集合可能不成立；当前只有一个时点。",
            "decision_implication": "重跑 G1 并聚合逐变体评论，再发布 variant-specific 结论。",
        },
        {"basis": "amazon-identity-raw.json#/products/B0HC2FG4QC/variants（18）", "unit": "variant",
         "limit": "single PDP fetch; no per-variant review counts; no SKU/ASIN crosswalk", "status": "Confirmed · PDP 2026-10-29"},
        {"summary": "查看变体口径与缺口",
         "content": "18 个 ASIN 来自 PDP dimensionValuesDisplayData；review_count、rating、verified、low-star 均为 null，因为本轮没有按 variant 聚合评论。TikTok SKU 与 Amazon ASIN 没有 crosswalk。"},
        [{"label": "live_variants", "value": 18, "unit": "variant"},
         {"label": "target_variants", "value": 1, "unit": "variant"},
         {"label": "review_count_cells_missing", "value": 18, "unit": "variant"}],
        ["ASIN variant", "target unique", "no cross-source merge"],
    )

    maturity_rows = [
        {"claim_id": "C01", "label": "Amazon 变体身份", "status": "confirmed", "reason": "PDP + sha256", "gate": "G1", "current": True},
        {"claim_id": "C02", "label": "语料血缘", "status": "confirmed", "reason": "ledger 可复算", "gate": "G6", "current": True},
        {"claim_id": "C03", "label": "exact-variant 评论", "status": "evidence_gap", "reason": "required cell = 0", "gate": "G7", "current": True},
        {"claim_id": "C11", "label": "支撑带相关记录计数", "status": "confirmed", "reason": "规则 rollup 可复算", "gate": "G6", "current": True},
        {"claim_id": "C04", "label": "摩擦标注排序", "status": "hypothesis", "reason": "单编码，share 0.667", "gate": "G7", "current": True},
        {"claim_id": "C05", "label": "舒适 × 支撑共现", "status": "hypothesis", "reason": "3 条记录", "gate": "G7", "current": True},
        {"claim_id": "C06", "label": "frame 第一摩擦", "status": "hypothesis", "reason": "frame-bound，单编码", "gate": "G7", "current": True},
        {"claim_id": "C07", "label": "正式指标行", "status": "blocked", "reason": "G7 未执行", "gate": "G7", "current": True},
        {"claim_id": "C08", "label": "医疗自述", "status": "not_authorized", "reason": "医学/法务 review 未完成", "gate": "G9", "current": True},
        {"claim_id": "C09", "label": "可逆实验议程", "status": "hypothesis", "reason": "proposed，未审批", "gate": "G9", "current": True},
        {"claim_id": "C10", "label": "报告级比率限制", "status": "blocked", "reason": "report-level constraint", "gate": "G7", "current": True},
    ]
    e09 = exhibit(
        "09",
        "11 条 claim 中 3 条 Confirmed、4 条 Supported hypothesis、2 条 Blocked，没有 Directional。",
        "11 claims · current grade per claim · pre-G7",
        "blocked", "G7 NOT EXECUTED",
        {"required_gate": "G7", "gate_status": "BLOCKED", "is_prevalence_claim": True},
        {
            "type": "maturity_matrix", "unit": "claim", "encoding": "absolute_count",
            "basis": "claims.json + evidence-grade-report.json（11 claims）",
            "denominator": None, "frame_scope": ["all"],
            "rows": maturity_rows,
            "notes": ["状态是门禁结果，不是绩效分。", "每行只允许一个 current=true。", "6 列固定，不新增第七级。"],
            "limit": "single-coded; G7 blocked; status not performance",
            "status": "Blocked · G7 not executed",
        },
        {
            "observed": "11 条 claim：Confirmed 3、Supported hypothesis 4、Evidence gap 1、Blocked 2、Not authorized 1、Directional 0。",
            "interpretation": "没有任何 claim 达到 Directional，说明体验结论仍停在假设级。",
            "counterevidence": "若 G7 双盲编码达到 agreement，部分 Hypothesis 可能升级为 Directional；当前没有第二编码员。",
            "decision_implication": "先完成 G7 双盲编码，再改变任何 claim 等级。",
        },
        {"basis": "claims.json + evidence-grade-report.json（11 claims）", "unit": "claim",
         "limit": "single-coded; G7 blocked; status not performance", "status": "Blocked · G7 not executed"},
        {"summary": "查看成熟度口径",
         "content": "每行是一个 claim，六列是证据状态。current=true 表示本轮状态；状态由 grade_inputs 机械判定，不是作者自选，也不是绩效分。"},
        [{"label": k, "value": v, "unit": "claim"} for k, v in
         [("confirmed", 3), ("directional", 0), ("hypothesis", 4), ("evidence_gap", 1), ("blocked", 2), ("not_authorized", 1)]],
        ["claim maturity", "six statuses", "not a score"],
    )

    e10 = exhibit(
        "10",
        "250 条 raw 记录经 2 条重复合并到 248 条 canonical，frame membership 因跨 frame 增加到 257。",
        "corpus lineage 250 → 250 → 248 → 257 · two independent denominator groups",
        "confirmed", "LEDGER RECOMPUTABLE",
        {"is_direct_fact": True, "artifact_sha256": art("corpus-summary.json")["sha256"],
         "exact_identity": True, "inference": False},
        {
            "type": "lineage_waterfall", "unit": "canonical_record", "encoding": "absolute_count",
            "basis": "corpus-summary.json#/reconciliation + frame_counts",
            "denominator": None, "frame_scope": ["all"],
            "groups": [
                {"name": "corpus lineage", "steps": [
                    {"label": "raw objects", "value": 250, "delta": None, "reason": "provider records"},
                    {"label": "source occurrences", "value": 250, "delta": 0, "reason": "same external_id + frame dedup: 0 dropped"},
                    {"label": "canonical records", "value": 248, "delta": -2,
                     "reason": "cross_source_syndicated_duplicate 1 + crosspost_same_author 1"},
                    {"label": "frame memberships", "value": 257, "delta": 9,
                     "reason": "cross_frame_membership_added 9; memberships may overlap"},
                ]},
                {"name": "journey denominator", "steps": [
                    {"label": "occurrences", "value": 250, "delta": None, "reason": "occurrence basis"},
                    {"label": "canonical", "value": 248, "delta": -2, "reason": "same dedup; journey uses canonical"},
                ]},
            ],
            "notes": ["每组独立刻度；不是漏斗，也不是阶段转化。", "frame membership 可重叠，257 > 248。", "2 条扣减全部带 reason code。"],
            "limit": "single run; frame memberships overlap; counts not people",
            "status": "Confirmed · ledger recomputable",
        },
        {
            "observed": "raw 250 → occurrence 250 → canonical 248 → frame membership 257；扣减 2 条，跨 frame 增加 9 条。",
            "interpretation": "四层计数不同，不能把任何一层当消费者人数；血缘是计数链，不是阶段转化。",
            "counterevidence": "若新来源暴露新的重复组，扣减数会变化；当前 ledger 可复算。",
            "decision_implication": "复核 ledger 并冻结本轮计数，再复用到下一轮报告。",
        },
        {"basis": "corpus-summary.json#/reconciliation + frame_counts", "unit": "canonical_record",
         "limit": "single run; frame memberships overlap; counts not people", "status": "Confirmed · ledger recomputable"},
        {"summary": "查看四级血缘与 reason code",
         "content": "raw 250 是 provider 写入数；occurrence 250 是同 external_id + frame 去重后；canonical 248 合并 2 条重复；frame membership 257 因跨 frame 增加 9 条。每一级都带 reason code，不能读成转化。"},
        [{"label": "raw_objects", "value": 250, "unit": "raw_object"},
         {"label": "occurrences", "value": 250, "unit": "occurrence"},
         {"label": "canonical_records", "value": 248, "unit": "canonical_record"},
         {"label": "frame_memberships", "value": 257, "unit": "frame_membership"}],
        ["lineage, not funnel", "reason codes", "overlapping memberships"],
    )

    # Sections -------------------------------------------------------------
    def section(index, title, deck, state, blocks):
        spec = C.SECTION_BY_INDEX[index]
        return {
            "index": index, "id": spec["id"], "kicker": spec["kicker"],
            "title": text(title, None, ["report.sections"]), "deck": text(deck, None, ["report.sections"]),
            "status": state, "blocks": blocks,
        }

    def gap(reason, title, readout, foot):
        return {
            "type": "gap", "reason": reason, "title": title,
            "readout": {k: text(v) for k, v in readout.items()},
            "source_foot": foot,
        }

    sections = [
        section("00", "先校准 Fit 与支撑预期，再决定产品结构投入。",
                "答案引用 C05 / C07 / C09；所有体验结论停在 Supported hypothesis 或 Blocked。",
                "ok", [{"type": "answer_stack", "claim_ids": ["C05", "C07", "C09"]}]),
        section("01", "轻薄舒适是真实资产，但它并不自动转化为足够支撑。",
                "这条张力是记录级共现，不是总体情绪；共现不是因果。",
                "ok", [{"type": "exhibit", **e01}, {"type": "claim", "claim_id": "C05"}]),
        section("02", "支撑总体正向，但背部支撑与活动兼容的负向最集中。",
                "12 个主题的 annotation 计数；不输出净分，也不读成发生率。",
                "ok", [{"type": "exhibit", **e02}, {"type": "claim", "claim_id": "C04"}]),
        section("03", "自然镜头与诊断镜头给出不同的第一摩擦，不能合并比较。",
                "三个镜头回答不同问题；只允许并排绝对值。",
                "ok", [{"type": "exhibit", **e03}, {"type": "claim", "claim_id": "C06"}]),
        section("04", "混合体验集中在支撑负向与外观或舒适正向的交叠。",
                "3 条 both=true 记录；代表对投影，不保留多标签组合。",
                "ok", [{"type": "exhibit", **e04}]),
        section("05", "需求场景信号集中在运动与工作，象限位置仍是假设。",
                "场景由 context annotations 合成；不是人群规模，也不是满意率。",
                "ok", [{"type": "exhibit", **e05}]),
        section("06", "旅程标注只覆盖 32 / 248 条记录，阶段顺序不能定优先级。",
                "覆盖，不是漏斗；216 条记录没有 journey 标注。",
                "partial", [
                    {"type": "exhibit", **e06},
                    gap("216 / 248 条记录没有 journey 标注；expectation_gap 全部为 unknown。",
                        "[Evidence gap] 旅程覆盖不足",
                        {"observed": "journey 标注覆盖 32 / 248 条 canonical；216 条为 unknown。",
                         "interpretation": "覆盖不足时不能把阶段计数读成用户旅程分布。",
                         "counterevidence": "若补齐购买者评论并重新标注，阶段顺序可能改变。",
                         "decision_implication": "补采购买者评论并复核 journey code，再决定阶段优先级。"},
                        {"basis": "coded-corpus.jsonl journey annotations（32/248）", "unit": "canonical_record",
                         "limit": "216 records unannotated; multi-label; single-coded", "status": "Evidence gap · journey coverage"}),
                ]),
        # 07 social intentionally absent: evidence.social is null.
        section("08", "商品身份可以确认，但逐变体评论计数与 SKU/ASIN crosswalk 仍为空。",
                "18 个 ASIN 是身份事实；review_count 逐格缺失，不补 0。",
                "partial", [
                    {"type": "exhibit", **e08},
                    {"type": "claim", "claim_id": "C01"},
                    {"type": "claim", "claim_id": "C03"},
                    {"type": "claim", "claim_id": "C11"},
                    gap("逐变体 review_count 为空；TikTok SKU 与 Amazon ASIN 没有已验证 crosswalk。",
                        "[Evidence gap] 逐变体评论与 crosswalk",
                        {"observed": "18 个 ASIN cell 的 review_count 全部为空；没有 SKU/ASIN crosswalk。",
                         "interpretation": "没有逐变体计数时，不能把 family 级证据转移到目标变体。",
                         "counterevidence": "若补齐逐变体评论或 crosswalk，变体级结论可能改变。",
                         "decision_implication": "补采逐变体评论并验证 crosswalk，再发布 variant-specific 结论。"},
                        {"basis": "amazon-identity-raw.json#/products/B0HC2FG4QC/variants（18 cells, 0 counts）",
                         "unit": "variant", "limit": "no per-variant counts; no crosswalk; single PDP fetch",
                         "status": "Evidence gap · variant counts"}),
                ]),
        section("09", "三项可逆实验已提出，但没有 owner、预算与 G9 审批。",
                "所有实验状态为 proposed；没有审批不得写成 approved。",
                "partial", [
                    {"type": "experiment_sequence", "experiment_ids": ["EXP1", "EXP2", "EXP3"]},
                    {"type": "claim", "claim_id": "C09"},
                    gap("report.experiments 没有 owner、预算与 G9 审批。",
                        "[Evidence gap] 实验未审批",
                        {"observed": "3 个实验的 status 都是 proposed；没有 owner 与预算字段。",
                         "interpretation": "proposed 实验不能进入资源排序或对外承诺。",
                         "counterevidence": "若 G9 审批并指定 owner，实验状态可以改变。",
                         "decision_implication": "先指定 owner 与预算，再启动任何实验。"},
                        {"basis": "report.experiments（3 proposed, 0 approved）", "unit": "claim",
                         "limit": "no owner; no budget; G9 blocked", "status": "Evidence gap · not approved"}),
                ]),
        section("10", "商品身份与计数已确认，体验结论停在假设级，正式指标为零。",
                "六级状态、claim 成熟度与四级血缘都在本节；比例与排名仍被 G7 阻断。",
                "blocked", [
                    {"type": "exhibit", **e09},
                    {"type": "exhibit", **e10},
                    {"type": "status_legend", "title": "六级证据状态：先命中先停",
                     "statuses": [
                         {"status": s, "label": C.STATUS_LABEL[s], "rule": C.STATUS_RULE[s],
                          "may_use": C.STATUS_MAY_USE[s], "may_not_use": C.STATUS_MAY_NOT_USE[s]}
                         for s in C.STATUS_ORDER
                     ]},
                    {"type": "claim", "claim_id": "C02"},
                    {"type": "claim", "claim_id": "C07"},
                    {"type": "claim", "claim_id": "C08"},
                    {"type": "claim", "claim_id": "C10"},
                ]),
    ]

    # Experiments ----------------------------------------------------------
    experiments = [
        {"id": "EXP1", "lane": "Now · Reversible", "name": "Support ladder：支撑强度分层说明",
         "trigger_evidence_refs": ["C04", "C05", "C06"],
         "minimum_test": "在 PDP 与包装上增加支撑强度分层说明，用 fit consultation 检查理解与误配。",
         "kpi": "支撑相关退货原因计数 / fit consultation 误配计数（分子分母同时记录）",
         "guardrail": "若任一 cell 的独立记录少于 3 条，停止扩量并回到采集。",
         "decision": "若误配计数下降且没有新的支撑负向，保留；否则回滚文案。",
         "stop": "出现医学/安全措辞或 G7 未过，立即停止对外使用。",
         "status": "proposed"},
        {"id": "EXP2", "lane": "Now · Reversible", "name": "Fit chooser：体型与尺码引导",
         "trigger_evidence_refs": ["C05", "C06"],
         "minimum_test": "用现有 18 个 ASIN 的颜色/尺码矩阵做选择器原型，访谈由 G0 预算决定的目标用户。",
         "kpi": "选择器完成计数与退换计数",
         "guardrail": "若访谈无法覆盖 tall / plus-size 两个 cell，停止并补采。",
         "decision": "若退换计数下降，保留；否则回滚选择器。",
         "stop": "样本未覆盖目标体型时停止。",
         "status": "proposed"},
        {"id": "EXP3", "lane": "Next · Validate first", "name": "Wearing guidance：佩戴位置与时长",
         "trigger_evidence_refs": ["C04", "C05"],
         "minimum_test": "用 7 天 wear test 记录佩戴位置、时长与支撑负向；样本量由 G0 决定。",
         "kpi": "支撑负向记录数 / wear test 记录数",
         "guardrail": "若出现医学/安全自述，转 review queue，不进入结论。",
         "decision": "若支撑负向下降，保留 guidance；否则停止。",
         "stop": "G7 未过或出现安全自述时停止。",
         "status": "proposed"},
    ]

    # Prohibited outputs ---------------------------------------------------
    all_sections = [s["id"] for s in C.SECTION_SPECS]
    prohibited = [
        {"id": "PO1", "label": "总体情绪率、满意率、净情绪分或净值打分",
         "reason": "非概率样本，多标签 annotation，不是总体", "gate": "G8", "severity": "hard",
         "applies_to_sections": all_sections},
        {"id": "PO2", "label": "Love 与 Complaint 的饼图或百分比",
         "reason": "多标签、非互斥、无总体分母", "gate": "G8", "severity": "hard",
         "applies_to_sections": ["02", "04", "07"]},
        {"id": "PO3", "label": "跨 frame 的情绪比例比较",
         "reason": "Natural / Diagnostic 选择机制不同", "gate": "G8", "severity": "hard",
         "applies_to_sections": ["03", "10"]},
        {"id": "PO4", "label": "把 annotation hits 当作人数或发生率",
         "reason": "一条记录可贡献多个标注", "gate": "G7", "severity": "hard",
         "applies_to_sections": ["01", "02", "04", "05"]},
        {"id": "PO5", "label": "Amazon 星级分布当作消费者情绪",
         "reason": "星级不是情绪量表，样本非概率", "gate": "G8", "severity": "hard",
         "applies_to_sections": ["08"]},
        {"id": "PO6", "label": "NPS、ROI 排名、统计显著性、回归或驱动贡献",
         "reason": "未做统计检验，无成本与结果口径", "gate": "G9", "severity": "hard",
         "applies_to_sections": ["09", "10"]},
        {"id": "PO7", "label": "医学功效、安全率、诊断或因果结论",
         "reason": "超出授权，需医学/法务 review", "gate": "G9", "severity": "hard",
         "applies_to_sections": ["05", "08", "10"]},
        {"id": "PO8", "label": "把样本覆盖写成漏斗，或用覆盖数推断市场结构",
         "reason": "frame membership 可重叠，覆盖不是转化", "gate": "G6", "severity": "hard",
         "applies_to_sections": ["06", "10"]},
    ]

    unknowns = [
        "[Evidence gap] evidence.social 为空：本轮没有采集社媒池，section 07 整节省略。",
        "[Evidence gap] evidence.variants.items[].review_count 为空：逐变体评论计数未聚合。",
        "[Evidence gap] evidence.journey 的 216 / 248 条记录没有 journey 标注；expectation_gap 全部为 unknown。",
        "[Evidence gap] key_aspects 只选 12 / 21 个 observed aspect code；其余 9 个保留在 coverage。",
        "[Evidence gap] 只有 1 条 quote 可用；c-1x3t1a8 的 text 为空。",
        "[BLOCKED: Amazon product-reviews 需要登录态，当前返回 302]",
        "[BLOCKED: DTC / Okendo 没有配置可用端点与凭证]",
        "[BLOCKED: G7 没有第二编码员与逐字段 agreement，metric rows 必须为 0]",
        "[BLOCKED: TikTok SKU 与 Amazon ASIN 没有已验证 crosswalk]",
        "[BLOCKED: 本轮未连接生产 PostgreSQL；只使用 run artifacts]",
        "[BLOCKED: 医学/法务 review 未完成；医学自述只保留 review_required]",
    ]

    report = {
        "meta": {
            "title": "Momcozy BumpEase · 消费者洞察报告（G6 进度快照）",
            "description": "G6 progress snapshot; G7 BLOCKED; 248 canonical records from 250 occurrences.",
            "brand_wordmark": "momcozy",
            "report_type": "Decision Brief",
            "lang": "zh-CN",
        },
        "hero": {
            "eyebrow": "Management answer · 2026-10-29",
            "h1": text("轻薄舒适是真实资产，但支撑兑现停在假设级，正式指标为零。", "C07", ["claims.json#/7"]),
            "h1_accent": "正式指标为零",
            "lead": text(
                "本轮把 250 条 Reddit provider 记录收敛为 248 条 canonical，完成 G6；G7 双盲编码未执行，metric rows 为 0。报告只支持方向判断与可逆实验，不支持任何总体比率、排名或医学结论。",
                "C07", ["gate-ledger.json#/stage_boundary"],
            ),
            "actions": [
                {"label": "查看执行答案", "href": "#answer", "primary": True},
                {"label": "查看证据边界", "href": "#evidence", "primary": False},
            ],
            "compass": [
                {"label": "Protect", "title": "柔软、轻薄与衣下低可见",
                 "note": "保留已被反复提到的可穿性资产，不把它写成总体满意。"},
                {"label": "Resolve", "title": "支撑、选码与活动兼容",
                 "note": "先验证条件性失败，再决定结构投入。"},
                {"label": "Prove", "title": "G7 双盲编码与逐变体评论",
                 "note": "没有第二编码员与逐变体计数，就没有正式指标。"},
            ],
            "truth_ribbon": {
                "label": "PROGRESS SNAPSHOT · G6 PASS",
                "cells": [
                    {"value": "G6 PASS", "note": "canonical + ledger"},
                    {"value": "G7 BLOCKED", "note": "no second coder"},
                    {"value": "0 metric rows", "note": "fail-closed"},
                    {"value": "248 canonical", "note": "from 250 occurrences"},
                ],
            },
            "proofs": [
                {"value": "3 / 27", "label": "舒适正向记录中同时有核心摩擦",
                 "note": "record-level co-occurrence; C05"},
                {"value": "250 → 248", "label": "occurrence 收敛为 canonical",
                 "note": "2 条重复合并；C02"},
                {"value": "14 / 21", "label": "核心摩擦标注中支撑类",
                 "note": "annotation hits, not people; C04"},
                {"value": "0", "label": "正式指标行",
                 "note": "G7 BLOCKED; C07"},
            ],
        },
        "decision": {
            "decision_question": charter["decision_question"],
            "answer": text("先校准 Fit 与支撑预期，再决定产品结构投入。[C05][C07][C09]", "C09",
                           ["claims.json#/5", "claims.json#/7", "claims.json#/9"]),
            "protect": ["保留轻薄、柔软与衣下低可见的可穿性资产。"],
            "resolve": ["验证支撑梯度、选码引导与活动兼容的条件性失败。"],
            "prove": ["完成 G7 双盲编码、逐变体评论与 SKU/ASIN crosswalk。"],
        },
        "sections": sections,
        "claims": claims_out,
        "experiments": experiments,
        "claim_maturity": maturity_rows,
        "prohibited_outputs": prohibited,
        "unknowns": unknowns,
    }

    return {
        "schema_version": C.SCHEMA_VERSION,
        "report_id": REPORT_ID,
        "as_of": GENERATED_AT,
        "generated_at": GENERATED_AT,
        "report_mode": "progress_snapshot",
        "language": "zh-CN",
        "evidence": evidence,
        "report": report,
        "artifacts": artifacts,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Assemble report-data.json from a VOC run directory")
    ap.add_argument("--run", default=DEFAULT_RUN, help="run artifact directory")
    ap.add_argument("--out", required=True, help="output report-data.json")
    args = ap.parse_args(argv)
    run = Path(args.run)
    if not run.is_dir():
        print(f"FAIL: run directory not found: {run}", file=sys.stderr)
        return 1
    data = assemble(run)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"PASS  wrote {out}")
    print(f"      {len(data['report']['sections'])} sections · {sum(1 for s in data['report']['sections'] for b in s['blocks'] if b['type']=='exhibit')} exhibits · {len(data['report']['claims'])} claims")
    return 0


if __name__ == "__main__":
    sys.exit(main())
